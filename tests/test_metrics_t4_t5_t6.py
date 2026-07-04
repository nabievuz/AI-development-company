#!/usr/bin/env python3
"""tests/test_metrics_t4_t5_t6.py — T4 model-mix, T5 recovery, T6 review (R-1 / ADR-002)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_model_mix as cm  # noqa: E402  (import after path manipulation)
import check_recovery as crec  # noqa: E402
import check_review_eff as crev  # noqa: E402
import metrics_lib as ml  # noqa: E402


def _write(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


def _completion(model: str, to_status: str = "done", outcome: str = "ok", tid: str = "DAS-1") -> dict:
    return {
        "event_type": "routing_decision", "ticket_id": tid,
        "to_status": to_status, "model": model, "outcome": outcome,
        "created_at": "2026-06-21T10:00:00Z",
    }


def _drill(outcome: str = "success", corrupted: bool = False) -> dict:
    return {
        "event_type": "recovery_drill", "ticket_id": "DAS-1",
        "outcome": outcome, "corrupted": corrupted, "created_at": "2026-06-21T10:00:00Z",
    }


def _trans(frm: str, to: str, minute: int, tid: str = "DAS-1") -> dict:
    return {
        "event_type": "routing_decision", "ticket_id": tid,
        "from_status": frm, "to_status": to, "created_at": f"2026-06-21T10:{minute:02d}:00Z",
    }


# --------------------------------------------------------------------------- #
# T4 model mix + haiku classifier
# --------------------------------------------------------------------------- #

def test_haiku_eligible_classifier():
    assert ml.haiku_eligible("format") is True
    assert ml.haiku_eligible("routing", ["doc_update"]) is True
    assert ml.haiku_eligible("code_generation") is False
    assert ml.haiku_eligible(None, ["security"]) is False
    assert ml.haiku_eligible("unknown") is False  # conservative default


def test_model_mix_none_when_empty():
    assert ml.model_mix([]) is None


def test_model_mix_ratio_excludes_failed():
    evs = [
        _completion("haiku", tid="DAS-1"),
        _completion("haiku", outcome="failed", tid="DAS-2"),
        _completion("sonnet", tid="DAS-3"),
    ]
    m = ml.model_mix(evs)
    assert m["total"] == 2 and m["low_cost"] == 1 and m["ratio"] == 0.5


def test_model_mix_cli_inert(tmp_path):
    assert cm.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_model_mix_cli_below_target(tmp_path):
    p = _write(tmp_path, [_completion("sonnet", tid="DAS-1"), _completion("opus", tid="DAS-2")])
    assert cm.main(["--events", str(p), "--target", "0.25"]) == 1


def test_model_mix_cli_meets_target(tmp_path):
    p = _write(tmp_path, [_completion("haiku", tid="DAS-1"), _completion("sonnet", tid="DAS-2")])
    assert cm.main(["--events", str(p), "--target", "0.25"]) == 0


def test_model_mix_excludes_non_success_outcomes():
    # canonical failure is "error" (not "failed"); error/timeout/no_work must NOT count
    for bad in ("error", "timeout", "no_work", "aborted"):
        assert ml.model_mix([_completion("haiku", outcome=bad)]) is None
    # explicit success still counts
    assert ml.model_mix([_completion("haiku", outcome="success")])["total"] == 1


def test_model_mix_dedupes_same_unit():
    # one unit emitting BOTH a run_end and a routing->done must count once
    run_end = {"event_type": "run_end", "ticket_id": "DAS-7", "run_id": "R7",
               "model": "haiku", "created_at": "2026-06-21T10:00:00Z"}
    routed = {"event_type": "routing_decision", "ticket_id": "DAS-7", "run_id": "R7",
              "to_status": "done", "model": "haiku", "created_at": "2026-06-21T10:00:01Z"}
    assert ml.model_mix([run_end, routed])["total"] == 1


# --------------------------------------------------------------------------- #
# T5 recovery
# --------------------------------------------------------------------------- #

def test_recovery_none_when_no_drills():
    assert ml.recovery_reliability([]) is None


def test_recovery_corrupted_not_counted_as_success():
    r = ml.recovery_reliability([_drill(), _drill(corrupted=True)])
    assert r["successful"] == 1 and r["corrupted"] == 1 and r["drills"] == 2


def test_recovery_cli_inert(tmp_path):
    assert crec.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_recovery_cli_corrupted_fails(tmp_path):
    p = _write(tmp_path, [_drill(), _drill(corrupted=True)])
    assert crec.main(["--events", str(p)]) == 1


def test_recovery_cli_perfect_passes(tmp_path):
    p = _write(tmp_path, [_drill() for _ in range(100)])
    assert crec.main(["--events", str(p)]) == 0


# --------------------------------------------------------------------------- #
# T6 review efficiency
# --------------------------------------------------------------------------- #

def test_review_eff_none_when_no_reviews():
    assert ml.review_efficiency([]) is None


def test_review_eff_cycle_and_rework():
    evs = [
        _trans("in_progress", "in_review", 0, "DAS-1"), _trans("in_review", "done", 10, "DAS-1"),
        _trans("in_progress", "in_review", 0, "DAS-2"), _trans("in_review", "in_progress", 5, "DAS-2"),
    ]
    r = ml.review_efficiency(evs)
    assert r["completed"] == 1 and r["reviews"] == 2 and r["rework_rate"] == 0.5
    assert r["median_cycle_s"] == 600.0


def test_review_eff_cli_inert(tmp_path):
    assert crev.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_review_eff_cli_reports_exit_0(tmp_path):
    p = _write(tmp_path, [_trans("in_progress", "in_review", 0), _trans("in_review", "done", 10)])
    assert crev.main(["--events", str(p)]) == 0


def test_review_eff_cli_max_rework_gate(tmp_path):
    p = _write(tmp_path, [_trans("in_progress", "in_review", 0), _trans("in_review", "in_progress", 5)])
    assert crev.main(["--events", str(p), "--max-rework-rate", "0.3"]) == 1


def test_review_blocked_is_not_rework():
    # in_review -> blocked is a dependency block, NOT a quality bounce-back
    evs = [
        _trans("in_progress", "in_review", 0, "DAS-1"), _trans("in_review", "done", 10, "DAS-1"),
        _trans("in_progress", "in_review", 0, "DAS-2"), _trans("in_review", "blocked", 5, "DAS-2"),
    ]
    r = ml.review_efficiency(evs)
    assert r["reviews"] == 1 and r["rework_rate"] == 0.0  # blocked excluded
