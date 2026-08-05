#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROJECTS = REPO_ROOT / "projects"
DEFAULT_TICKETS = REPO_ROOT / "board" / "tickets"
QUEUE_NAME = "APPROVED-GOAL-QUEUE.md"


APPROVAL_RE = re.compile(
    r"(?<![\w-])(?:APPROVED|FOUNDER_APPROVED)\s*:"
    r"|(?<![\w-])TASDIQLANDI(?![\w-])",
    re.IGNORECASE,
)


def _fm_field(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    if end is None:
        return None
    for line in lines[1:end]:
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'").lower()
    return None


def _queue_approved(projects_dir: Path, slug: str) -> bool:
    queue = projects_dir / slug / QUEUE_NAME
    return queue.is_file() and bool(APPROVAL_RE.search(queue.read_text(encoding="utf-8", errors="ignore")))


def scan_queue_integrity(projects_dir: Path) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for queue in sorted(projects_dir.glob(f"*/{QUEUE_NAME}")):
        text = queue.read_text(encoding="utf-8", errors="ignore")
        if not APPROVAL_RE.search(text):
            violations.append(
                (queue.parent.name,
                 "queue present but no explicit Founder approval marker "
                 "(APPROVED: / TASDIQLANDI / founder_approved:) — the queue's own "
                 "name/title and per-goal status values do not count")
            )
    return violations


def scan_ticket_mapping(board_dir: Path, projects_dir: Path) -> list[tuple[str, str]]:
    if not projects_dir.is_dir() or not board_dir.is_dir():
        return []
    violations: list[tuple[str, str]] = []
    for md in sorted(board_dir.glob("DAS-*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        slug = _fm_field(text, "project")
        if not slug:
            continue
        if _fm_field(text, "status") == "backlog":
            continue
        if not _queue_approved(projects_dir, slug):
            violations.append(
                (md.name, f"declares project '{slug}' but projects/{slug}/{QUEUE_NAME} "
                          "is missing or not Founder-approved (QONUN-3)")
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default=str(DEFAULT_PROJECTS))
    ap.add_argument("--board", default=str(DEFAULT_TICKETS))
    args = ap.parse_args(argv)

    projects_dir = Path(args.projects)
    board_dir = Path(args.board)

    if not projects_dir.is_dir():

        print(f"OK: no projects/ directory ({projects_dir}) — nothing to check.")
        return 0

    queues = sorted(projects_dir.glob(f"*/{QUEUE_NAME}"))
    violations = scan_queue_integrity(projects_dir) + scan_ticket_mapping(board_dir, projects_dir)
    if violations:
        sys.stderr.write("FAIL: approved-goal-queue violations (QONUN-3):\n")
        for who, reason in violations:
            sys.stderr.write(f"  - {who}: {reason}\n")
        sys.stderr.write(f"\n{len(violations)} violation(s).\n")
        return 1

    print(f"OK: {len(queues)} queue(s) checked (integrity + local ticket→queue mapping), all Founder-approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
