#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT


SURFACE: tuple[str, ...] = (
    "design/CLAUDE.md",
    "engineering/CLAUDE.md",
    "marketing/CLAUDE.md",
    "operations/CLAUDE.md",
    "product/CLAUDE.md",
    "governance/CLAUDE.md",
    ".claude/agents/*.md",
)


_VERB = (
    r"(?:override|overrides|overriding|ignore|ignores|relax|relaxes|waive|waives|"
    r"bypass|bypasses|disregard|supersede|supersedes|nullif(?:y|ies)|"
    r"exempt(?:\s+from)?|opt\s+out\s+of)"
)
_TARGET = (
    r"(?:board\s+)?(?:policy|policies|gate|law|qonun|rule|constraint|precedence|"
    r"model[-\s]?allocation|raci|quality[-\s]?bar|lifecycle)"
)

_RELAX_FORWARD = re.compile(rf"\b{_VERB}\b[^.\n]{{0,48}}\b{_TARGET}\b", re.IGNORECASE)

_RELAX_REVERSE = re.compile(
    rf"\b{_TARGET}\b[^.\n]{{0,48}}\b(?:no longer applies|does not apply|is waived|"
    rf"is relaxed|may be (?:overridden|ignored|relaxed|waived)|can be (?:ignored|overridden|waived))",
    re.IGNORECASE,
)


def find_violations(files: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _RELAX_FORWARD.search(line) or _RELAX_REVERSE.search(line):
                violations.append(f"{rel}:{lineno}: relaxes a binding rule → {line.strip()[:90]}")
    return violations


def collect_surface(root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in SURFACE:
        files.extend(sorted(root.glob(pattern)))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description='check_precedence.py — enforce the precedence law in code.\n\ngovernance/charter.md §7 and AGENTS.md §2 bind every *lower-precedence* document\n(department charters, role overlays) to ADD constraints only — never to relax,\noverride, waive, or supersede a higher-level board policy / law / gate. The rule\nwas prose-only, so nothing stopped a department charter from quietly redefining\nmodel-allocation or declaring a gate "waived". This validator fails CI when a\nlower-precedence file contains relaxation language aimed at a binding rule.\n\nSurface (lower-precedence files):\n    <dept>/CLAUDE.md  department charters\n    .claude/agents/*.md  role overlays\n\nOut of scope by construction: governance/policies/** and governance/charter.md\n(they *set* constraints), and this scanner itself (it names the patterns as data).\n\nExit codes\n----------\n0  no precedence violation in the lower-precedence surface\n1  at least one lower-precedence file relaxes a binding rule\n2  usage / environment error')
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    files = collect_surface(args.root)
    violations = find_violations(files)

    if violations:
        print("Precedence violations (lower-precedence files may not relax board rules):")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} violation(s). See governance/charter.md §7 / AGENTS.md §2.")
        return 1

    print(f"check_precedence: OK — {len(files)} lower-precedence file(s) add-only, none relax a binding rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
