
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _resolve_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess

        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass

    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()
DEFAULT_RUNS_DIR: Path = _ROOT / "board" / "runs"


WORKSPACE_DIRNAME = "workspace"


def workspace_path(run_id: str, runs_dir: Path | None = None) -> Path:
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    return rd / run_id / WORKSPACE_DIRNAME


def create_workspace(run_id: str, runs_dir: Path | None = None) -> Path:
    ws = workspace_path(run_id, runs_dir)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def gc_workspace(run_id: str, runs_dir: Path | None = None) -> bool:
    ws = workspace_path(run_id, runs_dir)
    if not ws.exists():
        return False
    shutil.rmtree(ws)
    return True


WORKTREES_DIRNAME = ".worktrees"
_GIT_TIMEOUT = 120


class WorktreeError(RuntimeError):
    pass


def worktree_root(root: Path | None = None) -> Path:
    return (root if root is not None else _ROOT) / WORKTREES_DIRNAME


def worktree_path(run_id: str, ticket_id: str, root: Path | None = None) -> Path:
    return worktree_root(root) / run_id / ticket_id


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )


def branch_exists(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


DEFAULT_BASE_CANDIDATES = ("main", "master")


def default_base(repo: Path) -> str:
    for candidate in DEFAULT_BASE_CANDIDATES:
        if branch_exists(repo, candidate):
            return candidate
    return "HEAD"


def existing_ticket_branch(repo: Path, ticket_id: str) -> str:
    proc = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    if proc.returncode != 0:
        return ""
    prefix = f"{ticket_id}-"
    matches = [b for b in proc.stdout.split() if b == ticket_id or b.startswith(prefix)]
    return sorted(matches)[0] if len(matches) == 1 else ""


def create_git_worktree(repo: Path, path: Path, branch: str, base: str = "") -> Path:
    if not (repo / ".git").exists():
        raise WorktreeError(f"not a git repository: {repo}")
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    argv = (
        ["worktree", "add", str(path), branch]
        if branch_exists(repo, branch)
        else ["worktree", "add", "-b", branch, str(path), base or default_base(repo)]
    )
    proc = _git(repo, *argv)
    if proc.returncode != 0:
        raise WorktreeError(
            f"git worktree add failed for {branch} at {path}: {proc.stderr.strip()[:300]}"
        )
    return path


def worktree_is_dirty(path: Path) -> bool:
    proc = _git(path, "status", "--porcelain")
    return proc.returncode != 0 or bool(proc.stdout.strip())


def ignored_entries(path: Path) -> tuple[str, ...]:
    proc = _git(path, "status", "--porcelain", "--ignored=matching")
    if proc.returncode != 0:
        return ()
    return tuple(
        line[3:] for line in proc.stdout.splitlines() if line.startswith("!! ")
    )


def remove_git_worktree(repo: Path, path: Path) -> str:
    if not path.exists():
        return "absent"
    if worktree_is_dirty(path):
        return "kept-dirty"
    proc = _git(repo, "worktree", "remove", str(path))
    if proc.returncode == 0:
        return "removed"
    if not ignored_entries(path):
        return "kept-failed"
    forced = _git(repo, "worktree", "remove", "--force", str(path))
    return "removed-ignored" if forced.returncode == 0 else "kept-failed"
