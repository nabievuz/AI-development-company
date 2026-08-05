#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finale_gate_battery as fgb


def _ok(name: str) -> fgb.Gate:
    return fgb.Gate(name, ["python3", "-c", "import sys;sys.exit(0)"])


def _fail(name: str, *, informational: bool = False) -> fgb.Gate:
    return fgb.Gate(name, ["python3", "-c", "import sys;sys.exit(1)"], informational=informational)


def test_all_passing_gates_aggregate_zero() -> None:
    gates = [_ok("a"), _ok("b"), _ok("c")]
    results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 0
    assert [r.status for r in results] == ["PASS", "PASS", "PASS"]
    assert all(r.rc == 0 for r in results)


def test_failing_required_gate_aggregate_one() -> None:
    gates = [_ok("a"), _fail("b"), _ok("c")]
    results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 1
    statuses = {r.name: r.status for r in results}
    assert statuses == {"a": "PASS", "b": "FAIL", "c": "PASS"}


def test_informational_failure_does_not_fail_battery() -> None:

    gates = [_ok("a"), _fail("readiness", informational=True), _ok("c")]
    results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 0
    info = next(r for r in results if r.name == "readiness")
    assert info.status == "INFO"
    assert info.rc == 1
    assert info.informational is True


def test_required_failure_overrides_informational_passes() -> None:

    gates = [_ok("a"), _fail("b"), _fail("readiness", informational=True)]
    _results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 1


def test_build_battery_expected_names_and_readiness_informational() -> None:
    battery = fgb.build_battery()
    names = [g.name for g in battery]
    for expected in ("diagnostics", "board_lint", "evals-enforce", "readiness"):
        assert expected in names, f"missing gate {expected!r}"

    by_name = {g.name: g for g in battery}

    assert by_name["readiness"].informational is True
    assert [g.name for g in battery if g.informational] == ["readiness"]

    assert all(not g.informational for g in battery if g.name != "readiness")


def test_build_battery_pytest_argv_is_module_invocation() -> None:

    by_name = {g.name: g for g in fgb.build_battery()}
    assert by_name["pytest"].argv == ["python3", "-m", "pytest", "-q"]
    assert by_name["readiness"].argv == ["python3", "scripts/check_heartbeat_readiness.py"]


def test_list_mode_returns_zero() -> None:
    assert fgb.main(["--list"]) == 0


def test_list_json_mode_returns_zero() -> None:
    assert fgb.main(["--list", "--json"]) == 0


def _slow(name: str, *, informational: bool = False) -> fgb.Gate:
    return fgb.Gate(name, ["python3", "-c", "import time;time.sleep(30)"], informational=informational)


def test_hanging_required_gate_times_out_as_fail() -> None:
    results, rc = fgb.run_battery([_ok("a"), _slow("stuck")], stream=False, timeout=0.5)
    assert rc == 1
    stuck = next(r for r in results if r.name == "stuck")
    assert stuck.status == "FAIL"
    assert stuck.rc == 124
    assert "timed out" in stuck.tail


def test_hanging_informational_gate_times_out_without_failing_battery() -> None:
    results, rc = fgb.run_battery([_ok("a"), _slow("readiness", informational=True)], stream=False, timeout=0.5)
    assert rc == 0
    info = next(r for r in results if r.name == "readiness")
    assert info.status == "INFO"
    assert info.rc == 124
