#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wave_kpi
from _paths import ROOT
from dgox.events import validate_span


def _reconcile_tokens(
    events: list[dict],
    span_events: list[dict],
) -> list[str]:

    span_sums: dict[str, int] = {}
    for sp in span_events:
        rid = sp.get("run_id")
        if not rid:
            continue
        inp = sp.get("gen_ai.usage.input_tokens", 0) or 0
        out = sp.get("gen_ai.usage.output_tokens", 0) or 0
        span_sums[rid] = span_sums.get(rid, 0) + int(inp) + int(out)


    run_end_totals: dict[str, int] = {}
    for ev in events:
        if ev.get("event_type") != "run_end":
            continue
        rid = ev.get("run_id")
        total = ev.get("token_total")
        if rid and total is not None:
            with contextlib.suppress(TypeError, ValueError):
                run_end_totals[str(rid)] = int(total)

    if not run_end_totals:

        return []

    mismatches: list[str] = []
    for rid, expected in run_end_totals.items():
        actual = span_sums.get(rid, 0)
        if actual != expected:
            mismatches.append(
                f"run_id={rid}: run_end.token_total={expected} != "
                f"sum(span tokens)={actual}"
            )
    return mismatches


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_spans.py — span-coverage and well-formedness validator (DAS-1456).')
    ap.add_argument(
        "--events",
        type=Path,
        default=ROOT / "board" / ".events.jsonl",
        help="Path to the DGO-X JSONL event store (default: board/.events.jsonl).",
    )
    args = ap.parse_args(argv)


    events = wave_kpi.read_events(str(args.events))
    if not events:
        print(
            "check_spans: no events — store absent or empty. "
            "Inert (loop off; no dispatches yet)."
        )
        return 0


    dispatched_run_ids: set[str] = set()
    for ev in events:
        if ev.get("event_type") == "run_start":
            rid = ev.get("run_id")
            if rid:
                dispatched_run_ids.add(str(rid))


    span_events = [ev for ev in events if ev.get("event_type") == "span"]

    if not dispatched_run_ids and not span_events:
        print(
            "check_spans: events present but no dispatches or spans found. "
            "Inert (nothing to validate)."
        )
        return 0

    failures: list[str] = []


    span_run_ids: set[str] = set()
    for sp in span_events:
        rid = sp.get("run_id")
        if rid:
            span_run_ids.add(str(rid))

    missing = sorted(dispatched_run_ids - span_run_ids)
    for rid in missing:
        failures.append(f"dispatch run_id={rid!r} has no matching span event")


    for sp in span_events:
        errs = validate_span(sp)
        if errs:
            sid = sp.get("span_id", "<no span_id>")
            rid = sp.get("run_id", "<no run_id>")
            for err in errs:
                failures.append(f"span span_id={sid!r} run_id={rid!r}: {err}")


    token_mismatches = _reconcile_tokens(events, span_events)
    failures.extend(token_mismatches)


    if not failures:
        dispatched_n = len(dispatched_run_ids)
        span_n = len(span_events)
        print(
            f"check_spans OK: {dispatched_n} dispatch(es), {span_n} span(s) — "
            f"all well-formed, coverage 100%."
        )
        return 0

    sys.stderr.write(
        f"check_spans FAIL: {len(failures)} issue(s) found:\n"
    )
    for msg in failures:
        sys.stderr.write(f"  - {msg}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
