#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

LADDER = ["shadow", "measured", "limited_live", "full"]
MIN_CLEAN_DAYS = 7


DEFAULT_TARGETS = {"t1_min": 0.60, "t2_max": 0.15, "t3_min": 6, "t4_min": 0.25, "t5_min": 0.99}


_DEFAULT_MAX_CONCURRENT_WAVES = 1


def next_mode(current: str) -> str | None:
    if current not in LADDER:
        return None
    i = LADDER.index(current)
    return LADDER[i + 1] if i + 1 < len(LADDER) else None


def day_is_clean(day: dict, targets: dict) -> bool:
    if not isinstance(day, dict):
        return False
    try:
        return (
            float(day.get("t1", -1)) >= targets["t1_min"]
            and float(day.get("t2", 1)) <= targets["t2_max"]
            and float(day.get("t3", -1)) >= targets["t3_min"]
            and float(day.get("t4", -1)) >= targets["t4_min"]
            and float(day.get("t5", -1)) >= targets["t5_min"]
            and bool(day.get("t7_holds", False))
        )
    except (TypeError, ValueError):
        return False


def clean_live_days(metrics_history: list[dict], targets: dict) -> int:
    streak = 0
    for day in reversed(metrics_history):
        if day_is_clean(day, targets):
            streak += 1
        else:
            break
    return streak


def has_approved_promotion_record(records: list[dict], current: str, target: str) -> bool:
    for rec in records:
        r = rec.get("gate_6_record", rec) if isinstance(rec, dict) else None
        if not isinstance(r, dict) or r.get("change_type") != "capability_promotion":
            continue
        pc = r.get("proposed_change")
        if not (isinstance(pc, dict) and pc.get("from_mode") == current and pc.get("to_mode") == target):
            continue
        if (r.get("guardrails") or {}).get("max_quality_drop") not in (0, 0.0):
            continue
        approver = (r.get("approval") or {}).get("approved_by")
        if isinstance(approver, str) and approver.strip():
            return True
    return False


def evaluate_promotion(current_mode: str, records: list[dict], metrics_history: list[dict],
                       targets: dict) -> dict:
    if current_mode not in LADDER:
        return {"eligible": False, "current": current_mode, "target": None,
                "blockers": [f"unknown loop mode {current_mode!r}"], "clean_days": 0}
    target = next_mode(current_mode)
    if target is None:
        return {"eligible": False, "current": current_mode, "target": None,
                "blockers": ["already at 'full' — no further promotion"], "clean_days": 0}

    streak = clean_live_days(metrics_history, targets)
    blockers: list[str] = []
    if streak < MIN_CLEAN_DAYS:
        blockers.append(f"insufficient clean live evidence: {streak}/{MIN_CLEAN_DAYS} clean day(s)")
    if not has_approved_promotion_record(records, current_mode, target):
        blockers.append(f"no human-approved GATE-6 record for promotion {current_mode}->{target}")
    return {"eligible": not blockers, "current": current_mode, "target": target,
            "blockers": blockers, "clean_days": streak}


def promotion_draft(current: str, target: str, created_at: str) -> dict:
    return {"gate_6_record": {
        "id": f"GATE6-PROMOTE-{current}-to-{target}",
        "created_at": created_at,
        "proposed_by": "loop_controller",
        "change_type": "capability_promotion",
        "hypothesis": f"Promote the self-optimizing loop {current} -> {target} after >=1 week clean live T1-T7.",
        "baseline_metrics": {"note": "one-week live T1-T7 readings"},
        "proposed_change": {"description": f"loop mode {current} -> {target}", "from_mode": current,
                            "to_mode": target, "config_diff_hash": "sha256:PENDING", "blast_radius": "high"},
        "guardrails": {"max_quality_drop": 0, "rollback_condition": "revert to previous mode on any T7 drop or incident"},
        "evidence": {"trace_ids": [], "ci_runs": [], "review_ids": [], "experiment_ids": []},
        "approval": {"required_role": "founder", "approved_by": "", "approved_at": ""},
        "rollout": {"mode": "shadow"},
        "result": {"status": "deferred"},
    }}


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


def _load_records(experiments: Path) -> list[dict]:
    records: list[dict] = []
    if not experiments.exists():
        return records
    for f in sorted(list(experiments.rglob("*.yaml")) + list(experiments.rglob("*.yml"))):
        if "TEMPLATE" in f.name.upper():
            continue
        try:
            data = yaml.safe_load(f.read_text())
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            records.append(data)
    return records


def _load_schedule(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def _in_quiet_hours(schedule: dict, now: datetime) -> bool:
    qh = (schedule.get("quiet_hours") or {})
    start_str = str(qh.get("start") or "").strip()
    end_str = str(qh.get("end") or "").strip()
    if not start_str or not end_str or start_str == end_str:
        return False
    try:
        sh, sm = (int(p) for p in start_str.split(":"))
        eh, em = (int(p) for p in end_str.split(":"))
    except (ValueError, AttributeError):
        return False

    now_utc = now.astimezone(UTC)
    cur = now_utc.hour * 60 + now_utc.minute
    s = sh * 60 + sm
    e = eh * 60 + em

    if s < e:

        return s <= cur < e

    return cur >= s or cur < e


def _window_start(now: datetime, *, unit: str) -> datetime:
    now_utc = now.astimezone(UTC) if now.tzinfo is not None else now
    naive = now_utc.replace(tzinfo=None)
    if unit == "month":
        return naive.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if unit == "day":
        return naive.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"_window_start: unsupported unit {unit!r} (want 'month' or 'day')")


def _per_day_budget_exceeded(
    budgets_path: Path,
    events_path: Path,
    *,
    now: datetime | None = None,
) -> bool:
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from ws_b_admission import load_mustaqil_budgets

        mustaqil = load_mustaqil_budgets(budgets_path)
        cap_usd = float((((mustaqil.get("caps") or {}).get("per_day")) or {}).get("max_cost_usd", 0) or 0)
    except Exception:
        return False
    if cap_usd <= 0:
        return False


    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from cost.cost_ledger import aggregate_spans
        _now = now or datetime.now(tz=UTC)
        day_start = _window_start(_now, unit="day")
        ledger = aggregate_spans(events_path, budgets_path, since=day_start)
        if ledger is None:
            return False
        total_usd = ledger.raw_estimated_cost_usd
        return total_usd >= cap_usd
    except Exception:
        return False


def _monthly_credit_exhausted(
    budgets_path: Path,
    events_path: Path,
    credit_state=None,
    *,
    now: datetime | None = None,
) -> bool:
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from ws_b_admission import (
            CreditState,
            check_credit_exhaustion,
            load_mustaqil_budgets,
        )

        mustaqil = load_mustaqil_budgets(budgets_path)
        if credit_state is None:
            ceiling_cfg = mustaqil.get("monthly_credit_ceiling") or {}
            active_plan = ceiling_cfg.get("active_plan")
            if not isinstance(active_plan, str) or not active_plan.strip():
                return False
            from cost.cost_ledger import aggregate_spans

            _now = now or datetime.now(tz=UTC)
            month_start = _window_start(_now, unit="month")
            ledger = aggregate_spans(events_path, budgets_path, since=month_start)
            used_usd = ledger.raw_estimated_cost_usd if ledger is not None else 0.0
            credit_state = CreditState(plan=active_plan, used_usd=used_usd)
        exhaustion = check_credit_exhaustion(credit_state, mustaqil)
        return exhaustion is not None
    except Exception:
        return False


def tick(
    *,
    schedule_path: Path | None = None,
    loop_config: Path | None = None,
    experiments: Path | None = None,
    metrics_history: Path | None = None,
    events_path: Path | None = None,
    budgets_path: Path | None = None,
    feature_flags_path: Path | None = None,
    trigger: str = "cron_tick",
    pending_work: bool = False,
    now: datetime | None = None,
) -> dict:
    _now = now or datetime.now(tz=UTC)


    _schedule = schedule_path or (ROOT / "board" / "schedule.yaml")
    _loop_cfg = loop_config or (ROOT / "config" / "loop.yaml")
    _experiments = experiments or (ROOT / "experiments")
    _history = metrics_history or (ROOT / "board" / ".metrics-history.jsonl")
    _events = events_path or (ROOT / "board" / ".events.jsonl")
    _budgets = budgets_path or (ROOT / "config" / "budgets.yaml")


    try:
        from feature_flags import enabled as _ff_enabled
        heartbeat_on = _ff_enabled("heartbeat_enabled", path=feature_flags_path)
    except Exception:
        heartbeat_on = False
    mode = "live" if heartbeat_on else "shadow"


    schedule = _load_schedule(_schedule)
    max_concurrent = int(schedule.get("max_concurrent_waves") or _DEFAULT_MAX_CONCURRENT_WAVES)


    try:
        from break_glass import is_active as _bg_is_active
        break_glass_active = _bg_is_active(_now, path=str(_events))
    except Exception:
        break_glass_active = True


    quiet_hours = _in_quiet_hours(schedule, _now)


    budget_exceeded = _per_day_budget_exceeded(_budgets, _events, now=_now)


    credit_exhausted = _monthly_credit_exhausted(_budgets, _events, now=_now)


    try:
        from flow_router import route_from_store
        decision = route_from_store(
            trigger,
            path=str(_events),
            max_concurrent_waves=max_concurrent,
            pending_work=pending_work,
            in_quiet_hours=quiet_hours,
            break_glass_active=break_glass_active,
            per_day_budget_exceeded=budget_exceeded,
            credit_exhausted=credit_exhausted,
        )
    except Exception as exc:
        from flow_router import IDLE, Decision
        decision = Decision(IDLE, trigger, f"flow_router error degraded to idle: {exc!r}")


    current_mode = str(_load_yaml(_loop_cfg).get("mode", "shadow"))
    promotion = evaluate_promotion(
        current_mode,
        _load_records(_experiments),
        _load_jsonl(_history),
        DEFAULT_TARGETS,
    )


    try:
        import alerting
        alert = alerting.sanctioned_pause_alert(budget_exceeded, credit_exhausted)
    except Exception:
        alert = None

    result: dict = {
        "mode": mode,
        "decision": decision.as_dict(),
        "promotion": promotion,
        "safety_rails": {
            "break_glass_active": break_glass_active,
            "in_quiet_hours": quiet_hours,
            "per_day_budget_exceeded": budget_exceeded,
            "monthly_credit_exhausted": credit_exhausted,
        },
        "alert": alert,
    }


    if mode == "shadow":
        result["shadow_note"] = (
            f"SHADOW-OBSERVE: heartbeat_enabled=false — would {decision.action} "
            f"({decision.reason}); no wave dispatched. "
            f"Enable: flip heartbeat_enabled: true in config/features.yaml "
            f"(Founder-only act, ADR-0027 SI-7, after >=3-day clean shadow window)."
        )

    return result


def _print_tick(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
        return

    mode = result.get("mode", "shadow")
    decision = result.get("decision", {})
    promotion = result.get("promotion", {})
    rails = result.get("safety_rails", {})

    header = "SHADOW-OBSERVE" if mode == "shadow" else "LIVE"
    action = decision.get("action", "idle").upper()
    trigger = decision.get("trigger", "?")
    reason = decision.get("reason", "")

    print(f"[{header}] tick: {trigger} -> {action}")
    print(f"  reason: {reason}")
    if mode == "shadow":
        print(f"  note: {result.get('shadow_note', '')}")
    print("  safety rails:")
    print(f"    break_glass_active       = {rails.get('break_glass_active', '?')}")
    print(f"    in_quiet_hours           = {rails.get('in_quiet_hours', '?')}")
    print(f"    per_day_budget_exceeded  = {rails.get('per_day_budget_exceeded', '?')}")
    print(f"    monthly_credit_exhausted = {rails.get('monthly_credit_exhausted', '?')}")
    alert = result.get("alert")
    if alert:
        print(f"  alert: [{alert['severity'].upper()}] {alert['metric']}: {alert['message']}")
    print(f"  promotion: loop stays in '{promotion.get('current', '?')}' — eligible={promotion.get('eligible', False)}")
    if promotion.get("blockers"):
        for b in promotion["blockers"]:
            print(f"    blocker: {b}")
    print("  [never-auto-applies: a human edits config/loop.yaml to promote]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='loop_controller.py — Self-optimization loop promotion controller + WS4 heartbeat tick.')
    ap.add_argument("--loop-config", type=Path, default=ROOT / "config" / "loop.yaml")
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    ap.add_argument("--metrics-history", type=Path, default=ROOT / "board" / ".metrics-history.jsonl")
    ap.add_argument("--propose", action="store_true", help="emit an unapproved GATE-6 promotion draft")


    ap.add_argument(
        "--tick",
        action="store_true",
        help=(
            "run one heartbeat tick: evaluate the trigger state and report the "
            "tempo decision (dispatch/validate/idle). NEVER auto-applies. Gated by "
            "heartbeat_enabled feature flag (default OFF = shadow-observe mode)."
        ),
    )
    ap.add_argument(
        "--trigger",
        default="cron_tick",
        choices=["cron_tick", "ticket_created", "wave_completed",
                 "interrupt_answered", "after_n_runs"],
        help="which heartbeat trigger woke the tick (default: cron_tick)",
    )
    ap.add_argument(
        "--schedule",
        type=Path,
        default=ROOT / "board" / "schedule.yaml",
        help="path to board/schedule.yaml (quiet hours + safety config)",
    )
    ap.add_argument(
        "--events",
        type=Path,
        default=None,
        help="path to the JSONL event store (default: board/.events.jsonl)",
    )
    ap.add_argument(
        "--budgets",
        type=Path,
        default=ROOT / "config" / "budgets.yaml",
        help="path to config/budgets.yaml (per-day cost cap, SI-5)",
    )
    ap.add_argument(
        "--pending-work",
        action="store_true",
        help="signal that actionable board work is waiting (drives cron_tick dispatch arm)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="emit the tick result as JSON (--tick only)",
    )
    args = ap.parse_args(argv)


    if args.tick:
        result = tick(
            schedule_path=args.schedule,
            loop_config=args.loop_config,
            experiments=args.experiments,
            metrics_history=args.metrics_history,
            events_path=args.events,
            budgets_path=args.budgets,
            trigger=args.trigger,
            pending_work=args.pending_work,
        )
        _print_tick(result, as_json=args.json)
        return 0


    current = str(_load_yaml(args.loop_config).get("mode", "shadow"))
    result = evaluate_promotion(current, _load_records(args.experiments),
                                _load_jsonl(args.metrics_history), DEFAULT_TARGETS)

    if result["eligible"]:
        print(
            f"Loop promotion {result['current']} -> {result['target']}: ELIGIBLE "
            f"({result['clean_days']} clean day(s) + an approved GATE-6 record). Applying is a governance "
            f"change (a human edits config/loop.yaml) — never auto-applied."
        )
        return 0

    print(f"Loop stays in '{result['current']}' — promotion NOT eligible:")
    for blocker in result["blockers"]:
        print(f"  - {blocker}")
    if args.propose and result["target"]:
        draft = promotion_draft(result["current"], result["target"],
                                datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("\nProposed GATE-6 promotion DRAFT (UNAPPROVED — fill evidence + human approval to apply):")
        print(json.dumps(draft["gate_6_record"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
