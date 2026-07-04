"""dispatch_emitter.py — the missing DGO-X event PRODUCER (ORGANISM WS3 / DAS-1455).

DasLab's whole observability stack (T1–T7 gates, anti-gaming R-9,
concurrency/model-mix KPIs) reads the append-only DGO-X event store at
``board/.events.jsonl``.  Until now that store had typed *builders*
(``scripts/dgox/events.py``) and *readers* (``scripts/wave_kpi.py`` /
``scripts/metrics_lib.py``) but **no producer** — nothing appended the paired
``run_start`` / ``run_end`` / span events a real wave should emit.  As a result
every event-based T-gate read "inert" (returned ``None`` — a shipped lever with
no live data).  This module is that missing producer.

Given a wave's dispatch/collect data — the per-ticket dispatch records the
orchestrator already has (``ticket_id``, ``run_id``, ``model``, ``outcome``,
PR/CI/T7 evidence, start/end timestamps) — it appends, **via the DAS-1443/1454
typed builders only** (never hand-rolled dicts), for each dispatch:

- a ``run_start`` event,
- a ``run_end`` event carrying ``metrics_lib``'s EXACT evidence field names
  (``outcome``, ``model``, ``merged_pr``, ``ci_status``, ``t7_pass``,
  ``t7_score``), and
- a ``span`` (``invoke_agent`` / ``execute_tool`` / ``chat`` / ``wave`` /
  ``run``).

Design invariants (EXTEND, do not fork):
- **Pure core.** ``build_dispatch_events`` / ``build_wave_events`` are pure
  functions of their inputs — every timestamp is a caller-supplied argument
  (``created_at`` injectable); there is NO ``utcnow()`` / clock / network read
  in the core path.  This makes the producer deterministic and unit-testable in
  isolation.
- **Append-only.** The emit wrappers use ``EventStore.append`` exclusively and
  never truncate, rewrite, or edit existing lines in the store.
- **REUSE, never re-implement.** All events come from the ``scripts/dgox/events.py``
  typed builders and are validated by that module's shape validators before a
  single line is written; ``events.py`` / ``metrics_lib.py`` / ``wave_kpi.py``
  are imported, never modified.

Pairing contract (``scripts/wave_kpi.py`` / ``scripts/metrics_lib.py``): every
``run_start.run_id`` has a matching ``run_end.run_id`` and both carry
``created_at`` as ``YYYY-MM-DDTHH:MM:SSZ`` so ``run_intervals`` /
``busy_fraction_from_events`` pair them by ``run_id`` and count ``model`` once
per ``run_start``.

**This module does NOT flip ``dgox_emit``.**  Turning the producer on for real
waves is a governance flag flip done at wiring time (DAS-1452) — this ticket
only makes the producer exist and be correct.  The store stays in shadow mode
until the wiring ticket flips the flag.

Public API
----------
    DispatchRecord                         # typed per-dispatch input
    build_dispatch_events(record)          # pure: record -> [run_start, run_end, span]
    build_wave_events(records)             # pure: [record, ...] -> [event, ...]
    emit_dispatch(record, *, store/store_path)   # append one dispatch's events
    emit_wave(records, *, store/store_path)      # append a whole wave's events
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating import of the dgox typed builders (same pattern as
# scripts/dgox/board_adapter.py — make scripts/ importable regardless of how
# the module is invoked, then import the builder/store library).
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent  # scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.events import (  # noqa: E402
    SPAN_KINDS,
    EventStore,
    build_run_end,
    build_run_start,
    build_span,
    validate_run_end,
    validate_run_start,
    validate_span,
)

__all__ = [
    "DispatchRecord",
    "build_dispatch_events",
    "build_wave_events",
    "emit_dispatch",
    "emit_wave",
]


# ---------------------------------------------------------------------------
# Typed per-dispatch input record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchRecord:
    """One wave dispatch/collect record — the producer's pure input.

    These are exactly the fields the orchestrator already has at dispatch and
    collect time.  ``run_id`` is the join key across the ``run_start`` /
    ``run_end`` / span triplet (and, downstream, the whole observability layer).

    Timestamps are caller-supplied ISO-8601 ``Z`` strings — the producer never
    reads a clock.  ``start`` / ``end`` bound the run and the span; the two
    optional ``run_start_at`` / ``run_end_at`` overrides let a caller decouple
    the run-boundary timestamps from the span window when needed (they default
    to ``start`` / ``end``).  For the metrics readers to pair the run,
    ``run_end``'s timestamp must be ``>=`` ``run_start``'s.

    Attributes:
        ticket_id:      DAS-NNNN identifier of the dispatched unit.
        run_id:         Run join key (pairs run_start/run_end; spans reference it).
        goal:           Goal slug this run advances (``run_start`` field).
        engine_version: Engine VERSION string at run start (``run_start`` field).
        model:          Explicit model name (LAW 3); lower-cased downstream for T4.
        role_key:       Agent/role name → the span's ``gen_ai.agent.name``.
        start:          Run/span start, ISO-8601 ``Z`` (caller-supplied).
        end:            Run/span end, ISO-8601 ``Z`` (caller-supplied).
        outcome:        Run outcome — ``metrics_lib`` success vocabulary.
        merged_pr:      Merged-PR evidence (R-9; truthy ⇒ counts).
        ci_status:      CI status (R-9 ``GREEN_CI``).
        t7_pass:        T7 pass flag (robust truthiness).
        t7_score:       T7 impact score (float; ``t1b_high_impact`` >= 0.90).
        span_kind:      Span kind ∈ ``SPAN_KINDS`` (default ``invoke_agent``).
        span_id:        Opaque span id; defaults to ``span-<run_id>`` when empty.
        parent_span_id: Enclosing span id, or ``None`` for a root span.
        input_tokens/output_tokens/cached_input_tokens: token usage for the span.
        span_status:    Span outcome ∈ {``ok``, ``error``} (default ``ok``).
        run_start_at:   Optional override for the ``run_start`` timestamp
                        (defaults to ``start``).
        run_end_at:     Optional override for the ``run_end`` timestamp
                        (defaults to ``end``).
    """

    ticket_id: str
    run_id: str
    goal: str
    engine_version: str
    model: str
    role_key: str
    start: str
    end: str
    outcome: str
    merged_pr: Any
    ci_status: str
    t7_pass: Any
    t7_score: float
    span_kind: str = "invoke_agent"
    span_id: str | None = None
    parent_span_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    span_status: str = "ok"
    run_start_at: str | None = None
    run_end_at: str | None = None


# ---------------------------------------------------------------------------
# Pure core — record(s) -> event dict(s)
# ---------------------------------------------------------------------------


def build_dispatch_events(record: DispatchRecord) -> list[dict[str, Any]]:
    """Pure: turn one ``DispatchRecord`` into ``[run_start, run_end, span]``.

    Deterministic — no clock or network read.  Every event is built via the
    ``scripts/dgox/events.py`` typed builders (never a hand-rolled dict) and
    validated by that module's shape validators before it is returned; an
    invalid record raises ``ValueError`` so a malformed dispatch can never be
    appended (the store's own envelope check is a second, redundant guard).

    Args:
        record: The dispatch/collect record to convert.

    Returns:
        A 3-element list ``[run_start, run_end, span]`` ready for
        ``EventStore.append``.  ``run_start`` and ``run_end`` share
        ``record.run_id`` so the metrics readers pair them.

    Raises:
        ValueError: If ``record.span_kind`` is not a valid span kind, or any
            built event fails its shape validator (surfaces the exact errors).
    """
    if record.span_kind not in SPAN_KINDS:
        raise ValueError(
            f"span_kind must be one of {sorted(SPAN_KINDS)}; got {record.span_kind!r}"
        )

    run_start_at = record.run_start_at or record.start
    run_end_at = record.run_end_at or record.end
    span_id = record.span_id or f"span-{record.run_id}"

    run_start = build_run_start(
        ticket_id=record.ticket_id,
        run_id=record.run_id,
        goal=record.goal,
        engine_version=record.engine_version,
        created_at=run_start_at,
    )
    run_end = build_run_end(
        ticket_id=record.ticket_id,
        run_id=record.run_id,
        outcome=record.outcome,
        model=record.model,
        merged_pr=record.merged_pr,
        ci_status=record.ci_status,
        t7_pass=record.t7_pass,
        t7_score=record.t7_score,
        created_at=run_end_at,
        # R6: token_total = span input+output sum, activating the check_spans
        # reconciliation seam (span sum == run_end.token_total by construction).
        # Emitted ONLY when the run carried tokens, so a zero-token record leaves
        # the seam inert and never perturbs a zero-token fixture (e.g. the
        # committed sample attestation).
        token_total=(record.input_tokens + record.output_tokens) or None,
    )
    span = build_span(
        ticket_id=record.ticket_id,
        span_id=span_id,
        parent_span_id=record.parent_span_id,
        kind=record.span_kind,
        agent_name=record.role_key,
        model=record.model,
        start=record.start,
        end=record.end,
        created_at=run_end_at,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cached_input_tokens=record.cached_input_tokens,
        status=record.span_status,
        run_id=record.run_id,
    )

    errors: list[str] = []
    errors += [f"run_start: {e}" for e in validate_run_start(run_start)]
    errors += [f"run_end: {e}" for e in validate_run_end(run_end)]
    errors += [f"span: {e}" for e in validate_span(span)]
    if errors:
        raise ValueError(
            f"dispatch record for {record.ticket_id!r} built invalid events: {errors}"
        )

    return [run_start, run_end, span]


def build_wave_events(records: list[DispatchRecord]) -> list[dict[str, Any]]:
    """Pure: flatten a wave of ``DispatchRecord`` into an ordered event list.

    The order is dispatch order, each dispatch expanded to its
    ``[run_start, run_end, span]`` triplet (the same order ``EventStore.append``
    would write them).  No clock read; deterministic for a given input.

    Args:
        records: The wave's dispatch/collect records.

    Returns:
        The concatenated event dicts, ready to append in order.
    """
    events: list[dict[str, Any]] = []
    for record in records:
        events.extend(build_dispatch_events(record))
    return events


# ---------------------------------------------------------------------------
# Emit wrappers — append the pure output to the (append-only) event store
# ---------------------------------------------------------------------------


def _resolve_store(
    store: EventStore | None,
    store_path: Path | str | None,
) -> EventStore:
    """Return the ``EventStore`` to append to.

    Exactly one of ``store`` / ``store_path`` may be given.  With neither, the
    live default store (``board/.events.jsonl``) is used — production callers
    (DAS-1452 wiring) rely on that default; tests always pass an explicit
    ``store_path`` (a ``tmp_path``) so they never touch the live store.
    """
    if store is not None and store_path is not None:
        raise ValueError("pass either store or store_path, not both")
    if store is not None:
        return store
    return EventStore(path=store_path) if store_path is not None else EventStore()


def emit_dispatch(
    record: DispatchRecord,
    *,
    store: EventStore | None = None,
    store_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Append one dispatch's ``[run_start, run_end, span]`` to the event store.

    Builds the events with the pure core, then appends each — in order — via
    ``EventStore.append`` (append-only: never truncates or rewrites).  Returns
    the events that were appended so a caller can log/inspect them.

    Args:
        record:     The dispatch/collect record to emit.
        store:      An existing ``EventStore`` to append to.
        store_path: Path to a store to open (mutually exclusive with ``store``).
                    Neither ⇒ the live ``board/.events.jsonl`` store.

    Returns:
        The list of appended event dicts (``[run_start, run_end, span]``).
    """
    target = _resolve_store(store, store_path)
    events = build_dispatch_events(record)
    for event in events:
        target.append(event)
    return events


def emit_wave(
    records: list[DispatchRecord],
    *,
    store: EventStore | None = None,
    store_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Append a whole wave's events to the event store (append-only).

    Resolves the store once, then appends every dispatch's triplet in dispatch
    order.  Equivalent to calling :func:`emit_dispatch` per record against the
    same store.

    Args:
        records:    The wave's dispatch/collect records.
        store:      An existing ``EventStore`` to append to.
        store_path: Path to a store to open (mutually exclusive with ``store``).
                    Neither ⇒ the live ``board/.events.jsonl`` store.

    Returns:
        The list of all appended event dicts, in append order.
    """
    target = _resolve_store(store, store_path)
    appended: list[dict[str, Any]] = []
    for record in records:
        for event in build_dispatch_events(record):
            target.append(event)
            appended.append(event)
    return appended
