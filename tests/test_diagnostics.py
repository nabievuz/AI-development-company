
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTICS = REPO_ROOT / "scripts" / "diagnostics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("diagnostics", DIAGNOSTICS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_script_runs_and_emits_per_dimension_json() -> None:
    proc = subprocess.run(
        [sys.executable, str(DIAGNOSTICS), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    assert "Traceback" not in proc.stderr, proc.stderr
    payload = json.loads(proc.stdout)

    assert payload["maximum"] == 100
    assert {d["key"] for d in payload["dimensions"]} == {
        "docs",
        "architecture",
        "code_quality",
        "consistency",
        "portability",
        "security",
        "git_hygiene",
    }

    for dim in payload["dimensions"]:
        assert 0 <= dim["score"] <= dim["weight"]
        assert isinstance(dim["checks"], list) and dim["checks"]


    assert payload["total"] == sum(d["score"] for d in payload["dimensions"])
    assert proc.returncode == (0 if payload["total"] == 100 else 1)


def test_missing_artifact_fails_gracefully_not_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_module()

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    results = mod.score_dimension("git_hygiene", "Git-hygiene", 5)
    assert results.passed is False
    assert results.score == 0

    assert any(not c.passed and c.detail for c in results.checks)


def test_ruff_absent_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    real_run = mod.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, list | tuple) and cmd and cmd[0] == "ruff":
            raise FileNotFoundError("ruff not installed")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    dim = mod.score_dimension("code_quality", "Code-quality", 15)
    ruff_check = next((c for c in dim.checks if c.name == "ruff-clean"), None)
    assert ruff_check is not None and ruff_check.passed is False
    assert dim.score == 0


def test_board_alias_targets_consistency_dimension() -> None:
    results = _load_module().run("board")
    assert len(results) == 1
    assert results[0].key == "consistency"


def test_seeded_consistency_defect_drops_that_dimension_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_module()

    board = tmp_path / "tickets"
    board.mkdir()
    (board / "DAS-0001-good.md").write_text(
        "---\n"
        "id: DAS-0001\n"
        "title: ok\n"
        "status: todo\n"
        "assignee: qa-lead\n"
        "author: ceo\n"
        "---\n\n## Description\nfine\n",
        encoding="utf-8",
    )

    (board / "DAS-0002-bad.md").write_text(
        "---\n"
        "id: DAS-0002\n"
        "title: broken\n"
        "status: not_a_real_status\n"
        "assignee: qa-lead\n"
        "author: ceo\n"
        "---\n\n## Description\nbad\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "TICKETS_DIR", board)

    dim = mod.score_dimension("consistency", "Consistency", 15)
    assert dim.passed is False
    assert dim.score == 0
    failing = [c for c in dim.checks if not c.passed]
    assert any(c.name == "status-enum" for c in failing)


    assert {c.name for c in dim.checks if c.passed} >= {
        "frontmatter-fields",
        "no-self-review",
    }


def test_clean_board_keeps_consistency_dimension_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_module()

    board = tmp_path / "tickets"
    board.mkdir()
    (board / "DAS-0001-good.md").write_text(
        "---\n"
        "id: DAS-0001\n"
        "title: ok\n"
        "status: in_review\n"
        "assignee: cto\n"
        "author: qa-lead\n"
        "---\n\n## Description\nfine\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "TICKETS_DIR", board)

    dim = mod.score_dimension("consistency", "Consistency", 15)
    assert dim.passed is True
    assert dim.score == 15
