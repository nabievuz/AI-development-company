from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _founder_allow_event_line() -> str:
    return json.dumps(
        {
            "event_type": "a2a_publish",
            "ts": "2026-07-26T00:00:00Z",
            "principal_id": "founder",
            "principal_kind": "founder",
            "decision": "allow",
            "flag_state": True,
            "target": "http://127.0.0.1:8765",
            "reason": "founder publish",
        }
    )


def test_run_reports_no_findings_when_all_three_legs_are_clean(monkeypatch, tmp_path):


    mod = _load_health_check()
    events = tmp_path / "events.jsonl"
    events.write_text(_founder_allow_event_line() + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "EVENTS_PATH", events)


    features = tmp_path / "features.yaml"
    features.write_text("a2a_outbound: true\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", features)

    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["in_tenant_drift"]["ok"] is True
    assert result["checks"]["flag_publish_drift"]["ok"] is True
    assert result["checks"]["negative_test_drift"]["ok"] is True


def test_run_is_unhealthy_when_any_single_leg_reports_a_finding(monkeypatch):


    mod = _load_health_check()
    legs = ("check_in_tenant_drift", "check_flag_publish_drift", "check_negative_test_drift")
    clean = {"ok": True, "detail": "stub clean"}
    for leg in legs:
        monkeypatch.setattr(mod, leg, lambda: dict(clean))
    assert mod.run()["healthy"] is True

    for leg in legs:
        monkeypatch.setattr(mod, leg, lambda: {"ok": False, "detail": "injected finding"})
        assert mod.run()["healthy"] is False, leg
        monkeypatch.setattr(mod, leg, lambda: dict(clean))


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


def test_flag_publish_drift_live_contract_flag_is_tracked_ledger_is_not():


    mod = _load_health_check()
    ff = _load("scripts/feature_flags.py", "_ws_a2a_live_contract_feature_flags")
    assert ff.enabled(mod.FLAG, mod.FEATURES_PATH) is True


    ledger = mod.EVENTS_PATH
    assert ledger.name == ".events.jsonl"
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ledger.name],
            cwd=ledger.parent,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pytest.skip("git unavailable — the ledger's tracked status cannot be read here")


    if ignored.returncode not in (0, 1):
        pytest.skip(f"git could not answer (rc={ignored.returncode}): {ignored.stderr.strip()}")
    assert ignored.returncode == 0, (
        "board/.events.jsonl is no longer gitignored — the audited leg became "
        "distributable evidence, so this check's ambient verdict is now assertable "
        "and docs/06-maintenance/ws-a2a-outbound-health.md needs revisiting"
    )


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


def test_flag_publish_drift_selects_the_newest_publish_event_not_the_newest_record(
    monkeypatch, tmp_path
):


    mod = _load_health_check()
    on_features = tmp_path / "features.yaml"
    on_features.write_text("a2a_outbound: true\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FEATURES_PATH", on_features)
    events = tmp_path / "events.jsonl"
    events.write_text(
        _founder_allow_event_line()
        + "\n"
        + json.dumps({"event_type": "dispatch", "ts": "2026-07-27T00:00:00Z", "ticket": "DAS-1"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "EVENTS_PATH", events)
    result = mod.check_flag_publish_drift()
    assert result["ok"] is True
    assert "agrees" in result["detail"]


def test_flag_publish_drift_needs_both_allow_and_flag_state_not_either_alone(monkeypatch, tmp_path):


    mod = _load_health_check()
    events = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "EVENTS_PATH", events)

    def _verdict(record: dict, flag: str) -> dict:
        events.write_text(json.dumps(record) + "\n", encoding="utf-8")
        features = tmp_path / f"features-{flag}.yaml"
        features.write_text(f"a2a_outbound: {flag}\n", encoding="utf-8")
        monkeypatch.setattr(mod, "FEATURES_PATH", features)
        return mod.check_flag_publish_drift()

    base = {
        "event_type": "a2a_publish",
        "ts": "2026-07-26T00:00:00Z",
        "principal_id": "founder",
        "principal_kind": "founder",
        "target": "http://127.0.0.1:8765",
        "reason": "founder act",
    }


    assert _verdict({**base, "decision": "deny", "flag_state": True}, "true")["ok"] is False
    assert _verdict({**base, "decision": "deny", "flag_state": True}, "false")["ok"] is True

    assert _verdict({**base, "decision": "allow", "flag_state": False}, "false")["ok"] is True
    assert _verdict({**base, "decision": "allow", "flag_state": False}, "true")["ok"] is False


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


def test_negative_test_drift_flags_a_red_suite(monkeypatch, tmp_path):


    mod = _load_health_check()
    red = tmp_path / "test_red_suite.py"
    red.write_text("def test_red():\n    assert False\n", encoding="utf-8")
    monkeypatch.setattr(mod, "TEST_PATHS", (red,))
    result = mod.check_negative_test_drift()
    assert result["ok"] is False
    assert "failed" in result["detail"]


def test_cli_emits_all_three_checks_and_its_exit_code_agrees_with_the_payload():


    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_a2a_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    payload = json.loads(proc.stdout)
    assert set(payload["checks"]) == {
        "in_tenant_drift",
        "flag_publish_drift",
        "negative_test_drift",
    }
    assert proc.returncode == (0 if payload["healthy"] else 1)


def test_main_maps_healthy_to_exit_zero_and_a_finding_to_exit_one(monkeypatch, capsys):


    mod = _load_health_check()
    legs = {
        "in_tenant_drift": {"ok": True, "detail": "stub"},
        "flag_publish_drift": {"ok": True, "detail": "stub"},
        "negative_test_drift": {"ok": True, "detail": "stub"},
    }

    monkeypatch.setattr(mod, "run", lambda: {"healthy": True, "checks": legs})
    assert mod.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["healthy"] is True

    monkeypatch.setattr(mod, "run", lambda: {"healthy": False, "checks": legs})
    assert mod.main([]) == 1
    assert "UNHEALTHY" in capsys.readouterr().out


def test_maintenance_schedule_registers_the_ws_a2a_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_a2a_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-a2a-outbound-health" in names
    entry = names["ws-a2a-outbound-health"]
    assert entry["command"] == ["python3", "scripts/ws_a2a_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
