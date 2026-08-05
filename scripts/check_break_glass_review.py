#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import break_glass as bg
from _paths import ROOT

DEFAULT_STORE = ROOT / "board" / ".events.jsonl"


def find_problems(activations: list[dict], reviews: list[dict], now: datetime) -> list[str]:
    closed = [
        (bg.parse_ts(str(r.get("created_at", ""))), str(r.get("review_for")))
        for r in reviews
        if str(r.get("status", "")).lower() == "closed" and r.get("review_for")
    ]

    problems: list[str] = []
    valid: list[tuple[datetime, str, datetime]] = []
    for a in activations:
        aid = str(a.get("activation_id", a.get("id", "?")))
        start = bg.parse_ts(str(a.get("created_at", "")))
        if start is None:
            problems.append(f"{aid}: activation has no valid created_at")
        else:
            valid.append((start, aid, start + timedelta(hours=bg.REVIEW_DEADLINE_HOURS)))

    def eligible(act_i: int, rev_j: int) -> bool:
        start, aid, deadline = valid[act_i]
        t, rfor = closed[rev_j]
        return t is not None and rfor == aid and start <= t <= deadline


    review_owner = [-1] * len(closed)

    def assign(act_i: int, seen: list[bool]) -> bool:
        for rev_j in range(len(closed)):
            if seen[rev_j] or not eligible(act_i, rev_j):
                continue
            seen[rev_j] = True
            if review_owner[rev_j] == -1 or assign(review_owner[rev_j], seen):
                review_owner[rev_j] = act_i
                return True
        return False

    for act_i in range(len(valid)):
        assign(act_i, [False] * len(closed))

    matched = set(review_owner)
    for act_i, (_, aid, deadline) in enumerate(valid):
        if act_i not in matched and now > deadline:
            problems.append(f"{aid}: no closed post-incident review within 24h (missing/late/pre-dated)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_break_glass_review.py — enforce the 24h post-incident review (R-8 / ADR-008).')
    ap.add_argument("--events", type=Path, default=DEFAULT_STORE)
    ap.add_argument("--now", default=None, help="ISO-8601 Z 'now' override (default: current UTC)")
    args = ap.parse_args(argv)

    if not args.events.exists():
        print(f"OK: no event store yet ({args.events}); no break-glass activations to review.")
        return 0

    now = bg.parse_ts(args.now) if args.now else datetime.now(tz=UTC)
    if now is None:
        sys.stderr.write(f"ERROR: --now must be ISO-8601 Z; got {args.now!r}\n")
        return 2

    events = bg.read_events(str(args.events))
    activations = [e for e in events if e.get("event_type") == bg.ACTIVATION_EVENT]
    reviews = [e for e in events if e.get("event_type") == bg.REVIEW_EVENT]

    problems = find_problems(activations, reviews, now)
    if problems:
        sys.stderr.write("FAIL: BREAK-GLASS post-incident review (R-8 / ADR-008):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1

    print(f"OK: {len(activations)} break-glass activation(s), all reviewed within 24h.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
