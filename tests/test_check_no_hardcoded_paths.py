"""tests/test_check_no_hardcoded_paths.py — pytest for check_no_hardcoded_paths.py.

Hermetic: builds a synthetic git repo under tmp_path and scans it via --root.
Proves (a) a hardcoded /Users/<name> or /home/<name> path is detected, (b) a
clean tree passes, and (c) board/tickets are allowlisted.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_no_hardcoded_paths import main, offenders  # noqa: E402

# Assemble at runtime so this test file holds no literal hardcoded path either.
_U = "/" + "Users" + "/" + "someone" + "/proj"
_H = "/" + "home" + "/" + "someone" + "/proj"


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_detects_users_path(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "a.py").write_text(f'ROOT = "{_U}"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    found = offenders(repo)
    assert len(found) == 1 and "a.py" in found[0]
    assert main(["--root", str(repo)]) == 1


def test_detects_home_path(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "b.sh").write_text(f'cd {_H}\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert main(["--root", str(repo)]) == 1


def test_clean_tree_passes(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "c.py").write_text("from _paths import ROOT\nprint(ROOT)\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert offenders(repo) == []
    assert main(["--root", str(repo)]) == 0


def test_board_tickets_allowlisted(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    tickets = repo / "board" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / "DAS-1.md").write_text(f"verify: grep `{_U}`\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert offenders(repo) == []
    assert main(["--root", str(repo)]) == 0
