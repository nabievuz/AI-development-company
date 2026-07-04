"""pulse_checkpoint.py — Wave-checkpoint writer (DAS-1444 / ORGANISM WS1 PULSE).

Implements crash-safe wave execution for /daslab-cycle:

  1. **Wave-boundary checkpoint** — at each wave boundary writes
     ``board/runs/<run_id>/wave-NNN.checkpoint.json`` with:
     - ``board_hash``       SHA-256 over sorted ticket-file contents
     - ``event_offset``     byte offset into ``board/.events.jsonl``
     - ``ticket_states``    DELTA since prior checkpoint (ADR-0023 §3)
     - ``pending_interrupts``
     - ``ledger_hashes``    ``{prev, self}`` tamper-evidence chain

  2. **Per-ticket completion record** — as each ticket finishes mid-wave,
     appends a durable record to ``board/runs/<run_id>/completions.jsonl``
     using the same O_APPEND + flock + fsync discipline as ``EventStore``.
     A crash after N completions leaves exactly those N recorded; a resume
     calls ``get_completed_tickets()`` and re-dispatches only the remainder.

All events are emitted via the typed builders in ``scripts/dgox/events.py``
(build_checkpoint, build_ticket_completion) — no raw event dicts.

Design invariants (EXTEND, do not fork):
- Self-locating root via ``DASLAB_ROOT`` env var or git rev-parse fallback.
- ``created_at`` is always an *argument* (injectable for tests — never
  generated inside a pure helper).  Callers pass ``utcnow()`` from
  ``dgox.events`` for production use.
- ULID generation from the standard library only (ADR-0023 §1 — no
  third-party package).

Public API
----------
    generate_ulid()
    compute_board_hash(tickets_dir)
    get_event_offset(store_path)
    compute_delta(prev_states, curr_states)
    compute_ledger_hash(checkpoint)
    write_wave_checkpoint(*, run_id, wave, ticket_id, curr_ticket_states,
                          pending_interrupts, created_at, ...)
    append_ticket_completion(*, run_id, ticket_id, status, wave, created_at, ...)
    get_completed_tickets(run_id, runs_dir)
    reconstruct_ticket_states(run_id, up_to_wave, runs_dir)
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating root (LAW A — same pattern as scripts/dgox/events.py)
# ---------------------------------------------------------------------------


def _resolve_root() -> Path:
    """Resolve the repo root (DASLAB_ROOT env → git → relative fallback)."""
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
    # Fallback: scripts/pulse_checkpoint.py → scripts/ → repo root
    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()

DEFAULT_STORE_PATH: Path = _ROOT / "board" / ".events.jsonl"
DEFAULT_TICKETS_DIR: Path = _ROOT / "board" / "tickets"
DEFAULT_RUNS_DIR: Path = _ROOT / "board" / "runs"

# Sentinel prev-hash used for the first wave in a run (no prior checkpoint).
_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64

# ---------------------------------------------------------------------------
# ULID — from stdlib only (ADR-0023 §1 — no new dependency allowed)
# ---------------------------------------------------------------------------

# Crockford base32 alphabet (no I, L, O, U to avoid confusion).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Generate a ULID: 48-bit ms timestamp + 80 random bits, 26 Crockford chars.

    No third-party library — generated from ``time`` + ``os.urandom`` per
    ADR-0023 §1.  ULIDs are lexicographically sortable in creation order,
    making them the correct ``run_id`` join key (see ADR-0023 §1 rationale).
    """
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF  # clamp to 48 bits
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    value = (ms << 80) | rand  # 128-bit value
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


# ---------------------------------------------------------------------------
# Board hash — SHA-256 over sorted ticket file contents
# ---------------------------------------------------------------------------


def compute_board_hash(tickets_dir: Path | None = None) -> str:
    """Stable SHA-256 over all board ticket Markdown files (sorted by name).

    The hash changes when any ticket file is added, removed, or modified —
    allowing a resumed run to detect out-of-band board mutations since the
    checkpoint was cut (ADR-0023 §2 ``board_hash`` field).

    Args:
        tickets_dir: Path to the board tickets directory
                     (default: ``board/tickets/``).

    Returns:
        ``"sha256:<hex>"`` string.
    """
    tdir = tickets_dir if tickets_dir is not None else DEFAULT_TICKETS_DIR
    h = hashlib.sha256()
    if tdir.exists():
        for p in sorted(tdir.glob("*.md")):
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return f"sha256:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# Event-store offset — resume point into board/.events.jsonl
# ---------------------------------------------------------------------------


def get_event_offset(store_path: Path | None = None) -> int:
    """Return the current byte length of the event store.

    This is the **resume point**: a run that crashed and is being resumed
    replays ``board/.events.jsonl`` up to this offset to reconstruct state,
    then re-dispatches only unfinished tickets (ADR-0023 §2 ``event_offset``).

    Returns 0 when the store does not yet exist.
    """
    p = store_path if store_path is not None else DEFAULT_STORE_PATH
    if not p.exists():
        return 0
    return p.stat().st_size


# ---------------------------------------------------------------------------
# Per-step delta — ADR-0023 §3
# ---------------------------------------------------------------------------


def compute_delta(
    prev_states: dict[str, str],
    curr_states: dict[str, str],
) -> dict[str, str]:
    """Return only the ticket states that changed since ``prev_states``.

    Each ``wave-NNN.checkpoint.json`` stores only the *changes* since the
    prior checkpoint — never a full board snapshot per wave (ADR-0023 §3
    "per-step DELTA storage").  This keeps the run-artifact tree proportional
    to work done, not wall-clock.

    Args:
        prev_states: Full ticket-state mapping at the prior wave boundary.
        curr_states: Full ticket-state mapping at the current wave boundary.

    Returns:
        ``{ticket_id: new_status}`` for every ticket whose status differs
        from ``prev_states``, plus any new tickets not present before.
        Tickets whose status is unchanged are omitted.
    """
    return {
        tid: status
        for tid, status in curr_states.items()
        if prev_states.get(tid) != status
    }


# ---------------------------------------------------------------------------
# Ledger hash chain — tamper-evident checkpoints (ADR-0023 §2)
# ---------------------------------------------------------------------------


def _canonical_bytes(obj: dict[str, Any]) -> bytes:
    """Deterministic JSON encoding (sorted keys, no extra whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def compute_ledger_hash(checkpoint: dict[str, Any]) -> str:
    """SHA-256 of the checkpoint with ``ledger_hashes.self`` excluded (the preimage).

    The ``self`` hash is always computed over the checkpoint dict that has no
    ``ledger_hashes.self`` key — so the hash can be independently verified by
    any reader that loads the file and re-derives it.  A gap or tampered
    checkpoint breaks the chain (ADR-0023 §2 ``ledger_hashes``).

    Args:
        checkpoint: The checkpoint dict (``ledger_hashes.self`` may or may
                    not be present — it is excluded from the preimage either way).

    Returns:
        ``"sha256:<hex>"`` string.
    """
    preimage = dict(checkpoint)
    lh = dict(preimage.get("ledger_hashes", {}))
    lh.pop("self", None)
    preimage["ledger_hashes"] = lh
    return f"sha256:{hashlib.sha256(_canonical_bytes(preimage)).hexdigest()}"


# ---------------------------------------------------------------------------
# Delta-chain reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_from_chain(
    runs_dir: Path,
    run_id: str,
    up_to_wave: int,
) -> dict[str, str]:
    """Apply checkpoint deltas wave-001 … wave-NNN to recover full ticket states.

    Starts from an empty baseline (the manifest planned states are not yet
    stored here — this gives us "what changed from nothing") and accumulates
    last-writer-wins per ticket.  The result equals the authoritative ticket
    state at wave ``up_to_wave``.
    """
    states: dict[str, str] = {}
    for w in range(1, up_to_wave + 1):
        cp_path = runs_dir / run_id / f"wave-{w:03d}.checkpoint.json"
        if cp_path.exists():
            cp = json.loads(cp_path.read_text(encoding="utf-8"))
            states.update(cp.get("ticket_states", {}))
    return states


def reconstruct_ticket_states(
    run_id: str,
    up_to_wave: int,
    runs_dir: Path | None = None,
) -> dict[str, str]:
    """Public API: reconstruct full ticket states at wave ``up_to_wave``.

    Rebuilds by applying the ``ticket_states`` deltas from
    ``wave-001.checkpoint.json`` … ``wave-NNN.checkpoint.json`` in order
    (last-writer-wins per ticket).  This is the O(waves) reconstruction path
    described in ADR-0023 §3 — the event log replay is the always-available
    fallback and gives the same answer.

    Args:
        run_id:       ULID run identifier.
        up_to_wave:   Inclusive upper bound (1-based).
        runs_dir:     Path to ``board/runs/`` (default: canonical).

    Returns:
        ``{ticket_id: status}`` for every ticket that appeared in any delta
        up to and including ``up_to_wave``.
    """
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    return _reconstruct_from_chain(rd, run_id, up_to_wave)


# ---------------------------------------------------------------------------
# Wave-boundary checkpoint writer (primary API)
# ---------------------------------------------------------------------------


def write_wave_checkpoint(
    *,
    run_id: str,
    wave: int,
    ticket_id: str,
    curr_ticket_states: dict[str, str],
    pending_interrupts: list[str] | None = None,
    created_at: str,
    store_path: Path | None = None,
    tickets_dir: Path | None = None,
    runs_dir: Path | None = None,
    emit_event: bool = True,
) -> dict[str, Any]:
    """Write ``board/runs/<run_id>/wave-NNN.checkpoint.json`` at a wave boundary.

    Computes the delta from the previous checkpoint, chains the ledger hash,
    writes the JSON file, and (optionally) appends a typed ``checkpoint`` event
    to the event store via ``build_checkpoint``.

    Args:
        run_id:               ULID run join key (ADR-0023 §1).
        wave:                 1-based wave index within the run.
        ticket_id:            Envelope anchor ticket (ADR-0011 envelope law —
                              every stored event must be ticket-scoped; use the
                              run's anchor / first ticket).
        curr_ticket_states:   Full ``{ticket_id: status}`` mapping at the wave
                              boundary (not just the delta — the delta is computed
                              internally from the prior checkpoint).
        pending_interrupts:   Ticket ids halted awaiting a human interrupt answer
                              (WS1 interrupt-card mechanism).  Defaults to ``[]``.
        created_at:           ISO-8601 UTC timestamp string (caller-supplied —
                              injectable for tests; do NOT generate inside here).
        store_path:           Path to the event store (default: canonical
                              ``board/.events.jsonl``).
        tickets_dir:          Path to ticket files for ``board_hash`` (default:
                              canonical ``board/tickets/``).
        runs_dir:             Path to the runs artifact tree (default: canonical
                              ``board/runs/``).
        emit_event:           If ``True`` (default), append a ``checkpoint`` event
                              to the event store via ``build_checkpoint``.

    Returns:
        The checkpoint dict that was written to disk.
    """
    from dgox.events import EventStore, build_checkpoint  # noqa: PLC0415

    sp = store_path if store_path is not None else DEFAULT_STORE_PATH
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR

    # ------------------------------------------------------------------ #
    # 1. Load previous checkpoint for delta base + ledger chain
    # ------------------------------------------------------------------ #
    prev_cp_path = rd / run_id / f"wave-{wave - 1:03d}.checkpoint.json"
    prev_cp: dict[str, Any] | None = None
    if wave > 1 and prev_cp_path.exists():
        prev_cp = json.loads(prev_cp_path.read_text(encoding="utf-8"))

    # Full ticket states at the *previous* wave boundary (for delta computation)
    prev_states = _reconstruct_from_chain(rd, run_id, wave - 1) if wave > 1 else {}

    # ------------------------------------------------------------------ #
    # 2. Compute delta (ADR-0023 §3 — never a full snapshot)
    # ------------------------------------------------------------------ #
    delta = compute_delta(prev_states, curr_ticket_states)

    # ------------------------------------------------------------------ #
    # 3. Board hash + event offset
    # ------------------------------------------------------------------ #
    board_hash = compute_board_hash(tickets_dir)
    event_offset = get_event_offset(sp)

    # ------------------------------------------------------------------ #
    # 4. Ledger hash chain
    # ------------------------------------------------------------------ #
    # Re-derive the previous checkpoint's self-hash for tamper-evidence, or use
    # the genesis sentinel for the first wave (no prior checkpoint).
    prev_hash: str = (
        compute_ledger_hash(prev_cp) if prev_cp is not None else _GENESIS_PREV_HASH
    )

    # ------------------------------------------------------------------ #
    # 5. Build checkpoint dict (self hash placeholder → compute → fill in)
    # ------------------------------------------------------------------ #
    pi = list(pending_interrupts) if pending_interrupts is not None else []
    cp: dict[str, Any] = {
        "run_id": run_id,
        "wave": wave,
        "created_at": created_at,
        "board_hash": board_hash,
        "event_offset": event_offset,
        "ticket_states": delta,
        "pending_interrupts": pi,
        "ledger_hashes": {"prev": prev_hash, "self": ""},  # self computed below
    }
    self_hash = compute_ledger_hash(cp)  # preimage excludes "self"
    cp["ledger_hashes"]["self"] = self_hash

    # ------------------------------------------------------------------ #
    # 6. Write JSON file to board/runs/<run_id>/wave-NNN.checkpoint.json
    # ------------------------------------------------------------------ #
    run_dir = rd / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cp_path = run_dir / f"wave-{wave:03d}.checkpoint.json"
    cp_path.write_text(
        json.dumps(cp, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------ #
    # 7. Emit checkpoint event via the typed builder (DAS-1443 builders)
    # ------------------------------------------------------------------ #
    if emit_event:
        ev = build_checkpoint(
            ticket_id=ticket_id,
            run_id=run_id,
            wave=wave,
            board_hash=board_hash,
            event_offset=event_offset,
            ticket_states=delta,
            ledger_hashes={"prev": prev_hash, "self": self_hash},
            created_at=created_at,
            pending_interrupts=pi,
        )
        EventStore(sp).append(ev)

    return cp


# ---------------------------------------------------------------------------
# Per-ticket completion record — pending-writes analogue (DAS-1444 §2)
# ---------------------------------------------------------------------------


def _durable_append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append *record* to a JSONL file with O_APPEND + flock + fsync.

    Same discipline as ``EventStore.append`` (ADR-0011 durability contract).
    The parent directory is created on first use.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError):
                fcntl.flock(fh, fcntl.LOCK_UN)


def append_ticket_completion(
    *,
    run_id: str,
    ticket_id: str,
    status: str,
    wave: int,
    created_at: str,
    runs_dir: Path | None = None,
) -> None:
    """Append a durable per-ticket completion record (pending-writes analogue).

    Called as each ticket finishes mid-wave.  Writes to
    ``board/runs/<run_id>/completions.jsonl`` via O_APPEND + flock + fsync so
    a crash after N completions leaves exactly those N recorded.  A resumed run
    calls ``get_completed_tickets()`` before re-dispatching and skips any
    ticket already present there.

    All records are constructed via ``build_ticket_completion`` — no raw
    event dicts (acceptance criterion: all emitted events go through the
    DAS-1443 typed builders).

    Args:
        run_id:     ULID run join key.
        ticket_id:  DAS-NNNN identifier of the completed ticket.
        status:     Completion status (e.g. ``"done"``, ``"in_review"``).
        wave:       1-based wave index the ticket completed in.
        created_at: ISO-8601 UTC timestamp string (caller-supplied — injectable).
        runs_dir:   Path to ``board/runs/`` (default: canonical).
    """
    from dgox.events import build_ticket_completion  # noqa: PLC0415

    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    completions_path = rd / run_id / "completions.jsonl"

    record = build_ticket_completion(
        ticket_id=ticket_id,
        run_id=run_id,
        status=status,
        wave=wave,
        created_at=created_at,
    )
    _durable_append_jsonl(completions_path, record)


def get_completed_tickets(
    run_id: str,
    runs_dir: Path | None = None,
) -> set[str]:
    """Return the set of ticket_ids that have a completion record for this run.

    Reads ``board/runs/<run_id>/completions.jsonl`` and returns every
    ``ticket_id`` that appears in a ``ticket_completion`` event for this
    ``run_id``.  Returns an empty set when the completions file does not yet
    exist (no tickets have finished mid-wave in this run).

    This is the resume-guard: a caller building the re-dispatch list should
    filter out any ticket whose id is in the returned set.

    Args:
        run_id:   ULID run join key.
        runs_dir: Path to ``board/runs/`` (default: canonical).

    Returns:
        ``{ticket_id, …}`` — the set of tickets already completed.
    """
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    completions_path = rd / run_id / "completions.jsonl"
    if not completions_path.exists():
        return set()

    completed: set[str] = set()
    try:
        with open(completions_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                # Filter to this run's ticket_completion records
                if (
                    ev.get("event_type") == "ticket_completion"
                    and ev.get("run_id") == run_id
                ):
                    tid = ev.get("ticket_id")
                    if tid:
                        completed.add(str(tid))
    except FileNotFoundError:
        pass
    return completed
