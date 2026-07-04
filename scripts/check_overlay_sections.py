#!/usr/bin/env python3
"""check_overlay_sections.py — role-overlay contract (ADR-0018, ADR-0002, remediation P3).

Every role overlay (`<dept>/agents/<role>/AGENTS.md`) must carry the four contract
sections so a shipped role is actually defined, not a hollow stub (atom-audit P3):

  - ## Mission              — what this role exists to do
  - ## Scope                — what it owns / does NOT own
  - ## Definition of Done   — when its work is complete
  - ## Escalation           — when/how to escalate ("## When to escalate" is accepted)

Each section must be present AND non-trivial (>= MIN_CHARS of body).

Rollout (ADR-0018): ships WARN-ONLY (exit 0, prints gaps). Pass --strict to fail closed
once the overlays are filled.

Usage:
    python scripts/check_overlay_sections.py [--strict]

Exit 0 = clean (or warn-only). Exit 1 = gaps under --strict. Exit 2 = IO error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPTS = ["governance", "engineering", "product", "design", "marketing", "operations"]
SKIP: set[str] = set()  # (no external-runtime pilots)
MIN_CHARS = 40

# section key -> accepted heading regexes (case-insensitive)
REQUIRED = {
    "Mission": [r"^##\s+mission\b"],
    "Scope": [r"^##\s+scope\b"],
    "Definition of Done": [r"^##\s+definition of done\b"],
    "Escalation": [r"^##\s+escalation\b", r"^##\s+when to escalate\b"],
}


def _overlays() -> list[Path]:
    out: list[Path] = []
    for dept in DEPTS:
        d = REPO_ROOT / dept / "agents"
        if d.is_dir():
            for role in sorted(d.iterdir()):
                if role.name in SKIP:
                    continue
                f = role / "AGENTS.md"
                if f.is_file():
                    out.append(f)
    return out


def _section_body(text: str, heading_res: list[str]) -> str | None:
    """Return the body under the first matching heading (until the next ## ), or None."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if any(re.match(rx, line, re.IGNORECASE) for rx in heading_res):
            body: list[str] = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                body.append(nxt)
            return "\n".join(body).strip()
    return None


def scan(overlays: list[Path]) -> list[tuple[str, str]]:
    gaps: list[tuple[str, str]] = []
    for f in overlays:
        text = f.read_text(encoding="utf-8", errors="ignore")
        try:
            rel = f.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = f.as_posix()  # path outside the repo (e.g. a test fixture)
        for name, heading_res in REQUIRED.items():
            body = _section_body(text, heading_res)
            if body is None:
                gaps.append((rel, f"missing section '## {name}'"))
            elif len(body) < MIN_CHARS:
                gaps.append((rel, f"section '## {name}' is thin (<{MIN_CHARS} chars)"))
    return gaps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="fail closed (exit 1) on gaps")
    args = ap.parse_args(argv)

    overlays = _overlays()
    if not overlays:
        sys.stderr.write("ERROR: no role overlays found\n")
        return 2

    gaps = scan(overlays)
    if not gaps:
        print(f"OK: {len(overlays)} role overlays all carry the contract sections.")
        return 0

    stream = sys.stderr if args.strict else sys.stdout
    n_roles = len({g[0] for g in gaps})
    stream.write(f"{'FAIL' if args.strict else 'WARN'}: overlay-section contract (ADR-0018) — {len(gaps)} gap(s) in {n_roles} overlay(s):\n")
    for rel, reason in gaps:
        stream.write(f"  - {rel}: {reason}\n")
    if args.strict:
        return 1
    stream.write("Warn-only (ADR-0018 rollout); flip to --strict once overlays are filled.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
