#!/usr/bin/env python3
"""approval_digest.py — Approval-Queue Digest.

Batches the low-risk pending approvals into a single digest so the Founder is not
worn down by approval fatigue (which causes the rubber-stamping the platform is
built to prevent), while routing any never-auto-approve (QONUN-5) item to an
INDIVIDUAL human review. Reads board tickets in status 'in_review'. Inert when none pending.

Usage:
    python3 scripts/approval_digest.py [--board board]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import check_never_auto_approve as nap
from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


def build_digest(tickets: list[dict], taxonomy: dict) -> dict:
    never = taxonomy.get("never_auto_approve", [])
    matchers = taxonomy.get("matchers", {}) or {}
    batchable, individual = [], []
    for t in tickets:
        if str(t.get("status", "")).lower() != "in_review":
            continue
        cats = [c for c in never if nap.matches_category(t, matchers.get(c, {}))]
        entry = {"id": t.get("id"), "title": t.get("title", ""), "categories": cats}
        (individual if cats else batchable).append(entry)
    return {"batchable_low_risk": batchable, "needs_individual_review": individual}


def render_digest(digest: dict) -> str:
    lines = ["Approval-Queue Digest",
             f"  batchable (low-risk, approve as a batch): {len(digest['batchable_low_risk'])}"]
    for e in digest["batchable_low_risk"]:
        lines.append(f"    - {e['id']}: {e['title']}")
    lines.append(f"  individual human review (QONUN-5): {len(digest['needs_individual_review'])}")
    for e in digest["needs_individual_review"]:
        lines.append(f"    - {e['id']}: {e['title']}  [{', '.join(e['categories'])}]")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--board", type=Path, default=ROOT / "board")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "risk_taxonomy.yaml")
    args = ap.parse_args(argv)

    if not args.config.is_file():
        sys.stderr.write(f"ERROR: risk taxonomy not found: {args.config}\n")
        return 2
    try:
        # Fail CLOSED: a malformed taxonomy must error, NEVER default to {} (which
        # would empty never_auto_approve and batch every QONUN-5 ticket).
        taxonomy = yaml.safe_load(args.config.read_text())
    except yaml.YAMLError as exc:
        sys.stderr.write(f"ERROR: invalid risk taxonomy: {exc}\n")
        return 2
    taxonomy = taxonomy or {}

    tickets: list[dict] = []
    malformed: list[str] = []
    tickets_dir = args.board / "tickets"
    if tickets_dir.is_dir():
        for f in sorted(tickets_dir.glob("DAS-*.md")):
            try:
                fm = nap.parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if fm is None:
                malformed.append(f.name)  # unparseable/smuggled -> surface for review
            elif fm:
                tickets.append(fm)

    digest = build_digest(tickets, taxonomy)
    for name in malformed:
        digest["needs_individual_review"].append(
            {"id": name, "title": "(unparseable/smuggled frontmatter)",
             "categories": ["unparseable-or-smuggled-frontmatter"]})
    if not digest["batchable_low_risk"] and not digest["needs_individual_review"]:
        print("Approval-Queue Digest: no pending (in_review) approvals. Inert.")
        return 0
    print(render_digest(digest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
