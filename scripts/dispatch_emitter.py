
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.events import (
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


@dataclass(frozen=True)
class DispatchRecord:

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


def build_dispatch_events(record: DispatchRecord) -> list[dict[str, Any]]:
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
    events: list[dict[str, Any]] = []
    for record in records:
        events.extend(build_dispatch_events(record))
    return events


def _resolve_store(
    store: EventStore | None,
    store_path: Path | str | None,
) -> EventStore:
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
    target = _resolve_store(store, store_path)
    appended: list[dict[str, Any]] = []
    for record in records:
        for event in build_dispatch_events(record):
            target.append(event)
            appended.append(event)
    return appended
