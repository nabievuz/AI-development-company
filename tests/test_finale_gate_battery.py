#!/usr/bin/env python3
"""tests/test_finale_gate_battery.py — the FINALE §4-P5 gate-battery aggregator.

These tests drive ``run_battery`` with SEEDED fake gates (cheap ``python3 -c``
subprocesses) so the real, heavy battery (full pytest + kill/fork drills) is
NEVER executed. They verify the aggregate exit-code contract:

    * all gates pass                       -> aggregate rc 0
    * a required gate fails                -> aggregate rc 1
    * an INFORMATIONAL gate fails          -> aggregate rc 0 (never fatal)

plus that ``build_battery()`` (the real list) carries the expected gate names
and marks ``readiness`` informational WITHOUT running any of them, and that
``--list`` mode exits 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finale_gate_battery as fgb  # noqa: E402


def _ok(name: str) -> fgb.Gate:
    """A seeded gate that exits 0 — never touches the real scripts."""
    return fgb.Gate(name, ["python3", "-c", "import sys;sys.exit(0)"])


def _fail(name: str, *, informational: bool = False) -> fgb.Gate:
    """A seeded gate that exits 1."""
    return fgb.Gate(name, ["python3", "-c", "import sys;sys.exit(1)"], informational=informational)


# ---------------------------------------------------------------------------
# Aggregate exit-code contract (seeded gates — the real battery never runs)
# ---------------------------------------------------------------------------


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
    # An informational gate that exits non-zero -> INFO row, aggregate stays 0.
    gates = [_ok("a"), _fail("readiness", informational=True), _ok("c")]
    results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 0
    info = next(r for r in results if r.name == "readiness")
    assert info.status == "INFO"
    assert info.rc == 1
    assert info.informational is True


def test_required_failure_overrides_informational_passes() -> None:
    # Mix: one required fail forces rc 1 even though an informational gate failed too.
    gates = [_ok("a"), _fail("b"), _fail("readiness", informational=True)]
    _results, rc = fgb.run_battery(gates, stream=False)
    assert rc == 1


# ---------------------------------------------------------------------------
# The real battery is inspected as DATA — WITHOUT executing any gate
# ---------------------------------------------------------------------------


def test_build_battery_expected_names_and_readiness_informational() -> None:
    battery = fgb.build_battery()
    names = [g.name for g in battery]
    for expected in ("diagnostics", "board_lint", "evals-enforce", "readiness"):
        assert expected in names, f"missing gate {expected!r}"

    by_name = {g.name: g for g in battery}
    # readiness is the only informational gate, and it must be marked so.
    assert by_name["readiness"].informational is True
    assert [g.name for g in battery if g.informational] == ["readiness"]
    # Every non-readiness gate is a hard/required gate.
    assert all(not g.informational for g in battery if g.name != "readiness")


def test_build_battery_pytest_argv_is_module_invocation() -> None:
    # Pin the exact contract for the two special argvs so a refactor can't drift them.
    by_name = {g.name: g for g in fgb.build_battery()}
    assert by_name["pytest"].argv == ["python3", "-m", "pytest", "-q"]
    assert by_name["readiness"].argv == ["python3", "scripts/check_heartbeat_readiness.py"]


# ---------------------------------------------------------------------------
# CLI — --list must not run the battery and must exit 0
# ---------------------------------------------------------------------------


def test_list_mode_returns_zero() -> None:
    assert fgb.main(["--list"]) == 0


def test_list_json_mode_returns_zero() -> None:
    assert fgb.main(["--list", "--json"]) == 0


# ---------------------------------------------------------------------------
# A hanging gate must FAIL (rc 124), never hang the battery unboundedly
# ---------------------------------------------------------------------------


def _slow(name: str, *, informational: bool = False) -> fgb.Gate:
    """A seeded gate that sleeps longer than the test timeout."""
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
