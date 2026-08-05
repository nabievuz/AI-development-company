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
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_health_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return _load("scripts/ws_e_health_check.py", "_ws_e_health_check")


def test_healthy_repo_reports_no_findings():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["rbac_drift"]["ok"] is True
    assert result["checks"]["gateway_host_pin_drift"]["ok"] is True
    assert result["checks"]["in_tenant_drift"]["ok"] is True
    assert result["checks"]["guardrail_eval_drift"]["ok"] is True


def test_rbac_drift_flags_an_agent_granted_gate_approve(monkeypatch):
    mod = _load_health_check()
    tampered = {
        "founder": {"gate.approve": "allow", "config.edit.security": "allow"},
        "agent": {"gate.approve": "allow"},
    }
    rbac = mod._rbac_mod()
    monkeypatch.setattr(rbac, "load_grants", lambda path: tampered)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "was NOT denied" in result["detail"] or "carries founder-only" in result["detail"]


def test_rbac_drift_flags_founder_missing_a_founder_only_permission(monkeypatch):
    mod = _load_health_check()
    tampered = {"founder": {"gate.approve": "allow"}}
    rbac = mod._rbac_mod()
    monkeypatch.setattr(rbac, "load_grants", lambda path: tampered)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "config.edit.security" in result["detail"]


def test_rbac_drift_surfaces_a_structurally_invalid_config(monkeypatch, tmp_path):
    mod = _load_health_check()
    bad = tmp_path / "rbac.yaml"
    bad.write_text("grants:\n  agent:\n    gate.approve: allow\n", encoding="utf-8")
    monkeypatch.setattr(mod, "RBAC_CONFIG_PATH", bad)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "structurally invalid" in result["detail"]


def test_rbac_drift_ok_on_the_real_tracked_config():
    mod = _load_health_check()
    result = mod.check_rbac_drift()
    assert result["ok"] is True


def test_gateway_host_pin_drift_flags_a_regression_that_stops_pinning(monkeypatch):
    mod = _load_health_check()

    class _AlwaysAcceptGateway:
        class GatewayConfigError(Exception):
            pass

        @staticmethod
        def ModelRoute(**kwargs):
            return kwargs

        @staticmethod
        def enforce_boundary(route):
            return None

    monkeypatch.setattr(mod, "_gateway_mod", lambda: _AlwaysAcceptGateway())
    result = mod.check_gateway_host_pin_drift()
    assert result["ok"] is False
    assert "ACCEPTED" in result["detail"]


def test_gateway_host_pin_drift_ok_on_the_real_gateway():
    mod = _load_health_check()
    result = mod.check_gateway_host_pin_drift()
    assert result["ok"] is True


def test_in_tenant_drift_flags_a_hosted_endpoint(monkeypatch, tmp_path):
    mod = _load_health_check()
    tampered = tmp_path / "tenant_boundary.yaml"
    tampered.write_text(
        "accepted_external_roles: [model]\n"
        "endpoints:\n"
        "  - name: rogue\n"
        "    role: sandbox\n"
        "    carries_code_ip: true\n"
        "    url: https://sandbox.example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "TENANT_BOUNDARY_PATH", tampered)
    result = mod.check_in_tenant_drift()
    assert result["ok"] is False
    assert "EXTERNAL" in result["detail"]


def test_in_tenant_drift_flags_a_missing_config(monkeypatch, tmp_path):
    mod = _load_health_check()
    monkeypatch.setattr(mod, "TENANT_BOUNDARY_PATH", tmp_path / "does-not-exist.yaml")
    result = mod.check_in_tenant_drift()
    assert result["ok"] is False
    assert "missing" in result["detail"]


def test_in_tenant_drift_ok_on_the_real_tracked_config():
    mod = _load_health_check()
    result = mod.check_in_tenant_drift()
    assert result["ok"] is True


def test_guardrail_eval_drift_flags_a_redaction_miss(monkeypatch):
    mod = _load_health_check()
    chain = mod._guardrail_chain_mod()

    class _Passthrough:
        denied = False
        action = "redact"
        output_text = mod._GUARDRAIL_PROBE_TEXT
        reason = ""

    monkeypatch.setattr(chain, "guard", lambda *a, **k: _Passthrough())
    result = mod.check_guardrail_eval_drift()
    assert result["ok"] is False
    assert "redaction miss" in result["detail"]


def test_guardrail_eval_drift_flags_a_denied_probe(monkeypatch):
    mod = _load_health_check()
    chain = mod._guardrail_chain_mod()

    class _Denied:
        denied = True
        action = "deny"
        output_text = None
        reason = "role not admitted"

    monkeypatch.setattr(chain, "guard", lambda *a, **k: _Denied())
    result = mod.check_guardrail_eval_drift()
    assert result["ok"] is False
    assert "did not run cleanly" in result["detail"]


def test_guardrail_eval_drift_flags_a_clean_fixture_regression(monkeypatch):
    mod = _load_health_check()
    runner = mod._golden_runner_mod()

    class _RedResult:
        judge_eligible = False

    orig_run = runner.run_golden_set
    monkeypatch.setattr(runner, "run_golden_set", lambda path: _RedResult())
    try:
        result = mod.check_guardrail_eval_drift()
    finally:
        monkeypatch.setattr(runner, "run_golden_set", orig_run)
    assert result["ok"] is False
    assert "clean golden-set" in result["detail"]


def test_guardrail_eval_drift_flags_a_false_green_on_the_gaming_fixture(monkeypatch):
    mod = _load_health_check()
    runner = mod._golden_runner_mod()

    def _fake_run(path):
        class _R:
            judge_eligible = True

        return _R()

    monkeypatch.setattr(runner, "run_golden_set", _fake_run)
    result = mod.check_guardrail_eval_drift()
    assert result["ok"] is False
    assert "false green" in result["detail"]


def test_guardrail_eval_drift_ok_on_the_real_chain_and_golden_set():
    mod = _load_health_check()
    result = mod.check_guardrail_eval_drift()
    assert result["ok"] is True


def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_e_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_e_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_e_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-e-tenant-health" in names
    entry = names["ws-e-tenant-health"]
    assert entry["command"] == ["python3", "scripts/ws_e_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
