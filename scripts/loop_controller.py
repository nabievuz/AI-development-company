#!/usr/bin/env python3
"""loop_controller.py — Self-optimization loop promotion controller + WS4 heartbeat tick.

The self-optimizing loop is promoted up the ladder

    shadow -> measured -> limited_live -> full

ONE rung at a time, and ONLY when BOTH hold:
  1. >= 1 week (7 days) of clean live T1-T7 readings, AND
  2. a complete, HUMAN-APPROVED GATE-6 capability_promotion record (max_quality_drop 0)
     authorizing exactly that rung.

This controller NEVER promotes anything — it EVALUATES eligibility and (with
--propose) emits an UNAPPROVED GATE-6 draft. Applying a promotion means editing
config/loop.yaml, which is a governance change -> never-auto-approve (QONUN-5). So
the loop stays OFF until a human, holding real evidence, signs off. With no live
data (the state today) it reports 'not eligible' and never fabricates readiness.

--tick (WS4 HEARTBEAT, ADR-0027):
    One-shot heartbeat tick: evaluates the trigger state (event stream) against
    board/schedule.yaml safety rails and reports the tempo decision
    (dispatch / validate / idle). NEVER auto-applies anything, NEVER auto-approves
    any gate or interrupt-card. Gated by the heartbeat_enabled feature flag
    (default OFF); when off, runs in shadow-observe mode and dispatches nothing.

Exit codes: 0 (an evaluator/reporter — never a mutator).

Usage:
    python3 scripts/loop_controller.py
    python3 scripts/loop_controller.py --propose
    python3 scripts/loop_controller.py --tick
    python3 scripts/loop_controller.py --tick --trigger cron_tick --pending-work
    python3 scripts/loop_controller.py --tick --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

LADDER = ["shadow", "measured", "limited_live", "full"]
MIN_CLEAN_DAYS = 7

# Promotion-readiness targets (PRD-001 §1). A clean day meets all of these + T7 holds.
DEFAULT_TARGETS = {"t1_min": 0.60, "t2_max": 0.15, "t3_min": 6, "t4_min": 0.25, "t5_min": 0.99}

# SI-6 default: autonomous substrate runs at most 1 wave at a time.
_DEFAULT_MAX_CONCURRENT_WAVES = 1


def next_mode(current: str) -> str | None:
    """The next rung up the ladder, or None at the top / for an unknown mode.
    One rung only — promotions can never skip a stage (C4)."""
    if current not in LADDER:
        return None
    i = LADDER.index(current)
    return LADDER[i + 1] if i + 1 < len(LADDER) else None


def day_is_clean(day: dict, targets: dict) -> bool:
    """A day is clean iff every gated metric meets its target and T7 holds."""
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
    """Consecutive clean days at the END of the (oldest->newest) history."""
    streak = 0
    for day in reversed(metrics_history):
        if day_is_clean(day, targets):
            streak += 1
        else:
            break
    return streak


def has_approved_promotion_record(records: list[dict], current: str, target: str) -> bool:
    """A complete, HUMAN-APPROVED GATE-6 record authorizing exactly current->target.
    A draft (approved_by empty) never counts — only a human sign-off authorizes."""
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
        if isinstance(approver, str) and approver.strip():  # a draft ('' or whitespace) never counts
            return True
    return False


def evaluate_promotion(current_mode: str, records: list[dict], metrics_history: list[dict],
                       targets: dict) -> dict:
    """Report (never apply) promotion eligibility for the next rung."""
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
    """An UNAPPROVED GATE-6 promotion draft (human must fill evidence + approve to apply)."""
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


# ---------------------------------------------------------------------------
# WS4 HEARTBEAT — --tick path helpers (ADR-0027 SI-1..SI-7)
# ---------------------------------------------------------------------------


def _load_schedule(path: Path) -> dict:
    """Load board/schedule.yaml; returns {} if absent or malformed (failure-isolated)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def _in_quiet_hours(schedule: dict, now: datetime) -> bool:
    """True if *now* (UTC) falls inside the configured quiet-hours window (SI-4).

    The window may wrap midnight (e.g. 22:00–06:00 UTC).  An unset, empty, or
    start==end quiet_hours config means *no quiet window* (returns False).
    Malformed time strings are failure-isolated to False (never a crash).
    """
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
        # Normal same-day range (e.g. 09:00–17:00)
        return s <= cur < e
    # Wraps midnight (e.g. 22:00–06:00)
    return cur >= s or cur < e


def _window_start(now: datetime, *, unit: str) -> datetime:
    """Return the inclusive start of the current UTC calendar window containing *now*.

    Shared windowing primitive for every spend ceiling that must reset at a
    calendar boundary rather than accumulate lifetime (D1/DAS-1618, and its
    sibling D-per-day/DAS-1632): the monthly credit ceiling and the per-day
    cap in ``_per_day_budget_exceeded`` both consume ``unit="day"``/
    ``unit="month"`` here — ONE mechanism, not two divergent ones. Returns a
    naive UTC datetime — the same convention
    ``created_at`` envelope strings parse to (see
    ``cost_ledger._parse_created_at`` / ``metrics_history_feeder._parse_iso``),
    so it compares directly against parsed span timestamps.

    Args:
        now:  The current instant (aware or naive; aware is normalised to UTC
              then stripped, naive is assumed already UTC).
        unit: ``"month"`` -> first instant (00:00:00) of *now*'s UTC calendar
              month. ``"day"`` -> midnight UTC of *now*'s UTC calendar day.
              No other unit is accepted.

    Raises:
        ValueError: if ``unit`` is not ``"month"`` or ``"day"``.
    """
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
    """True if today's estimated spend already meets or exceeds the SI-5 per-day cap.

    Reads ``config/budgets.yaml``'s ``mustaqil.caps.per_day.max_cost_usd`` — the
    MUSTAQIL runner's self-imposed hard dispatch ceiling (ADR-0027 SI-5;
    ADR-0042 SI-5.1: "the tightest binding constraint wins", evaluated alongside
    ``_monthly_credit_exhausted``). It is deliberately NOT the top-level
    ``caps.per_day.max_cost_usd`` block: that org-wide block is documented in
    ``config/budgets.yaml`` itself as "informational — not a blocking gate until
    C1 is promoted", and reading it here was DAS-1639's defect (the rail
    enforced $500/day while every Founder-facing artifact — e.g.
    ``heartbeat_go_no_go.py`` — quoted the $15/day ``mustaqil`` ceiling; a rail
    and a report quoting different numbers is the defect regardless of which
    number is "right"). Loaded via ``ws_b_admission.load_mustaqil_budgets`` —
    the same reader ``_monthly_credit_exhausted`` uses — so there is ONE
    accountant for the ``mustaqil:`` block, not two ad-hoc YAML reads
    (ADR-0042 SI-5.1 "one accountant, no second one", applied here by analogy).

    Then queries the cost-ledger for accumulated cost.

    Fails OPEN, not closed: on a missing budgets file, unparseable YAML, an
    absent ``mustaqil:``/``caps``/``per_day`` key, or any read/parse/import
    error, this returns ``False`` — i.e. dispatch is NOT withheld. This is a
    deliberate, reviewed trade-off (DAS-1639), not an oversight: a false
    "idle" here would freeze the substrate on a config typo, which is worse
    than a missed breach for a self-imposed, non-billing ceiling. The
    compensating control is fail-CLOSED: ``ws_b_health_check.
    check_budget_ceiling_drift`` treats every one of those same five inputs
    as ``ok=False`` and is composed into ``heartbeat_go_no_go.py``'s FR-004
    gate, so a malformed/absent cap blocks go-live even though it would not
    block an individual tick. Read this rail and that gate together — this
    function alone does not guarantee "if in doubt, idle".

    ``since`` window (D1/DAS-1632 fix, sibling of DAS-1618's monthly fix): the
    ledger is queried with ``since=_window_start(now, unit="day")`` — spend
    from a *previous* UTC calendar day is excluded, so the cap actually resets
    at the day boundary instead of latching permanently once a lifetime total
    crosses it (a lifetime total is monotonic and would freeze the tick at
    idle forever). ``now`` defaults to the current instant when the caller
    (``tick()``) does not thread its own ``_now`` through, but ``tick()``
    always does — one clock read per tick, never two.

    ``aggregate_spans`` is called with ``budgets_path`` (DAS-1641/R3) so span
    pricing resolves from the SAME ``budgets_path`` this rail was given, not
    always the real ``config/budgets.yaml`` — matching ``_monthly_credit_
    exhausted``'s call one function below, which already threads it. Before
    this fix a caller-supplied ``budgets_path``'s ``tiers:`` block (e.g. a
    test fixture) was silently ignored for pricing purposes.
    """
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from ws_b_admission import load_mustaqil_budgets  # noqa: PLC0415

        mustaqil = load_mustaqil_budgets(budgets_path)
        cap_usd = float((((mustaqil.get("caps") or {}).get("per_day")) or {}).get("max_cost_usd", 0) or 0)
    except Exception:  # noqa: BLE001 — any failure is failure-safe (don't block)
        return False
    if cap_usd <= 0:
        return False

    # Consult the cost-ledger — "activate, don't duplicate" (ADR-0027 §Decision)
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from cost.cost_ledger import aggregate_spans  # noqa: PLC0415
        _now = now or datetime.now(tz=UTC)
        day_start = _window_start(_now, unit="day")
        ledger = aggregate_spans(events_path, budgets_path, since=day_start)
        if ledger is None:
            return False
        total_usd = ledger.raw_estimated_cost_usd
        return total_usd >= cap_usd
    except Exception:  # noqa: BLE001 — ledger unavailable is failure-safe
        return False


def _monthly_credit_exhausted(
    budgets_path: Path,
    events_path: Path,
    credit_state=None,
    *,
    now: datetime | None = None,
) -> bool:
    """True if the monthly subscription credit ceiling is exhausted (SI-5/FR-004).

    A thin adapter — reuses ``ws_b_admission.load_mustaqil_budgets`` /
    ``check_credit_exhaustion`` directly (the SOLE credit accountant; ADR-0034
    SR-2). No arithmetic of its own. Deliberately does NOT call ``admit()``
    (fails closed on the absent per-tick ``model``) or ``gated_admit()`` (gated
    on the unrelated ``ws_b_agent_sdk_runner`` flag — routing SI-5 through it
    would make the ceiling silently vanish whenever WS-B is OFF).

    The ``active_plan`` residual (design §3.5): ``config/budgets.yaml`` declares
    credit per plan but not which plan is active. ``CreditState``'s dataclass
    default (``plan="max_20x"``) must NOT be silently inherited — that would
    under-report exhaustion on a smaller plan. When no ``credit_state`` is
    supplied and ``active_plan`` is undeclared, this returns False (inert in
    the tick; the undeclared plan becomes a readiness blocker in
    ``check_heartbeat_readiness.py`` instead — a false-red here would freeze
    the substrate and prevent the shadow window from ever accumulating).

    ``used_usd`` window (D1/DAS-1618 fix): design §3.5 specifies "same reader,
    different window" — a month-to-date total, not a lifetime one. When no
    ``credit_state`` is injected, ``used_usd`` is derived from
    ``cost_ledger.aggregate_spans(..., since=_window_start(now, unit="month"))``
    — spend from a *previous* billing month is excluded, so the ceiling
    actually resets at the month boundary instead of latching permanently
    once crossed (a lifetime total is monotonic and would freeze the tick at
    idle forever, per design §3.3).

    Failure-isolated to False (mirrors ``_per_day_budget_exceeded``): a missing
    file, absent yaml, or import error must never fabricate a pause.
    """
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from ws_b_admission import (  # noqa: PLC0415
            CreditState,
            check_credit_exhaustion,
            load_mustaqil_budgets,
        )

        mustaqil = load_mustaqil_budgets(budgets_path)
        if credit_state is None:
            ceiling_cfg = mustaqil.get("monthly_credit_ceiling") or {}
            active_plan = ceiling_cfg.get("active_plan")
            if not isinstance(active_plan, str) or not active_plan.strip():
                return False  # undeclared plan -> inert here (readiness blocker instead, §3.5)
            from cost.cost_ledger import aggregate_spans  # noqa: PLC0415

            _now = now or datetime.now(tz=UTC)
            month_start = _window_start(_now, unit="month")
            ledger = aggregate_spans(events_path, budgets_path, since=month_start)
            used_usd = ledger.raw_estimated_cost_usd if ledger is not None else 0.0
            credit_state = CreditState(plan=active_plan, used_usd=used_usd)
        exhaustion = check_credit_exhaustion(credit_state, mustaqil)
        return exhaustion is not None
    except Exception:  # noqa: BLE001 — any failure is failure-safe (never fabricate a pause)
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
    """Evaluate one heartbeat tick; return the decision dict (never mutates anything).

    This is the ``--tick`` path for the WS4 HEARTBEAT (ADR-0027). It is a pure
    evaluator/reporter: exit 0, no mutation, no gate-signing, no interrupt-answering,
    no loop.yaml edit (SI-2). The caller (OS scheduler or human) decides what to do
    with the printed decision.

    Safety rail enforcement (ADR-0027):
      SI-1  One-shot: this function holds no process, loop, or timer.
      SI-2  Never edits loop.yaml. Reads it for evaluate_promotion only.
      SI-3  Consults break_glass.is_active() — dispatch blocked while active.
      SI-4  Consults _in_quiet_hours() — dispatch blocked inside the window.
      SI-5  Consults _per_day_budget_exceeded() and _monthly_credit_exhausted()
            — dispatch blocked if either cap/ceiling is hit (FR-004).
      SI-6  max_concurrent_waves passed to flow_router (defaults to 1).
      SI-7  Never auto-approves. Decision alphabet is {dispatch, validate, idle};
            no "answer"/"approve" action exists in the closed set (flow_router SI-7).

    Returns a dict with:
      ``mode``          "shadow" (heartbeat_enabled=False) or "live" (=True)
      ``decision``      {action, trigger, reason} from flow_router.route()
      ``promotion``     {eligible, current, target, blockers, clean_days}
      ``safety_rails``  {break_glass_active, in_quiet_hours, per_day_budget_exceeded}
      ``shadow_note``   present only in shadow mode — what tick WOULD do if live
    """
    _now = now or datetime.now(tz=UTC)

    # Resolve paths (never hardcoded — LAW A via ROOT)
    _schedule = schedule_path or (ROOT / "board" / "schedule.yaml")
    _loop_cfg = loop_config or (ROOT / "config" / "loop.yaml")
    _experiments = experiments or (ROOT / "experiments")
    _history = metrics_history or (ROOT / "board" / ".metrics-history.jsonl")
    _events = events_path or (ROOT / "board" / ".events.jsonl")
    _budgets = budgets_path or (ROOT / "config" / "budgets.yaml")

    # SI-7: check feature flag — if OFF, run in shadow-observe mode only
    try:
        from feature_flags import enabled as _ff_enabled  # noqa: PLC0415
        heartbeat_on = _ff_enabled("heartbeat_enabled", path=feature_flags_path)
    except Exception:  # noqa: BLE001 — flag unavailable → safe default OFF
        heartbeat_on = False
    mode = "live" if heartbeat_on else "shadow"

    # Load schedule config (quiet hours, max_concurrent_waves)
    schedule = _load_schedule(_schedule)
    max_concurrent = int(schedule.get("max_concurrent_waves") or _DEFAULT_MAX_CONCURRENT_WAVES)

    # SI-3: break-glass kill-switch
    try:
        from break_glass import is_active as _bg_is_active  # noqa: PLC0415
        break_glass_active = _bg_is_active(_now, path=str(_events))
    except Exception:  # noqa: BLE001 — failure-safe: treat as active (block dispatch)
        break_glass_active = True

    # SI-4: quiet hours
    quiet_hours = _in_quiet_hours(schedule, _now)

    # SI-5: per-day budget
    budget_exceeded = _per_day_budget_exceeded(_budgets, _events, now=_now)

    # SI-5/FR-004: monthly subscription credit ceiling (the outer ceiling)
    credit_exhausted = _monthly_credit_exhausted(_budgets, _events, now=_now)

    # Route via flow_router (SI-3/4/5/6/7 all enforced inside the router)
    try:
        from flow_router import route_from_store  # noqa: PLC0415
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
    except Exception as exc:  # noqa: BLE001 — failure-isolated to idle
        from flow_router import IDLE, Decision  # noqa: PLC0415
        decision = Decision(IDLE, trigger, f"flow_router error degraded to idle: {exc!r}")

    # SI-2: evaluate_promotion (read-only — NEVER auto-applied)
    current_mode = str(_load_yaml(_loop_cfg).get("mode", "shadow"))
    promotion = evaluate_promotion(
        current_mode,
        _load_records(_experiments),
        _load_jsonl(_history),
        DEFAULT_TARGETS,
    )

    # SI-5/FR-004 alert limb (DAS-1634): a budget-rail trip is routed through
    # the EXISTING alerting machinery (alerting.sanctioned_pause_alert) — no
    # second notifier. This is OBSERVATION-ONLY: it reads the same
    # budget_exceeded/credit_exhausted booleans already computed above for
    # route_from_store() and is computed AFTER `decision` — it cannot alter
    # the decision, and a failure here is failure-isolated to "no alert"
    # rather than ever touching the tempo decision.
    try:
        import alerting  # noqa: PLC0415 — lazy: alerting imports loop_controller._window_start; avoid a load-time cycle
        alert = alerting.sanctioned_pause_alert(budget_exceeded, credit_exhausted)
    except Exception:  # noqa: BLE001 — alert emission must never affect the decision
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

    # In shadow mode, annotate what would have happened
    if mode == "shadow":
        result["shadow_note"] = (
            f"SHADOW-OBSERVE: heartbeat_enabled=false — would {decision.action} "
            f"({decision.reason}); no wave dispatched. "
            f"Enable: flip heartbeat_enabled: true in config/features.yaml "
            f"(Founder-only act, ADR-0027 SI-7, after >=3-day clean shadow window)."
        )

    return result


def _print_tick(result: dict, as_json: bool) -> None:
    """Print a tick result to stdout in the requested format (never mutates)."""
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--loop-config", type=Path, default=ROOT / "config" / "loop.yaml")
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    ap.add_argument("--metrics-history", type=Path, default=ROOT / "board" / ".metrics-history.jsonl")
    ap.add_argument("--propose", action="store_true", help="emit an unapproved GATE-6 promotion draft")

    # WS4 HEARTBEAT — --tick subpath (ADR-0027)
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

    # --tick: WS4 HEARTBEAT path
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

    # Default path: promotion evaluator
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
