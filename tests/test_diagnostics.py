"""Failing-case tests for the diagnostics.py release-gate scorer.

These tests prove two things:

1. The scorer RUNS cleanly on the live repo and emits a per-dimension JSON
   breakdown without crashing, attributing each dimension its weighted score.
2. A seeded defect makes the *right* dimension drop to 0 — the scorer attributes
   failures to the dimension whose check the defect breaks, and a missing or
   unbuilt artifact degrades gracefully instead of raising.

They are intentionally tolerant of the current sub-100 score: the acceptance
criterion for DAS-1262 is "runs cleanly, --json emits per-dimension scores, a
missing artifact fails its dimension gracefully" — not a green 100/100, which
only lands once every other epic merges.
"""

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
    """Import scripts/diagnostics.py as a module for white-box checks.

    The module is registered in ``sys.modules`` before execution because its
    dataclasses use ``from __future__ import annotations``; under that flag the
    dataclass machinery resolves field annotations against
    ``sys.modules[cls.__module__]``, which must therefore be present.
    """
    spec = importlib.util.spec_from_file_location("diagnostics", DIAGNOSTICS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_script_runs_and_emits_per_dimension_json() -> None:
    """`diagnostics.py --json` runs cleanly and emits all 7 dimension scores."""
    proc = subprocess.run(
        [sys.executable, str(DIAGNOSTICS), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    # It must not crash (a crash would surface as a traceback on stderr).
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
    # Per-dimension scores are present and within their weight bounds.
    for dim in payload["dimensions"]:
        assert 0 <= dim["score"] <= dim["weight"]
        assert isinstance(dim["checks"], list) and dim["checks"]

    # Sub-100 now (most epics unbuilt); exit code mirrors the pass/fail state.
    assert payload["total"] == sum(d["score"] for d in payload["dimensions"])
    assert proc.returncode == (0 if payload["total"] == 100 else 1)


def test_missing_artifact_fails_gracefully_not_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dimension whose artifacts are absent scores 0 with a reason, no exception."""
    mod = _load_module()
    # Point the scorer at an empty tree: VERSION/CHANGELOG/.gitignore/CI/templates absent.
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    results = mod.score_dimension("git_hygiene", "Git-hygiene", 5)
    assert results.passed is False
    assert results.score == 0
    # Failure is reported as a check detail, not raised.
    assert any(not c.passed and c.detail for c in results.checks)


def test_ruff_absent_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0021: when ruff is unavailable, the Code-quality dimension must NOT earn
    full marks (fail-closed) — so the total can never reach 100/100 without lint."""
    mod = _load_module()
    real_run = mod.subprocess.run

    def fake_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "ruff":
            raise FileNotFoundError("ruff not installed")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    dim = mod.score_dimension("code_quality", "Code-quality", 15)
    ruff_check = next((c for c in dim.checks if c.name == "ruff-clean"), None)
    assert ruff_check is not None and ruff_check.passed is False
    assert dim.score == 0  # an unmeasured lint gate cannot earn the dimension


def test_board_alias_targets_consistency_dimension() -> None:
    """`--check board` resolves to the consistency (board-integrity) dimension."""
    results = _load_module().run("board")
    assert len(results) == 1
    assert results[0].key == "consistency"


def test_seeded_consistency_defect_drops_that_dimension_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed a malformed ticket; the consistency dimension must drop to 0.

    We point the scorer's TICKETS_DIR at a temp board containing one valid
    ticket and one with a bad status enum, then assert that only the
    consistency dimension's status-enum check fails.
    """
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
    # Seeded defect: bogus status not in the enum.
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
    # The other consistency checks (fields, self-review) still pass — the defect
    # is attributed precisely to the status-enum check, not the whole dimension.
    assert {c.name for c in dim.checks if c.passed} >= {
        "frontmatter-fields",
        "no-self-review",
    }


def test_clean_board_keeps_consistency_dimension_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A well-formed board makes the consistency dimension earn its full weight."""
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
