#!/usr/bin/env python3
"""alerting.py — Threshold-based proactive alerting + Quiet Mode.

Turns the passive (look-only) cockpit into a proactive notifier: it reads the
current live state and raises an alert when a threshold is breached (config/
alert_thresholds.yaml). Quiet Mode (--quiet) emits only anomalies (warning /
critical), suppressing routine info — defeating noise-induced anxiety.

Cost-breach alerting (DAS-1461): when the cost ledger totals from
``scripts/cost/cost_ledger.py`` cross the caps in ``config/budgets.yaml``,
a COST alert fires at warning (warn band) or critical (at/over limit) severity.
The ``budget_governor`` function is a callable library — WS4 HEARTBEAT will
consume it; it is NOT wired into any live loop here.

NOTE: With the loop off and no live waves, the readings are absent and the system
reports NO alerts — this ships the alerting LOGIC + thresholds, which activate
once live evidence exists.

Exit codes: 0 (a notifier); 1 only with --fail-on-critical when a critical alert fires.

Usage:
    python3 scripts/alerting.py
    python3 scripts/alerting.py --quiet --fail-on-critical
"""
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
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Cost ledger import (graceful — inert when the package is unavailable)
# ---------------------------------------------------------------------------
try:
    from cost.cost_ledger import aggregate_spans as _aggregate_spans

    _COST_LEDGER_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    _COST_LEDGER_AVAILABLE = False

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
ANOMALY = {"warning", "critical"}

# Warn when spend reaches this fraction of the budget limit (configurable via
# budgets.yaml ``warn_ratio`` key; default 0.80 = 80 %).
_DEFAULT_WARN_RATIO = 0.80


# ---------------------------------------------------------------------------
# Budget governor (pure library — callable by WS4 HEARTBEAT; no I/O here)
# ---------------------------------------------------------------------------


def budget_governor(totals: dict, budgets: dict) -> dict:
    """Classify current spend as ok / warn / breach (pure — no I/O, no side effects).

    Called by ``evaluate_alerts`` and exportable as a library for WS4 HEARTBEAT.
    WS4 is responsible for wiring it into a live loop; this function has none.

    Args:
        totals:  dict with optional keys ``per_run_cost_usd`` and
                 ``per_day_cost_usd``.  A missing or ``None`` value makes that
                 dimension inert (does not fabricate a breach).
        budgets: dict matching ``config/budgets.yaml`` structure.  Must contain
                 ``caps.per_run.max_cost_usd`` and/or ``caps.per_day.max_cost_usd``
                 for those dimensions to be evaluated.  An empty dict or a
                 missing ``caps`` key makes every dimension inert.

    Returns:
        dict with two keys:
        - ``status``: ``"ok"`` | ``"warn"`` | ``"breach"`` — the most severe
          verdict across all evaluated dimensions.
        - ``details``: list of per-dimension dicts (only non-ok dimensions are
          included), each with ``dimension``, ``status``, ``cost_usd``,
          ``limit_usd``, and ``over_by_usd``.

    Verdict bands (per dimension):
        - ``breach`` — cost >= limit
        - ``warn``   — cost >= warn_ratio * limit  (default 0.80)
        - ``ok``     — cost < warn_ratio * limit
    The overall verdict is the most severe of the two dimensions.
    """
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
            continue  # dimension is inert

        total = float(raw_total)
        limit = float(raw_limit)
        if limit <= 0:
            continue  # guard against a misconfigured zero limit

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


# ---------------------------------------------------------------------------
# Threshold evaluation (pure — no I/O)
# ---------------------------------------------------------------------------


def evaluate_alerts(
    readings: dict,
    thresholds: dict,
    budgets: dict | None = None,
) -> list[dict]:
    """Pure threshold evaluation: readings -> alerts, sorted critical-first.

    Args:
        readings:   live-data snapshot from ``gather_readings``.
        thresholds: loaded from ``config/alert_thresholds.yaml``.
        budgets:    loaded from ``config/budgets.yaml``; ``None`` or empty dict
                    disables cost-breach alerting (inert).
    """
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

    # Cost-breach via budget governor
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


def filter_quiet(alerts: list[dict]) -> list[dict]:
    """Quiet Mode: anomalies only (warning/critical), suppress routine info."""
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
    """Pull what live data supports; None / False / 0 where the data is absent (inert).

    Cost readings are added when ``scripts/cost/cost_ledger.py`` is importable
    and the event store contains span events.  When absent or on any error, cost
    keys default to ``None`` so the governor treats them as inert.

    Args:
        events:       Path to the JSONL event store.
        memory_store: Path to the ArcRift outbox JSONL.
        memory_config: Path to ``config/memory_governance.yaml``.
        budgets_path: Path to ``config/budgets.yaml`` (forwarded to
                      ``aggregate_spans`` for pricing; defaults to the ledger's
                      own default when ``None``).
    """
    evs = wave_kpi.read_events(str(events))
    t1, _ = wave_kpi.busy_fraction_from_events(evs)
    mems = _load_jsonl(memory_store)
    mh = memory_lib.memory_health(mems, datetime.now(tz=UTC).replace(tzinfo=None), _load_yaml(memory_config)) if mems else None

    # Cost ledger — inert when the package is unavailable, the store is absent,
    # or any error occurs during aggregation.
    per_run_cost_usd: float | None = None
    per_day_cost_usd: float | None = None
    if _COST_LEDGER_AVAILABLE:
        try:
            kwargs: dict = {"store_path": events}
            if budgets_path is not None:
                kwargs["budgets_path"] = budgets_path
            ledger = _aggregate_spans(**kwargs)
            if ledger is not None:
                # per-run: most expensive single run observed in the event store
                if ledger.by_run:
                    per_run_cost_usd = max(g.estimated_cost_usd for g in ledger.by_run.values())
                # per-day: total cost across all events (proxy for today's spend)
                per_day_cost_usd = ledger.raw_estimated_cost_usd
        except Exception:  # noqa: BLE001  — degrade to inert on any ledger error
            pass

    return {
        "t1_busy_fraction": t1,
        "memory_health": mh,
        "break_glass_active": break_glass.is_active(datetime.now(tz=UTC), str(events)),
        "per_run_cost_usd": per_run_cost_usd,
        "per_day_cost_usd": per_day_cost_usd,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
    budgets = _load_yaml(args.budgets)  # empty dict when file absent -> cost alerting inert
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
