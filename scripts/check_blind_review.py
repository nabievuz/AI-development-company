#!/usr/bin/env python3
"""check_blind_review.py — Blind review + reviewer rotation (T6 anti-drift).

T6 reviewer drift / rubber-stamping is a HIGH risk: mitigate with BLIND review
(the reviewer does not see the author's identity), reviewer ROTATION (no reviewer
repeatedly reviews the same author -> norm formation), and calibration sessions.
Validates `review` events. Inert when there are no reviews yet.

Exit codes: 0 = blind + rotated OR unmeasured, 1 = non-blind / over-paired review, 2 = usage.

Usage:
    python3 scripts/check_blind_review.py [--events board/.events.jsonl] [--max-same-pair 3]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT

MAX_SAME_PAIR = 3


def _is_true(value) -> bool:
    """Strict boolean — a STRING 'false'/'no'/'0' must NOT pass as blind."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _norm_id(value) -> str:
    """Normalize an identity (case/whitespace) so 'Eng-1' and 'eng-1 ' are the same human."""
    return str(value).strip().lower() if value not in (None, "") else ""


def violations(reviews: list[dict], max_same_pair: int = MAX_SAME_PAIR) -> list[str]:
    probs: list[str] = []
    for r in reviews:
        tid = str(r.get("ticket_id", "?"))
        if not _is_true(r.get("blind", False)):
            probs.append(f"{tid}: review not blind (reviewer saw the author identity)")
        rev, auth = _norm_id(r.get("reviewer")), _norm_id(r.get("author"))
        if not rev or not auth:
            probs.append(f"{tid}: review missing reviewer/author identity")
        elif rev == auth:
            probs.append(f"{tid}: self-review (reviewer == author)")

    pair_counts: dict[tuple, int] = {}
    for r in reviews:
        rev, auth = _norm_id(r.get("reviewer")), _norm_id(r.get("author"))
        if rev and auth:
            pair_counts[(rev, auth)] = pair_counts.get((rev, auth), 0) + 1
    for (rev, auth), count in sorted(pair_counts.items()):
        if count > max_same_pair:
            probs.append(
                f"reviewer '{rev}' reviewed author '{auth}' {count}x (> {max_same_pair}); "
                f"rotate to prevent norm formation"
            )
    return probs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--max-same-pair", type=int, default=MAX_SAME_PAIR)
    args = ap.parse_args(argv)

    events = wave_kpi.read_events(str(args.events))
    reviews = [e for e in events if e.get("event_type") == "review"]
    if not reviews:
        print("Blind review: unmeasured — no review events yet. Gate inert (loop off).")
        return 0

    calibrations = sum(1 for e in events if e.get("event_type") == "review_calibration")
    probs = violations(reviews, args.max_same_pair)
    if probs:
        sys.stderr.write("FAIL: blind review / rotation (T6 anti-drift):\n")
        for p in probs:
            sys.stderr.write(f"  - {p}\n")
        return 1

    print(f"OK: {len(reviews)} review(s) blind + rotated; {calibrations} calibration session(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
