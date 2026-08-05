#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from _paths import ROOT

_HOME_PREFIXES = ("/" + "Users" + "/", "/" + "home" + "/")
_NEEDLE_RE = re.compile(
    "(?:" + "|".join(re.escape(p) for p in _HOME_PREFIXES) + r")[A-Za-z0-9_.\-]+"
)


_ALLOW_PREFIXES = ("board/",)
_ALLOW_FILES = {"scripts/check_no_hardcoded_paths.py", "scripts/diagnostics.py"}


def tracked_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        )
        return [line for line in out.stdout.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def offenders(root: Path) -> list[str]:
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
    parser = argparse.ArgumentParser(description='check_no_hardcoded_paths.py — fail on any machine-specific absolute path.')
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
