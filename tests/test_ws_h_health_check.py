"""WS-H CONTROL Maintenance health/eval tests (GATE-6 / DAS-1605).

Covers ``scripts/ws_h_health_check.py``: the RBAC-drift probe, the
audit-redaction-drift probe, the degrade/flag-drift probe, the
token-compare-drift probe, and the Maintenance-schedule registration
(``scripts/stage_gate.py: maintenance_schedule()``).
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
    sys.modules[name] = mod  # dataclasses need self in sys.modules before exec
    spec.loader.exec_module(mod)
    return mod


def _load_health_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return _load("scripts/ws_h_health_check.py", "_ws_h_health_check")


def test_healthy_repo_reports_no_findings():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["rbac_drift"]["ok"] is True
    assert result["checks"]["audit_redaction_drift"]["ok"] is True
    assert result["checks"]["degrade_flag_drift"]["ok"] is True
    assert result["checks"]["token_compare_drift"]["ok"] is True


# --------------------------------------------------------------------------- #
# 1. RBAC drift
# --------------------------------------------------------------------------- #

def test_rbac_drift_flags_an_agent_granted_gate_approve(monkeypatch):
    mod = _load_health_check()
    tampered = {
        "founder": {"gate.approve": "allow", "run.trigger": "allow"},
        "agent": {"gate.approve": "allow"},  # simulated tamper — never legal in real rbac.yaml
    }
    rbac = mod._rbac_mod()
    monkeypatch.setattr(rbac, "load_grants", lambda path: tampered)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "was NOT denied" in result["detail"] or "carries founder-only" in result["detail"]


def test_rbac_drift_flags_an_agent_granted_run_trigger(monkeypatch):
    mod = _load_health_check()
    tampered = {
        "founder": {"gate.approve": "allow", "run.trigger": "allow"},
        "orchestrator": {"run.trigger": "allow"},  # simulated tamper
    }
    rbac = mod._rbac_mod()
    monkeypatch.setattr(rbac, "load_grants", lambda path: tampered)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "run.trigger" in result["detail"]


def test_rbac_drift_flags_founder_missing_a_founder_only_permission(monkeypatch):
    mod = _load_health_check()
    tampered = {"founder": {"gate.approve": "allow"}}  # run.trigger silently dropped
    rbac = mod._rbac_mod()
    monkeypatch.setattr(rbac, "load_grants", lambda path: tampered)
    result = mod.check_rbac_drift()
    assert result["ok"] is False
    assert "run.trigger" in result["detail"]


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


# --------------------------------------------------------------------------- #
# 2. Audit-redaction drift
# --------------------------------------------------------------------------- #

def test_audit_redaction_drift_flags_a_raw_secret_passthrough(monkeypatch):
    mod = _load_health_check()

    class _NoOpRedaction:
        @staticmethod
        def safe_scrub(value):
            return str(value)  # simulates a scrubber regressed to a no-op

    monkeypatch.setattr(mod, "_redaction_mod", lambda: _NoOpRedaction())
    result = mod.check_audit_redaction_drift()
    assert result["ok"] is False
    assert "survive raw" in result["detail"] or "no-op" in result["detail"]


def test_audit_redaction_drift_ok_on_the_real_scrubber():
    mod = _load_health_check()
    result = mod.check_audit_redaction_drift()
    assert result["ok"] is True


# --------------------------------------------------------------------------- #
# 3. Degrade / flag drift
# --------------------------------------------------------------------------- #

def test_degrade_flag_drift_flags_flag_on_by_default(monkeypatch, tmp_path):
    mod = _load_health_check()
    on_features = tmp_path / "features.yaml"
    on_features.write_text("ws_h_control_plane: true\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", on_features)
    result = mod.check_degrade_flag_drift()
    assert result["ok"] is False
    assert "expected default OFF" in result["detail"]


def test_degrade_flag_drift_flags_resolve_surface_regression(monkeypatch):
    mod = _load_health_check()

    class _AlwaysControlPlane:
        @staticmethod
        def resolve_surface(*, features_path=None, force_static=False):
            class _Decision:
                mode = "control-plane"
                reason = "simulated regression"

            return _Decision()

    monkeypatch.setattr(mod, "_degrade_mod", lambda: _AlwaysControlPlane())
    result = mod.check_degrade_flag_drift()
    assert result["ok"] is False
    assert "control-plane" in result["detail"]


def test_degrade_flag_drift_flags_force_static_regression(monkeypatch):
    mod = _load_health_check()

    class _Decision:
        def __init__(self, mode):
            self.mode = mode
            self.reason = "simulated"

    class _ForceStaticBroken:
        @staticmethod
        def resolve_surface(*, features_path=None, force_static=False):
            return _Decision("static" if not force_static else "control-plane")

    monkeypatch.setattr(mod, "_degrade_mod", lambda: _ForceStaticBroken())
    result = mod.check_degrade_flag_drift()
    assert result["ok"] is False
    assert "--force-static regression" in result["detail"]


def test_degrade_flag_drift_ok_on_the_real_tracked_config():
    mod = _load_health_check()
    result = mod.check_degrade_flag_drift()
    assert result["ok"] is True


# --------------------------------------------------------------------------- #
# 4. Token-compare drift
# --------------------------------------------------------------------------- #

def test_token_compare_drift_flags_a_missing_match_token_function(monkeypatch, tmp_path):
    mod = _load_health_check()
    stub = tmp_path / "app.py"
    stub.write_text("def other_function():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(mod, "CONTROL_PLANE_APP_PATH", stub)
    result = mod.check_token_compare_drift()
    assert result["ok"] is False
    assert "no longer present" in result["detail"]


def test_token_compare_drift_flags_a_missing_file(monkeypatch, tmp_path):
    mod = _load_health_check()
    monkeypatch.setattr(mod, "CONTROL_PLANE_APP_PATH", tmp_path / "does-not-exist.py")
    result = mod.check_token_compare_drift()
    assert result["ok"] is False
    assert "missing" in result["detail"]


def test_token_compare_drift_flags_a_bare_dict_get_regression(monkeypatch, tmp_path):
    mod = _load_health_check()
    stub = tmp_path / "app.py"
    stub.write_text(
        "def _match_token(tokens, token):\n"
        "    return tokens.get(token)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "CONTROL_PLANE_APP_PATH", stub)
    result = mod.check_token_compare_drift()
    assert result["ok"] is False
    assert "bare dict .get()" in result["detail"]


def test_token_compare_drift_flags_a_missing_compare_digest_call(monkeypatch, tmp_path):
    mod = _load_health_check()
    stub = tmp_path / "app.py"
    stub.write_text(
        "def _match_token(tokens, token):\n"
        "    for candidate, entry in tokens.items():\n"
        "        if candidate == token:\n"
        "            return entry\n"
        "    return None\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "CONTROL_PLANE_APP_PATH", stub)
    result = mod.check_token_compare_drift()
    assert result["ok"] is False
    assert "hmac.compare_digest" in result["detail"]


def test_token_compare_drift_ok_on_the_real_app_source():
    mod = _load_health_check()
    result = mod.check_token_compare_drift()
    assert result["ok"] is True


# --------------------------------------------------------------------------- #
# CLI + schedule registration
# --------------------------------------------------------------------------- #

def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_h_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_h_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_h_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-h-control-health" in names
    entry = names["ws-h-control-health"]
    assert entry["command"] == ["python3", "scripts/ws_h_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
