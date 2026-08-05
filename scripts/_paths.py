#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def repo_root() -> Path:
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
