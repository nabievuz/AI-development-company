"""tests/test_check_codeowners.py — pytest for gen_codeowners + check_codeowners.

Hermetic: builds a synthetic git repo, generates CODEOWNERS, and proves a
missing area and drift are both detected while a generated file passes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_codeowners import offenders  # noqa: E402
from gen_codeowners import render, top_level_areas  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for area in ("scripts", "docs", "board"):
        (tmp_path / area).mkdir()
        (tmp_path / area / "f.txt").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_generated_codeowners_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".github").mkdir()
    (repo / ".github" / "CODEOWNERS").write_text(render(repo))
    assert offenders(repo) == []
    assert set(top_level_areas(repo)) >= {"scripts", "docs", "board"}


def test_missing_codeowners_detected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert offenders(repo) == [".github/CODEOWNERS is missing"]


def test_missing_area_and_drift_detected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".github").mkdir()
    # hand-written, missing /docs/ and /board/ and not matching the generator
    (repo / ".github" / "CODEOWNERS").write_text("*  @someone\n/scripts/  @someone\n")
    issues = offenders(repo)
    assert any("/docs/" in i for i in issues)
    assert any("drifts" in i for i in issues)


def test_stable_after_runtime_gitignored_dir(tmp_path: Path) -> None:
    """Durable 100: a runtime-created gitignored dir (projects/) is NOT a spurious area.

    No .git here, so this exercises the gitignore-aware no-git fallback — the exact
    `git archive` + post-bootstrap scenario that used to drop the score to 95.
    """
    (tmp_path / ".gitignore").write_text("/projects/\nnode_modules/\n")
    for area in ("scripts", "docs", ".github"):
        (tmp_path / area).mkdir()
        (tmp_path / area / "f.txt").write_text("x\n")
    before = render(tmp_path)
    # simulate bootstrap + a project run: gitignored projects/ now has files
    (tmp_path / "projects" / "demo").mkdir(parents=True)
    (tmp_path / "projects" / "demo" / "app.py").write_text("print('x')\n")
    after = render(tmp_path)
    assert before == after, "CODEOWNERS drifted after a gitignored projects/ appeared"
    assert "projects" not in set(top_level_areas(tmp_path))
    (tmp_path / ".github" / "CODEOWNERS").write_text(after)
    assert offenders(tmp_path) == []
