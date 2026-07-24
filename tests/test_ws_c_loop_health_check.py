"""WS-C loop/sandbox Maintenance health/eval tests (ADR-0035 GATE-6 / DAS-1569).

Covers ``scripts/ws_c_loop_health_check.py``: board-canonical (checkpoint
never a tiebreaker) drift, sandbox fail-closed-wall drift, import-ban
carve-out drift, and the Maintenance-schedule registration
(``scripts/stage_gate.py:maintenance_schedule()``).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses (stage_gate.py) need self in sys.modules
    spec.loader.exec_module(mod)
    return mod


def _load_health_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return _load("scripts/ws_c_loop_health_check.py", "_ws_c_loop_health_check")


# --------------------------------------------------------------------------- #
# run() end-to-end on the real repo
# --------------------------------------------------------------------------- #


def test_healthy_repo_reports_no_drift():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["board_canonical_drift"]["ok"] is True
    assert result["checks"]["sandbox_wall_drift"]["ok"] is True
    assert result["checks"]["import_ban_carveout_drift"]["ok"] is True


# --------------------------------------------------------------------------- #
# 1. Board-canonical drift
# --------------------------------------------------------------------------- #


def test_board_canonical_drift_ok_board_wins():
    mod = _load_health_check()
    result = mod.check_board_canonical_drift()
    assert result["ok"] is True
    assert "board value" in result["detail"]


def test_board_canonical_drift_flags_checkpoint_winning(monkeypatch):
    mod = _load_health_check()
    ll = mod._load_langgraph_loop()

    def _checkpoint_wins(projected, board_state):
        # Simulate a regression: the checkpoint/projection value is returned
        # instead of the board value — exactly the LG-1/§1.3 violation this
        # check exists to catch.
        bogus = ll.GraphState(ticket_id=board_state.ticket_id, dept=projected.channels["identity"]["dept"])
        return ll.Reconciliation(board_state=bogus, diverged=[("identity", "dept")], event={"rule": "board_wins_reconciliation"})

    monkeypatch.setattr(ll, "reconcile", _checkpoint_wins)
    monkeypatch.setattr(mod, "_load_langgraph_loop", lambda: ll)
    result = mod.check_board_canonical_drift()
    assert result["ok"] is False
    assert "checkpoint" in result["detail"] or "won instead" in result["detail"]


def test_board_canonical_drift_flags_undetected_divergence(monkeypatch):
    mod = _load_health_check()
    ll = mod._load_langgraph_loop()

    def _no_divergence_detected(projected, board_state):
        return ll.Reconciliation(board_state=board_state, diverged=[], event=None)

    monkeypatch.setattr(ll, "reconcile", _no_divergence_detected)
    monkeypatch.setattr(mod, "_load_langgraph_loop", lambda: ll)
    result = mod.check_board_canonical_drift()
    assert result["ok"] is False
    assert "did not detect" in result["detail"]


def test_board_canonical_drift_flags_missing_reconciliation_event(monkeypatch):
    mod = _load_health_check()
    ll = mod._load_langgraph_loop()

    def _no_event(projected, board_state):
        return ll.Reconciliation(board_state=board_state, diverged=[("identity", "dept")], event=None)

    monkeypatch.setattr(ll, "reconcile", _no_event)
    monkeypatch.setattr(mod, "_load_langgraph_loop", lambda: ll)
    result = mod.check_board_canonical_drift()
    assert result["ok"] is False
    assert "event" in result["detail"]


# --------------------------------------------------------------------------- #
# 2. Sandbox-wall drift
# --------------------------------------------------------------------------- #


def test_sandbox_wall_drift_ok_all_walls_deny():
    mod = _load_health_check()
    result = mod.check_sandbox_wall_drift()
    assert result["ok"] is True
    assert "four fail-closed walls still deny" in result["detail"]


def test_sandbox_wall_drift_flags_a_host_escape_that_is_allowed(monkeypatch):
    mod = _load_health_check()
    contract, local_stub = mod._load_sandbox_stub()

    class _LeakySandbox(local_stub.LocalStubSandbox):
        def exec(self, handle, argv):
            if argv and argv[0] == "read":
                return contract.ExecResult(ok=True, exit_code=0, stdout="leaked")
            return super().exec(handle, argv)

    monkeypatch.setattr(local_stub, "LocalStubSandbox", _LeakySandbox)
    monkeypatch.setattr(mod, "_load_sandbox_stub", lambda: (contract, local_stub))
    result = mod.check_sandbox_wall_drift()
    assert result["ok"] is False
    assert "host-escape wall" in result["detail"]


def test_sandbox_wall_drift_flags_cross_task_allowed(monkeypatch):
    mod = _load_health_check()
    contract, local_stub = mod._load_sandbox_stub()

    class _CrossTaskLeak(local_stub.LocalStubSandbox):
        def exec(self, handle, argv):
            if handle.task_id == "ws-c-health-other-task":
                return contract.ExecResult(ok=True, exit_code=0, stdout="leaked")
            return super().exec(handle, argv)

    monkeypatch.setattr(local_stub, "LocalStubSandbox", _CrossTaskLeak)
    monkeypatch.setattr(mod, "_load_sandbox_stub", lambda: (contract, local_stub))
    result = mod.check_sandbox_wall_drift()
    assert result["ok"] is False
    assert "cross-task wall" in result["detail"]


def test_sandbox_wall_drift_flags_unscoped_credential_allowed(monkeypatch):
    mod = _load_health_check()
    contract, local_stub = mod._load_sandbox_stub()
    real_open = local_stub.LocalStubSandbox.open

    class _CredLeak(local_stub.LocalStubSandbox):
        def open(self, *, task_id, scope):
            # Regression simulation: strip the mis-scoped credential before
            # delegating, so the real wall never sees it and never raises.
            safe_scope = contract.SandboxScope(
                task_id=scope.task_id,
                workdir_mounts=scope.workdir_mounts,
                egress_profile=scope.egress_profile,
                credentials=[],
                resource_limits=scope.resource_limits,
                egress_allowlist=scope.egress_allowlist,
            )
            return real_open(self, task_id=task_id, scope=safe_scope)

    monkeypatch.setattr(local_stub, "LocalStubSandbox", _CredLeak)
    monkeypatch.setattr(mod, "_load_sandbox_stub", lambda: (contract, local_stub))
    result = mod.check_sandbox_wall_drift()
    assert result["ok"] is False
    assert "unscoped-credential wall" in result["detail"]


def test_sandbox_wall_drift_flags_egress_allowed(monkeypatch):
    mod = _load_health_check()
    contract, local_stub = mod._load_sandbox_stub()

    class _EgressLeak(local_stub.LocalStubSandbox):
        def exec(self, handle, argv):
            if argv and argv[0] == "net":
                return contract.ExecResult(ok=True, exit_code=0, stdout="leaked egress")
            return super().exec(handle, argv)

    monkeypatch.setattr(local_stub, "LocalStubSandbox", _EgressLeak)
    monkeypatch.setattr(mod, "_load_sandbox_stub", lambda: (contract, local_stub))
    result = mod.check_sandbox_wall_drift()
    assert result["ok"] is False
    assert "egress wall" in result["detail"]


# --------------------------------------------------------------------------- #
# 3. Import-ban carve-out drift
# --------------------------------------------------------------------------- #


def test_import_ban_carveout_drift_ok_on_the_real_repo():
    mod = _load_health_check()
    result = mod.check_import_ban_carveout_drift()
    assert result["ok"] is True
    assert "scripts/dgox/" in result["detail"]


def test_import_ban_carveout_drift_flags_a_widened_path(monkeypatch):
    mod = _load_health_check()
    cib = mod._load_import_ban()
    monkeypatch.setattr(cib, "SANCTIONED_IMPORT_PATHS", [("langgraph", "scripts/dgox/"), ("langgraph", "scripts/")])
    monkeypatch.setattr(mod, "_load_import_ban", lambda: cib)
    result = mod.check_import_ban_carveout_drift()
    assert result["ok"] is False
    assert "widened" in result["detail"]


def test_import_ban_carveout_drift_flags_another_lib_getting_a_carveout(monkeypatch):
    mod = _load_health_check()
    cib = mod._load_import_ban()
    monkeypatch.setattr(cib, "SANCTIONED_IMPORT_PATHS", [("langgraph", "scripts/dgox/"), ("crewai", "scripts/dgox/")])
    monkeypatch.setattr(mod, "_load_import_ban", lambda: cib)
    result = mod.check_import_ban_carveout_drift()
    assert result["ok"] is False
    assert "no donor lib besides langgraph" in result["detail"] or "widened" in result["detail"]


def test_import_ban_carveout_drift_flags_a_shrunk_banned_list(monkeypatch):
    mod = _load_health_check()
    cib = mod._load_import_ban()
    monkeypatch.setattr(cib, "BANNED", [("langgraph", ["langgraph"])])
    monkeypatch.setattr(mod, "_load_import_ban", lambda: cib)
    result = mod.check_import_ban_carveout_drift()
    assert result["ok"] is False
    assert "BANNED lib set" in result["detail"]


def test_import_ban_carveout_drift_flags_a_live_violation(monkeypatch):
    mod = _load_health_check()
    cib = mod._load_import_ban()
    monkeypatch.setattr(cib, "check", lambda root: ["scripts/rogue.py:1: banned import 'crewai' (found 'import crewai')"])
    monkeypatch.setattr(mod, "_load_import_ban", lambda: cib)
    result = mod.check_import_ban_carveout_drift()
    assert result["ok"] is False
    assert "violation" in result["detail"]


# --------------------------------------------------------------------------- #
# CLI + Maintenance-schedule registration
# --------------------------------------------------------------------------- #


def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_c_loop_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_c_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_c_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-c-loop-health" in names
    entry = names["ws-c-loop-health"]
    assert entry["command"] == ["python3", "scripts/ws_c_loop_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
