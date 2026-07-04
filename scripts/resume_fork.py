#!/usr/bin/env python3
"""resume_fork.py — Resume and time-travel fork for /daslab-cycle (DAS-1445).

Two operator affordances for crash-safe and alternative-plan recovery:

  --resume <run_id>
      Replay board/.events.jsonl for that run_id to the last valid checkpoint,
      then return only the UNFINISHED tickets (whose last recorded to_status is
      not a terminal done/blocked) for re-dispatch.  Refuses with ValueError if
      the replay chain is corrupted (T5 zero-corrupted guardrail).

  --fork <run_id>@wave-NNN
      Copy the checkpoint state at wave-NNN into a NEW run_id (ULID minted by
      generate_ulid); return the new run_id and the reconstructed ticket states.
      The original run's events in board/.events.jsonl are never modified —
      fork only produces a new run_id and state snapshot; the original run
      replays byte-for-byte unchanged after the fork.

SHADOW-RULE CONTRACT (ADR-0025 — supersedes the ADR-0011 Phase-1 shadow rule):
  This module READS board/.events.jsonl to decide which tickets to re-dispatch.
  This tensions the Phase-1 "dispatch-decision scripts don't import dgox"
  structural guarantee; however, three mitigations keep the invariant honest:

    (a) Scope: this reader is scoped ONLY to the explicit operator-invoked
        --resume / --fork recovery path.  Normal wave dispatch (daslab-cycle
        step 3 selection + step 5 dispatch) is UNCHANGED — it never reads
        events.  The "flag-on == flag-off dispatch" guarantee holds for all
        normal invocations.

    (b) Import hygiene: this module does NOT import dgox.* directly.  Event
        reading is done via wave_kpi.read_events and replay_qa (neither
        imports dgox), so the ADR-0011 import-scan gate (P1 in
        test_dgox_phase1_shadow.py) is not tripped.  The only non-stdlib
        lazy imports are pulse_checkpoint (for completion records and ULID
        minting) and replay_qa (for group_runs + replay_run).

    (c) Failure isolation: a missing or corrupt event store surfaces as an
        empty unfinished set or a ValueError — it never silently dispatches
        wrong tickets.

  ADR-0025 canonicalizes this: "events are load-bearing for explicit
  operator-invoked recovery" while normal dispatch stays flag-on == flag-off.
  test_dgox_phase1_shadow.py enforces the principled reader-vs-router rule.

Reuse contract (DAS-1445 §replay):
  group_runs and replay_run from replay_qa are the canonical transition model;
  get_completed_tickets and reconstruct_ticket_states from pulse_checkpoint are
  the canonical completion / state-reconstruction helpers.  This module does
  NOT re-implement run grouping or the ordered-transition walk.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Self-locating root (same pattern as other scripts — LAW A)
# ---------------------------------------------------------------------------


def _resolve_root() -> Path:
    """Resolve the repo root via DASLAB_ROOT env, git, or relative fallback."""
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess

        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass
    # Fallback: scripts/resume_fork.py → scripts/ → repo root
    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()

# ---------------------------------------------------------------------------
# Terminal statuses — a ticket in these states is NOT re-dispatched on resume.
# Mirrors the semantic used in replay_qa.VALID_STATUSES; "done" and "blocked"
# are the two lifecycle endpoints that close a ticket without further work.
# ---------------------------------------------------------------------------

TERMINAL_STATUSES: frozenset[str] = frozenset({"done", "blocked"})

# ---------------------------------------------------------------------------
# Internal helpers — read-only, no dgox imports
# ---------------------------------------------------------------------------


def _run_events(run_id: str, events_path: Path) -> list[dict]:
    """Return routing_decision events for run_id using replay_qa.group_runs.

    Uses replay_qa.group_runs as the canonical grouping contract (DAS-1445
    reuse rule).  Events are read via wave_kpi.read_events (no dgox import).

    Returns an empty list when run_id is not found in the event store.
    """
    import replay_qa  # noqa: PLC0415 (lazy; not at module level — avoids dgox at import time)
    import wave_kpi  # noqa: PLC0415

    all_events = wave_kpi.read_events(str(events_path))
    runs = replay_qa.group_runs(all_events)
    return runs.get(run_id, [])


def _per_ticket_events(run_events: list[dict]) -> dict[str, list[dict]]:
    """Group a run's events by ticket_id for per-ticket chain replay.

    Second-level grouping: within a wave's events (already filtered to one
    run_id by _run_events / replay_qa.group_runs), partition by ticket_id so
    that replay_qa.replay_run can be called per-ticket.

    In the current event schema, events without an explicit run_id are grouped
    by ticket_id at the top level by group_runs (_run_key fallback).  When
    run_id IS set (ULID wave identifier), all tickets in that wave share the
    same run_id, so this second-level partition is required.
    """
    per_ticket: dict[str, list[dict]] = {}
    for ev in run_events:
        tid = str(ev.get("ticket_id") or "")
        if tid:
            per_ticket.setdefault(tid, []).append(ev)
    return per_ticket


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_unfinished_tickets(
    run_id: str,
    events_path: Path | None = None,
) -> dict[str, str]:
    """Return {ticket_id: last_status} for non-terminal tickets in the run.

    Calls replay_qa.group_runs (run-level grouping) and replay_qa.replay_run
    (per-ticket ordered-transition walk) as the canonical replay contract
    mandated by DAS-1445.  The caller should cross-check the result against
    pulse_checkpoint.get_completed_tickets before dispatching (see resume_run).

    Args:
        run_id:       The run's group key.  Matches routing_decision events
                      whose run_id field equals run_id, or (for old events
                      lacking an explicit run_id) whose ticket_id equals
                      run_id (the _run_key fallback in replay_qa).
        events_path:  Path to the JSONL event store.
                      Default: board/.events.jsonl (canonical).

    Returns:
        {ticket_id: final_status} for every ticket whose last recorded
        to_status is NOT in TERMINAL_STATUSES (done, blocked).
        An empty dict means the run is fully resolved (no re-dispatch needed).

    Raises:
        ValueError:  Any ticket in the run has a corrupted transition chain
                     (T5 zero-corrupted guardrail — refuse to re-dispatch off
                     a corrupted replay, consistent with check_recovery.py).
    """
    import replay_qa  # noqa: PLC0415

    ep = events_path if events_path is not None else (_ROOT / "board" / ".events.jsonl")
    run_evs = _run_events(run_id, ep)

    # Per-ticket chain validation using replay_qa.replay_run (canonical contract)
    unfinished: dict[str, str] = {}
    for ticket_id, ticket_events in _per_ticket_events(run_evs).items():
        result = replay_qa.replay_run(ticket_events)
        if result["corrupted"]:
            raise ValueError(
                f"Corrupted transition chain for ticket {ticket_id!r} in run "
                f"{run_id!r}: {result['reason']} (T5 zero-corrupted guardrail — "
                f"resume refuses to re-dispatch off a corrupted replay)"
            )
        final = result.get("final_status")
        if final and final not in TERMINAL_STATUSES:
            unfinished[ticket_id] = final

    return unfinished


def resume_run(
    run_id: str,
    events_path: Path | None = None,
    runs_dir: Path | None = None,
) -> dict[str, str]:
    """Identify tickets to re-dispatch for --resume <run_id>.

    Combines event-log replay (via replay_qa — the canonical transition model)
    with the durable per-ticket completion records written by
    pulse_checkpoint.append_ticket_completion.  A ticket that has a completion
    record is NOT re-dispatched even if the event-log replay shows it as
    unfinished (crash-recovery: the completion was durably recorded before the
    crash, so the work is done).

    Four selection guards (from daslab-cycle §3) still apply to the
    re-dispatch set returned here — the caller is responsible for applying
    zone/dep-blocked/AADL/clarify checks before dispatching.

    Args:
        run_id:       Run identifier (ULID or ticket_id fallback).
        events_path:  Path to board/.events.jsonl (default: canonical).
        runs_dir:     Path to board/runs/ (default: canonical).

    Returns:
        {ticket_id: last_status} for tickets that still need dispatch.
        Empty dict means nothing left to do (fully completed run).

    Raises:
        ValueError:  Corrupted transition chain in the event log.
                     Resume refuses to re-dispatch off a corrupted replay
                     (T5 guardrail — consistent with check_recovery.py).
    """
    import pulse_checkpoint as pc  # noqa: PLC0415 (lazy; not in dispatch-decision path)

    ep = events_path if events_path is not None else (_ROOT / "board" / ".events.jsonl")
    rd = runs_dir if runs_dir is not None else (_ROOT / "board" / "runs")

    # T5 guardrail: validate all chains BEFORE consulting completion records —
    # a corrupted replay is an error regardless of what completions say.
    unfinished = get_unfinished_tickets(run_id, ep)

    # Cross-check: exclude tickets that have a durable completion record.
    # These finished before the crash; do NOT re-dispatch them (no duplicate work).
    completed = pc.get_completed_tickets(run_id, rd)
    return {tid: status for tid, status in unfinished.items() if tid not in completed}


def fork_run(
    source_run_id: str,
    wave_num: int,
    events_path: Path | None = None,  # noqa: ARG001 (accepted for API symmetry; fork does not read events directly)
    runs_dir: Path | None = None,
) -> tuple[str, dict[str, str]]:
    """Create a divergent new run forked from source_run_id at wave-NNN.

    The original run's events in board/.events.jsonl are NEVER modified —
    this function only reads checkpoint files (board/runs/<source_run_id>/)
    and mints a new run_id.  The original run replays byte-for-byte unchanged.

    The caller seeds new waves under the returned new_run_id.  New wave
    checkpoints should be written to board/runs/<new_run_id>/ (separate
    from the source's checkpoint tree — do NOT share checkpoint files between
    the source and the fork, as it would corrupt the ledger hash chain).

    Args:
        source_run_id:  The run to fork from.
        wave_num:       The 1-based wave number to fork at.  The fork
                        inherits the cumulative ticket states from
                        wave-001 … wave-NNN of the source run.
        events_path:    Accepted for API symmetry; currently unused (fork
                        reads checkpoint files, not the event store).
                        Default: canonical board/.events.jsonl.
        runs_dir:       Path to board/runs/ (default: canonical).

    Returns:
        (new_run_id, ticket_states) where:
            new_run_id:    Freshly minted ULID for the forked run.
            ticket_states: {ticket_id: status} reconstructed from the source
                           run's checkpoint deltas up to wave_num (via
                           pulse_checkpoint.reconstruct_ticket_states).

    Raises:
        ValueError:  wave_num < 1.
    """
    import pulse_checkpoint as pc  # noqa: PLC0415 (lazy; not in dispatch-decision path)

    if wave_num < 1:
        raise ValueError(f"wave_num must be a positive (1-based) integer; got {wave_num!r}")

    rd = runs_dir if runs_dir is not None else (_ROOT / "board" / "runs")

    # Reconstruct ticket states at the fork point by applying checkpoint deltas
    # wave-001 … wave-NNN from the source run (pulse_checkpoint canonical helper).
    ticket_states = pc.reconstruct_ticket_states(source_run_id, wave_num, rd)

    # Mint a fresh ULID for the divergent new run (stdlib only — ADR-0023 §1).
    new_run_id = pc.generate_ulid()

    # The original run's events are untouched.  The new run starts empty —
    # new waves will emit events with run_id = new_run_id and write their
    # own checkpoint files under board/runs/<new_run_id>/.
    return new_run_id, ticket_states


def parse_fork_arg(arg: str) -> tuple[str, int]:
    """Parse a '--fork <run_id>@wave-NNN' argument string into (run_id, wave_num).

    Args:
        arg: The value that follows '--fork' on the command line, e.g.
             "01J9Z8QK3M7Q0W9E4R5T6Y7U8I@wave-003".

    Returns:
        (run_id, wave_num) — run_id is a non-empty string; wave_num >= 1.

    Raises:
        ValueError: The format is not '<run_id>@wave-<digits>' or wave_num < 1.
    """
    separator = "@wave-"
    if separator not in arg:
        raise ValueError(
            f"--fork argument must be '<run_id>@wave-NNN'; got {arg!r}. "
            f"Example: --fork 01J9Z8QK3M7Q0W9E4R5T6Y7U8I@wave-003"
        )
    run_id_part, wave_part = arg.rsplit(separator, 1)
    if not run_id_part:
        raise ValueError(f"run_id part is empty in --fork argument {arg!r}")
    try:
        wave_num = int(wave_part)
    except ValueError:
        raise ValueError(
            f"Wave number in --fork argument must be digits; got {wave_part!r} "
            f"(full arg: {arg!r})"
        ) from None
    if wave_num < 1:
        raise ValueError(
            f"Wave number must be >= 1 (1-based); got {wave_num!r} (full arg: {arg!r})"
        )
    return run_id_part, wave_num
