
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import metrics_lib
import wave_kpi
from dgox.events import (
    RUN_END_METRICS_FIELDS,
    SPAN_KINDS,
    iter_events,
    validate_envelope,
)
from dispatch_emitter import (
    DispatchRecord,
    build_dispatch_events,
    build_wave_events,
    emit_dispatch,
    emit_wave,
)


def _record(
    *,
    ticket_id: str = "DAS-1455",
    run_id: str = "run-1455",
    start: str = "2026-07-03T00:00:00Z",
    end: str = "2026-07-03T00:05:00Z",
    model: str = "sonnet",
    outcome: str = "success",
    merged_pr: object = "https://example/pr/1",
    ci_status: str = "green",
    t7_pass: object = "pass",
    t7_score: float = 0.95,
    span_kind: str = "invoke_agent",
    role_key: str = "backend-em",
) -> DispatchRecord:
    return DispatchRecord(
        ticket_id=ticket_id,
        run_id=run_id,
        goal="organism-ws3-bridge",
        engine_version="1.2.0",
        model=model,
        role_key=role_key,
        start=start,
        end=end,
        outcome=outcome,
        merged_pr=merged_pr,
        ci_status=ci_status,
        t7_pass=t7_pass,
        t7_score=t7_score,
        span_kind=span_kind,
    )


def _synthetic_wave() -> list[DispatchRecord]:
    return [
        _record(
            ticket_id="DAS-2001", run_id="run-2001",
            start="2026-07-03T00:00:00Z", end="2026-07-03T00:06:00Z",
            model="sonnet",
        ),
        _record(
            ticket_id="DAS-2002", run_id="run-2002",
            start="2026-07-03T00:01:00Z", end="2026-07-03T00:07:00Z",
            model="haiku", span_kind="execute_tool",
        ),
        _record(
            ticket_id="DAS-2003", run_id="run-2003",
            start="2026-07-03T00:02:00Z", end="2026-07-03T00:08:00Z",
            model="opus", span_kind="chat",
        ),
        _record(
            ticket_id="DAS-2004", run_id="run-2004",
            start="2026-07-03T00:03:00Z", end="2026-07-03T00:09:00Z",
            model="haiku",
        ),
    ]


def test_dispatch_yields_run_start_run_end_span() -> None:
    events = build_dispatch_events(_record())
    assert [e["event_type"] for e in events] == ["run_start", "run_end", "span"]


def test_every_event_passes_validate_envelope() -> None:
    for event in build_wave_events(_synthetic_wave()):
        assert validate_envelope(event) == [], (
            f"{event['event_type']} failed envelope validation: "
            f"{validate_envelope(event)}"
        )


def test_run_end_carries_exact_metrics_fields() -> None:
    _, run_end, _ = build_dispatch_events(_record())
    for field in RUN_END_METRICS_FIELDS:
        assert field in run_end, f"run_end missing metrics field {field!r}"
    assert run_end["event_type"] == "run_end"

    assert run_end["outcome"] == "success"
    assert run_end["model"] == "sonnet"
    assert run_end["merged_pr"] == "https://example/pr/1"
    assert run_end["ci_status"] == "green"
    assert run_end["t7_pass"] == "pass"
    assert run_end["t7_score"] == 0.95


def test_run_start_and_run_end_share_run_id() -> None:
    run_start, run_end, span = build_dispatch_events(_record(run_id="run-XYZ"))
    assert run_start["run_id"] == "run-XYZ"
    assert run_end["run_id"] == "run-XYZ"
    assert span["run_id"] == "run-XYZ"


def test_span_kind_is_valid_and_traces_ticket() -> None:
    _, _, span = build_dispatch_events(_record(span_kind="execute_tool"))
    assert span["event_type"] == "span"
    assert span["kind"] in SPAN_KINDS
    assert span["kind"] == "execute_tool"

    assert span["trace_id"] == span["ticket_id"] == "DAS-1455"


def test_invalid_span_kind_rejected() -> None:
    with pytest.raises(ValueError, match="span_kind"):
        build_dispatch_events(_record(span_kind="not_a_kind"))


def test_pure_core_is_deterministic() -> None:
    rec = _record()
    assert build_dispatch_events(rec) == build_dispatch_events(rec)


def test_run_end_timestamp_defaults_to_record_end() -> None:
    run_start, run_end, _ = build_dispatch_events(_record())
    assert run_start["created_at"] == "2026-07-03T00:00:00Z"
    assert run_end["created_at"] == "2026-07-03T00:05:00Z"


def test_emit_dispatch_appends_three_lines(tmp_path: Path) -> None:
    store_path = tmp_path / "events.jsonl"
    emit_dispatch(_record(), store_path=store_path)
    lines = store_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_emit_is_append_only(tmp_path: Path) -> None:
    store_path = tmp_path / "events.jsonl"
    emit_dispatch(_record(ticket_id="DAS-3001", run_id="run-3001"), store_path=store_path)
    first = store_path.read_text(encoding="utf-8")
    emit_dispatch(_record(ticket_id="DAS-3002", run_id="run-3002"), store_path=store_path)
    second = store_path.read_text(encoding="utf-8")

    assert second.startswith(first)
    assert len(second.splitlines()) == 6


def test_emit_wave_writes_all_dispatches(tmp_path: Path) -> None:
    store_path = tmp_path / "events.jsonl"
    records = _synthetic_wave()
    emit_wave(records, store_path=store_path)
    events = wave_kpi.read_events(str(store_path))
    assert len(events) == 3 * len(records)
    starts = [e for e in events if e["event_type"] == "run_start"]
    ends = [e for e in events if e["event_type"] == "run_end"]

    assert {e["run_id"] for e in starts} == {e["run_id"] for e in ends}


def test_store_and_store_path_are_mutually_exclusive(tmp_path: Path) -> None:
    from dgox.events import EventStore

    store = EventStore(path=tmp_path / "e.jsonl")
    with pytest.raises(ValueError, match="not both"):
        emit_dispatch(_record(), store=store, store_path=tmp_path / "other.jsonl")


def test_emitted_events_replay_via_iter_events(tmp_path: Path) -> None:
    store_path = tmp_path / "events.jsonl"
    emit_dispatch(_record(run_id="run-REPLAY"), store_path=store_path)
    replayed = list(iter_events(path=store_path, run_id="run-REPLAY"))
    assert [e["event_type"] for e in replayed] == ["run_start", "run_end", "span"]


def test_synthetic_wave_makes_metrics_non_none(tmp_path: Path) -> None:
    store_path = tmp_path / "events.jsonl"
    emit_wave(_synthetic_wave(), store_path=store_path)
    events = wave_kpi.read_events(str(store_path))


    fraction, stats = wave_kpi.busy_fraction_from_events(events)
    assert fraction is not None, "T1 busy fraction still unmeasured — emitter inert"
    assert 0.0 <= fraction <= 1.0
    assert stats["runs_completed"] == 4


    conc = metrics_lib.concurrency_stats(events)
    assert conc is not None, "T3 concurrency still unmeasured — emitter inert"
    assert conc["median"] >= 1.0

    assert conc["median"] > 1.0


    mix = metrics_lib.model_mix(events)
    assert mix is not None, "T4 model mix still unmeasured — emitter inert"
    assert mix["total"] == 4

    assert mix["low_cost"] == 2
    assert mix["ratio"] == pytest.approx(0.5)


def test_check_scripts_exit_ok_on_synthetic_store(tmp_path: Path) -> None:
    import check_busy_fraction
    import check_concurrency
    import check_model_mix

    store_path = tmp_path / "events.jsonl"
    emit_wave(_synthetic_wave(), store_path=store_path)
    argv = ["--events", str(store_path)]


    assert check_busy_fraction.main([*argv, "--target", "0.0"]) == 0
    assert check_concurrency.main([*argv, "--target", "1"]) == 0
    assert check_model_mix.main([*argv, "--target", "0.25"]) == 0
