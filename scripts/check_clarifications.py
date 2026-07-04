#!/usr/bin/env python3
"""check_clarifications.py — DasLab Definition-of-Ready gate (ADR-0014).

GitHub Spec Kit graft: enforces that a `[NEEDS CLARIFICATION: ...]` marker is
RESOLVED before a ticket leaves the planning altitude. A ticket that reached
``in_progress`` / ``in_review`` / ``done`` while still carrying an unresolved
marker means work proceeded on an under-specified Description — the documented
20-40% rework failure mode.

Two rules:
  1. Unresolved-marker-in-active-work: a ticket whose status is ``in_progress``,
     ``in_review``, or ``done`` MUST NOT contain an unresolved marker. (``backlog`` /
     ``todo`` / ``blocked`` may carry markers — the /daslab-cycle selection step
     routes a marked ``todo`` to a reviewer instead of dispatching it.)
  2. Too-many-markers: a dispatch-candidate ticket (``todo`` or active) with more
     than 3 markers is too under-specified to be ONE ticket — it must return to
     /daslab-plan for decomposition (Spec Kit's max-3 cap).

A marker shown as a CODE EXAMPLE (inside ``backticks`` or a fenced ``` block) is
documentation, not a live request — those are stripped before scanning, so a
ticket may legitimately describe the marker syntax. A genuine clarification is
written as plain prose in the Description (how /daslab-plan emits it).

Rollout (ADR-0014): ships WARN-ONLY (exit 0, prints findings to stdout). Pass
``--strict`` to fail closed (exit 1 on any finding) — the post-ADR-0013 flip.

Usage:
    python scripts/check_clarifications.py [--tickets board/tickets] [--strict]

Exit 0 = clean (or warn-only). Exit 1 = finding(s) under --strict. Exit 2 = IO error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TICKETS = REPO_ROOT / "board" / "tickets"

MARKER_RE = re.compile(r"\[NEEDS[ _]CLARIFICATION\b", re.IGNORECASE)
MAX_MARKERS = 3

# A marker is a defect once work has started or finished here.
ACTIVE_STATUSES = {"in_progress", "in_review", "done"}
# The > 3 cap applies to any dispatch-candidate ticket (everything but backlog).
NON_BACKLOG = {"todo", "in_progress", "in_review", "done", "blocked"}


def _status(text: str) -> str | None:
    """Extract the lowercased ``status:`` value from YAML frontmatter, dependency-free.

    Returns None when there is no frontmatter / no status line — such a ticket is
    skipped by the status-scoped rules rather than crashing the scan.
    """
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    if end is None:
        return None
    for line in lines[1:end]:
        if line.strip().startswith("status:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'").lower()
    return None


def _body(text: str) -> str:
    """Return the markdown body after the YAML frontmatter.

    A live clarification lives in the Description, never in the title/frontmatter
    (a ticket whose TITLE names the marker — e.g. the ADR-0014 tracking ticket — is
    not itself an unresolved request), so the frontmatter is excluded from scanning.
    """
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    return text if end is None else "\n".join(lines[end + 1:])


def _strip_code(text: str) -> str:
    """Drop fenced code blocks and inline code spans — markers shown there are docs."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def scan(tickets_dir: Path) -> list[tuple[str, str]]:
    """Return (ticket-file, reason) findings across the ticket files."""
    findings: list[tuple[str, str]] = []
    for path in sorted(tickets_dir.glob("DAS-*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        n = len(MARKER_RE.findall(_strip_code(_body(text))))
        if n == 0:
            continue
        status = _status(text)
        if status in ACTIVE_STATUSES:
            findings.append((path.name, f"{n} unresolved [NEEDS CLARIFICATION] marker(s) in status={status}"))
        if status in NON_BACKLOG and n > MAX_MARKERS:
            findings.append((path.name, f"{n} markers (> {MAX_MARKERS}); decompose via /daslab-plan"))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", default=str(DEFAULT_TICKETS))
    ap.add_argument("--strict", action="store_true",
                    help="fail closed (exit 1) on findings; default is warn-only (exit 0)")
    args = ap.parse_args(argv)

    tickets_dir = Path(args.tickets)
    if not tickets_dir.is_dir():
        sys.stderr.write(f"ERROR: tickets dir not found: {tickets_dir}\n")
        return 2

    findings = scan(tickets_dir)
    if not findings:
        print("OK: no unresolved [NEEDS CLARIFICATION] markers in active tickets.")
        return 0

    stream = sys.stderr if args.strict else sys.stdout
    stream.write(f"{'FAIL' if args.strict else 'WARN'}: Definition-of-Ready (ADR-0014) clarify-gate findings:\n")
    for name, reason in findings:
        stream.write(f"  - {name}: {reason}\n")
    stream.write(f"\n{len(findings)} finding(s). ")
    if args.strict:
        stream.write("Resolve markers (or decompose) before the ticket proceeds.\n")
        return 1
    stream.write("Warn-only (ADR-0014 rollout); flip to --strict after ADR-0013 ratifies.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
