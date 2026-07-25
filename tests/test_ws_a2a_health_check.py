"""A2A OUTBOUND Maintenance health/eval tests (GATE-6 / DAS-1614/DAS-1624).

Covers ``scripts/ws_a2a_health_check.py``: the in-tenant boundary drift
probe, the flag/publish-state drift probe, the negative-test drift probe,
and the Maintenance-schedule registration
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
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_health_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return _load("scripts/ws_a2a_health_check.py", "_ws_a2a_health_check")


def test_healthy_repo_reports_no_findings():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["in_tenant_drift"]["ok"] is True
    assert result["checks"]["flag_publish_drift"]["ok"] is True
    assert result["checks"]["negative_test_drift"]["ok"] is True


# --------------------------------------------------------------------------- #
# 1. In-tenant boundary drift
# --------------------------------------------------------------------------- #

def test_in_tenant_drift_ok_on_the_real_tracked_config():
    mod = _load_health_check()
    result = mod.check_in_tenant_drift()
    assert result["ok"] is True


def test_in_tenant_drift_flags_a_missing_boundary_file(monkeypatch, tmp_path):
    mod = _load_health_check()
    monkeypatch.setattr(mod, "TENANT_BOUNDARY_PATH", tmp_path / "does-not-exist.yaml")
    result = mod.check_in_tenant_drift()
    assert result["ok"] is False
    assert "missing" in result["detail"]


def test_in_tenant_drift_flags_an_external_endpoint(monkeypatch, tmp_path):
    mod = _load_health_check()
    bad = tmp_path / "tenant_boundary.yaml"
    bad.write_text(
        "endpoints:\n"
        "  - name: rogue-a2a\n"
        "    role: a2a\n"
        "    carries_code_ip: true\n"
        "    url: https://relay.example.com\n"
        "accepted_external_roles: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "TENANT_BOUNDARY_PATH", bad)
    result = mod.check_in_tenant_drift()
    assert result["ok"] is False
    assert "EXTERNAL" in result["detail"]


# --------------------------------------------------------------------------- #
# 2. Flag/publish-state drift
# --------------------------------------------------------------------------- #

def test_flag_publish_drift_ok_on_the_real_honest_baseline():
    mod = _load_health_check()
    result = mod.check_flag_publish_drift()
    assert result["ok"] is True
    assert "no drift" in result["detail"]


def test_flag_publish_drift_flags_flag_on_with_zero_events(monkeypatch, tmp_path):
    mod = _load_health_check()
    on_features = tmp_path / "features.yaml"
    on_features.write_text("a2a_outbound: true\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", on_features)
    monkeypatch.setattr(mod, "EVENTS_PATH", tmp_path / "does-not-exist.jsonl")
    result = mod.check_flag_publish_drift()
    assert result["ok"] is False
    assert "zero" in result["detail"]


def test_flag_publish_drift_ok_when_allow_event_matches_flag_on(monkeypatch, tmp_path):
    mod = _load_health_check()
    on_features = tmp_path / "features.yaml"
    on_features.write_text("a2a_outbound: true\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", on_features)
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_type": "a2a_publish",
                "decision": "allow",
                "flag_state": True,
                "principal_id": "founder",
                "principal_kind": "founder",
                "target": "http://127.0.0.1:8765",
                "reason": "founder publish",
                "ts": "2026-07-24T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "EVENTS_PATH", events)
    result = mod.check_flag_publish_drift()
    assert result["ok"] is True


def test_flag_publish_drift_flags_a_rollback_that_outran_the_ledger(monkeypatch, tmp_path):
    mod = _load_health_check()
    off_features = tmp_path / "features.yaml"
    off_features.write_text("a2a_outbound: false\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", off_features)
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_type": "a2a_publish",
                "decision": "allow",
                "flag_state": True,
                "principal_id": "founder",
                "principal_kind": "founder",
                "target": "http://127.0.0.1:8765",
                "reason": "founder publish",
                "ts": "2026-07-24T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "EVENTS_PATH", events)
    result = mod.check_flag_publish_drift()
    assert result["ok"] is False
    assert "implies" in result["detail"]


def test_flag_publish_drift_uses_the_newest_event_when_several_are_logged(monkeypatch, tmp_path):
    mod = _load_health_check()
    off_features = tmp_path / "features.yaml"
    off_features.write_text("a2a_outbound: false\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", off_features)
    events = tmp_path / "events.jsonl"
    lines = [
        {
            "event_type": "a2a_publish",
            "decision": "allow",
            "flag_state": True,
            "principal_id": "founder",
            "principal_kind": "founder",
            "target": "http://127.0.0.1:8765",
            "reason": "founder publish",
            "ts": "2026-07-24T00:00:00Z",
        },
        {
            "event_type": "a2a_publish",
            "decision": "deny",
            "flag_state": False,
            "principal_id": "founder",
            "principal_kind": "founder",
            "target": "http://127.0.0.1:8765",
            "reason": "founder rollback",
            "ts": "2026-07-24T01:00:00Z",
        },
    ]
    events.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "EVENTS_PATH", events)
    result = mod.check_flag_publish_drift()
    assert result["ok"] is True


# --------------------------------------------------------------------------- #
# 3. Negative-test drift
# --------------------------------------------------------------------------- #

def test_negative_test_drift_ok_on_the_real_suite():
    mod = _load_health_check()
    result = mod.check_negative_test_drift()
    assert result["ok"] is True
    assert "green" in result["detail"]


def test_negative_test_drift_flags_a_missing_test_file(monkeypatch, tmp_path):
    mod = _load_health_check()
    monkeypatch.setattr(mod, "TEST_PATHS", (tmp_path / "does-not-exist.py",))
    result = mod.check_negative_test_drift()
    assert result["ok"] is False
    assert "missing" in result["detail"]


# --------------------------------------------------------------------------- #
# CLI + schedule registration
# --------------------------------------------------------------------------- #

def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_a2a_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_a2a_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_a2a_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-a2a-outbound-health" in names
    entry = names["ws-a2a-outbound-health"]
    assert entry["command"] == ["python3", "scripts/ws_a2a_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
