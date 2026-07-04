#!/usr/bin/env python3
"""metrics_lib.py — T2-T6 + anti-gaming computations.

Reads the live DGO-X event store (``board/.events.jsonl``) via ``wave_kpi`` and
the wave log (``board/.wave-log``), and computes T2-T6 + the anti-gaming checks.
Every function returns None (inert) when there is no live data yet — the levers
are shipped, never a fabricated KPI. The loop stays off until real waves read
clean for >= 1 week (RFC-001 §5).
"""
from __future__ import annotations

import datetime as dt

import wave_kpi


def _parse_iso(ts: str) -> dt.datetime | None:
    """Parse an ISO-8601 'YYYY-MM-DDTHH:MM:SSZ' timestamp, or None."""
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None


def read_waves(path: str = wave_kpi.LIVE_LOG) -> list[dict]:
    """Parse the wave log via wave_kpi; [] if absent (no waves run yet)."""
    try:
        return wave_kpi.parse(path)
    except FileNotFoundError:
        return []


# --------------------------------------------------------------------------- #
# T2 — idle-wave rate, split into T2a (idle) vs T2b (blocked) per RFC-001 §2
# --------------------------------------------------------------------------- #

def _is_nothing_actionable(wave: dict) -> bool:
    return any("nothing actionable" in line.lower() for line in wave.get("txt", []))


def idle_wave_rates(waves: list[dict]) -> dict | None:
    """T2 split: T2a (idle = nothing actionable, scheduling waste) vs T2b (blocked
    = actionable but dependency-blocked, NOT waste). None when no waves logged."""
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


# --------------------------------------------------------------------------- #
# T3 — effective concurrency (median & p95 of concurrently-active runs)
# --------------------------------------------------------------------------- #

def run_intervals(events: list[dict]) -> list[tuple[dt.datetime, dt.datetime]]:
    """Paired [run_start, run_end] intervals from the event store (run_id keyed)."""
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
    """T3: median & p95 of concurrently-active runs, sampled at each run start.
    None when there are no paired run events."""
    intervals = run_intervals(events)
    if not intervals:
        return None
    # Count a run active at instant s0 when s <= s0 < e, OR when it is a
    # zero-length run at exactly that instant (s == s0 == e) — sub-second runs
    # collapse to start==end at the event store's second resolution and must
    # still count themselves / their concurrent siblings.
    levels = sorted(
        float(sum(1 for s, e in intervals if s <= s0 < e or s == s0 == e))
        for s0, _ in intervals
    )
    return {
        "median": _percentile(levels, 50),
        "p95": _percentile(levels, 95),
        "samples": len(levels),
    }


# --------------------------------------------------------------------------- #
# T4 — cost / model mix + haiku-eligibility classifier (RFC-001 §2)
# --------------------------------------------------------------------------- #

LOW_COST_MODELS = {"haiku"}
HAIKU_ELIGIBLE_TYPES = {"format", "lint", "routing", "doc_update", "rename", "boilerplate", "status_update"}
HAIKU_INELIGIBLE_TYPES = {"code_generation", "architecture", "security", "design", "migration"}


def haiku_eligible(task_type: str | None = None, labels: list | None = None) -> bool:
    """RFC-001 §2: simple formatting/routing eligible for the cheap model; complex
    code generation / security / architecture NOT. Conservative default: ineligible
    (quality first — never route hard work to the cheap tier to chase T4)."""
    t = str(task_type or "").lower()
    labs = {str(x).lower() for x in (labels or [])}
    if t in HAIKU_INELIGIBLE_TYPES or (labs & HAIKU_INELIGIBLE_TYPES):
        return False
    return t in HAIKU_ELIGIBLE_TYPES or bool(labs & HAIKU_ELIGIBLE_TYPES)


# Canonical success vocabulary (positive match, like T5). An explicit outcome
# OUTSIDE this set (error / timeout / no_work / failed / …) is NOT a success.
SUCCESS_OUTCOMES = {"success", "ok", "passed", "done"}


def _is_completion_event(ev: dict) -> bool:
    return ev.get("event_type") == "run_end" or ev.get("to_status") == "done"


def _is_successful_completion(ev: dict) -> bool:
    if not _is_completion_event(ev):
        return False
    outcome = str(ev.get("outcome", "")).strip().lower()
    # Absent outcome (e.g. a routing_decision -> done) counts; an explicit outcome
    # must be a known SUCCESS value — error/timeout/no_work do NOT count.
    return outcome == "" or outcome in SUCCESS_OUTCOMES


def _unit_key(ev: dict) -> str:
    return str(ev.get("run_id") or ev.get("ticket_id") or id(ev))


def model_mix(events: list[dict]) -> dict | None:
    """T4: share of successful completed work on a low-cost (haiku) model. None when
    no successful completion carries a model field. De-duplicates per unit so a unit
    that emits both a run_end and a routing->done is not counted twice."""
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


# --------------------------------------------------------------------------- #
# T5 — recovery reliability (successful replays / drills; zero corrupted)
# --------------------------------------------------------------------------- #

def recovery_reliability(events: list[dict]) -> dict | None:
    """T5: successful_replays / recovery_drills. None when no drills have run. A
    corrupted resume is never counted as success (guardrail: zero corrupted)."""
    drills = [e for e in events if e.get("event_type") == "recovery_drill"]
    if not drills:
        return None
    corrupted = sum(1 for d in drills if d.get("corrupted"))
    ok = sum(
        1 for d in drills
        if str(d.get("outcome", "")).lower() == "success" and not d.get("corrupted")
    )
    return {"ratio": ok / len(drills), "successful": ok, "drills": len(drills), "corrupted": corrupted}


# --------------------------------------------------------------------------- #
# T6 — review efficiency (cycle time + rework rate; downward-trend metric)
# --------------------------------------------------------------------------- #

def review_efficiency(events: list[dict]) -> dict | None:
    """T6: median review cycle time + rework rate from routing transitions. None
    when no reviews. 'Downward trend' is a time-series property — this reads the
    current numbers; trend comparison needs a stored baseline window."""
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
            # dependency-blocked is NOT a quality bounce-back (T2 semantics) —
            # drop the open review without counting it as rework.
            review_start.pop(tid, None)
    if reviews == 0:
        return None
    cycles_sorted = sorted(cycles)
    return {
        "reviews": reviews,
        "completed": len(cycles),
        "median_cycle_s": _percentile(cycles_sorted, 50) if cycles_sorted else 0.0,
        "rework_rate": rework / reviews,
    }


# --------------------------------------------------------------------------- #
# Anti-gaming (R-9) + orthogonal T1b (human-oversight, agent-invisible)
# --------------------------------------------------------------------------- #

GREEN_CI = {"green", "pass", "passed", "success"}
TRUE_VALUES = {"true", "pass", "passed", "1", "yes", "ok"}


def _is_true_flag(value) -> bool:
    """Robust truthiness for an event flag — a STRING 'false'/'no'/'0' must NOT pass."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return str(value).strip().lower() in TRUE_VALUES


def gaming_violations(events: list[dict]) -> dict | None:
    """R-9: a unit counts toward T1-T6 ONLY if it ended in a merged PR + green CI +
    a T7 pass. Flags counted completions missing ANY of that evidence (Goodhart
    busywork — all missing pieces reported at once). None when no completions."""
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
    """Orthogonal T1b: share of completions passing T7 >= 0.90. Computed for HUMAN
    oversight only and never exposed to agents, so it cannot be Goodhart-gamed.
    None when there are no completions."""
    completions = [e for e in events if _is_completion_event(e)]
    if not completions:
        return None
    high = sum(
        1 for e in completions
        if _is_true_flag(e.get("t7_pass")) and float(e.get("t7_score", 0) or 0) >= 0.90
    )
    return {"rate": high / len(completions), "high_impact": high, "completions": len(completions)}
