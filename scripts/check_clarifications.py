#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TICKETS = REPO_ROOT / "board" / "tickets"

MARKER_RE = re.compile(r"\[NEEDS[ _]CLARIFICATION\b", re.IGNORECASE)
MAX_MARKERS = 3


ACTIVE_STATUSES = {"in_progress", "in_review", "done"}

NON_BACKLOG = {"todo", "in_progress", "in_review", "done", "blocked"}


def _status(text: str) -> str | None:
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
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    return text if end is None else "\n".join(lines[end + 1:])


def _strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def scan(tickets_dir: Path) -> list[tuple[str, str]]:
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
