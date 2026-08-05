#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import org_model

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPTS = ["governance", "engineering", "product", "design", "marketing", "operations"]
SKIP: set[str] = set()
MIN_CHARS = 40


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
            rel = f.as_posix()
        for name, heading_res in REQUIRED.items():
            body = _section_body(text, heading_res)
            if body is None:
                gaps.append((rel, f"missing section '## {name}'"))
            elif len(body) < MIN_CHARS:
                gaps.append((rel, f"section '## {name}' is thin (<{MIN_CHARS} chars)"))
    return gaps


def scan_role_charters(org) -> list[tuple[str, str]]:
    gaps: list[tuple[str, str]] = []
    for role in org.roles:
        where = f"config/org.yaml:roles[{role.key}].charter"
        for name, body in role.charter.sections():
            if not body.strip():
                gaps.append((where, f"missing section '{name}'"))
            elif len(body.strip()) < MIN_CHARS:
                gaps.append((where, f"section '{name}' is thin (<{MIN_CHARS} chars)"))
    return gaps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="fail closed (exit 1) on gaps")
    args = ap.parse_args(argv)

    try:
        org = org_model.load_org()
    except org_model.OrgConfigError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2

    if not org.roles:
        sys.stderr.write("ERROR: no role charters found\n")
        return 2

    overlays = _overlays()
    gaps = scan_role_charters(org) + scan(overlays)
    subjects = len(org.roles) + len(overlays)
    if not gaps:
        print(f"OK: {subjects} role charters all carry the contract sections.")
        return 0

    stream = sys.stderr if args.strict else sys.stdout
    n_roles = len({g[0] for g in gaps})
    stream.write(f"{'FAIL' if args.strict else 'WARN'}: overlay-section contract (ADR-0018) — {len(gaps)} gap(s) in {n_roles} role charter(s):\n")
    for rel, reason in gaps:
        stream.write(f"  - {rel}: {reason}\n")
    if args.strict:
        return 1
    stream.write("Warn-only (ADR-0018 rollout); flip to --strict once charters are filled.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
