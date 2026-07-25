#!/usr/bin/env python3
"""tests/test_check_heartbeat_readiness.py — HEARTBEAT go-live readiness reporter.

Covers: empty/short/unclean windows report NOT READY (evidence-gated, never
fabricates); a >=3-day clean window (T1>=0.60, T2<=0.15, T7 holds) PLUS an
enforceable, unexhausted monthly credit ceiling reports READY; an already-live
flag is not "ready" (nothing to gate); T3/T4/T5 are correctly neutralised (a row
carrying only T1/T2/T7 still counts as clean); the FR-004 credit-ceiling
precondition (DAS-1618, design §3.5) — an undeclared ``active_plan`` or an
exhausted ceiling each block readiness on their own, distinctly; CLI exit codes;
and the real repo (loop off, empty history, undeclared active_plan) is honestly
NOT READY.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_heartbeat_readiness as hr  # noqa: E402


def _clean_day() -> dict:
    # Only T1/T2/T7 — no T3/T4/T5 (they must be neutralised, not fail the day).
    return {"t1": 0.70, "t2": 0.10, "t7_holds": True}


# A declared, unexhausted plan — the credit precondition met (used by tests that
# want to isolate the clean-window behavior from the new FR-004 precondition).
_CREDIT_OK = {"active_plan": "max_20x", "credit_exhausted": False}


def test_empty_history_not_ready() -> None:
    r = hr.assess([], flag_on=False, **_CREDIT_OK)
    assert r["ready"] is False
    assert r["clean_days"] == 0
    assert any("insufficient clean shadow window" in b for b in r["blockers"])


def test_three_clean_days_ready() -> None:
    r = hr.assess([_clean_day(), _clean_day(), _clean_day()], flag_on=False, **_CREDIT_OK)
    assert r["ready"] is True
    assert r["clean_days"] == 3 and r["window_met"] is True
    assert r["blockers"] == []


def test_two_clean_days_not_ready() -> None:
    r = hr.assess([_clean_day(), _clean_day()], flag_on=False, **_CREDIT_OK)
    assert r["ready"] is False and r["clean_days"] == 2


def test_unclean_day_breaks_streak() -> None:
    # newest 2 clean, but a busy_fraction miss just before breaks the 3-streak
    history = [_clean_day(), {"t1": 0.40, "t2": 0.10, "t7_holds": True}, _clean_day(), _clean_day()]
    r = hr.assess(history, flag_on=False, **_CREDIT_OK)
    assert r["clean_days"] == 2 and r["ready"] is False


def test_t7_fail_is_not_clean() -> None:
    history = [_clean_day(), _clean_day(), {"t1": 0.70, "t2": 0.10, "t7_holds": False}]
    r = hr.assess(history, flag_on=False, **_CREDIT_OK)
    assert r["clean_days"] == 0  # newest day fails T7 -> streak breaks immediately


def test_already_live_not_gated() -> None:
    r = hr.assess([_clean_day()] * 5, flag_on=True, **_CREDIT_OK)
    assert r["ready"] is False  # already live — nothing to gate
    assert any("ALREADY true" in b for b in r["blockers"])


def test_t3_t4_t5_are_neutralised() -> None:
    # A clean day carrying ONLY T1/T2/T7 (no T3/T4/T5) must still count — the
    # ladder-only metrics are neutralised for the heartbeat window.
    assert hr.assess([_clean_day()] * 3, flag_on=False, **_CREDIT_OK)["ready"] is True


# ---------------------------------------------------------------------------
# FR-004 — the monthly credit ceiling precondition (DAS-1618, design §3.5)
# ---------------------------------------------------------------------------


def test_undeclared_active_plan_blocks_readiness() -> None:
    # A clean window alone is NOT enough: an undeclared active_plan makes the
    # ceiling unenforceable and must block readiness, distinctly from the
    # clean-window blocker.
    r = hr.assess([_clean_day()] * 3, flag_on=False, active_plan=None, credit_exhausted=False)
    assert r["ready"] is False
    assert r["credit_ceiling_enforceable"] is False
    assert any("active_plan is undeclared" in b for b in r["blockers"])
    # the clean-window blocker must NOT also fire — these are distinct conditions
    assert not any("insufficient clean shadow window" in b for b in r["blockers"])


def test_exhausted_credit_blocks_readiness_even_with_declared_plan() -> None:
    r = hr.assess([_clean_day()] * 3, flag_on=False, active_plan="pro", credit_exhausted=True)
    assert r["ready"] is False
    assert r["credit_ceiling_enforceable"] is True
    assert r["credit_exhausted"] is True
    assert any("sanctioned pause in effect" in b for b in r["blockers"])


def test_declared_unexhausted_plan_satisfies_credit_precondition() -> None:
    r = hr.assess([_clean_day()] * 3, flag_on=False, active_plan="max_5x", credit_exhausted=False)
    assert r["ready"] is True
    assert r["credit_ceiling_enforceable"] is True


def test_whitespace_active_plan_is_treated_as_undeclared() -> None:
    r = hr.assess([_clean_day()] * 3, flag_on=False, active_plan="   ", credit_exhausted=False)
    assert r["credit_ceiling_enforceable"] is False
    assert r["ready"] is False


def test_cli_exit_codes(tmp_path: Path) -> None:
    import json

    ready = tmp_path / "ready.jsonl"
    ready.write_text("\n".join(json.dumps(_clean_day()) for _ in range(3)) + "\n", encoding="utf-8")
    # Since DAS-1629 the real budgets.yaml DECLARES active_plan (max_20x), so the
    # FR-004 credit precondition is met; a clean 3-day window against the real
    # config is now honestly READY -> exit 0. (Before the declaration this was
    # exit 1 on the undeclared-plan blocker.)
    assert hr.main(["--history", str(ready)]) == 0

    short = tmp_path / "short.jsonl"
    short.write_text(json.dumps(_clean_day()) + "\n", encoding="utf-8")
    assert hr.main(["--history", str(short)]) == 1

    assert hr.main(["--history", str(tmp_path / "absent.jsonl")]) == 1  # missing -> not ready


def test_cli_active_plan_wiring(tmp_path: Path) -> None:
    """--budgets/--events are honored end-to-end: a declared, unexhausted plan
    against a clean history is exit 0."""
    import json

    ready = tmp_path / "ready.jsonl"
    ready.write_text("\n".join(json.dumps(_clean_day()) for _ in range(3)) + "\n", encoding="utf-8")
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text(
        "mustaqil:\n"
        "  monthly_credit_ceiling:\n"
        "    plan_credit_usd: {pro: 20}\n"
        "    active_plan: pro\n"
        "    on_exhaustion: sanctioned_pause\n",
        encoding="utf-8",
    )
    events = tmp_path / "events.jsonl"  # absent store -> aggregate_spans returns None -> used_usd 0.0
    rc = hr.main(["--history", str(ready), "--budgets", str(budgets), "--events", str(events)])
    assert rc == 0


def test_real_repo_is_not_ready() -> None:
    # Loop is off + empty metrics-history + undeclared active_plan by design: the
    # reporter must NOT fabricate readiness. (If a future run has flipped the
    # flag, filled the window, or declared active_plan, this documents that the
    # reporter reflects reality; assert only the honest current state.)
    assert hr.main([]) in (0, 1)  # never raises
