#!/usr/bin/env python3
"""check_secrets.py — secrets never in prompts / runtime (R-6 / ADR-006).

Scans the DGO-X event store (gitignored RUNTIME state, NOT covered by the
tracked-file gitleaks scan) for secret patterns in any event value — especially
the agent_invocation context_contract (the agent's prompt). Also scans
experiments/ records. Inert (exit 0) when there is no event store. Complements
gitleaks (which guards tracked files) by guarding the runtime prompt surface.

Exit codes: 0 = no secrets OR unmeasured, 1 = secret pattern found, 2 = usage.

Usage:
    python3 scripts/check_secrets.py [--events board/.events.jsonl] [--experiments experiments]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _paths import ROOT

SECRET_PAT = re.compile(
    r"(sk-ant-[a-z]+\d{2}-[A-Za-z0-9_-]{40,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{36}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def scan_text(text: str) -> bool:
    return SECRET_PAT.search(text) is not None


def scan_store(path: Path) -> list[str]:
    leaks: list[str] = []
    if not path.exists():
        return leaks
    for i, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if raw.strip() and scan_text(raw):
            try:
                ev = json.loads(raw)
                ref = ev.get("id") or ev.get("ticket_id") or f"line {i}"
            except json.JSONDecodeError:
                ref = f"line {i}"
            leaks.append(f"event {ref}: secret pattern in a runtime event value")
    return leaks


def scan_dir(path: Path) -> list[str]:
    leaks: list[str] = []
    if not path.exists():
        return leaks
    for f in sorted(path.rglob("*")):
        if not f.is_file():
            continue
        try:
            if scan_text(f.read_text(encoding="utf-8", errors="ignore")):
                leaks.append(f"{f.name}: secret pattern")
        except OSError:
            continue
    return leaks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    args = ap.parse_args(argv)

    leaks = scan_store(args.events) + scan_dir(args.experiments)
    if leaks:
        sys.stderr.write("FAIL: secrets in the runtime surface (R-6 / ADR-006):\n")
        for v in leaks:
            sys.stderr.write(f"  - {v}\n")
        return 1
    note = "no event store yet; " if not args.events.exists() else ""
    print(f"OK: {note}no secret patterns in the event store or experiments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
