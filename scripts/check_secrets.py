#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from _paths import ROOT

EXIT_OK = 0
EXIT_LEAK = 1
EXIT_USAGE = 2
EXIT_NO_DATA = 3


@dataclass(frozen=True)
class SecretPattern:
    kind: str
    pattern: re.Pattern[str]


SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("anthropic_api_key", re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}")),
    SecretPattern("openrouter_api_key", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{32,}")),
    SecretPattern("stripe_live_key", re.compile(r"\bsk_live_[0-9A-Za-z]{16,}")),
    SecretPattern("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    SecretPattern("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    SecretPattern("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    SecretPattern("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    SecretPattern("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    SecretPattern("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
)


def detect_secret_kinds(text: str) -> list[str]:
    return [sp.kind for sp in SECRET_PATTERNS if sp.pattern.search(text)]


def scan_text(text: str) -> bool:
    return bool(detect_secret_kinds(text))


def scan_store(path: Path) -> list[str]:
    leaks: list[str] = []
    if not path.exists():
        return leaks
    for i, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if not raw.strip():
            continue
        kinds = detect_secret_kinds(raw)
        if not kinds:
            continue
        try:
            ev = json.loads(raw)
            ref = ev.get("id") or ev.get("ticket_id") or f"line {i}"
        except json.JSONDecodeError:
            ref = f"line {i}"
        leaks.append(f"event {ref}: {', '.join(kinds)} in a runtime event value")
    return leaks


def scan_dir(path: Path) -> list[str]:
    leaks: list[str] = []
    if not path.exists():
        return leaks
    for f in sorted(path.rglob("*")):
        if not f.is_file():
            continue
        try:
            kinds = detect_secret_kinds(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if kinds:
            leaks.append(f"{f.name}: {', '.join(kinds)}")
    return leaks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_secrets.py",
        description="check_secrets.py — secrets never in prompts / runtime (R-6 / ADR-006).",
        epilog=f"exit codes: {EXIT_OK} clean · {EXIT_LEAK} secret found · "
               f"{EXIT_USAGE} usage error · {EXIT_NO_DATA} nothing to scan",
    )
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl",
                    help="runtime event store to scan (JSONL)")
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments",
                    help="experiments directory to scan recursively")
    ap.add_argument("--list-patterns", action="store_true",
                    help="print the secret pattern kinds this scanner recognises and exit")
    args = ap.parse_args(argv)

    if args.list_patterns:
        for sp in SECRET_PATTERNS:
            print(f"{sp.kind}\t{sp.pattern.pattern}")
        return EXIT_OK

    if not args.events.exists() and not args.experiments.exists():
        sys.stderr.write(
            "NO DATA: neither the event store nor the experiments directory exists; "
            "nothing was scanned — this is not a pass.\n"
        )
        return EXIT_NO_DATA

    leaks = scan_store(args.events) + scan_dir(args.experiments)
    if leaks:
        sys.stderr.write("FAIL: secrets in the runtime surface (R-6 / ADR-006):\n")
        for v in leaks:
            sys.stderr.write(f"  - {v}\n")
        return EXIT_LEAK
    note = "no event store yet; " if not args.events.exists() else ""
    print(f"OK: {note}no secret patterns in the event store or experiments.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
