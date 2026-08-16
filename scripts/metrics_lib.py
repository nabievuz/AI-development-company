#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt

import wave_kpi
from dgox.created_at import parse_created_at


def _parse_iso(ts: str) -> dt.datetime | None:
    return parse_created_at(ts)


def read_waves(path: str = wave_kpi.LIVE_LOG) -> list[dict]:
    try:
        return wave_kpi.parse(path)
    except FileNotFoundError:
        return []


def _is_nothing_actionable(wave: dict) -> bool:
    return any("nothing actionable" in line.lower() for line in wave.get("txt", []))


def idle_wave_rates(waves: list[dict]) -> dict | None:
    total = len(waves)
    if total == 0:
        return None
    t2a = sum(1 for w in waves if not w.get("disp") and _is_nothing_actionable(w))
    t2b = sum(1 for w in waves if not w.get("disp") and not _is_nothing_actionable(w))
    return {
        "total": total,
        "t2a_idle": t2a,
        "t2b_blocked": t2b,
        "t2a_rate": t2a / total,
        "t2b_rate": t2b / total,
    }


def run_intervals(events: list[dict]) -> list[tuple[dt.datetime, dt.datetime]]:
    starts: dict[str, dt.datetime] = {}
    ends: dict[str, dt.datetime] = {}
    for ev in events:
        ts = _parse_iso(str(ev.get("created_at", "")))
        rid = ev.get("run_id")
        if ts is None or not rid:
            continue
        if ev.get("event_type") == "run_start":
            starts[str(rid)] = ts
        elif ev.get("event_type") == "run_end":
            ends[str(rid)] = ts
    return [(starts[r], ends[r]) for r in starts if r in ends and ends[r] >= starts[r]]


def _dropped_undated(events: list[dict], event_types: frozenset[str] | None = None) -> int:
    return sum(
        1 for ev in events
        if (event_types is None or ev.get("event_type") in event_types)
        and _parse_iso(str(ev.get("created_at", ""))) is None
    )


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    if lo == hi:
        return float(sorted_vals[lo])
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def concurrency_stats(events: list[dict]) -> dict | None:
    intervals = run_intervals(events)
    if not intervals:
        return None


    levels = sorted(
        float(sum(1 for s, e in intervals if s <= s0 < e or s == s0 == e))
        for s0, _ in intervals
    )
    return {
        "median": _percentile(levels, 50),
        "p95": _percentile(levels, 95),
        "samples": len(levels),


        "dropped_undated": _dropped_undated(events, frozenset({"run_start", "run_end"})),
    }


LOW_COST_MODELS = {"haiku"}
HAIKU_ELIGIBLE_TYPES = {"format", "lint", "routing", "doc_update", "rename", "boilerplate", "status_update"}
HAIKU_INELIGIBLE_TYPES = {"code_generation", "architecture", "security", "design", "migration"}


def haiku_eligible(task_type: str | None = None, labels: list | None = None) -> bool:
    t = str(task_type or "").lower()
    labs = {str(x).lower() for x in (labels or [])}
    if t in HAIKU_INELIGIBLE_TYPES or (labs & HAIKU_INELIGIBLE_TYPES):
        return False
    return t in HAIKU_ELIGIBLE_TYPES or bool(labs & HAIKU_ELIGIBLE_TYPES)


SUCCESS_OUTCOMES = {"success", "ok", "passed", "done"}


COMPLETED_STATUSES = {"done", "closed", "merged", "shipped"}


def _is_completion_event(ev: dict) -> bool:
    if ev.get("to_status") == "done":
        return True
    if ev.get("event_type") != "run_end":
        return False
    declared = str(ev.get("final_status", "")).strip().lower()
    return declared in COMPLETED_STATUSES if declared else True


def _is_successful_completion(ev: dict) -> bool:
    if not _is_completion_event(ev):
        return False
    outcome = str(ev.get("outcome", "")).strip().lower()


    return outcome == "" or outcome in SUCCESS_OUTCOMES


def _unit_key(ev: dict) -> str:
    return str(ev.get("run_id") or ev.get("ticket_id") or id(ev))


def model_mix(events: list[dict]) -> dict | None:
    total = 0
    low = 0
    seen: set[str] = set()
    for ev in events:
        if not _is_successful_completion(ev):
            continue
        mdl = str(ev.get("model", "")).lower()
        if not mdl:
            continue
        key = _unit_key(ev)
        if key in seen:
            continue
        seen.add(key)
        total += 1
        if mdl in LOW_COST_MODELS:
            low += 1
    if total == 0:
        return None
    return {"ratio": low / total, "low_cost": low, "total": total}


def recovery_reliability(events: list[dict]) -> dict | None:
    drills = [e for e in events if e.get("event_type") == "recovery_drill"]
    if not drills:
        return None
    corrupted = sum(1 for d in drills if d.get("corrupted"))
    ok = sum(
        1 for d in drills
        if str(d.get("outcome", "")).lower() == "success" and not d.get("corrupted")
    )
    return {"ratio": ok / len(drills), "successful": ok, "drills": len(drills), "corrupted": corrupted}


def review_efficiency(events: list[dict]) -> dict | None:
    review_start: dict[str, dt.datetime] = {}
    cycles: list[float] = []
    rework = 0
    reviews = 0
    for ev in sorted(events, key=lambda e: str(e.get("created_at", ""))):
        if ev.get("event_type") != "routing_decision":
            continue
        tid = ev.get("ticket_id")
        to_status = ev.get("to_status")
        from_status = ev.get("from_status")
        ts = _parse_iso(str(ev.get("created_at", "")))
        if ts is None or not tid:
            continue
        if to_status == "in_review":
            review_start[tid] = ts
        elif to_status == "done" and tid in review_start:
            cycles.append((ts - review_start.pop(tid)).total_seconds())
            reviews += 1
        elif from_status == "in_review" and to_status in ("in_progress", "todo"):
            rework += 1
            reviews += 1
            review_start.pop(tid, None)
        elif from_status == "in_review" and to_status == "blocked":


            review_start.pop(tid, None)
    if reviews == 0:
        return None
    cycles_sorted = sorted(cycles)
    return {
        "reviews": reviews,
        "completed": len(cycles),
        "median_cycle_s": _percentile(cycles_sorted, 50) if cycles_sorted else 0.0,
        "rework_rate": rework / reviews,


        "dropped_undated": _dropped_undated(events, frozenset({"routing_decision"})),
    }


GREEN_CI = {"green", "pass", "passed", "success"}
TRUE_VALUES = {"true", "pass", "passed", "1", "yes", "ok"}


def _is_true_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return str(value).strip().lower() in TRUE_VALUES


def gaming_violations(events: list[dict]) -> dict | None:
    completions = [e for e in events if _is_completion_event(e)]
    if not completions:
        return None
    violations: list[str] = []
    for e in completions:
        tid = str(e.get("ticket_id", "?"))
        reasons = []
        if not e.get("merged_pr"):
            reasons.append("no merged PR")
        if str(e.get("ci_status", "")).lower() not in GREEN_CI:
            reasons.append("no green CI")
        if not _is_true_flag(e.get("t7_pass")):
            reasons.append("no T7 pass")
        if reasons:
            violations.append(f"{tid}: counted completion ({', '.join(reasons)})")
    return {"completions": len(completions), "violations": violations}


def t1b_high_impact(events: list[dict]) -> dict | None:
    completions = [e for e in events if _is_completion_event(e)]
    if not completions:
        return None
    high = sum(
        1 for e in completions
        if _is_true_flag(e.get("t7_pass")) and float(e.get("t7_score", 0) or 0) >= 0.90
    )
    return {"rate": high / len(completions), "high_impact": high, "completions": len(completions)}
