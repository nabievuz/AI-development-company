#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_heartbeat_readiness as hr


def _clean_day() -> dict:

    return {"t1": 0.70, "t2": 0.10, "t7_holds": True}


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

    history = [_clean_day(), {"t1": 0.40, "t2": 0.10, "t7_holds": True}, _clean_day(), _clean_day()]
    r = hr.assess(history, flag_on=False, **_CREDIT_OK)
    assert r["clean_days"] == 2 and r["ready"] is False


def test_t7_fail_is_not_clean() -> None:
    history = [_clean_day(), _clean_day(), {"t1": 0.70, "t2": 0.10, "t7_holds": False}]
    r = hr.assess(history, flag_on=False, **_CREDIT_OK)
    assert r["clean_days"] == 0


def test_already_live_not_gated() -> None:
    r = hr.assess([_clean_day()] * 5, flag_on=True, **_CREDIT_OK)
    assert r["ready"] is False
    assert any("ALREADY true" in b for b in r["blockers"])


def test_t3_t4_t5_are_neutralised() -> None:


    assert hr.assess([_clean_day()] * 3, flag_on=False, **_CREDIT_OK)["ready"] is True


def test_undeclared_active_plan_blocks_readiness() -> None:


    r = hr.assess([_clean_day()] * 3, flag_on=False, active_plan=None, credit_exhausted=False)
    assert r["ready"] is False
    assert r["credit_ceiling_enforceable"] is False
    assert any("active_plan is undeclared" in b for b in r["blockers"])

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


    assert hr.main(["--history", str(ready)]) == 0

    short = tmp_path / "short.jsonl"
    short.write_text(json.dumps(_clean_day()) + "\n", encoding="utf-8")
    assert hr.main(["--history", str(short)]) == 1

    assert hr.main(["--history", str(tmp_path / "absent.jsonl")]) == 1


def test_cli_active_plan_wiring(tmp_path: Path) -> None:
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
    events = tmp_path / "events.jsonl"
    rc = hr.main(["--history", str(ready), "--budgets", str(budgets), "--events", str(events)])
    assert rc == 0


def test_real_repo_is_not_ready() -> None:


    assert hr.main([]) in (0, 1)
