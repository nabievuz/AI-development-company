from __future__ import annotations

import collections
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import loop_controller
import orchestrator
import wave_planner

CANONICAL_ORG = ROOT / "config" / "org.yaml"
EXPECTED_ROLE_COUNT = 32
EXPECTED_MODEL_SPLIT = {"opus": 10, "sonnet": 19, "haiku": 3}


def test_canonical_org_yaml_loads_every_role():
    org = wave_planner.load_org_model(CANONICAL_ORG)
    assert len(org.role_models) == EXPECTED_ROLE_COUNT


def test_canonical_org_yaml_preserves_the_model_allocation_split():
    org = wave_planner.load_org_model(CANONICAL_ORG)
    assert dict(collections.Counter(org.role_models.values())) == EXPECTED_MODEL_SPLIT


def test_list_shaped_roles_are_parsed_not_silently_dropped():
    data = {"roles": [{"key": "cto", "model": "opus"}, {"key": "backend-eng-1", "model": "sonnet"}]}
    org = wave_planner.org_model_from_mapping(data)
    assert org.role_models == {"cto": "opus", "backend-eng-1": "sonnet"}


def test_mapping_shaped_roles_still_parse():
    data = {"roles": {"cto": {"model": "opus"}, "qa-eng": "haiku"}}
    org = wave_planner.org_model_from_mapping(data)
    assert org.role_models == {"cto": "opus", "qa-eng": "haiku"}


@pytest.mark.parametrize("module", [orchestrator, loop_controller])
def test_runtime_entry_points_read_the_canonical_org_model(module):
    assert module.DEFAULT_ORG_PATH == CANONICAL_ORG
    org = wave_planner.load_org_model(module.DEFAULT_ORG_PATH)
    assert len(org.role_models) == EXPECTED_ROLE_COUNT


def _run_no_prose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "check_no_prose.py"), *args],
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_no_prose_gate_reports_usage_error_for_a_missing_path():
    assert _run_no_prose("/nonexistent-path-for-tests").returncode == 2


def test_no_prose_gate_refuses_to_pass_on_an_empty_scan(tmp_path):
    result = _run_no_prose(str(tmp_path))
    assert result.returncode == 3
    assert "scan surface collapsed" in result.stderr


def test_no_prose_gate_help_does_not_masquerade_as_a_clean_scan():
    result = _run_no_prose("--help")
    assert result.returncode == 0
    assert "violations: 0" not in result.stdout


def test_no_prose_gate_detects_a_planted_comment(tmp_path):
    (tmp_path / "planted.py").write_text("x = 1  # prose\n", encoding="utf-8")
    result = _run_no_prose(str(tmp_path))
    assert result.returncode == 1
    assert "violations: 1" in result.stdout


def test_no_prose_gate_detects_a_planted_docstring(tmp_path):
    (tmp_path / "planted.py").write_text('def f():\n    "doc"\n    return 1\n', encoding="utf-8")
    result = _run_no_prose(str(tmp_path))
    assert result.returncode == 1
    assert "docstring on f" in result.stdout


def test_no_prose_gate_passes_on_the_real_tree():
    result = _run_no_prose(str(ROOT))
    assert result.returncode == 0
    assert "violations: 0" in result.stdout
