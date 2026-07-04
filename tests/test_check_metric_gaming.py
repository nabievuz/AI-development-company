#!/usr/bin/env python3
"""tests/test_check_metric_gaming.py — anti-gaming rule + T1b (R-9 / RFC-001 §2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_metric_gaming as cmg  # noqa: E402  (import after path manipulation)
import metrics_lib as ml  # noqa: E402


def _done(merged_pr="PR-1", ci_status="green", t7_pass=True, t7_score=0.95, tid="DAS-1") -> dict:
    return {
        "event_type": "routing_decision", "ticket_id": tid, "to_status": "done",
        "merged_pr": merged_pr, "ci_status": ci_status, "t7_pass": t7_pass,
        "t7_score": t7_score, "created_at": "2026-06-21T10:00:00Z",
    }


def _write(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


def test_gaming_none_when_no_completions():
    assert ml.gaming_violations([]) is None


def test_clean_completion_no_violation():
    assert ml.gaming_violations([_done()])["violations"] == []


def test_missing_merged_pr_flagged():
    assert ml.gaming_violations([_done(merged_pr=None)])["violations"]


def test_missing_green_ci_flagged():
    assert ml.gaming_violations([_done(ci_status="red")])["violations"]


def test_missing_t7_pass_flagged():
    assert ml.gaming_violations([_done(t7_pass=False)])["violations"]


def test_t1b_high_impact_rate():
    evs = [_done(t7_score=0.95), _done(t7_score=0.80, tid="DAS-2")]
    t1b = ml.t1b_high_impact(evs)
    assert t1b["high_impact"] == 1 and t1b["rate"] == 0.5


def test_cli_inert(tmp_path):
    assert cmg.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_cli_clean_exit_0(tmp_path):
    assert cmg.main(["--events", str(_write(tmp_path, [_done()]))]) == 0


def test_cli_gamed_exit_1(tmp_path):
    assert cmg.main(["--events", str(_write(tmp_path, [_done(merged_pr=None)]))]) == 1


def test_string_false_t7_pass_is_flagged():
    # a STRING 'false' is Python-truthy but must NOT pass the gate
    assert ml.gaming_violations([_done(t7_pass="false")])["violations"]
    assert ml.t1b_high_impact([_done(t7_pass="false")])["high_impact"] == 0


def test_all_missing_evidence_reported_together():
    v = ml.gaming_violations([_done(merged_pr=None, ci_status="red", t7_pass=False)])["violations"]
    assert len(v) == 1
    assert "no merged PR" in v[0] and "no green CI" in v[0] and "no T7 pass" in v[0]
