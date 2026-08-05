#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

from _paths import ROOT


ENGINE_PATTERNS = (
    "scripts/*.py",
    "scripts/*.sh",
    "skills/**/*.md",
    ".claude/agents/*.md",
    ".claude/skills/**/*.md",
    "board/ROUTING.md",
    "board/README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "governance/policies/*.md",
    "*/AGENTS.md",
    "*/CLAUDE.md",
    "*/agents/*/AGENTS.md",
)


_BASE_DENY: tuple[str, ...] = ()

_SCRATCH_DIRS = {"worktrees"}

_SELF = {"scripts/check_project_isolation.py"}


_ALLOWLIST_HISTORICAL = (
    "board/tickets/",


    "docs/adr/",
    "governance/board-minutes/",
)


def tracked_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        )
        files = [line for line in out.stdout.splitlines() if line]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return [
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    ]


def engine_files(root: Path) -> list[str]:
    out: list[str] = []
    for rel in tracked_files(root):
        if rel in _SELF:
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in ENGINE_PATTERNS):
            out.append(rel)
    return out


def denylist(root: Path) -> set[str]:


    names = {d for d in _BASE_DENY if d}
    projects = root / "projects"
    if projects.is_dir():
        for child in projects.iterdir():
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and child.name not in _SCRATCH_DIRS
            ):
                names.add(child.name)
    return names


def offenders(root: Path, deny: set[str] | None = None) -> list[str]:
    deny = deny if deny is not None else denylist(root)
    if not deny:
        return []
    pat = re.compile(r"\b(" + "|".join(re.escape(d) for d in sorted(deny)) + r")\b", re.IGNORECASE)
    hits: list[str] = []
    for rel in engine_files(root):
        path = root / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            m = pat.search(line)
            if m:
                hits.append(f"{rel}:{i}: project name '{m.group(1)}' in engine file")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='check_project_isolation.py — keep the engine project-agnostic (LAW C).')
    parser.add_argument("--root", type=Path, default=None, help="repo root (default: self-located)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()
    if not root.is_dir():
        print(f"check_project_isolation: FATAL — {root} is not a directory", file=sys.stderr)
        return 2

    hits = offenders(root)
    if hits:
        print(f"check_project_isolation: {len(hits)} project-name leak(s):", file=sys.stderr)
        for h in hits:
            print(f"  FAIL  {h}", file=sys.stderr)
        return 1
    print("check_project_isolation: OK — engine is project-agnostic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
