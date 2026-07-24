"""WS-A Maintenance health/eval tests (ADR-0033 GATE-6 / DAS-1551).

Covers ``scripts/ws_a_health_check.py``: the allow-list drift check, the
redaction probe, and the Maintenance-schedule registration
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
    sys.modules[name] = mod  # dataclasses (stage_gate.py) needs self in sys.modules
    spec.loader.exec_module(mod)
    return mod


def _load_health_check():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return _load("scripts/ws_a_health_check.py", "_ws_a_health_check")


def test_healthy_repo_reports_no_drift_and_no_redaction_miss():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["allowlist_drift"]["ok"] is True
    assert result["checks"]["redaction_probe"]["ok"] is True


def test_allowlist_drift_detected_when_tracked_file_diverges(tmp_path, monkeypatch):
    mod = _load_health_check()
    tampered = tmp_path / "tampered-allowlist.json"
    tampered.write_text(json.dumps({"mcp__not-real": ["nobody"]}, indent=2) + "\n")
    monkeypatch.setattr(mod, "TOOL_ALLOWLIST_PATH", tampered)
    result = mod.check_allowlist_drift()
    assert result["ok"] is False
    assert "diverges" in result["detail"]


def test_allowlist_drift_detected_when_tracked_file_missing(tmp_path, monkeypatch):
    mod = _load_health_check()
    missing = tmp_path / "does-not-exist.json"
    monkeypatch.setattr(mod, "TOOL_ALLOWLIST_PATH", missing)
    result = mod.check_allowlist_drift()
    assert result["ok"] is False
    assert "missing" in result["detail"]


def test_redaction_probe_flags_a_scrubber_that_stops_redacting(monkeypatch):
    mod = _load_health_check()

    class _PassthroughRedaction:
        @staticmethod
        def safe_scrub(value):
            return value  # simulates a broken/regressed scrubber

    monkeypatch.setattr(mod, "_load_redaction_module", lambda: _PassthroughRedaction())
    result = mod.check_redaction_probe()
    assert result["ok"] is False
    assert "expected redaction" in result["detail"]


def test_redaction_probe_flags_over_redaction_of_a_tier_m_control(monkeypatch):
    mod = _load_health_check()

    class _OverRedact:
        @staticmethod
        def safe_scrub(value):
            return "[REDACTED:everything]"

    monkeypatch.setattr(mod, "_load_redaction_module", lambda: _OverRedact())
    result = mod.check_redaction_probe()
    assert result["ok"] is False
    assert "over-redacted" in result["detail"]


def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_a_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_a_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_a_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-a-tool-edge-health" in names
    entry = names["ws-a-tool-edge-health"]
    assert entry["command"] == ["python3", "scripts/ws_a_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
