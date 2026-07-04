#!/usr/bin/env python3
"""tests/test_loop_controller.py — self-optimization loop promotion controller (RFC-001 §5).

The load-bearing safety properties: promotions never skip a rung, require >=1 week
clean live evidence AND a human-approved GATE-6 record, and the controller NEVER
mutates loop.yaml (it only reports / drafts).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import loop_controller as lc  # noqa: E402  (import after path manipulation)

T = lc.DEFAULT_TARGETS


def _clean_day():
    return {"t1": 0.65, "t2": 0.10, "t3": 7, "t4": 0.30, "t5": 0.999, "t7_holds": True}


def _approved_record(frm="shadow", to="measured", approver="founder"):
    return {"gate_6_record": {
        "change_type": "capability_promotion",
        "proposed_change": {"from_mode": frm, "to_mode": to},
        "guardrails": {"max_quality_drop": 0},
        "approval": {"approved_by": approver},
    }}


# --------------------------------------------------------------------------- #
# Ladder — one rung at a time, never skip
# --------------------------------------------------------------------------- #

def test_ladder_one_rung():
    assert lc.next_mode("shadow") == "measured"
    assert lc.next_mode("measured") == "limited_live"
    assert lc.next_mode("limited_live") == "full"
    assert lc.next_mode("full") is None
    assert lc.next_mode("bogus") is None


# --------------------------------------------------------------------------- #
# Clean-live-days evidence
# --------------------------------------------------------------------------- #

def test_clean_days_counts_trailing_streak():
    history = [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(7)]
    assert lc.clean_live_days(history, T) == 7


def test_a_bad_day_breaks_the_streak():
    history = [_clean_day() for _ in range(5)] + [{"t1": 0.1, "t7_holds": False}] + [_clean_day() for _ in range(2)]
    assert lc.clean_live_days(history, T) == 2  # only the trailing clean days


def test_day_not_clean_if_t7_drops():
    day = dict(_clean_day(), t7_holds=False)
    assert lc.day_is_clean(day, T) is False


# --------------------------------------------------------------------------- #
# Approved promotion record
# --------------------------------------------------------------------------- #

def test_approved_record_required():
    assert lc.has_approved_promotion_record([_approved_record()], "shadow", "measured") is True


def test_unapproved_record_does_not_count():
    rec = _approved_record(approver="")  # no human sign-off
    assert lc.has_approved_promotion_record([rec], "shadow", "measured") is False


def test_wrong_rung_record_does_not_count():
    assert lc.has_approved_promotion_record([_approved_record(to="full")], "shadow", "measured") is False


# --------------------------------------------------------------------------- #
# evaluate_promotion — the safety gate
# --------------------------------------------------------------------------- #

def test_not_eligible_with_no_evidence():
    r = lc.evaluate_promotion("shadow", [], [], T)
    assert r["eligible"] is False
    assert len(r["blockers"]) == 2  # insufficient evidence + no approved record


def test_not_eligible_with_clean_days_but_no_record():
    r = lc.evaluate_promotion("shadow", [], [_clean_day() for _ in range(7)], T)
    assert r["eligible"] is False
    assert any("no human-approved" in b for b in r["blockers"])


def test_not_eligible_with_record_but_insufficient_days():
    r = lc.evaluate_promotion("shadow", [_approved_record()], [_clean_day() for _ in range(3)], T)
    assert r["eligible"] is False
    assert any("insufficient clean live evidence" in b for b in r["blockers"])


def test_eligible_only_with_both():
    r = lc.evaluate_promotion("shadow", [_approved_record()], [_clean_day() for _ in range(7)], T)
    assert r["eligible"] is True and r["target"] == "measured"


def test_full_mode_not_eligible():
    r = lc.evaluate_promotion("full", [], [_clean_day() for _ in range(30)], T)
    assert r["eligible"] is False and any("already at 'full'" in b for b in r["blockers"])


# --------------------------------------------------------------------------- #
# Draft is unapproved; controller never mutates
# --------------------------------------------------------------------------- #

def test_promotion_draft_is_unapproved():
    rec = lc.promotion_draft("shadow", "measured", "2026-06-22T00:00:00Z")["gate_6_record"]
    assert rec["approval"]["approved_by"] == ""
    assert rec["guardrails"]["max_quality_drop"] == 0
    assert rec["rollout"]["mode"] == "shadow"


def test_cli_inert_loop_stays_shadow():
    # real shadow config + no live data -> not eligible -> exit 0, loop unchanged
    assert lc.main([]) == 0


def test_cli_does_not_mutate_loop_config():
    before = (REPO_ROOT / "config" / "loop.yaml").read_text()
    lc.main(["--propose"])
    assert (REPO_ROOT / "config" / "loop.yaml").read_text() == before  # never mutated


# --------------------------------------------------------------------------- #
# Robustness hardening (review nits)
# --------------------------------------------------------------------------- #

def test_whitespace_approver_rejected():
    assert lc.has_approved_promotion_record([_approved_record(approver="   ")], "shadow", "measured") is False


def test_day_is_clean_non_dict_is_false():
    assert lc.day_is_clean(None, T) is False
    assert lc.clean_live_days([None, "x"], T) == 0


def test_unreadable_experiment_does_not_crash(tmp_path):
    exp = tmp_path / "experiments"
    exp.mkdir()
    (exp / "bad.yaml").mkdir()  # a directory named like a record -> read raises OSError
    assert lc._load_records(exp) == []
    rc = lc.main(["--loop-config", str(REPO_ROOT / "config" / "loop.yaml"),
                  "--experiments", str(exp), "--metrics-history", str(tmp_path / "nope.jsonl")])
    assert rc == 0
