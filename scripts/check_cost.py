#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml


_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cost.cost_ledger import (
    TokenGroup,
    aggregate_spans,
    check_reconciliation,
)
from dgox.created_at import parse_created_at
from dgox.events import iter_events


_ROOT = _SCRIPTS.parent
_BUDGETS_PATH = _ROOT / "config" / "budgets.yaml"


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
    try:
        import re
        text = budgets_path.read_text(encoding="utf-8")

        m = re.search(r"per_run:\s*\n(?:[ \t]+\S[^\n]*\n)*?[ \t]+max_cost_usd:\s*([\d.]+)", text)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


def _load_imagegen_config(budgets_path: Path) -> dict | None:
    try:
        raw = yaml.safe_load(budgets_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        sys.stderr.write(f"check_cost --check-imagegen: could not parse {budgets_path}: {exc}\n")
        return None
    cfg = (raw.get("third_party_tools") or {}).get("imagegen")
    return cfg if isinstance(cfg, dict) else None


def _imagegen_day_start(now: datetime | None = None) -> datetime:
    from datetime import UTC

    n = now if now is not None else datetime.now(UTC)
    if n.tzinfo is not None:
        n = n.astimezone(UTC).replace(tzinfo=None)
    return datetime(n.year, n.month, n.day)


def _imagegen_calls_from_events(
    events_path: Path | None,
    models: set[str],
    since: datetime | None,
) -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(models, 0)
    for ev in iter_events(events_path, event_type="span"):
        model = str(ev.get("gen_ai.request.model") or "")
        if model not in counts:
            continue
        if since is not None:
            ts = parse_created_at(str(ev.get("created_at", "")))
            if ts is None or ts < since:
                continue
        counts[model] += 1
    return counts


def evaluate_imagegen_ceiling(calls_by_model: dict[str, int], cfg: dict) -> tuple[bool, str]:
    models_cfg = cfg.get("models") or {}
    caps = (cfg.get("caps") or {}).get("per_day") or {}
    max_calls = caps.get("max_calls")
    max_cost = caps.get("max_cost_usd")

    total_calls = sum(calls_by_model.values())
    total_cost = 0.0
    unpriced: list[str] = []
    for model, count in calls_by_model.items():
        if count <= 0:
            continue
        price = (models_cfg.get(model) or {}).get("usd_per_image")
        if price is None:
            unpriced.append(model)
            continue
        total_cost += float(price) * count

    reasons = []
    if max_calls is not None and total_calls > max_calls:
        reasons.append(f"calls {total_calls} > per_day cap {max_calls}")
    if max_cost is not None and total_cost > max_cost:
        reasons.append(f"estimated cost ${total_cost:.4f} > per_day cap ${max_cost:.2f}")

    lines = [
        "mcp__imagegen per-day ceiling "
        "(governance/policies/third-party-model-tools.md §5):",
        f"  calls={total_calls} (cap {max_calls})  "
        f"estimated_cost=${total_cost:.4f} (cap ${max_cost if max_cost is None else f'{max_cost:.2f}'})",
    ]
    for model, count in sorted(calls_by_model.items()):
        if count:
            lines.append(f"    {model}: {count} call(s)")
    if unpriced:
        lines.append(
            f"    UNPRICED model(s) — counted toward calls, NOT toward cost: {sorted(unpriced)}"
        )

    if reasons:
        lines.append("DENY: " + "; ".join(reasons))
        return False, "\n".join(lines)
    lines.append("OK: within cap")
    return True, "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_cost.py — C1 cost-ledger informational reader (ORGANISM WS3 P12 / DAS-1459).')
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
    ap.add_argument(
        "--check-imagegen", action="store_true",
        help=(
            "Enforce the mcp__imagegen per-day mechanical ceiling from "
            "config/budgets.yaml (third_party_tools.imagegen.caps.per_day); "
            "exit 1 on breach. Independent of the token ledger above (DAS-1647)."
        ),
    )
    ap.add_argument(
        "--imagegen-model",
        help=(
            "Probe mode (use with --imagegen-calls): attribute the synthetic "
            "call count to this model id instead of reading the event store."
        ),
    )
    ap.add_argument(
        "--imagegen-calls", type=int,
        help=(
            "Probe mode (use with --imagegen-model): evaluate the ceiling "
            "against this synthetic call count instead of counting real "
            "'span' events. Lets the ceiling be proven both directions "
            "(under cap passes, over cap denies) without needing live traffic."
        ),
    )
    args = ap.parse_args(argv)


    if args.check_imagegen:
        cfg = _load_imagegen_config(args.budgets)
        if cfg is None:
            sys.stderr.write(
                f"check_cost --check-imagegen: no third_party_tools.imagegen "
                f"section in {args.budgets}\n"
            )
            return 2
        models = set((cfg.get("models") or {}).keys())
        if args.imagegen_calls is not None:
            if not args.imagegen_model:
                sys.stderr.write(
                    "check_cost --check-imagegen: --imagegen-calls requires --imagegen-model\n"
                )
                return 2
            calls_by_model = {args.imagegen_model: args.imagegen_calls}
        else:
            calls_by_model = _imagegen_calls_from_events(
                args.events, models, since=_imagegen_day_start()
            )
        ok, message = evaluate_imagegen_ceiling(calls_by_model, cfg)
        print(message)
        return 0 if ok else 1


    try:
        ledger = aggregate_spans(
            store_path=args.events,
            budgets_path=args.budgets,
        )
    except FileNotFoundError as exc:
        sys.stderr.write(f"check_cost: cannot open required file: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"check_cost: error during aggregation: {exc}\n")
        return 2

    if ledger is None:
        print(
            "C1 cost ledger: no span events yet. "
            "Gate inert (loop off / no waves run). "
            "Exit 0."
        )
        return 0


    recon_errors = check_reconciliation(ledger)
    if recon_errors:
        sys.stderr.write("check_cost: RECONCILIATION FAILURE (bug in cost_ledger.py):\n")
        for err in recon_errors:
            sys.stderr.write(f"  {err}\n")
        return 2


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
    if ledger.dropped_undated:
        print(
            f"  Dropped (undated) spans: {ledger.dropped_undated} span(s) with a "
            f"missing/non-conforming created_at (DAS-1633) — excluded from any "
            f"windowed (--since) total; visible here instead of silently vanishing"
        )

    _print_axis("Per ticket", ledger.by_ticket)
    _print_axis("Per agent", ledger.by_agent)
    _print_axis("Per tier", ledger.by_tier)
    _print_axis("Per run", ledger.by_run)


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
