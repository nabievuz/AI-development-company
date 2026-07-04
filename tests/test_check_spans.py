#!/usr/bin/env python3
"""tests/test_check_spans.py — unit tests for scripts/check_spans.py.

Verifies the span-coverage validator (DAS-1456):
  - Inert (exit 0) when the event store is absent or empty.
  - Exit 0 when all dispatches have well-formed matching spans.
  - Exit 1 when a dispatch is missing its span.
  - Exit 1 when a span event is malformed (fails validate_span).
  - Token reconciliation: inert (exit 0) when token_total absent on run_end;
    exit 1 when token_total present but disagrees with span sums.
  - Reads events exclusively via wave_kpi.read_events (single reader).

All tests write to tmp_path — never the live board/.events.jsonl.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any  # noqa: F401

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_spans  # noqa: E402
import wave_kpi  # noqa: E402
from dispatch_emitter import DispatchRecord, build_wave_events  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record(
    *,
    ticket_id: str = "DAS-1456",
    run_id: str = "run-span-test-1",
    start: str = "2026-07-03T10:00:00Z",
    end: str = "2026-07-03T10:05:00Z",
    model: str = "sonnet",
    outcome: str = "success",
    merged_pr: object = "https://example/pr/42",
    ci_status: str = "green",
    t7_pass: object = True,
    t7_score: float = 0.95,
    span_kind: str = "invoke_agent",
    role_key: str = "backend-eng-1",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cached_input_tokens: int = 0,
) -> DispatchRecord:
    """A well-formed dispatch record with overridable defaults."""
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
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
    )


def _write(tmp_path: Path, events: list[dict[str, Any]]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Inert behaviour — no events / store absent
# ---------------------------------------------------------------------------

def test_inert_store_absent(tmp_path):
    """Exit 0 when the event store file does not exist."""
    rc = check_spans.main(["--events", str(tmp_path / "no-such.jsonl")])
    assert rc == 0


def test_inert_store_empty(tmp_path):
    """Exit 0 when the event store exists but has no events."""
    p = tmp_path / ".events.jsonl"
    p.write_text("", encoding="utf-8")
    rc = check_spans.main(["--events", str(p)])
    assert rc == 0


def test_inert_events_no_dispatches_or_spans(tmp_path):
    """Exit 0 when events exist but there are no run_start or span events."""
    events = [
        {
            "event_type": "routing_decision",
            "ticket_id": "DAS-1456",
            "from_status": "todo",
            "to_status": "in_progress",
            "assignee": "backend-eng-1",
            "model": "sonnet",
            "reason": "route",
            "confidence": 0.9,
            "policy_checks": ["gate_ok"],
            "fallback": "block",
            "created_at": "2026-07-03T10:00:00Z",
        }
    ]
    p = _write(tmp_path, events)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 0


# ---------------------------------------------------------------------------
# T1 — 100% well-formed spans (positive case)
# ---------------------------------------------------------------------------

def test_single_dispatch_well_formed(tmp_path):
    """Exit 0: one dispatch with a matching, well-formed span."""
    events = build_wave_events([_record()])
    p = _write(tmp_path, events)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 0


def test_multi_dispatch_all_well_formed(tmp_path):
    """Exit 0: multiple dispatches, all with matching well-formed spans."""
    records = [
        _record(run_id=f"run-span-{i}", ticket_id=f"DAS-{1456 + i}")
        for i in range(5)
    ]
    events = build_wave_events(records)
    p = _write(tmp_path, events)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 0


# ---------------------------------------------------------------------------
# T2 — missing span for a dispatch (negative case)
# ---------------------------------------------------------------------------

def test_missing_span_exits_1(tmp_path):
    """Exit 1 when a run_start exists but has no matching span event."""
    events = build_wave_events([_record()])
    # Remove span events — keep run_start and run_end only.
    events_no_span = [e for e in events if e["event_type"] != "span"]
    assert any(e["event_type"] == "run_start" for e in events_no_span), (
        "Precondition: run_start must remain after removing spans."
    )
    p = _write(tmp_path, events_no_span)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


def test_partial_missing_span_exits_1(tmp_path):
    """Exit 1 when only some dispatches have spans (partial coverage)."""
    r1 = _record(run_id="run-ok", ticket_id="DAS-1456")
    r2 = _record(run_id="run-missing", ticket_id="DAS-1457")
    events = build_wave_events([r1, r2])
    # Remove span only for run-missing.
    filtered = [
        e for e in events
        if not (e["event_type"] == "span" and e.get("run_id") == "run-missing")
    ]
    p = _write(tmp_path, filtered)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


# ---------------------------------------------------------------------------
# T3 — malformed span (validate_span fires)
# ---------------------------------------------------------------------------

def test_malformed_span_exits_1(tmp_path):
    """Exit 1 when a span event fails validate_span (bad kind field)."""
    events = build_wave_events([_record()])
    # Corrupt the span: set an invalid kind.
    corrupted = []
    for ev in events:
        if ev["event_type"] == "span":
            ev = {**ev, "kind": "not_a_valid_kind"}
        corrupted.append(ev)
    p = _write(tmp_path, corrupted)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


def test_span_duration_mismatch_exits_1(tmp_path):
    """Exit 1 when a span carries an incorrect duration_ms (must equal end-start)."""
    events = build_wave_events([_record()])
    corrupted = []
    for ev in events:
        if ev["event_type"] == "span":
            ev = {**ev, "duration_ms": 99999999}   # deliberately wrong
        corrupted.append(ev)
    p = _write(tmp_path, corrupted)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


def test_span_cached_inconsistent_exits_1(tmp_path):
    """Exit 1 when cached flag is inconsistent with cached_input_tokens."""
    events = build_wave_events([_record(cached_input_tokens=0)])
    corrupted = []
    for ev in events:
        if ev["event_type"] == "span":
            # cached=True but cached_input_tokens=0 -> inconsistent.
            ev = {**ev, "cached": True}
        corrupted.append(ev)
    p = _write(tmp_path, corrupted)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


# ---------------------------------------------------------------------------
# Token reconciliation seam
# ---------------------------------------------------------------------------

def test_token_reconciliation_active_from_emitter(tmp_path):
    """Slice-2 (R6): the dispatch emitter now sets run_end.token_total = the span
    input+output sum, so reconciliation is ACTIVE and passes by construction."""
    events = build_wave_events([_record(input_tokens=200, output_tokens=80)])
    ends = [ev for ev in events if ev["event_type"] == "run_end"]
    assert ends and all(ev.get("token_total") == 280 for ev in ends)  # 200 + 80
    p = _write(tmp_path, events)
    assert check_spans.main(["--events", str(p)]) == 0


def test_token_reconciliation_inert_on_zero_token_run(tmp_path):
    """A zero-token run emits NO token_total, so the reconciliation seam stays
    inert (exit 0) — and a zero-token fixture (e.g. the committed sample) is
    never perturbed."""
    events = build_wave_events([_record(input_tokens=0, output_tokens=0)])
    ends = [ev for ev in events if ev["event_type"] == "run_end"]
    assert ends and all("token_total" not in ev for ev in ends)
    p = _write(tmp_path, events)
    assert check_spans.main(["--events", str(p)]) == 0


def test_token_reconciliation_passes_when_matching(tmp_path):
    """Exit 0 when run_end.token_total matches span token sum."""
    rec = _record(run_id="run-tokens", ticket_id="DAS-1456",
                  input_tokens=150, output_tokens=50)
    events = build_wave_events([rec])
    # Inject matching token_total on run_end.
    annotated = []
    for ev in events:
        if ev["event_type"] == "run_end" and ev.get("run_id") == "run-tokens":
            ev = {**ev, "token_total": 200}   # 150 + 50
        annotated.append(ev)
    p = _write(tmp_path, annotated)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 0


def test_token_reconciliation_fails_when_mismatch(tmp_path):
    """Exit 1 when run_end.token_total disagrees with the span token sum."""
    rec = _record(run_id="run-mismatch", ticket_id="DAS-1456",
                  input_tokens=100, output_tokens=50)
    events = build_wave_events([rec])
    # Inject wrong token_total.
    annotated = []
    for ev in events:
        if ev["event_type"] == "run_end" and ev.get("run_id") == "run-mismatch":
            ev = {**ev, "token_total": 999}   # wrong; actual = 150
        annotated.append(ev)
    p = _write(tmp_path, annotated)
    rc = check_spans.main(["--events", str(p)])
    assert rc == 1


# ---------------------------------------------------------------------------
# Reconciliation with wave_kpi.read_events (single-reader invariant)
# ---------------------------------------------------------------------------

def test_read_events_is_single_reader(tmp_path):
    """check_spans uses wave_kpi.read_events; the events it reads match raw file."""
    records = [_record(run_id=f"run-sr-{i}", ticket_id=f"DAS-{1456+i}") for i in range(3)]
    events = build_wave_events(records)
    p = _write(tmp_path, events)
    # Verify wave_kpi.read_events returns the same count check_spans will process.
    loaded = wave_kpi.read_events(str(p))
    assert len(loaded) == len(events)
    # Run the validator — must exit 0.
    assert check_spans.main(["--events", str(p)]) == 0
