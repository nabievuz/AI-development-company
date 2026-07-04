#!/usr/bin/env python3
"""check_spec_consistency.py — Phase 2 SPEC.md consistency (ADR-0015, ADR-0002).

Validates the OPTIONAL, size-gated per-epic SPEC.md layer (spec-kit Phase 2):

A. STRUCTURE — every SPEC.md that exists has the three sections (User Scenarios /
   Functional Requirements / Success Criteria), >= 1 `FR-NNN`, and unique FR + SC ids.

B. NO DANGLING REFS — a board ticket that declares `spec: <slug>` must point at a real
   spec, and every id in its `implements: [FR-001, ...]` must be defined in that spec.

Structural limit (honest, matches ADR-0015): passes when no SPEC.md exists (today and on
a fresh CI runner). The `docs/specs/templates/` template is skipped. Project specs under
gitignored `projects/<slug>/specs/` are validated only locally. The reverse "every FR is
covered by a ticket" is deliberately NOT a hard gate (it would false-fail a fresh spec) —
that is a planner/reviewer judgement.

Usage:
    python scripts/check_spec_consistency.py [--specs docs/specs] [--projects projects] [--board board/tickets]

Exit 0 = clean. Exit 1 = violation(s). Exit 2 = usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPECS = REPO_ROOT / "docs" / "specs"
DEFAULT_PROJECTS = REPO_ROOT / "projects"
DEFAULT_BOARD = REPO_ROOT / "board" / "tickets"

SPEC_NAME = "SPEC.md"
REQUIRED_SECTIONS = ("## User Scenarios", "## Functional Requirements", "## Success Criteria")
FR_RE = re.compile(r"\bFR-\d+\b")
SC_RE = re.compile(r"\bSC-\d+\b")
ID_RE = re.compile(r"\b(?:FR|SC)-\d+\b")


def _spec_files(specs_dir: Path, projects_dir: Path) -> list[Path]:
    files: list[Path] = []
    roots = [specs_dir]
    if projects_dir.is_dir():
        roots += sorted(projects_dir.glob("*/specs"))
    for root in roots:
        if root.is_dir():
            files += [p for p in sorted(root.rglob(SPEC_NAME)) if "templates" not in p.parts]
    return files


def check_structure(text: str) -> list[str]:
    errs: list[str] = []
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            errs.append(f"missing section '{sec}'")
    frs = FR_RE.findall(text)
    if not frs:
        errs.append("no FR-NNN functional requirements")
    if len(frs) != len(set(frs)):
        errs.append("duplicate FR ids")
    scs = SC_RE.findall(text)
    if len(scs) != len(set(scs)):
        errs.append("duplicate SC ids")
    return errs


def _fm_field_raw(text: str, key: str) -> str | None:
    """Return the raw frontmatter value string for *key* (or None)."""
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    if end is None:
        return None
    for line in lines[1:end]:
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def scan(specs_dir: Path, projects_dir: Path, board_dir: Path) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    specs_by_slug: dict[str, set[str]] = {}

    for spec in _spec_files(specs_dir, projects_dir):
        text = spec.read_text(encoding="utf-8", errors="ignore")
        slug = spec.parent.name
        for err in check_structure(text):
            violations.append((f"{slug}/{SPEC_NAME}", err))
        specs_by_slug[slug] = set(ID_RE.findall(text))

    if board_dir.is_dir():
        for md in sorted(board_dir.glob("DAS-*.md")):
            text = md.read_text(encoding="utf-8", errors="ignore")
            slug = _fm_field_raw(text, "spec")
            impl_raw = _fm_field_raw(text, "implements")
            if not slug and not impl_raw:
                continue
            slug = (slug or "").strip().strip('"').strip("'")
            if slug and slug not in specs_by_slug:
                violations.append((md.name, f"spec: '{slug}' has no SPEC.md under docs/specs or projects/*/specs"))
                continue
            if impl_raw and slug:
                known = specs_by_slug.get(slug, set())
                for ref in ID_RE.findall(impl_raw):
                    if ref not in known:
                        violations.append((md.name, f"implements {ref} not defined in spec '{slug}'"))
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(DEFAULT_SPECS))
    ap.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    ap.add_argument("--board", default=str(DEFAULT_BOARD))
    args = ap.parse_args(argv)

    specs_dir = Path(args.specs)
    projects_dir = Path(args.projects)
    board_dir = Path(args.board)

    n_specs = len(_spec_files(specs_dir, projects_dir))
    violations = scan(specs_dir, projects_dir, board_dir)
    if violations:
        sys.stderr.write("FAIL: SPEC.md consistency violations (ADR-0015):\n")
        for who, reason in violations:
            sys.stderr.write(f"  - {who}: {reason}\n")
        sys.stderr.write(f"\n{len(violations)} violation(s).\n")
        return 1

    print(f"OK: {n_specs} SPEC.md file(s) checked, structure + ticket refs consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
