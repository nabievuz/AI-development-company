#!/usr/bin/env python3
"""check_no_dead_runtime.py — no dead legacy-runtime endpoint in the active engine.

DasLab is file-based (the board is `board/tickets/*.md`; orchestration is
`/daslab-cycle` + `/daslab-plan`). An earlier HTTP-API runtime exposed an endpoint
on port **3100**; that endpoint no longer exists, and any reference to it in active
engine code is dead and must not regress. This validator fails CI on the dead-endpoint
literal in the active surface:

    scripts/*.py, scripts/*.sh, skills/**/*.md, .claude/agents/*.md, .claude/skills/**/*.md

Archival files that may legitimately mention the literal as data are out of scope by
construction (they are not in the active surface): `docs/**` and the board ticket
store. The scanner itself is allowlisted (it names the literal as data).

Exit codes
----------
0  no dead-runtime endpoint in the active surface
1  at least one dead-runtime endpoint
2  usage / environment error
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from _paths import ROOT

# Active engine surface (glob patterns, repo-root-relative).
SURFACE = (
    "scripts/*.py",
    "scripts/*.sh",
    "scripts/*.md",
    "skills/**/*.md",
    ".claude/agents/*.md",
    ".claude/skills/**/*.md",
)
# Dead legacy-runtime endpoint, assembled so this scanner is never its own offender.
_NEEDLE = ":" + "3100"
_SELF = {"scripts/check_no_dead_runtime.py"}


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


def surface_files(root: Path) -> list[str]:
    return [
        rel
        for rel in tracked_files(root)
        if rel not in _SELF and any(fnmatch.fnmatch(rel, pat) for pat in SURFACE)
    ]


def offenders(root: Path) -> list[str]:
    hits: list[str] = []
    for rel in surface_files(root):
        path = root / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if _NEEDLE in line:
                hits.append(f"{rel}:{i}: dead legacy-runtime endpoint ({_NEEDLE})")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="repo root (default: self-located)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()
    if not root.is_dir():
        print(f"check_no_dead_runtime: FATAL — {root} is not a directory", file=sys.stderr)
        return 2

    hits = offenders(root)
    if hits:
        print(f"check_no_dead_runtime: {len(hits)} dead-runtime reference(s):", file=sys.stderr)
        for h in hits:
            print(f"  FAIL  {h}", file=sys.stderr)
        return 1
    print("check_no_dead_runtime: OK — no dead legacy-runtime endpoint in the active engine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
