from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = ROOT / "evals" / "ws-e-guardrails"
CLEAN_FIXTURE = EVALS_DIR / "golden_set.json"
GAMING_FIXTURE = EVALS_DIR / "golden_set_with_gaming_probe.json"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


runner = _load("evals/ws-e-guardrails/runner.py", "ws_e_golden_set_runner_under_test")


def test_clean_golden_set_passes_and_is_judge_eligible():
    result = runner.run_golden_set(CLEAN_FIXTURE)
    assert result.total_count == 3
    assert result.passed_count == 3
    assert result.all_passed is True
    assert result.judge_eligible is True
    assert runner.gate_is_red(result) is False


def test_clean_golden_set_judge_stub_runs_when_eligible():
    result = runner.run_golden_set(CLEAN_FIXTURE)
    verdict = runner.run_judge_if_eligible(result)
    assert "judge-eligible" in verdict


def test_anti_gaming_probe_fails_a_gaming_model():
    result = runner.run_golden_set(GAMING_FIXTURE)
    assert result.total_count == 4
    assert result.passed_count == 3
    assert runner.ANTI_GAMING_CASE_NAME in result.failed_names
    assert result.anti_gaming_probe_failed is True


def test_no_golden_set_pass_is_red_when_gaming_probe_present():
    result = runner.run_golden_set(GAMING_FIXTURE)
    assert result.all_passed is False
    assert runner.gate_is_red(result) is True
    assert result.judge_eligible is False


def test_judge_refuses_to_run_on_a_red_gate():
    result = runner.run_golden_set(GAMING_FIXTURE)
    with pytest.raises(RuntimeError, match="RED"):
        runner.run_judge_if_eligible(result)


def test_missing_fixture_is_red_not_green():
    result = runner.run_golden_set(EVALS_DIR / "does-not-exist.json")
    assert result.total_count == 0
    assert result.all_passed is False
    assert runner.gate_is_red(result) is True


def test_runner_reuses_the_admitted_promptfoo_bridge_directly():
    bridge = runner._load_promptfoo_bridge()
    expected_summary = bridge.run_eval(str(CLEAN_FIXTURE))
    result = runner.run_golden_set(CLEAN_FIXTURE)
    assert result.raw_summary == expected_summary
