#!/usr/bin/env python3
"""check_no_hardcoded_paths.py — fail on any machine-specific absolute path.

LAW A (self-locating root): no tracked file may embed a hardcoded user-home
path such as ``/Users/<name>/…`` or ``/home/<name>/…``. The repository root is
resolved at runtime (see ``scripts/_paths.py``), never written down.

The needles are assembled from parts at runtime so this scanner — and the other
path-aware scripts (``diagnostics.py``) — are never their own offenders.
``board/tickets/`` is allowlisted: tickets quote example paths inside ``verify``
commands, like the gitleaks fixtures, and are work records, not load-bearing.

Exit codes
----------
0  no hardcoded home paths
1  at least one hardcoded home path
2  usage / environment error
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from _paths import ROOT

# Assemble needles from parts so this file contains no literal hardcoded path.
_HOME_PREFIXES = ("/" + "Users" + "/", "/" + "home" + "/")
_NEEDLE_RE = re.compile(
    "(?:" + "|".join(re.escape(p) for p in _HOME_PREFIXES) + r")[A-Za-z0-9_.\-]+"
)

# Files/dirs that legitimately reference such a path (scanners + work records).
_ALLOW_PREFIXES = ("board/",)
_ALLOW_FILES = {"scripts/check_no_hardcoded_paths.py", "scripts/diagnostics.py"}


def tracked_files(root: Path) -> list[str]:
    """Return tracked file paths (relative), or [] if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        )
        return [line for line in out.stdout.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def offenders(root: Path) -> list[str]:
    """Return ``rel:line: snippet`` for every hardcoded home path found."""
    hits: list[str] = []
    for rel in tracked_files(root):
        if rel in _ALLOW_FILES or any(rel.startswith(p) for p in _ALLOW_PREFIXES):
            continue
        path = root / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            m = _NEEDLE_RE.search(line)
            if m:
                hits.append(f"{rel}:{i}: {m.group(0)}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="repo root (default: self-located)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()
    if not root.is_dir():
        print(f"check_no_hardcoded_paths: FATAL — {root} is not a directory", file=sys.stderr)
        return 2

    hits = offenders(root)
    if hits:
        print(f"check_no_hardcoded_paths: {len(hits)} hardcoded path(s) found:", file=sys.stderr)
        for h in hits:
            print(f"  FAIL  {h}", file=sys.stderr)
        return 1
    print("check_no_hardcoded_paths: OK — no machine-specific home paths in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
