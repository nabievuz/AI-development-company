#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import break_glass
import memory_lib
import wave_kpi
from _paths import ROOT

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


try:
    from cost.cost_ledger import aggregate_spans as _aggregate_spans

    _COST_LEDGER_AVAILABLE = True
except ImportError:
    _COST_LEDGER_AVAILABLE = False


try:
    from loop_controller import _window_start as _WINDOW_START

    _WINDOW_START_AVAILABLE = True
except ImportError:
    _WINDOW_START_AVAILABLE = False

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
ANOMALY = {"warning", "critical"}


_DEFAULT_WARN_RATIO = 0.80


def budget_governor(totals: dict, budgets: dict) -> dict:
    caps = budgets.get("caps") or {}
    warn_ratio = float(budgets.get("warn_ratio", _DEFAULT_WARN_RATIO))

    _rank = {"ok": 0, "warn": 1, "breach": 2}
    worst = "ok"
    details: list[dict] = []

    for dim, key in (("per_run", "per_run_cost_usd"), ("per_day", "per_day_cost_usd")):
        raw_total = totals.get(key)
        cap_block = caps.get(dim) or {}
        raw_limit = cap_block.get("max_cost_usd")

        if raw_total is None or raw_limit is None:
            continue

        total = float(raw_total)
        limit = float(raw_limit)
        if limit <= 0:
            continue

        if total >= limit:
            status = "breach"
        elif total >= warn_ratio * limit:
            status = "warn"
        else:
            status = "ok"

        if _rank[status] > _rank[worst]:
            worst = status

        if status != "ok":
            details.append(
                {
                    "dimension": dim,
                    "status": status,
                    "cost_usd": total,
                    "limit_usd": limit,
                    "over_by_usd": max(0.0, total - limit),
                }
            )

    return {"status": worst, "details": details}


def evaluate_alerts(
    readings: dict,
    thresholds: dict,
    budgets: dict | None = None,
) -> list[dict]:
    alerts: list[dict] = []

    def add(severity: str, metric: str, message: str) -> None:
        alerts.append({"severity": severity, "metric": metric, "message": message})

    t1 = readings.get("t1_busy_fraction")
    if t1 is not None and t1 < thresholds.get("t1_busy_min", 0.60):
        add("warning", "T1", f"busy fraction {t1:.2f} below target {thresholds.get('t1_busy_min', 0.60)}")
    if readings.get("t7_regressed"):
        add("critical", "T7", "quality regression detected (hard blocker)")
    if readings.get("break_glass_active"):
        add("critical", "BREAK-GLASS", "an emergency override is ACTIVE")
    violations = readings.get("never_auto_violations", 0)
    if violations:
        n = len(violations) if isinstance(violations, list | tuple | set) else violations
        add("critical", "QONUN-5", f"{n} never-auto-approve violation(s)")
    mh = readings.get("memory_health")
    if mh is not None and mh < thresholds.get("memory_health_min", 0.80):
        add("warning", "memory", f"health {mh:.2f} below {thresholds.get('memory_health_min', 0.80)}")


    if budgets:
        cost_totals = {
            "per_run_cost_usd": readings.get("per_run_cost_usd"),
            "per_day_cost_usd": readings.get("per_day_cost_usd"),
        }
        verdict = budget_governor(cost_totals, budgets)
        sev_map = {"warn": "warning", "breach": "critical"}
        sev = sev_map.get(verdict["status"])
        if sev and verdict["details"]:
            parts: list[str] = []
            for d in verdict["details"]:
                over = d["over_by_usd"]
                if over > 0:
                    parts.append(
                        f"{d['dimension']} ${d['cost_usd']:.4f} exceeds "
                        f"${d['limit_usd']:.2f} (over by ${over:.4f})"
                    )
                else:
                    parts.append(
                        f"{d['dimension']} ${d['cost_usd']:.4f} in warn band "
                        f"(limit ${d['limit_usd']:.2f})"
                    )
            add(sev, "COST", "; ".join(parts))

    return sorted(alerts, key=lambda a: -SEVERITY_ORDER.get(a["severity"], 0))


def sanctioned_pause_alert(
    per_day_budget_exceeded: bool,
    monthly_credit_exhausted: bool,
) -> dict | None:
    if not (per_day_budget_exceeded or monthly_credit_exhausted):
        return None
    which: list[str] = []
    if per_day_budget_exceeded:
        which.append("per-day budget cap (SI-5)")
    if monthly_credit_exhausted:
        which.append("monthly credit ceiling (SI-5/FR-004)")
    return {
        "severity": "info",
        "metric": "SI-5",
        "message": (
            "sanctioned_pause — substrate paused at its " + " and ".join(which) +
            " as designed; expected/healthy, not a breach or unexpected stall"
        ),
    }


def filter_quiet(alerts: list[dict]) -> list[dict]:
    return [a for a in alerts if a["severity"] in ANOMALY]


def _load_yaml(path: Path) -> dict:
    try:
        loaded = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def gather_readings(
    events: Path,
    memory_store: Path,
    memory_config: Path,
    budgets_path: Path | None = None,
) -> dict:
    evs = wave_kpi.read_events(str(events))
    t1, _ = wave_kpi.busy_fraction_from_events(evs)
    mems = _load_jsonl(memory_store)
    mh = memory_lib.memory_health(mems, datetime.now(tz=UTC).replace(tzinfo=None), _load_yaml(memory_config)) if mems else None


    per_run_cost_usd: float | None = None
    per_day_cost_usd: float | None = None
    if _COST_LEDGER_AVAILABLE:
        try:


            run_kwargs: dict = {"store_path": events}
            if budgets_path is not None:
                run_kwargs["budgets_path"] = budgets_path
            run_ledger = _aggregate_spans(**run_kwargs)
            if run_ledger is not None and run_ledger.by_run:
                per_run_cost_usd = max(g.estimated_cost_usd for g in run_ledger.by_run.values())


            if _WINDOW_START_AVAILABLE:
                day_kwargs: dict = {"store_path": events, "since": _WINDOW_START(datetime.now(tz=UTC), unit="day")}
                if budgets_path is not None:
                    day_kwargs["budgets_path"] = budgets_path
                day_ledger = _aggregate_spans(**day_kwargs)
                if day_ledger is not None:
                    per_day_cost_usd = day_ledger.raw_estimated_cost_usd
        except Exception:
            pass

    return {
        "t1_busy_fraction": t1,
        "memory_health": mh,
        "break_glass_active": break_glass.is_active(datetime.now(tz=UTC), str(events)),
        "per_run_cost_usd": per_run_cost_usd,
        "per_day_cost_usd": per_day_cost_usd,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='alerting.py — Threshold-based proactive alerting + Quiet Mode.')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--memory-store", type=Path, default=ROOT / "board" / ".arcrift-outbox.jsonl")
    ap.add_argument("--memory-config", type=Path, default=ROOT / "config" / "memory_governance.yaml")
    ap.add_argument("--thresholds", type=Path, default=ROOT / "config" / "alert_thresholds.yaml")
    ap.add_argument(
        "--budgets",
        type=Path,
        default=ROOT / "config" / "budgets.yaml",
        help="path to config/budgets.yaml (cost caps; absent = cost alerting inert)",
    )
    ap.add_argument("--quiet", action="store_true", help="emit anomalies only (suppress routine info)")
    ap.add_argument("--fail-on-critical", action="store_true", help="exit 1 if a critical alert fires (CI)")
    args = ap.parse_args(argv)

    thresholds = _load_yaml(args.thresholds).get("thresholds", {})
    budgets = _load_yaml(args.budgets)
    readings = gather_readings(args.events, args.memory_store, args.memory_config, args.budgets if budgets else None)
    alerts = evaluate_alerts(readings, thresholds, budgets)
    if args.quiet:
        alerts = filter_quiet(alerts)

    if not alerts:
        print("Alerts: none — system nominal (or no live data yet; P5 alerting is trigger-gated).")
        return 0

    for a in alerts:
        print(f"[{a['severity'].upper()}] {a['metric']}: {a['message']}")
    if args.fail_on_critical and any(a["severity"] == "critical" for a in alerts):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
