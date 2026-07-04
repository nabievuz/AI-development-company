#!/usr/bin/env python3
"""check_cost.py — C1 cost-ledger informational reader (ORGANISM WS3 P12 / DAS-1459).

Reads ``span`` events from the DGO-X event store, aggregates token counts and
estimated USD cost per ticket, per agent, per tier, and per run via
``scripts/cost/cost_ledger.py``, then prints a human-readable summary.

Inert-by-design
---------------
When the event store is absent or contains no ``span`` events this script
prints a short message and exits 0 — identical to the pattern in
``scripts/check_busy_fraction.py`` and every other T-gate reader.  The cost
lever is *informational* (like T6 review-efficiency); it does NOT block CI
unless the caller passes ``--max`` and a live cap in ``config/budgets.yaml``
is exceeded.

Exit codes
----------
0  No span events (inert), OR spans present and no cap exceeded, OR ``--max``
   not passed.
1  ``--max`` was passed AND estimated total cost exceeds the per-run cap from
   ``config/budgets.yaml`` AND at least one span event exists.
2  Usage / IO error (missing budgets.yaml, unreadable store, etc.).

Usage
-----
    python3 scripts/check_cost.py
    python3 scripts/check_cost.py --events board/.events.jsonl
    python3 scripts/check_cost.py --max          # enforce per-run cost cap
    python3 scripts/check_cost.py --ticket DAS-1234
    python3 scripts/check_cost.py --run <run_id>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make sure scripts/ is on the path so cost.cost_ledger + dgox.events import.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cost.cost_ledger import (  # noqa: E402
    TokenGroup,
    aggregate_spans,
    check_reconciliation,
)

# ---------------------------------------------------------------------------
# Config path (self-locating root LAW A)
# ---------------------------------------------------------------------------

_ROOT = _SCRIPTS.parent
_BUDGETS_PATH = _ROOT / "config" / "budgets.yaml"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_cost(usd: float) -> str:
    return f"${usd:.6f}"


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def _print_axis(title: str, groups: dict[str, TokenGroup]) -> None:
    if not groups:
        return
    print(f"\n  {title}")
    print(f"  {'key':<40}  {'in_tok':>12}  {'cache_tok':>10}  {'out_tok':>10}  {'cost_usd':>12}")
    print("  " + "-" * 90)
    for key, g in sorted(groups.items(), key=lambda kv: -kv[1].estimated_cost_usd):
        print(
            f"  {key:<40}  "
            f"{_fmt_tokens(g.input_tokens):>12}  "
            f"{_fmt_tokens(g.cached_input_tokens):>10}  "
            f"{_fmt_tokens(g.output_tokens):>10}  "
            f"{_fmt_cost(g.estimated_cost_usd):>12}"
        )


def _load_run_cap(budgets_path: Path) -> float | None:
    """Read ``caps.per_run.max_cost_usd`` from budgets.yaml; None on failure."""
    try:
        import re
        text = budgets_path.read_text(encoding="utf-8")
        # Find per_run block, then max_cost_usd inside it.
        m = re.search(r"per_run:\s*\n(?:[ \t]+\S[^\n]*\n)*?[ \t]+max_cost_usd:\s*([\d.]+)", text)
        if m:
            return float(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--events", type=Path,
        default=None,
        help="Path to the DGO-X JSONL event store (default: board/.events.jsonl)",
    )
    ap.add_argument(
        "--budgets", type=Path,
        default=_BUDGETS_PATH,
        help="Path to config/budgets.yaml",
    )
    ap.add_argument(
        "--max", action="store_true",
        help="Enforce the per-run cost cap from budgets.yaml (exit 1 if exceeded)",
    )
    ap.add_argument("--ticket", help="Filter to a single ticket_id (informational)")
    ap.add_argument("--run", help="Filter to a single run_id (informational)")
    args = ap.parse_args(argv)

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    try:
        ledger = aggregate_spans(
            store_path=args.events,
            budgets_path=args.budgets,
        )
    except FileNotFoundError as exc:
        sys.stderr.write(f"check_cost: cannot open required file: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"check_cost: error during aggregation: {exc}\n")
        return 2

    if ledger is None:
        print(
            "C1 cost ledger: no span events yet. "
            "Gate inert (loop off / no waves run). "
            "Exit 0."
        )
        return 0

    # ------------------------------------------------------------------
    # Reconciliation check (always — a violation is a bug, not a gate)
    # ------------------------------------------------------------------
    recon_errors = check_reconciliation(ledger)
    if recon_errors:
        sys.stderr.write("check_cost: RECONCILIATION FAILURE (bug in cost_ledger.py):\n")
        for err in recon_errors:
            sys.stderr.write(f"  {err}\n")
        return 2

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print("C1 cost ledger — DasLab token and cost summary")
    print("=" * 72)
    print(f"  Total spans processed : {ledger.raw_span_count:,}")
    print(
        f"  Raw token totals      : "
        f"input={_fmt_tokens(ledger.raw_input_tokens)}  "
        f"cache_read={_fmt_tokens(ledger.raw_cached_input_tokens)}  "
        f"output={_fmt_tokens(ledger.raw_output_tokens)}"
    )
    print(f"  Estimated total cost  : {_fmt_cost(ledger.raw_estimated_cost_usd)}")
    if ledger.unknown_tiers:
        print(
            f"  Unknown tiers (no price): {sorted(ledger.unknown_tiers)} "
            f"(tokens counted, cost = $0.00)"
        )

    _print_axis("Per ticket", ledger.by_ticket)
    _print_axis("Per agent", ledger.by_agent)
    _print_axis("Per tier", ledger.by_tier)
    _print_axis("Per run", ledger.by_run)

    # ------------------------------------------------------------------
    # Optional cap enforcement (--max only)
    # ------------------------------------------------------------------
    if args.max:
        cap = _load_run_cap(args.budgets)
        if cap is None:
            sys.stderr.write(
                "check_cost --max: could not read caps.per_run.max_cost_usd from "
                f"{args.budgets}\n"
            )
            return 2
        if ledger.raw_estimated_cost_usd > cap:
            msg = (
                f"\nFAIL: estimated total cost "
                f"{_fmt_cost(ledger.raw_estimated_cost_usd)} "
                f"> per-run cap {_fmt_cost(cap)} (--max enforced)"
            )
            sys.stderr.write(msg + "\n")
            return 1
        print(
            f"\nOK: estimated total cost {_fmt_cost(ledger.raw_estimated_cost_usd)} "
            f"<= per-run cap {_fmt_cost(cap)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
