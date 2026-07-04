#!/usr/bin/env python3
"""Single source of truth for the DasLab repository root.

The root is *resolved at runtime, never written down* (LAW A — self-locating
root). Resolution order:

1. ``DASLAB_ROOT`` environment variable (explicit override / CI / containers).
2. ``git rev-parse --show-toplevel`` (the enclosing git work-tree).
3. The directory two levels up from this file (``scripts/_paths.py`` →
   repo root) as a last-resort fallback when git is unavailable.

Every script imports ``ROOT`` from here — no script hardcodes an absolute path.

    from _paths import ROOT          # scripts/ is on sys.path[0] when run directly
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def repo_root() -> Path:
    """Resolve the repository root at runtime (never a hardcoded path)."""
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return Path(__file__).resolve().parents[1]


ROOT = repo_root()


def _gitignored_top_level_dirs(root: Path) -> set[str]:
    """Top-level directory names excluded by .gitignore (for the no-git fallback).

    Only single-component directory patterns count as top-level exclusions:
    ``/projects/`` and ``node_modules/`` exclude those dirs, but ``/.claude/worktrees/``
    (a sub-path) does NOT exclude ``.claude`` itself.
    """
    ignored = {".git", "node_modules", "__pycache__"}
    gi = root / ".gitignore"
    if gi.is_file():
        for raw in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p for p in line.strip("/").split("/") if p]
            if len(parts) == 1 and "*" not in parts[0]:
                ignored.add(parts[0])
    return ignored


def tracked_top_level_dirs(root: Path | None = None) -> list[str]:
    """Top-level directories that are git-tracked (gitignored dirs excluded).

    Single source of truth for "what areas exist" (CODEOWNERS, etc.). Uses
    ``git ls-files``; a runtime-created gitignored dir such as ``projects/`` (made
    by ``bootstrap.py``) never appears, so the result is stable before and after
    bootstrap. Falls back to a filesystem walk that honours ``.gitignore`` when git
    is unavailable (e.g. a ``git archive`` extraction).
    """
    root = (root or ROOT)
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout
        dirs = {line.split("/", 1)[0] for line in out.splitlines() if "/" in line}
        if dirs:
            return sorted(dirs)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    ignored = _gitignored_top_level_dirs(root)
    dirs = set()
    for p in root.iterdir():
        if p.is_dir() and p.name not in ignored and any(f.is_file() for f in p.rglob("*")):
            dirs.add(p.name)
    return sorted(dirs)
