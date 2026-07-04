#!/usr/bin/env python3
"""check_codeowners.py — .github/CODEOWNERS covers every area + matches generator.

Fails CI if any top-level tracked directory lacks a CODEOWNERS entry, or if
`.github/CODEOWNERS` has drifted from `gen_codeowners.py` output (someone hand-
edited it, or a new area was added without regenerating).

Exit codes
----------
0  CODEOWNERS present, complete, and in sync with the generator
1  missing area coverage or drift
2  usage / environment error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _paths import ROOT
from gen_codeowners import render, top_level_areas


def offenders(root: Path) -> list[str]:
    issues: list[str] = []
    path = root / ".github" / "CODEOWNERS"
    if not path.is_file():
        return [".github/CODEOWNERS is missing"]
    actual = path.read_text(encoding="utf-8")

    for area in top_level_areas(root):
        if f"/{area}/" not in actual:
            issues.append(f"no CODEOWNERS entry for /{area}/")
    if "*" not in actual:
        issues.append("no default '*' owner")

    if actual != render(root):
        issues.append("CODEOWNERS drifts from gen_codeowners.py — re-run the generator")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()
    if not root.is_dir():
        print(f"check_codeowners: FATAL — {root} is not a directory", file=sys.stderr)
        return 2

    issues = offenders(root)
    if issues:
        print(f"check_codeowners: {len(issues)} problem(s):", file=sys.stderr)
        for i in issues:
            print(f"  FAIL  {i}", file=sys.stderr)
        return 1
    print("check_codeowners: OK — every area covered; in sync with gen_codeowners.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
