"""tests/test_check_no_dead_runtime.py — pytest for check_no_dead_runtime.py.

Hermetic: builds a synthetic engine tree under tmp_path. Proves the dead
dead legacy-runtime endpoint is detected in an active script, a clean script passes, and a
historical file (docs/, not in the active surface) is out of scope.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_no_dead_runtime import offenders, surface_files  # noqa: E402

# Assemble at runtime so this test file carries no literal dead endpoint.
_DEAD = "http://127.0.0.1:" + "3100"


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_detects_dead_endpoint_in_active_script(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "x.py").write_text(f'API = "{_DEAD}"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    found = offenders(repo)
    assert len(found) == 1 and "scripts/x.py" in found[0]


def test_clean_active_script_passes(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "x.py").write_text("from _paths import ROOT\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert offenders(repo) == []


def test_historical_docs_out_of_scope(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "history.md").write_text(f"the retired runtime used {_DEAD}\n")
    (repo / "board" / "archive").mkdir(parents=True)
    (repo / "board" / "archive" / "old.md").write_text(f"{_DEAD}\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    # docs/ and board/archive/ are not in the active surface.
    assert "docs/history.md" not in surface_files(repo)
    assert offenders(repo) == []
