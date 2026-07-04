#!/usr/bin/env python3
"""check_spans.py — span-coverage and well-formedness validator (DAS-1456).

Reads the DGO-X event store via wave_kpi.read_events (single source of truth)
and verifies three properties:

  1. **Coverage**: every dispatched ticket (``run_start`` event) has a matching
     ``span`` event paired by ``run_id``.
  2. **Validity**: every ``span`` event passes ``dgox.events.validate_span``
     (all required fields, ``trace_id == ticket_id``, ``duration_ms`` derived
     from ``end - start``, ``cached`` consistent with ``cached_input_tokens``).
  3. **Reconciliation seam**: where a ``run_end`` carries a ``token_total``
     field, the per-run sum of span input+output tokens must match. The seam
     passes inertly when ``token_total`` is absent on ``run_end`` (the
     cost-ledger lands in slice-2; this validator never fabricates a number).

Inert-by-design: exits 0 with a clear "no events" message when the event store
is absent or empty. Fails (exit 1) only when live events exist and a dispatch
is missing its span, a span is malformed, or a present token-sum reconciliation
fails.

Exit codes:
  0 — all spans well-formed, OR inert (store absent / empty / no dispatches).
  1 — at least one span is missing, malformed, or a token reconciliation fails.
  2 — usage / IO error.

Usage:
    python3 scripts/check_spans.py [--events board/.events.jsonl]
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path: ensure scripts/ is importable so dgox sub-package resolves when this
# script is invoked directly.  Tests and other callers that already have
# scripts/ on sys.path are unaffected (the guard is idempotent).
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wave_kpi  # noqa: E402
from _paths import ROOT  # noqa: E402
from dgox.events import validate_span  # noqa: E402

# ---------------------------------------------------------------------------
# Token reconciliation seam (slice-2 cost-ledger — inert when fields absent)
# ---------------------------------------------------------------------------

def _reconcile_tokens(
    events: list[dict],
    span_events: list[dict],
) -> list[str]:
    """Return a list of token-sum mismatch descriptions (empty when clean).

    For each ``run_id`` that appears on at least one span, sum
    ``gen_ai.usage.input_tokens`` + ``gen_ai.usage.output_tokens`` across
    all spans for that run.  If the corresponding ``run_end`` event carries
    a ``token_total`` field, verify the sums match.

    Returns ``[]`` trivially (inert) when no ``run_end`` carries
    ``token_total`` — the cost-ledger is slice-2 and the field is not
    emitted today.  Never fabricates a value.
    """
    # Build per-run span token sums.
    span_sums: dict[str, int] = {}
    for sp in span_events:
        rid = sp.get("run_id")
        if not rid:
            continue
        inp = sp.get("gen_ai.usage.input_tokens", 0) or 0
        out = sp.get("gen_ai.usage.output_tokens", 0) or 0
        span_sums[rid] = span_sums.get(rid, 0) + int(inp) + int(out)

    # Build per-run token_total from run_end events (slice-2 seam).
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
        # No run_end carries token_total yet — cost-ledger slice-2. Inert.
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--events",
        type=Path,
        default=ROOT / "board" / ".events.jsonl",
        help="Path to the DGO-X JSONL event store (default: board/.events.jsonl).",
    )
    args = ap.parse_args(argv)

    # Single reader: wave_kpi.read_events is the one source of truth.
    events = wave_kpi.read_events(str(args.events))
    if not events:
        print(
            "check_spans: no events — store absent or empty. "
            "Inert (loop off; no dispatches yet)."
        )
        return 0

    # Collect dispatched run_ids (run_start = one dispatch per ticket).
    dispatched_run_ids: set[str] = set()
    for ev in events:
        if ev.get("event_type") == "run_start":
            rid = ev.get("run_id")
            if rid:
                dispatched_run_ids.add(str(rid))

    # Collect span events.
    span_events = [ev for ev in events if ev.get("event_type") == "span"]

    if not dispatched_run_ids and not span_events:
        print(
            "check_spans: events present but no dispatches or spans found. "
            "Inert (nothing to validate)."
        )
        return 0

    failures: list[str] = []

    # --- Check 1: coverage — every dispatch has a matching span by run_id ---
    span_run_ids: set[str] = set()
    for sp in span_events:
        rid = sp.get("run_id")
        if rid:
            span_run_ids.add(str(rid))

    missing = sorted(dispatched_run_ids - span_run_ids)
    for rid in missing:
        failures.append(f"dispatch run_id={rid!r} has no matching span event")

    # --- Check 2: validity — every span must be well-formed ---
    for sp in span_events:
        errs = validate_span(sp)
        if errs:
            sid = sp.get("span_id", "<no span_id>")
            rid = sp.get("run_id", "<no run_id>")
            for err in errs:
                failures.append(f"span span_id={sid!r} run_id={rid!r}: {err}")

    # --- Check 3: token reconciliation (inert when cost-ledger absent) ---
    token_mismatches = _reconcile_tokens(events, span_events)
    failures.extend(token_mismatches)

    # --- Report ---
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
