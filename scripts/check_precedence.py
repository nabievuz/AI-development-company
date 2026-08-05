#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import org_model
from _paths import ROOT


def surface_patterns(org=None) -> tuple[str, ...]:
    org = org or org_model.load_org()
    patterns: list[str] = []
    for level in org.levels_with_authority(org_model.Authority.ADD_ONLY):
        for pattern in level.paths:
            if pattern not in patterns:
                patterns.append(pattern)
    patterns.append(".claude/agents/*.md")
    return tuple(patterns)


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


def collect_surface(root: Path, org=None) -> list[Path]:
    files: list[Path] = []
    for pattern in surface_patterns(org):
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path not in files:
                files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description='check_precedence.py — enforce the precedence law in code')
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
