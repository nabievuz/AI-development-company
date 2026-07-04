#!/usr/bin/env python3
"""check_project_isolation.py — keep the engine project-agnostic (LAW C).

DasLab is a factory for *any* goal, not one product. No project-specific name
may leak into the engine's load-bearing files — the generators, validators,
skills, agent shims, routing table, dept charters/overlays, and the umbrella
specs. Project material lives under ``projects/<slug>/`` (gitignored).

The denylist is derived at runtime from the names of any directories under
``projects/`` (gitignored). Historical/work-record areas (``board/tickets/``,
``docs/``, ``governance/board-minutes``) and the scanners themselves are out of
scope — they may reference a project by name as data.

Exit codes
----------
0  engine is project-agnostic
1  a project name leaked into an engine file
2  usage / environment error
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

from _paths import ROOT

# Load-bearing engine surface (glob patterns, repo-root-relative).
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
# Base denylist: derived from projects/ subdir names at runtime (see denylist()).
# Add an explicit slug here only to forbid a name with no projects/ dir present.
_BASE_DENY: tuple[str, ...] = ()
# Scratch dirs under projects/ that are not project slugs.
_SCRATCH_DIRS = {"worktrees"}
# Never scan the scanners (they hold the denylist as data).
_SELF = {"scripts/check_project_isolation.py"}

# ENGINE SURFACE vs HISTORY (the isolation boundary, made explicit).
# The engine surface scanned above (ENGINE_PATTERNS) is the reusable machinery that
# must be project-neutral. Everything else is OUT OF SCOPE BY CONSTRUCTION — these
# historical / work-record areas legitimately reference a project by name as data
# and must NOT be falsified to chase a grep-zero:
_ALLOWLIST_HISTORICAL = (
    "board/tickets/",          # platform-only board; a platform ticket may cite a
                               # project name as data (board_lint R9 forbids the
                               # structural `project:` field — project tickets live
                               # in projects/<slug>/board-tickets/)
    "docs/adr/",               # architecture decisions may cite a project as data
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
    # Derive forbidden project names from projects/ subdir names plus any explicit
    # _BASE_DENY entries. Dot-dirs and known scratch dirs (e.g. "worktrees") are
    # excluded — they are not project slugs and would false-flag legitimate
    # git-worktree references in engine docs.
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
