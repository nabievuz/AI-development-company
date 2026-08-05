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
    return _load("scripts/ws_d_health_check.py", "_ws_d_health_check")


def test_healthy_repo_reports_no_findings():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["redaction_probe"]["ok"] is True
    assert result["checks"]["in_tenant_target"]["ok"] is True
    assert result["checks"]["allowlist_drift"]["ok"] is True


def test_redaction_probe_flags_a_scrubber_that_stops_redacting(monkeypatch):
    mod = _load_health_check()

    class _PassthroughExporter:
        @staticmethod
        def redact_span(span):
            return dict(span)

    monkeypatch.setattr(mod, "_load_otlp_exporter_module", lambda: _PassthroughExporter())
    result = mod.check_redaction_probe()
    assert result["ok"] is False
    assert "expected" in result["detail"] and "redaction" in result["detail"]


def test_redaction_probe_flags_over_redaction_of_a_tier_m_key(monkeypatch):
    mod = _load_health_check()

    class _OverRedactExporter:
        @staticmethod
        def redact_span(span):
            return dict.fromkeys(span, "[REDACTED:everything]")

    monkeypatch.setattr(mod, "_load_otlp_exporter_module", lambda: _OverRedactExporter())
    result = mod.check_redaction_probe()
    assert result["ok"] is False
    assert "over-redacted" in result["detail"]


def test_redaction_probe_flags_a_dropped_span():
    mod = _load_health_check()

    class _AlwaysDropExporter:
        @staticmethod
        def redact_span(span):
            return None

    result_source = mod
    orig = result_source._load_otlp_exporter_module
    try:
        result_source._load_otlp_exporter_module = staticmethod(lambda: _AlwaysDropExporter())
        result = mod.check_redaction_probe()
    finally:
        result_source._load_otlp_exporter_module = orig
    assert result["ok"] is False
    assert "dropped" in result["detail"]


def test_in_tenant_target_flags_a_hosted_endpoint(monkeypatch):
    mod = _load_health_check()

    class _BoundaryError(RuntimeError):
        pass

    class _HostedExporter:
        BoundaryError = _BoundaryError

        @staticmethod
        def assert_in_tenant(config_path):
            raise _BoundaryError("TN-1: langfuse_observability resolves to an EXTERNAL host")

    monkeypatch.setattr(mod, "_load_otlp_exporter_module", lambda: _HostedExporter())
    result = mod.check_in_tenant_target()
    assert result["ok"] is False
    assert "EXTERNAL" in result["detail"]


def test_in_tenant_target_ok_when_exporter_resolves_local(monkeypatch):
    mod = _load_health_check()

    class _BoundaryError(RuntimeError):
        pass

    class _SelfHostExporter:
        BoundaryError = _BoundaryError

        @staticmethod
        def assert_in_tenant(config_path):
            return "http://127.0.0.1:3000/api/public/otel/v1/traces"

    monkeypatch.setattr(mod, "_load_otlp_exporter_module", lambda: _SelfHostExporter())
    result = mod.check_in_tenant_target()
    assert result["ok"] is True
    assert "127.0.0.1" in result["detail"]


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


def test_allowlist_drift_flags_a_wildcard_role(monkeypatch):
    mod = _load_health_check()
    wildcard_map = {"mcp__promptfoo__run_eval": ["qa-eng", "*"]}
    recompiled_text = json.dumps(wildcard_map, indent=2, sort_keys=True) + "\n"

    fake_path = mod.TOOL_ALLOWLIST_PATH

    class _FakePath:
        def exists(self):
            return True

        def read_text(self, encoding="utf-8"):
            return recompiled_text

    monkeypatch.setattr(mod.gen_subagents, "compile_tool_allowlist", lambda: wildcard_map)
    monkeypatch.setattr(mod, "TOOL_ALLOWLIST_PATH", _FakePath())
    try:
        result = mod.check_allowlist_drift()
    finally:
        monkeypatch.setattr(mod, "TOOL_ALLOWLIST_PATH", fake_path)
    assert result["ok"] is False
    assert "'*'" in result["detail"]


def test_allowlist_drift_flags_missing_eval_tool_grants(monkeypatch):
    mod = _load_health_check()
    no_eval_map = {"mcp__browser__navigate": ["frontend-eng"]}
    recompiled_text = json.dumps(no_eval_map, indent=2, sort_keys=True) + "\n"

    class _FakePath:
        def exists(self):
            return True

        def read_text(self, encoding="utf-8"):
            return recompiled_text

    monkeypatch.setattr(mod.gen_subagents, "compile_tool_allowlist", lambda: no_eval_map)
    monkeypatch.setattr(mod, "TOOL_ALLOWLIST_PATH", _FakePath())
    result = mod.check_allowlist_drift()
    assert result["ok"] is False
    assert "no promptfoo" in result["detail"]


def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_d_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_d_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_d_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-d-lens-health" in names
    entry = names["ws-d-lens-health"]
    assert entry["command"] == ["python3", "scripts/ws_d_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
