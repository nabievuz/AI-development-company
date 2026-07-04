"""dgox/events.py — DGO-X Phase-1 append-only event store.

Implements the JSONL event store specified in ADR 0011 §2.  Writes one JSON
object per line to ``board/.events.jsonl`` (gitignored runtime state, like
``board/.wave-log`` and ``board/.arcrift-outbox.jsonl``).

Design principles (from ADR 0011):
- Append-only, NEVER rewritten.  A correction is a new compensating event.
- One event per routing / tool / gate / approval / run change.
- Common envelope: ``event_type``, ``ticket_id``, ``created_at``, ``run_id``.
- Two load-bearing shapes: ``routing_decision`` (§8.2) and
  ``agent_invocation`` (§8.3).
- Durable, concurrency-safe append: uses ``O_APPEND`` + ``O_CREAT`` on POSIX
  (single-system-call atomic-line-append guarantee on POSIX; single-writer
  discipline recommended at the orchestrator level).
- Pure-Python, self-locating root via ``scripts/_paths``; no network.
- ``created_at`` is an *argument*, never generated inside pure helpers —
  callers pass a timestamp so helpers are fully deterministic and testable.
  A convenience wrapper ``utcnow()`` is provided for production callers.

Usage (library):

    from dgox.events import EventStore, build_routing_decision, build_agent_invocation

    store = EventStore()               # writes to board/.events.jsonl
    ts = "2026-06-20T00:00:00Z"
    ev = build_routing_decision(
        ticket_id="DAS-1234",
        from_status="todo",
        to_status="in_progress",
        assignee="backend-eng-1",
        model="sonnet",
        reason="Stage 3 backend implementation.",
        confidence=0.91,
        policy_checks=["aadl_predecessor_gate_closed", "repo_area_available"],
        fallback="block_and_escalate_to_backend-em",
        created_at=ts,
    )
    store.append(ev)

Shadow mode (ADR 0011 §4): the store is an advisory observer in Phase 1.
Nothing dispatches off the events it contains.  /daslab-cycle is unaffected.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating root (LAW A — never a hardcoded path).
# When imported from within the scripts/ namespace the regular sys.path
# already has scripts/ at index 0 via the package or a direct run.
# ---------------------------------------------------------------------------

def _resolve_root() -> Path:
    """Resolve the repo root at import time (same logic as scripts/_paths.py)."""
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
    # Fallback: scripts/dgox/events.py → scripts/dgox/ → scripts/ → repo root
    return Path(__file__).resolve().parents[2]


_ROOT = _resolve_root()

# Canonical path for the event store (gitignored runtime state — ADR 0011 §2).
DEFAULT_STORE_PATH: Path = _ROOT / "board" / ".events.jsonl"

# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string ending in 'Z'.

    This is the *only* place ``datetime.now()`` is called in this module.
    Pure builder/validator helpers receive ``created_at`` as an argument so
    they remain deterministic and easy to test without monkeypatching.
    """
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

_ENVELOPE_REQUIRED = frozenset({"event_type", "ticket_id", "created_at"})
_VALID_EVENT_TYPES = frozenset(
    {
        "routing_decision",
        "agent_invocation",
        "state_violation",
        "mirror_divergence",
        # reserved for future phases:
        "gate_check",
        "approval",
        "tool_call",
        "run_start",
        "run_end",
        "wave",
        "checkpoint",
        "tool_unavailable",
        # result-cache observability (ORGANISM P6 — DAS-1450):
        "cache_hit",
        # OTel GenAI trace span (ORGANISM WS3 BRIDGE — ADR 0024 / DAS-1454):
        "span",
        # per-ticket durable completion record (DAS-1444 / ORGANISM WS1 PULSE):
        "ticket_completion",
        # inner-loop plan regeneration on stall (ORGANISM WS2 LOOM — DAS-1470):
        "replanned",
    }
)


def validate_envelope(event: dict[str, Any]) -> list[str]:
    """Return a list of validation errors for the common event envelope.

    An empty list means the envelope is valid.  Does NOT raise — callers
    decide whether errors are fatal.

    Envelope rules (ADR 0011 §2):
    - ``event_type`` present and a known type string.
    - ``ticket_id`` present and a non-empty string starting with ``DAS-``.
    - ``created_at`` present as a non-empty ISO-8601 string (basic check).
    - ``run_id``, if present, must be a non-empty string.
    """
    errors: list[str] = []
    for field in _ENVELOPE_REQUIRED:
        if field not in event or event[field] is None:
            errors.append(f"missing required field: {field!r}")
    et = event.get("event_type")
    if et is not None and et not in _VALID_EVENT_TYPES:
        errors.append(
            f"unknown event_type {et!r}; expected one of {sorted(_VALID_EVENT_TYPES)}"
        )
    tid = event.get("ticket_id")
    if tid is not None and (not isinstance(tid, str) or not tid.startswith("DAS-") or len(tid) <= 4):
        errors.append(
            f"ticket_id must be a string starting with 'DAS-'; got {tid!r}"
        )
    ca = event.get("created_at")
    if ca is not None and (not isinstance(ca, str) or not ca):
        errors.append(f"created_at must be a non-empty string; got {ca!r}")
    rid = event.get("run_id")
    if rid is not None and (not isinstance(rid, str) or not rid):
        errors.append(f"run_id must be a non-empty string when present; got {rid!r}")
    return errors


# ---------------------------------------------------------------------------
# Shape A — routing_decision (ADR 0011 §2, report §8.2)
# ---------------------------------------------------------------------------

_ROUTING_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "from_status",
        "to_status",
        "assignee",
        "model",
        "reason",
        "confidence",
        "policy_checks",
        "fallback",
        "created_at",
    }
)


def build_routing_decision(
    *,
    ticket_id: str,
    from_status: str,
    to_status: str,
    assignee: str,
    model: str,
    reason: str,
    confidence: float,
    policy_checks: list[str],
    fallback: str,
    created_at: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a ``routing_decision`` event dict (Shape A — ADR 0011 §2 / report §8.2).

    Args:
        ticket_id:     DAS-NNNN ticket identifier.
        from_status:   Source lifecycle status (e.g. ``"todo"``).
        to_status:     Target lifecycle status (e.g. ``"in_progress"``).
        assignee:      Role key being assigned (supervisor-authored; never a worker).
        model:         Explicit model name (LAW 3 / ADR 0007 — never inferred from
                       frontmatter, matching ADR 0011's ``model`` field spec).
        reason:        Human-readable routing rationale.
        confidence:    Supervisor confidence score in [0.0, 1.0].
        policy_checks: List of preflight gate names that must pass.
        fallback:      Deterministic action if a policy check fails.
        created_at:    ISO-8601 UTC timestamp string (caller-supplied; injectable
                       for tests — do NOT call ``utcnow()`` inside this helper).
        run_id:        Optional run correlation identifier.

    Returns:
        A dict conforming to the ``routing_decision`` shape ready for ``EventStore.append``.
    """
    event: dict[str, Any] = {
        "event_type": "routing_decision",
        "ticket_id": ticket_id,
        "from_status": from_status,
        "to_status": to_status,
        "assignee": assignee,
        "model": model,
        "reason": reason,
        "confidence": confidence,
        "policy_checks": list(policy_checks),
        "fallback": fallback,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


def validate_routing_decision(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``routing_decision`` event.

    Checks the envelope first, then shape-specific constraints:
    - ``confidence`` in [0.0, 1.0].
    - ``policy_checks`` is a non-empty list of strings.
    - ``model`` is a non-empty string.
    - ``assignee`` is a non-empty string.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "routing_decision"):
        errors.append(
            f"event_type must be 'routing_decision'; got {event.get('event_type')!r}"
        )
    confidence = event.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, int | float) or not (0.0 <= float(confidence) <= 1.0)
    ):
        errors.append(
            f"confidence must be a float in [0.0, 1.0]; got {confidence!r}"
        )
    pc = event.get("policy_checks")
    if pc is not None and (not isinstance(pc, list) or not pc or not all(isinstance(s, str) for s in pc)):
        errors.append(
            "policy_checks must be a non-empty list of strings"
        )
    model = event.get("model")
    if model is not None and (not isinstance(model, str) or not model):
        errors.append("model must be a non-empty string")
    assignee = event.get("assignee")
    if assignee is not None and (not isinstance(assignee, str) or not assignee):
        errors.append("assignee must be a non-empty string")
    for field in ("from_status", "to_status", "reason", "fallback"):
        v = event.get(field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{field!r} must be a non-empty string")
    return errors


# ---------------------------------------------------------------------------
# Shape B — agent_invocation (ADR 0011 §2, report §8.3)
# ---------------------------------------------------------------------------

_AGENT_INVOCATION_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "role_key",
        "model",
        "workspace_id",
        "context_contract",
        "allowed_tools",
        "secrets_policy",
        "exit_contract",
        "created_at",
    }
)


def build_agent_invocation(
    *,
    ticket_id: str,
    run_id: str,
    role_key: str,
    model: str,
    workspace_id: str,
    context_contract: dict[str, Any],
    allowed_tools: list[str],
    secrets_policy: str,
    exit_contract: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Build an ``agent_invocation`` event dict (Shape B — ADR 0011 §2 / report §8.3).

    Args:
        ticket_id:        DAS-NNNN ticket identifier (board is canonical — ADR 0010 C2).
        run_id:           Correlation key joining this run across logs, events, traces,
                          CI, and the ticket log — the join key for all observability (P4).
        role_key:         ``.claude/agents/<role>.md``-compatible role identifier (RACI).
        model:            Explicit model dispatch — LAW 3 / ADR 0007, provider-abstracted,
                          never inferred from frontmatter (claude-code#44385).
        workspace_id:     Sandbox / worktree identity (ADR 0005 worktree = f(ticket)).
        context_contract: Minimal task context dict — NEVER raw full org state (report §10
                          prompt-injection control; Security-consulted per ADR 0011 §2).
        allowed_tools:    Tool allowlist by task class (least privilege — report §10
                          worker-overreach control).
        secrets_policy:   Secrets handling policy — defaults to ``"no_secrets"``; only
                          ``"scoped_creds_gate_approved"`` when gate-approved (report §10).
        exit_contract:    Required exit conditions: ticket log entry, artifacts, test
                          evidence, memory store result (board audit law + ADR 0008
                          store-at-end; or explicit ``tool_unavailable``).
        created_at:       ISO-8601 UTC timestamp string (caller-supplied — injectable for
                          tests; do NOT call ``utcnow()`` inside this helper).

    Returns:
        A dict conforming to the ``agent_invocation`` shape ready for ``EventStore.append``.
    """
    return {
        "event_type": "agent_invocation",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "role_key": role_key,
        "model": model,
        "workspace_id": workspace_id,
        "context_contract": dict(context_contract),
        "allowed_tools": list(allowed_tools),
        "secrets_policy": secrets_policy,
        "exit_contract": dict(exit_contract),
        "created_at": created_at,
    }


def validate_agent_invocation(event: dict[str, Any]) -> list[str]:
    """Return validation errors for an ``agent_invocation`` event.

    Checks the envelope first, then shape-specific constraints:
    - ``run_id`` is required (non-empty string).
    - ``role_key``, ``model``, ``workspace_id``, ``secrets_policy`` are non-empty strings.
    - ``context_contract`` and ``exit_contract`` are dicts.
    - ``allowed_tools`` is a list of strings.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "agent_invocation"):
        errors.append(
            f"event_type must be 'agent_invocation'; got {event.get('event_type')!r}"
        )
    # run_id is required for agent_invocation (not optional like in routing_decision)
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for agent_invocation and must be a non-empty string")
    for str_field in ("role_key", "model", "workspace_id", "secrets_policy"):
        v = event.get(str_field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{str_field!r} must be a non-empty string")
    for dict_field in ("context_contract", "exit_contract"):
        v = event.get(dict_field)
        if v is not None and not isinstance(v, dict):
            errors.append(f"{dict_field!r} must be a dict")
    at = event.get("allowed_tools")
    if at is not None and (
        not isinstance(at, list) or not all(isinstance(s, str) for s in at)
    ):
        errors.append("allowed_tools must be a list of strings")
    return errors


# ---------------------------------------------------------------------------
# Shape C — run_start (ADR 0023 §1/§4 — run lifecycle boundary)
# ---------------------------------------------------------------------------

_RUN_START_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "goal",
        "engine_version",
        "created_at",
    }
)


def build_run_start(
    *,
    ticket_id: str,
    run_id: str,
    goal: str,
    engine_version: str,
    created_at: str,
) -> dict[str, Any]:
    """Build a ``run_start`` event dict (Shape C — ADR 0023 §1/§4).

    Marks the opening boundary of a run (one supervised execution of the org
    across one or more waves). ``run_intervals`` in ``scripts/metrics_lib.py``
    pairs this with the matching ``run_end`` by ``run_id`` (T3 concurrency), so
    ``run_id`` and ``created_at`` are load-bearing.

    Args:
        ticket_id:      DAS-NNNN identifier anchoring the run (envelope law —
                        every stored event is ticket-scoped; for a run this is
                        the run's anchor/first ticket, matching ``run_end``).
        run_id:         ULID run identifier — the single join key across the
                        event store, run-artifact tree, ticket log, and recovery
                        drill (ADR 0023 §1; unchanged from ADR 0011).
        goal:           Goal slug this run advances (mirrors ``manifest.json``).
        engine_version: Engine ``VERSION`` string at run start (mirrors
                        ``manifest.json.engine_version``).
        created_at:     ISO-8601 UTC timestamp string (caller-supplied — injectable
                        for tests; do NOT call ``utcnow()`` inside this helper).

    Returns:
        A dict conforming to the ``run_start`` shape ready for ``EventStore.append``.
    """
    return {
        "event_type": "run_start",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "goal": goal,
        "engine_version": engine_version,
        "created_at": created_at,
    }


def validate_run_start(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``run_start`` event.

    Checks the envelope first (envelope-first pattern), then shape-specific
    constraints:
    - ``event_type`` pinned to ``"run_start"``.
    - ``run_id`` is required (non-empty string) — it is the run join key.
    - ``goal`` and ``engine_version`` are non-empty strings.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "run_start"):
        errors.append(
            f"event_type must be 'run_start'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for run_start and must be a non-empty string")
    for str_field in ("goal", "engine_version"):
        v = event.get(str_field)
        if v is None or not isinstance(v, str) or not v:
            errors.append(f"{str_field!r} must be a non-empty string")
    return errors


# ---------------------------------------------------------------------------
# Shape D — run_end (ADR 0023 §4 — LOAD-BEARING metrics_lib.py contract)
# ---------------------------------------------------------------------------
#
# ``run_end`` is the completion event (`_is_completion_event`) that the entire
# T-gate + anti-gaming layer in ``scripts/metrics_lib.py`` reads. The field
# names below are a HARD CONTRACT — renaming any of them silently zeroes out a
# KPI (ADR 0023 §4). Consumed by:
#   run_id      -> run_intervals (T3 pairing), _unit_key (T4 de-dup)
#   created_at  -> _parse_iso    (T3 interval endpoints)
#   outcome     -> _is_successful_completion (SUCCESS_OUTCOMES)
#   model       -> model_mix     (T4 low-cost share; LOW_COST_MODELS)
#   merged_pr   -> gaming_violations (R-9 "no merged PR")
#   ci_status   -> gaming_violations (GREEN_CI)
#   t7_pass     -> gaming_violations / t1b_high_impact (_is_true_flag)
#   t7_score    -> t1b_high_impact  (float(t7_score) >= 0.90)
#
# The single source of truth for that consumed field set, asserted by the
# schema-conformance test in tests/test_dgox_events.py:
RUN_END_METRICS_FIELDS = frozenset(
    {
        "run_id",
        "created_at",
        "outcome",
        "model",
        "merged_pr",
        "ci_status",
        "t7_pass",
        "t7_score",
    }
)

_RUN_END_REQUIRED = frozenset({"event_type", "ticket_id"}) | RUN_END_METRICS_FIELDS


def build_run_end(
    *,
    ticket_id: str,
    run_id: str,
    outcome: str,
    model: str,
    merged_pr: Any,
    ci_status: str,
    t7_pass: Any,
    t7_score: float,
    created_at: str,
) -> dict[str, Any]:
    """Build a ``run_end`` event dict (Shape D — ADR 0023 §4).

    This is the load-bearing completion event for the metrics layer. Every
    field name here MUST match ``scripts/metrics_lib.py`` exactly (see the
    module comment above and ``RUN_END_METRICS_FIELDS``); a rename silently
    breaks T3/T4, R-9 anti-gaming, and T1b high-impact.

    Args:
        ticket_id:  DAS-NNNN identifier of the completed unit (read by
                    ``gaming_violations`` and ``_unit_key`` T4 de-dup fallback).
        run_id:     ULID run join key — pairs with ``run_start`` in
                    ``run_intervals`` and de-dups the completion unit in ``model_mix``.
        outcome:    Run outcome; counts as success when in
                    ``SUCCESS_OUTCOMES = {"success","ok","passed","done"}``
                    (empty also counts) — anything else is NOT a success.
        model:      Explicit model name (LAW 3 / ADR 0007). ``model_mix``
                    lower-cases it and tests membership in ``LOW_COST_MODELS``.
        merged_pr:  Merged-PR evidence (R-9). Must be truthy for the completion
                    to count — a PR ref/URL string or ``True``.
        ci_status:  CI status; green ⇒ ``GREEN_CI = {"green","pass","passed","success"}``.
        t7_pass:    T7 pass flag; ``_is_true_flag`` truthiness (the string
                    ``"false"``/``"no"``/``"0"`` does NOT pass).
        t7_score:   T7 impact score; ``t1b_high_impact`` compares
                    ``float(t7_score) >= 0.90``.
        created_at: ISO-8601 UTC timestamp string (caller-supplied — injectable
                    for tests; do NOT call ``utcnow()`` inside this helper).

    Returns:
        A dict conforming to the ``run_end`` shape ready for ``EventStore.append``.
    """
    return {
        "event_type": "run_end",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "outcome": outcome,
        "model": model,
        "merged_pr": merged_pr,
        "ci_status": ci_status,
        "t7_pass": t7_pass,
        "t7_score": t7_score,
        "created_at": created_at,
    }


def validate_run_end(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``run_end`` event.

    Checks the envelope first (envelope-first pattern), then the load-bearing
    metrics contract:
    - ``event_type`` pinned to ``"run_end"``.
    - ``run_id`` is required (non-empty string) — the metrics join key.
    - every ``RUN_END_METRICS_FIELDS`` member is present (a missing one silently
      zeroes a KPI — flag it loudly here).
    - ``outcome``, ``model``, ``ci_status`` are non-empty strings.
    - ``t7_score`` is coercible to ``float`` (``t1b_high_impact`` calls ``float(...)``).
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "run_end"):
        errors.append(
            f"event_type must be 'run_end'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for run_end and must be a non-empty string")
    # The metrics contract: every consumed field must be present, else a KPI
    # silently zeroes (ADR 0023 §4). created_at/run_id already handled above.
    for field in ("outcome", "model", "merged_pr", "ci_status", "t7_pass", "t7_score"):
        if field not in event:
            errors.append(f"missing metrics-contract field: {field!r} (run_end)")
    for str_field in ("outcome", "model", "ci_status"):
        v = event.get(str_field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{str_field!r} must be a non-empty string")
    score = event.get("t7_score")
    if score is not None:
        try:
            float(score)
        except (TypeError, ValueError):
            errors.append(f"t7_score must be coercible to float; got {score!r}")
    return errors


# ---------------------------------------------------------------------------
# Shape E — wave (ADR 0023 §2 — a wave boundary within a run)
# ---------------------------------------------------------------------------

_WAVE_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "wave",
        "tickets",
        "created_at",
    }
)


def build_wave(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    tickets: list[str],
    created_at: str,
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a ``wave`` event dict (Shape E — ADR 0023 §2 manifest wave).

    Records one wave boundary of a run: the 1-based wave number and the ticket
    set dispatched in it (mirrors ``manifest.json.waves[]``). ``tickets`` is
    copied so a caller mutating the source list cannot mutate the event.

    Args:
        ticket_id:  DAS-NNNN anchor ticket for the run (envelope law).
        run_id:     ULID run join key.
        wave:       1-based wave index within the run (positive integer).
        tickets:    Ticket ids dispatched in this wave (copied defensively).
        created_at: ISO-8601 UTC timestamp string (caller-supplied — injectable
                    for tests; do NOT call ``utcnow()`` inside this helper).
        routing:    Optional per-ticket ``{ticket_id: {role, model}}`` routing
                    map (mirrors ``manifest.json.waves[].routing``); copied.

    Returns:
        A dict conforming to the ``wave`` shape ready for ``EventStore.append``.
    """
    event: dict[str, Any] = {
        "event_type": "wave",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "tickets": list(tickets),
        "created_at": created_at,
    }
    if routing is not None:
        event["routing"] = dict(routing)
    return event


def validate_wave(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``wave`` event.

    Checks the envelope first (envelope-first pattern), then shape-specific
    constraints:
    - ``event_type`` pinned to ``"wave"``.
    - ``run_id`` is required (non-empty string).
    - ``wave`` is a positive integer (1-based).
    - ``tickets`` is a list of non-empty strings.
    - ``routing``, if present, is a dict.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "wave"):
        errors.append(f"event_type must be 'wave'; got {event.get('event_type')!r}")
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for wave and must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    tickets = event.get("tickets")
    if tickets is not None and (
        not isinstance(tickets, list) or not all(isinstance(t, str) and t for t in tickets)
    ):
        errors.append("tickets must be a list of non-empty strings")
    routing = event.get("routing")
    if routing is not None and not isinstance(routing, dict):
        errors.append("routing must be a dict when present")
    return errors


# ---------------------------------------------------------------------------
# Shape F — checkpoint (ADR 0023 §2/§3 — per-wave resumable checkpoint)
# ---------------------------------------------------------------------------

_CHECKPOINT_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "wave",
        "board_hash",
        "event_offset",
        "ticket_states",
        "ledger_hashes",
        "created_at",
    }
)


def build_checkpoint(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    board_hash: str,
    event_offset: int,
    ticket_states: dict[str, str],
    ledger_hashes: dict[str, str],
    created_at: str,
    pending_interrupts: list[str] | None = None,
) -> dict[str, Any]:
    """Build a ``checkpoint`` event dict (Shape F — ADR 0023 §2/§3).

    Records a per-wave resumable checkpoint (mirrors ``wave-NNN.checkpoint.json``):
    the ``event_offset`` resume point into ``board/.events.jsonl``, the
    ``board_hash`` tamper check, the ``ticket_states`` DELTA (only tickets whose
    status changed since the previous checkpoint — ADR 0023 §3), and the
    ``ledger_hashes`` ``{prev,self}`` hash chain. Dict/list args are copied so a
    caller mutating a source cannot mutate the stored event (append-only law).

    Args:
        ticket_id:          DAS-NNNN anchor ticket for the run (envelope law).
        run_id:             ULID run join key.
        wave:               1-based wave index this checkpoint closes.
        board_hash:         Content hash of the board ticket set at the wave
                            boundary (out-of-band mutation detector).
        event_offset:       Byte offset into ``board/.events.jsonl`` — the resume
                            point (non-negative integer).
        ticket_states:      Per-ticket status DELTA since the previous checkpoint
                            (``{ticket_id: status}``); copied defensively.
        ledger_hashes:      ``{prev, self}`` hash chain linking checkpoints; copied.
        created_at:         ISO-8601 UTC timestamp string (caller-supplied —
                            injectable for tests; do NOT call ``utcnow()`` here).
        pending_interrupts: Ticket ids halted awaiting a human interrupt answer
                            (WS1 interrupt cards); copied. Defaults to ``[]``.

    Returns:
        A dict conforming to the ``checkpoint`` shape ready for ``EventStore.append``.
    """
    return {
        "event_type": "checkpoint",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "board_hash": board_hash,
        "event_offset": event_offset,
        "ticket_states": dict(ticket_states),
        "pending_interrupts": list(pending_interrupts) if pending_interrupts is not None else [],
        "ledger_hashes": dict(ledger_hashes),
        "created_at": created_at,
    }


def validate_checkpoint(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``checkpoint`` event.

    Checks the envelope first (envelope-first pattern), then shape-specific
    constraints:
    - ``event_type`` pinned to ``"checkpoint"``.
    - ``run_id`` is required (non-empty string).
    - ``wave`` is a positive integer (1-based).
    - ``board_hash`` is a non-empty string.
    - ``event_offset`` is a non-negative integer (byte offset / resume point).
    - ``ticket_states`` and ``ledger_hashes`` are dicts.
    - ``ledger_hashes`` carries the ``prev`` and ``self`` chain links.
    - ``pending_interrupts``, if present, is a list of strings.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "checkpoint"):
        errors.append(
            f"event_type must be 'checkpoint'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for checkpoint and must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    board_hash = event.get("board_hash")
    if board_hash is not None and (not isinstance(board_hash, str) or not board_hash):
        errors.append("board_hash must be a non-empty string")
    offset = event.get("event_offset")
    if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0):
        errors.append(f"event_offset must be a non-negative integer; got {offset!r}")
    for dict_field in ("ticket_states", "ledger_hashes"):
        v = event.get(dict_field)
        if v is not None and not isinstance(v, dict):
            errors.append(f"{dict_field!r} must be a dict")
    lh = event.get("ledger_hashes")
    if isinstance(lh, dict):
        for link in ("prev", "self"):
            if link not in lh:
                errors.append(f"ledger_hashes must carry {link!r} (checkpoint hash chain)")
    pi = event.get("pending_interrupts")
    if pi is not None and (not isinstance(pi, list) or not all(isinstance(s, str) for s in pi)):
        errors.append("pending_interrupts must be a list of strings")
    return errors


# ---------------------------------------------------------------------------
# Shape G — cache_hit (ORGANISM P6 — DAS-1450)
# ---------------------------------------------------------------------------


def build_cache_hit(
    *,
    ticket_id: str,
    cache_key: str,
    created_at: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a ``cache_hit`` event dict (Shape C — ORGANISM P6 / DAS-1450).

    Emitted by the result-cache module when a dispatch is short-circuited by a
    content-addressed cache hit.  The ``cached`` field is always ``True`` so
    consumers can filter events by type or field without inspecting other shapes.

    Args:
        ticket_id:   DAS-NNNN ticket identifier for the dispatch that hit.
        cache_key:   Hex SHA-256 of ``prompt + sorted(input_digests)`` — the
                     key that resolved to a valid (non-expired) cache entry.
        created_at:  ISO-8601 UTC timestamp string (caller-supplied; injectable
                     for tests — do NOT call ``utcnow()`` inside this helper).
        run_id:      Optional run correlation identifier.

    Returns:
        A dict conforming to the ``cache_hit`` shape ready for ``EventStore.append``.
    """
    event: dict[str, Any] = {
        "event_type": "cache_hit",
        "ticket_id": ticket_id,
        "cache_key": cache_key,
        "cached": True,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


# ---------------------------------------------------------------------------
# Shape H — span (ORGANISM WS3 BRIDGE — ADR 0024)
# ---------------------------------------------------------------------------
#
# A distributed-trace-style record for one unit of agent work, carrying the
# OpenTelemetry **GenAI semantic-convention attribute names** as its JSON field
# names so a real OTLPSpanExporter is a field-mapping shim, not a schema
# migration (ADR 0024 §2). The mapping table below is the single authoritative
# change-point; a rename here silently breaks the future exporter.
#
#   JSON key                            -> OTel attribute / concept
#   ----------------------------------  -> ---------------------------------
#   trace_id                            -> trace_id (OTel Span core; = ticket id)
#   span_id                             -> span_id  (OTel Span core)
#   parent_span_id                      -> parent_span_id (null ⇒ root span)
#   kind                                -> gen_ai.operation.name
#   gen_ai.agent.name                   -> gen_ai.agent.name (verbatim)
#   gen_ai.request.model                -> gen_ai.request.model (tier/model)
#   start / end                         -> OTel span start / end time
#   duration_ms                         -> daslab.span.duration_ms (derived)
#   gen_ai.usage.input_tokens           -> gen_ai.usage.input_tokens (verbatim)
#   gen_ai.usage.output_tokens          -> gen_ai.usage.output_tokens (verbatim)
#   gen_ai.usage.cached_input_tokens    -> gen_ai.usage.cached_input_tokens
#   cached                              -> daslab.usage.cached (bool)
#   status                              -> OTel span status code (OK/ERROR)

#: The OTel GenAI attribute names used as span JSON field names (single source
#: of truth for the §2 mapping — a test asserts the builder emits exactly these).
SPAN_OTEL_ATTRS: dict[str, str] = {
    "kind": "gen_ai.operation.name",
    "agent_name": "gen_ai.agent.name",
    "model": "gen_ai.request.model",
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
    "cached_input_tokens": "gen_ai.usage.cached_input_tokens",
}

#: Valid span kinds. invoke_agent/chat/execute_tool are OTel GenAI operation
#: names verbatim; wave/run are DasLab orchestration spans (ADR 0024 §1).
SPAN_KINDS = frozenset({"invoke_agent", "chat", "execute_tool", "wave", "run"})

#: Valid span statuses (aligned with the OTel span status code, ADR 0024 §1).
SPAN_STATUSES = frozenset({"ok", "error"})

_SPAN_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "kind",
        "gen_ai.agent.name",
        "gen_ai.request.model",
        "start",
        "end",
        "duration_ms",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "cached",
        "status",
        "created_at",
    }
)


def _iso_to_dt(ts: str) -> datetime:
    """Parse a caller-supplied ISO-8601 ``Z`` timestamp into a datetime.

    Pure — no clock read. ``fromisoformat`` handles the trailing ``Z`` only on
    3.11+, so it is normalised to ``+00:00`` for portability.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _duration_ms(start: str, end: str) -> int:
    """Derive span duration in milliseconds from caller-supplied start/end.

    Pure derivation (ADR 0024 §3 — no clock read); ``end - start`` in ms.
    """
    return int((_iso_to_dt(end) - _iso_to_dt(start)).total_seconds() * 1000)


def build_span(
    *,
    ticket_id: str,
    span_id: str,
    parent_span_id: str | None,
    kind: str,
    agent_name: str,
    model: str,
    start: str,
    end: str,
    created_at: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    status: str = "ok",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a ``span`` event dict (Shape H — ADR 0024).

    A distributed-trace span for one unit of agent work, using the OTel GenAI
    semantic-convention attribute names as JSON field names (ADR 0024 §2). Two
    fields are **derived** from caller-supplied inputs (no clock read, no
    independent state): ``trace_id`` (:= ``ticket_id``, ADR 0024 §1),
    ``duration_ms`` (:= ``end - start`` in ms), and ``cached``
    (:= ``cached_input_tokens > 0``).

    Args:
        ticket_id:           DAS-NNNN ticket identifier; also the ``trace_id``
                             (a run is traced under its ticket — ADR 0024 §1).
        span_id:             Opaque unique id for this span (non-empty string).
        parent_span_id:      Enclosing span's ``span_id``; ``None`` for a root
                             span (a top-level ``run`` / ``wave``).
        kind:                Span kind ∈ ``SPAN_KINDS`` (→ ``gen_ai.operation.name``).
        agent_name:          Agent/role name (→ ``gen_ai.agent.name``).
        model:               Model/tier the agent ran on — opus/sonnet/haiku or a
                             full model id (→ ``gen_ai.request.model``). In DasLab
                             tier and model are one axis (Model Allocation Law).
        start:               Span start, caller-supplied ISO-8601 ``Z`` (never
                             generated inside this pure helper).
        end:                 Span end, caller-supplied ISO-8601 ``Z``.
        created_at:          Envelope timestamp, caller-supplied ISO-8601 ``Z``
                             (append-only discipline; do NOT call ``utcnow()``
                             inside this helper — injectable for tests).
        input_tokens:        Input token count (→ ``gen_ai.usage.input_tokens``).
        output_tokens:       Output token count (→ ``gen_ai.usage.output_tokens``).
        cached_input_tokens: Cache-read input token count
                             (→ ``gen_ai.usage.cached_input_tokens``); 0 ⇒ nothing
                             served from cache. Drives the ``cached`` flag.
        status:              Span outcome ∈ ``SPAN_STATUSES`` (``ok`` / ``error``).
        run_id:              Optional run correlation identifier.

    Returns:
        A dict conforming to the ``span`` shape ready for ``EventStore.append``.
    """
    event: dict[str, Any] = {
        "event_type": "span",
        "ticket_id": ticket_id,
        "trace_id": ticket_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "kind": kind,
        "gen_ai.agent.name": agent_name,
        "gen_ai.request.model": model,
        "start": start,
        "end": end,
        "duration_ms": _duration_ms(start, end),
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.cached_input_tokens": cached_input_tokens,
        "cached": cached_input_tokens > 0,
        "status": status,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


def validate_span(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``span`` event (Shape H — ADR 0024).

    Checks the envelope first (envelope-first pattern), then the span-specific
    invariants from ADR 0024 §1 / implementation notes:
    - ``event_type`` pinned to ``"span"``.
    - ``trace_id`` is a non-empty string equal to ``ticket_id`` (ADR 0024 §1).
    - ``span_id`` is a non-empty string.
    - ``parent_span_id`` is ``None`` (root) or a non-empty string.
    - ``kind`` ∈ ``SPAN_KINDS``; ``status`` ∈ ``SPAN_STATUSES``.
    - ``gen_ai.agent.name`` / ``gen_ai.request.model`` are non-empty strings.
    - ``start`` / ``end`` are non-empty strings; ``duration_ms`` is a
      non-negative int equal to the derived ``end - start`` when both parse.
    - token counts are non-negative ints; ``cached`` is a bool consistent with
      ``cached_input_tokens > 0``.

    Never raises — returns ``[]`` for a well-formed span.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "span"):
        errors.append(f"event_type must be 'span'; got {event.get('event_type')!r}")

    # trace_id == ticket_id (a run is traced under its ticket — ADR 0024 §1).
    trace_id = event.get("trace_id")
    if not trace_id or not isinstance(trace_id, str):
        errors.append("trace_id must be a non-empty string (= ticket_id)")
    else:
        ticket_id = event.get("ticket_id")
        if ticket_id is not None and trace_id != ticket_id:
            errors.append(
                f"trace_id must equal ticket_id; got {trace_id!r} != {ticket_id!r}"
            )

    span_id = event.get("span_id")
    if not span_id or not isinstance(span_id, str):
        errors.append("span_id must be a non-empty string")

    # parent_span_id: None ⇒ root; otherwise a non-empty string.
    if "parent_span_id" in event:
        psid = event["parent_span_id"]
        if psid is not None and (not isinstance(psid, str) or not psid):
            errors.append("parent_span_id must be None (root) or a non-empty string")

    kind = event.get("kind")
    if kind is not None and kind not in SPAN_KINDS:
        errors.append(f"kind must be one of {sorted(SPAN_KINDS)}; got {kind!r}")

    status = event.get("status")
    if status is not None and status not in SPAN_STATUSES:
        errors.append(f"status must be one of {sorted(SPAN_STATUSES)}; got {status!r}")

    for attr in ("gen_ai.agent.name", "gen_ai.request.model"):
        v = event.get(attr)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{attr!r} must be a non-empty string")

    for tfield in ("start", "end"):
        v = event.get(tfield)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{tfield!r} must be a non-empty ISO-8601 string")

    # duration_ms: non-negative int, and == derived (end - start) when parseable.
    duration = event.get("duration_ms")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, int) or duration < 0
    ):
        errors.append(f"duration_ms must be a non-negative integer; got {duration!r}")
    else:
        start, end = event.get("start"), event.get("end")
        if isinstance(start, str) and start and isinstance(end, str) and end:
            try:
                derived = _duration_ms(start, end)
            except ValueError:
                pass
            else:
                if duration is not None and duration != derived:
                    errors.append(
                        f"duration_ms must equal end - start ({derived} ms); got {duration!r}"
                    )

    for tok in ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"):
        v = event.get(tok)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            errors.append(f"{tok!r} must be a non-negative integer; got {v!r}")

    cit = event.get("gen_ai.usage.cached_input_tokens")
    if cit is not None and (isinstance(cit, bool) or not isinstance(cit, int) or cit < 0):
        errors.append(
            f"'gen_ai.usage.cached_input_tokens' must be a non-negative integer; got {cit!r}"
        )

    # cached: bool, consistent with cached_input_tokens > 0 (ADR 0024 §1).
    cached = event.get("cached")
    if cached is not None and not isinstance(cached, bool):
        errors.append(f"cached must be a boolean; got {cached!r}")
    elif (
        isinstance(cached, bool)
        and isinstance(cit, int)
        and not isinstance(cit, bool)
        and cached != (cit > 0)
    ):
        errors.append(
            f"cached must equal (cached_input_tokens > 0); got cached={cached!r}, "
            f"cached_input_tokens={cit!r}"
        )

    return errors


# ---------------------------------------------------------------------------
# Event store — durable, concurrency-safe JSONL appender
# ---------------------------------------------------------------------------


class EventStore:
    """Append-only JSONL event store (ADR 0011 §2).

    Appends one JSON line per event to ``path`` (default:
    ``board/.events.jsonl``).  Each line is a single ``json.dumps`` call
    followed by a newline — this is the JSONL contract.

    **Concurrency safety:** uses ``fcntl.flock(LOCK_EX)`` on POSIX before
    every write, releasing immediately after.  Combined with ``O_APPEND``
    semantics (which guarantee the kernel advances the file offset
    atomically on POSIX), this provides safe single-host concurrent writers.
    On non-POSIX systems (Windows) the lock is silently skipped; the module
    is intended for POSIX-only CI/run environments.

    The store is **write-only by design** — reading/replaying is handled by
    the free function ``iter_events`` (below), which never goes through this
    class so the store interface stays minimal.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_STORE_PATH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, event: dict[str, Any]) -> None:
        """Append *event* to the store as a single JSONL line.

        The envelope is validated before writing.  If validation finds errors
        a ``ValueError`` is raised and nothing is written — the store is never
        left in a partial state.

        The parent directory is created on first use (``board/`` already
        exists in practice; the guard is for tests using tmp_path).
        """
        errors = validate_envelope(event)
        if errors:
            raise ValueError(
                f"Cannot append invalid event (errors: {errors}): {event!r}"
            )
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode — O_APPEND is atomic per POSIX on local filesystems.
        with open(self.path, "a", encoding="utf-8") as fh:
            with contextlib.suppress(AttributeError, OSError):
                fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                with contextlib.suppress(AttributeError, OSError):
                    fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Reader / replay helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Shape H — ticket_completion (DAS-1444 / ORGANISM WS1 — per-ticket durable
# completion record written mid-wave for crash-safe resume)
# ---------------------------------------------------------------------------


def build_ticket_completion(
    *,
    ticket_id: str,
    run_id: str,
    status: str,
    wave: int,
    created_at: str,
) -> dict[str, Any]:
    """Build a ``ticket_completion`` event dict (Shape H — DAS-1444 / WS1 PULSE).

    Emitted by ``pulse_checkpoint.append_ticket_completion`` as each ticket
    finishes mid-wave.  Stored in ``board/runs/<run_id>/completions.jsonl``
    using the same durable-append discipline (``O_APPEND`` + ``flock`` + ``fsync``)
    as ``EventStore.append`` — so a crash after N completions leaves exactly
    those N recorded and a resume re-dispatches only the remaining tickets.

    Args:
        ticket_id:  DAS-NNNN identifier of the completed ticket.
        run_id:     ULID run join key — scopes the completion to its run.
        status:     The status the ticket reached (e.g. ``"done"``, ``"in_review"``).
        wave:       1-based wave index within the run the ticket completed in.
        created_at: ISO-8601 UTC timestamp string (caller-supplied — injectable
                    for tests; do NOT call ``utcnow()`` inside this helper).

    Returns:
        A dict conforming to the ``ticket_completion`` shape ready for
        ``EventStore.append``.
    """
    return {
        "event_type": "ticket_completion",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "status": status,
        "wave": wave,
        "created_at": created_at,
    }


def validate_ticket_completion(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``ticket_completion`` event.

    Checks the envelope first (envelope-first pattern), then:
    - ``event_type`` pinned to ``"ticket_completion"``.
    - ``run_id`` is required (non-empty string) — run join key.
    - ``status`` is a non-empty string.
    - ``wave`` is a positive (1-based) integer.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "ticket_completion"):
        errors.append(
            f"event_type must be 'ticket_completion'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for ticket_completion and must be a non-empty string")
    status = event.get("status")
    if status is not None and (not isinstance(status, str) or not status):
        errors.append("status must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    return errors


# ---------------------------------------------------------------------------
# Shape I — replanned (ORGANISM WS2 LOOM — DAS-1470 inner loop)
# ---------------------------------------------------------------------------
#
# Emitted by the P7 inner loop (``scripts/check_ledger.py``) when the stall
# counter crosses its threshold and the task-ledger is regenerated (facts-update
# + plan-update via ``scripts/task_ledger.py``).  It records *that a replan
# happened*, the new task-ledger ``revision`` it produced, the ``stall`` value
# that triggered it, and the ``max_replans_remaining`` budget after the
# decrement — so a reader can reconstruct the self-correction history of a run
# and see how close it came to pause-on-stall (interrupt-card).


def build_replanned(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    revision: int,
    stall: int,
    max_replans_remaining: int,
    reason: str,
    created_at: str,
) -> dict[str, Any]:
    """Build a ``replanned`` event dict (Shape I — ORGANISM WS2 LOOM / DAS-1470).

    Emitted when the inner-loop stall counter exceeds its threshold and the
    task-ledger is regenerated.  All fields are caller-supplied — this helper
    reads no clock and no state (append-only discipline).

    Args:
        ticket_id:             DAS-NNNN anchor ticket for the run (envelope law).
        run_id:                ULID run join key.
        wave:                  1-based wave index at which the replan fired.
        revision:              The task-ledger ``revision`` produced by the
                               regeneration (post-bump; positive integer).
        stall:                 The stall-counter value that triggered the replan.
        max_replans_remaining: The bounded replan budget AFTER this replan's
                               decrement (non-negative integer).
        reason:                Human-readable trigger rationale (non-empty).
        created_at:            ISO-8601 UTC timestamp string (caller-supplied —
                               injectable for tests; do NOT call ``utcnow()`` here).

    Returns:
        A dict conforming to the ``replanned`` shape ready for ``EventStore.append``.
    """
    return {
        "event_type": "replanned",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "revision": revision,
        "stall": stall,
        "max_replans_remaining": max_replans_remaining,
        "reason": reason,
        "created_at": created_at,
    }


def validate_replanned(event: dict[str, Any]) -> list[str]:
    """Return validation errors for a ``replanned`` event (Shape I — DAS-1470).

    Checks the envelope first (envelope-first pattern), then shape-specific
    constraints:
    - ``event_type`` pinned to ``"replanned"``.
    - ``run_id`` is required (non-empty string).
    - ``wave`` and ``revision`` are positive (1-based) integers.
    - ``stall`` and ``max_replans_remaining`` are non-negative integers.
    - ``reason`` is a non-empty string.
    """
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "replanned"):
        errors.append(
            f"event_type must be 'replanned'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for replanned and must be a non-empty string")
    for pos_field in ("wave", "revision"):
        v = event.get(pos_field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 1):
            errors.append(f"{pos_field!r} must be a positive (1-based) integer; got {v!r}")
    for nn_field in ("stall", "max_replans_remaining"):
        v = event.get(nn_field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            errors.append(f"{nn_field!r} must be a non-negative integer; got {v!r}")
    reason = event.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason):
        errors.append("reason must be a non-empty string")
    return errors


def iter_events(
    path: Path | str | None = None,
    *,
    ticket_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate over events from a JSONL store, with optional filters.

    Args:
        path:        Path to the JSONL store (default: ``board/.events.jsonl``).
        ticket_id:   If given, yield only events whose ``ticket_id`` matches.
        run_id:      If given, yield only events whose ``run_id`` matches.
        event_type:  If given, yield only events of this type.

    Yields:
        Parsed event dicts, in append order (oldest first).  Lines that
        cannot be parsed as JSON are silently skipped (corrupted/partial
        writes are tolerated in replay; they never corrupt the iterator).

    Notes:
        - The store file may not exist yet (no waves run): returns immediately.
        - This is a generator — it does not load the whole file into memory.
    """
    p = Path(path) if path is not None else DEFAULT_STORE_PATH
    if not p.exists():
        return
    with open(p, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if ticket_id is not None and event.get("ticket_id") != ticket_id:
                continue
            if run_id is not None and event.get("run_id") != run_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            yield event
