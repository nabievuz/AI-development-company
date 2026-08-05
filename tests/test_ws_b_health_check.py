from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml

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
    return _load("scripts/ws_b_health_check.py", "_ws_b_health_check")


def test_healthy_repo_reports_no_drift():
    mod = _load_health_check()
    result = mod.run()
    assert result["healthy"] is True
    assert result["checks"]["dispatch_equivalence_drift"]["ok"] is True
    assert result["checks"]["budget_ceiling_drift"]["ok"] is True


def test_dispatch_equivalence_ok_on_the_real_daslab_sdk_tree():
    mod = _load_health_check()
    result = mod.check_dispatch_equivalence_drift()
    assert result["ok"] is True
    assert "single" in result["detail"]
    assert "reconciles clean" in result["detail"]


def test_dispatch_equivalence_flags_a_second_call_site(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake_sdk = tmp_path / "daslab_sdk"
    fake_sdk.mkdir()
    (fake_sdk / "runner.py").write_text("def dispatch_wave():\n    return wr.run_wave(1, 2)\n")
    (fake_sdk / "extra.py").write_text("def rogue():\n    return run_wave(3, 4)\n")
    monkeypatch.setattr(mod, "DASLAB_SDK_DIR", fake_sdk)
    result = mod.check_dispatch_equivalence_drift()
    assert result["ok"] is False
    assert "multiple" in result["detail"]


def test_dispatch_equivalence_flags_no_call_site_at_all(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake_sdk = tmp_path / "daslab_sdk"
    fake_sdk.mkdir()
    (fake_sdk / "runner.py").write_text("def dispatch_wave():\n    return None\n")
    monkeypatch.setattr(mod, "DASLAB_SDK_DIR", fake_sdk)
    result = mod.check_dispatch_equivalence_drift()
    assert result["ok"] is False
    assert "no run_wave" in result["detail"]


def test_dispatch_equivalence_flags_a_broken_ledger(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake_sdk = tmp_path / "daslab_sdk"
    fake_sdk.mkdir()
    (fake_sdk / "runner.py").write_text("def dispatch_wave():\n    return wr.run_wave(1, 2)\n")
    monkeypatch.setattr(mod, "DASLAB_SDK_DIR", fake_sdk)

    class _FakeWaveRunner:
        LEDGER_PATH = tmp_path / "board" / "wave-ledger.jsonl"
        ATTEST_DIR = tmp_path / "attest"

        @staticmethod
        def verify_wave_ledger(ledger_path, attest_dir=None):
            return ["tampered attestation hash on line 3"]

    monkeypatch.setattr(mod, "_load_wave_runner", lambda: _FakeWaveRunner())
    result = mod.check_dispatch_equivalence_drift()
    assert result["ok"] is False
    assert "does not reconcile" in result["detail"]


def _write_healthy_budgets(path: Path) -> dict:
    doc = {
        "mustaqil": {
            "caps": {
                "per_run": {"max_input_tokens": 1, "max_output_tokens": 1, "max_cost_usd": 1},
                "per_day": {"max_input_tokens": 1, "max_output_tokens": 1, "max_cost_usd": 1},
            },
            "on_breach": "idle_and_alert",
            "monthly_credit_ceiling": {
                "plan_credit_usd": {"pro": 20, "max_5x": 100, "max_20x": 200},
                "on_exhaustion": "sanctioned_pause",
                "metered_overflow": False,
            },
        }
    }
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return doc


def test_budget_ceiling_ok_on_the_real_config():
    mod = _load_health_check()
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is True
    assert "metered_overflow: false" in result["detail"]


def test_budget_ceiling_flags_metered_overflow_flip(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake = tmp_path / "budgets.yaml"
    doc = _write_healthy_budgets(fake)
    doc["mustaqil"]["monthly_credit_ceiling"]["metered_overflow"] = True
    fake.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setattr(mod, "BUDGETS_PATH", fake)
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is False
    assert "metered_overflow" in result["detail"]


def test_budget_ceiling_flags_a_removed_metered_overflow_key(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake = tmp_path / "budgets.yaml"
    doc = _write_healthy_budgets(fake)
    del doc["mustaqil"]["monthly_credit_ceiling"]["metered_overflow"]
    fake.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setattr(mod, "BUDGETS_PATH", fake)
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is False
    assert "metered_overflow" in result["detail"]


def test_budget_ceiling_flags_a_removed_cap(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake = tmp_path / "budgets.yaml"
    doc = _write_healthy_budgets(fake)
    del doc["mustaqil"]["caps"]["per_day"]
    fake.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setattr(mod, "BUDGETS_PATH", fake)
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is False
    assert "per_day" in result["detail"]


def test_budget_ceiling_flags_changed_exhaustion_policy(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake = tmp_path / "budgets.yaml"
    doc = _write_healthy_budgets(fake)
    doc["mustaqil"]["monthly_credit_ceiling"]["on_exhaustion"] = "auto_retry"
    fake.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setattr(mod, "BUDGETS_PATH", fake)
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is False
    assert "on_exhaustion" in result["detail"]


def test_budget_ceiling_flags_missing_mustaqil_block(tmp_path, monkeypatch):
    mod = _load_health_check()
    fake = tmp_path / "budgets.yaml"
    fake.write_text(yaml.safe_dump({"version": 1}), encoding="utf-8")
    monkeypatch.setattr(mod, "BUDGETS_PATH", fake)
    result = mod.check_budget_ceiling_drift()
    assert result["ok"] is False
    assert "mustaqil" in result["detail"]


def test_cli_exits_zero_when_healthy():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "ws_b_health_check.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["healthy"] is True


def test_maintenance_schedule_registers_the_ws_b_health_check():
    stage_gate = _load("scripts/stage_gate.py", "_stage_gate_for_ws_b_health_test")
    schedule = stage_gate.maintenance_schedule()
    names = {run["name"]: run for run in schedule["recurring_runs"]}
    assert "ws-b-runner-health" in names
    entry = names["ws-b-runner-health"]
    assert entry["command"] == ["python3", "scripts/ws_b_health_check.py", "--json"]
    assert schedule["installs_os_scheduler_entry"] is False
    assert schedule["never_auto_approve"] is True
