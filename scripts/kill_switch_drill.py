#!/usr/bin/env python3
"""kill_switch_drill.py — ORGANISM WS4 HEARTBEAT kill-switch + safety-rail drill (DAS-1478).

GATE-4 Testing for the WS4 heartbeat. This is the end-to-end DRILL that proves the
scheduler `--tick` (``scripts/loop_controller.py --tick``) can never run away: every
ADR-0027 safety invariant is exercised against a live, feature-flag-enabled tick in
an isolated temp workspace, and the never-auto-approve law is checked by scanning a
synthetic event log for zero gate/approval violations.

**Activate, don't duplicate (ADR-0027).** The drill imports and calls the real
brakes — ``loop_controller.tick``, ``break_glass``, ``flow_router``, the cost-ledger,
``check_loop_mode`` — never a re-implemented copy. It adds no controller logic; it is
purely an executable proof harness.

Six rails, one pass (:func:`run_all_drills`):
  * SI-3  break-glass kill-switch — an engaged override forces the tick to idle, and
          the override AUTO-EXPIRES after 60 min so dispatch resumes (bounded stop).
  * SI-4  quiet hours — a tick inside the quiet window idles.
  * SI-5  per-day budget cap — seeded spend over the cap idles the tick; the per-run
          cap is asserted present as a hard ceiling in config/budgets.yaml.
  * SI-6  max_concurrent_waves — a wave already in flight idles a new dispatch tick.
  * SI-7  never-auto-approve — the decision alphabet is the closed {dispatch, validate,
          idle} set (no approve/answer action), a synthetic event log scans to ZERO
          gate/approval violations, a seeded auto-approval is DETECTED (scanner has
          teeth), and the tick writes NOTHING to the store (it cannot sign a gate).
  * SI-2  check_loop_mode.py stays exit 0 — the loop never flips to live/auto_apply.

The cheap unit variant runs on every PR via ``tests/test_kill_switch_drill.py``
(and the ``--smoke`` step in ci.yml); the expensive >=20-iteration accumulation runs
on the scheduled ``.github/workflows/kill-switch-drill.yml`` job. All drills run in a
throwaway temp workspace — NEVER board/.events.jsonl, config/loop.yaml, or the real
config/features.yaml.

Exit codes: 0 = every rail held on every iteration, 1 = a rail failed, 2 = usage error.

Usage:
    python3 scripts/kill_switch_drill.py --smoke            # cheap: 1 pass (CI, every PR)
    python3 scripts/kill_switch_drill.py --iterations 30    # expensive: 30 passes (scheduled)
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make scripts/ importable (same pattern as every other entrypoint).
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import loop_controller as lc  # noqa: E402
from flow_router import DECISIONS, DISPATCH, IDLE, VALIDATE  # noqa: E402

_ROOT = _SCRIPTS.parent
_REAL_LOOP_CONFIG = _ROOT / "config" / "loop.yaml"
_REAL_BUDGETS = _ROOT / "config" / "budgets.yaml"

# A fixed noon UTC anchor — outside the default 22:00–06:00 quiet window.
_T_NOON = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
# 23:30 UTC — inside the default quiet window.
_T_QUIET = datetime(2026, 7, 3, 23, 30, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# SI-7 — gate/approval violation scanner (the load-bearing "zero violations" proof).
# ---------------------------------------------------------------------------

#: Actors that are NOT a human Founder — an approval/answer attributed to any of
#: these is an AUTO-approval (SI-7 forbids it). The empty string (no attributed
#: approver) is treated as automated too: a gate that "approved itself".
AUTO_ACTORS: frozenset[str] = frozenset(
    {
        "",
        "auto",
        "heartbeat",
        "loop_controller",
        "loop-controller",
        "flow_router",
        "flow-router",
        "scheduler",
        "cron",
        "cron_tick",
        "system",
        "bot",
        "agent",
        "daslab-cycle",
    }
)

#: Approval/answer decision strings that mean "granted".
_GRANTED = frozenset({"approved", "signed", "passed", "granted", "answered", "resumed"})


def _actor_is_auto(value: Any) -> bool:
    """True if *value* names an automated (non-human) actor (SI-7)."""
    return str(value or "").strip().lower() in AUTO_ACTORS


def _approval_value_is_auto(value: Any) -> bool:
    """True if an ``approval`` field is an auto-approval (``auto`` / ``auto:*``)."""
    return str(value or "").strip().lower().startswith("auto")


def scan_gate_approval_violations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the events that record an AUTO-approved gate or interrupt-card (SI-7).

    A violation is any event in which a gate was signed, an approval was granted,
    or an interrupt-card was answered/resumed **without an attributed human**
    (`approved_by`/`operator`/`interrupt_answered_by` ∈ :data:`AUTO_ACTORS`) or with
    an ``approval: auto*`` / ``auto_approved: true`` marker. A PENDING gate (awaiting
    the Founder) and a genuine human approval (`approved_by: founder`) are NOT
    violations — the scan proves the heartbeat never advances past a human gate.

    Pure and failure-isolated: non-dict entries are skipped, never raised on. An
    empty list means the log is clean (the SI-7 acceptance: count == 0).
    """
    violations: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        et = str(ev.get("event_type") or "")
        approver = ev.get("approved_by", ev.get("operator"))
        approval_val = ev.get("approval")
        decided = str(ev.get("decision") or ev.get("status") or "").strip().lower()

        auto = False
        if et in ("approval", "gate_check", "interrupt_answer", "interrupt_card"):
            auto = (
                bool(ev.get("auto_approved"))
                or _approval_value_is_auto(approval_val)
                # A GRANTED gate/approval attributed to an automated actor.
                or (decided in _GRANTED and _actor_is_auto(approver))
                # An `approval` event is a grant by definition; auto actor ⇒ violation.
                or (et == "approval" and _actor_is_auto(approver))
            )

        # An interrupt-card answered/resumed by a non-human, on any event shape.
        answered_by = ev.get("interrupt_answered_by") or ev.get("resumed_by")
        if answered_by is not None and _actor_is_auto(answered_by):
            auto = True

        if auto:
            violations.append(ev)
    return violations


def decision_alphabet_is_closed() -> bool:
    """True if the router decision set is exactly {dispatch, validate, idle} (SI-7).

    Structural proof: there is no ``approve``/``answer``/``sign`` action in the
    closed set, so the router cannot represent signing a gate or answering an
    interrupt-card.
    """
    forbidden = {"approve", "answer", "sign", "auto_approve", "grant"}
    return frozenset({DISPATCH, VALIDATE, IDLE}) == DECISIONS and not DECISIONS & forbidden


# ---------------------------------------------------------------------------
# Isolated-config writers (a drill NEVER touches real config).
# ---------------------------------------------------------------------------


def _write_flags(work_dir: Path, *, enabled: bool) -> Path:
    path = work_dir / "features.yaml"
    path.write_text(f"heartbeat_enabled: {'true' if enabled else 'false'}\n", encoding="utf-8")
    return path


def _write_schedule(work_dir: Path, *, start: str = "22:00", end: str = "06:00",
                    max_concurrent: int = 1) -> Path:
    path = work_dir / "schedule.yaml"
    path.write_text(
        f"max_concurrent_waves: {max_concurrent}\n"
        "never_auto_approve: true\n"
        "quiet_hours:\n"
        f"  start: '{start}'\n"
        f"  end: '{end}'\n"
        "  timezone: UTC\n",
        encoding="utf-8",
    )
    return path


def _write_budgets(work_dir: Path, *, per_day_usd: float) -> Path:
    path = work_dir / "budgets.yaml"
    path.write_text(
        f"caps:\n  per_day:\n    max_cost_usd: {per_day_usd}\n",
        encoding="utf-8",
    )
    return path


def _tick(work_dir: Path, *, schedule: Path, budgets: Path, flags: Path, events: Path,
          trigger: str, pending: bool, now: datetime) -> dict[str, Any]:
    """Run one real ``loop_controller.tick`` against isolated config (never real config)."""
    return lc.tick(
        schedule_path=schedule,
        loop_config=_REAL_LOOP_CONFIG,          # read-only; SI-2 asserts it is untouched
        experiments=work_dir / "experiments",
        metrics_history=work_dir / ".metrics-history.jsonl",
        events_path=events,
        budgets_path=budgets,
        feature_flags_path=flags,
        trigger=trigger,
        pending_work=pending,
        now=now,
    )


# ---------------------------------------------------------------------------
# The six rail drills. Each returns {"name", "ok", ...detail}.
# ---------------------------------------------------------------------------


def drill_break_glass(work_dir: Path) -> dict[str, Any]:
    """SI-3: an engaged break-glass halts the tick; auto-expiry restores dispatch."""
    from break_glass import append_event, build_activation, fmt_ts

    events = work_dir / "bg.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    append_event(
        build_activation(
            activation_id="BG-DRILL-001",
            reason="kill-switch drill",
            operator="sre-eng",
            created_at=fmt_ts(_T_NOON),
        ),
        path=events,
    )

    engaged = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="ticket_created", pending=True, now=_T_NOON)
    # 90 minutes later the 60-min override has auto-expired.
    expired = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="ticket_created", pending=True, now=_T_NOON + timedelta(minutes=90))

    ok = (
        engaged["safety_rails"]["break_glass_active"] is True
        and engaged["decision"]["action"] == IDLE
        and expired["safety_rails"]["break_glass_active"] is False
        and expired["decision"]["action"] == DISPATCH
    )
    return {
        "name": "SI-3 break_glass_kill_switch",
        "ok": ok,
        "engaged_action": engaged["decision"]["action"],
        "expired_action": expired["decision"]["action"],
    }


def drill_quiet_hours(work_dir: Path) -> dict[str, Any]:
    """SI-4: a dispatch tick inside the quiet window idles."""
    events = work_dir / "qh.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    quiet = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                  trigger="ticket_created", pending=True, now=_T_QUIET)
    ok = quiet["safety_rails"]["in_quiet_hours"] is True and quiet["decision"]["action"] == IDLE
    return {"name": "SI-4 quiet_hours", "ok": ok, "action": quiet["decision"]["action"]}


def drill_budget_caps(work_dir: Path) -> dict[str, Any]:
    """SI-5: per-day spend over the cap idles the tick; per-run cap is a hard ceiling."""
    import yaml
    from dgox.events import EventStore, build_span

    events = work_dir / "budget.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    # Tiny per-day cap; one opus span (priced from the REAL config) blows past it.
    budgets = _write_budgets(work_dir, per_day_usd=0.01)

    store = EventStore(events)
    store.append(
        build_span(
            ticket_id="DAS-DRILL",
            span_id="span-budget-1",
            parent_span_id=None,
            kind="invoke_agent",
            agent_name="qa-lead",
            model="opus",                 # $5.00 / 1M input tokens (config/budgets.yaml)
            start="2026-07-03T12:00:00Z",
            end="2026-07-03T12:00:01Z",
            created_at="2026-07-03T12:00:01Z",
            input_tokens=1_000_000,       # ⇒ ~$5.00 estimated cost ≫ $0.01 cap
            output_tokens=0,
            run_id="run-budget",
        )
    )

    over = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                 trigger="cron_tick", pending=True, now=_T_NOON)

    # Per-run cap presence in the REAL SSOT — a hard dispatch ceiling (ADR-0027 SI-5).
    real = yaml.safe_load(_REAL_BUDGETS.read_text(encoding="utf-8")) or {}
    per_run = ((real.get("caps") or {}).get("per_run") or {})
    per_day = ((real.get("caps") or {}).get("per_day") or {})
    per_run_ok = (
        float(per_run.get("max_cost_usd", 0) or 0) > 0
        and int(per_run.get("max_input_tokens", 0) or 0) > 0
        and int(per_run.get("max_output_tokens", 0) or 0) > 0
        and float(per_day.get("max_cost_usd", 0) or 0) >= float(per_run.get("max_cost_usd", 0) or 0)
    )

    ok = (
        over["safety_rails"]["per_day_budget_exceeded"] is True
        and over["decision"]["action"] == IDLE
        and per_run_ok
    )
    return {
        "name": "SI-5 budget_caps",
        "ok": ok,
        "per_day_action": over["decision"]["action"],
        "per_run_ceiling_ok": per_run_ok,
    }


def drill_max_concurrent(work_dir: Path) -> dict[str, Any]:
    """SI-6: a wave already in flight (run_start with no run_end) idles a dispatch tick."""
    from dgox.events import EventStore, build_run_start

    events = work_dir / "concurrent.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir, max_concurrent=1)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    # One open run: run_start with no matching run_end ⇒ a wave is in flight.
    EventStore(events).append(
        build_run_start(
            ticket_id="DAS-DRILL",
            run_id="run-in-flight",
            goal="organism-ws4-heartbeat",
            engine_version="1.2.0",
            created_at="2026-07-03T11:59:00Z",
        )
    )

    stacked = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="cron_tick", pending=True, now=_T_NOON)
    # The router degrades a would-be dispatch to idle citing SI-6.
    ok = stacked["decision"]["action"] == IDLE and "SI-6" in stacked["decision"]["reason"]
    return {
        "name": "SI-6 max_concurrent_waves",
        "ok": ok,
        "action": stacked["decision"]["action"],
        "reason": stacked["decision"]["reason"],
    }


def _synthetic_event_log() -> list[dict[str, Any]]:
    """A clean synthetic event log: real work, a PENDING gate, an UNANSWERED interrupt,
    and a genuine HUMAN approval — none of which is an auto-approval (SI-7)."""
    from dgox.events import build_routing_decision, build_run_end, build_run_start

    return [
        build_run_start(
            ticket_id="DAS-DRILL", run_id="run-1", goal="organism-ws4-heartbeat",
            engine_version="1.2.0", created_at="2026-07-03T12:00:00Z",
        ),
        build_routing_decision(
            ticket_id="DAS-DRILL", from_status="todo", to_status="in_progress",
            assignee="qa-lead", model="opus", reason="drill routing",
            confidence=0.9, policy_checks=["aadl_predecessor_gate_closed"],
            fallback="block_and_escalate_to_cto", created_at="2026-07-03T12:00:01Z",
            run_id="run-1",
        ),
        # A gate awaiting the Founder — PENDING, not granted → not a violation.
        {"event_type": "gate_check", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:02Z", "gate": "GATE-5",
         "decision": "pending", "approved_by": ""},
        # An interrupt-card raised, not yet answered → not a violation.
        {"event_type": "interrupt_card", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:03Z", "status": "open"},
        # A genuine HUMAN approval → not a violation.
        {"event_type": "approval", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:04Z", "approval": "human:founder",
         "approved_by": "founder", "decision": "approved"},
        build_run_end(
            ticket_id="DAS-DRILL", run_id="run-1", outcome="success", model="opus",
            merged_pr="PR-1", ci_status="green", t7_pass=True, t7_score=0.95,
            created_at="2026-07-03T12:05:00Z",
        ),
    ]


def drill_never_auto_approve(work_dir: Path) -> dict[str, Any]:
    """SI-7: closed decision alphabet, zero violations in a clean log, scanner has teeth,
    and a live tick writes NOTHING to the store (it cannot sign a gate)."""
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    # 1) The decision alphabet is structurally closed (no approve/answer action).
    alphabet_ok = decision_alphabet_is_closed()

    # 2) A clean synthetic event log scans to ZERO gate/approval violations.
    clean_log = _synthetic_event_log()
    clean_violations = scan_gate_approval_violations(clean_log)

    # 3) The scanner has teeth: a seeded auto-approval is detected (a false-clean
    #    scanner would silently pass every drill — this positive control prevents it).
    dirty_log = [
        *clean_log,
        {"event_type": "approval", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:06:00Z", "approval": "auto",
         "approved_by": "heartbeat", "decision": "approved"},
    ]
    dirty_violations = scan_gate_approval_violations(dirty_log)

    # 4) A live tick over a real event store writes NOTHING (heartbeat cannot sign).
    import contextlib

    from dgox.events import EventStore
    events = work_dir / "nse.events.jsonl"
    store = EventStore(events)
    for ev in clean_log:
        # only append events with a valid known envelope (gate_check/approval/interrupt
        # are reserved types the store accepts; the raw dicts validate fine)
        with contextlib.suppress(ValueError):
            store.append(ev)
    before = events.read_bytes() if events.exists() else b""
    for trigger in ("cron_tick", "ticket_created", "wave_completed",
                    "interrupt_answered", "after_n_runs"):
        _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
              trigger=trigger, pending=True, now=_T_NOON)
    after = events.read_bytes() if events.exists() else b""
    store_untouched = before == after
    post_violations = scan_gate_approval_violations(
        [__import_json_loads(line) for line in after.decode("utf-8").splitlines() if line.strip()]
    )

    ok = (
        alphabet_ok
        and len(clean_violations) == 0
        and len(dirty_violations) == 1
        and store_untouched
        and len(post_violations) == 0
    )
    return {
        "name": "SI-7 never_auto_approve",
        "ok": ok,
        "alphabet_closed": alphabet_ok,
        "clean_violations": len(clean_violations),
        "seeded_violation_detected": len(dirty_violations) == 1,
        "store_untouched": store_untouched,
        "post_tick_violations": len(post_violations),
    }


def __import_json_loads(line: str) -> dict[str, Any]:
    """Local json.loads shim (kept out of module import list for a tidy header)."""
    import json
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else {}
    except Exception:  # noqa: BLE001 — a corrupt line scans as no-violation
        return {}


def drill_loop_mode() -> dict[str, Any]:
    """SI-2: check_loop_mode.py stays exit 0 — the loop never flips to live/auto_apply."""
    import check_loop_mode as clm

    rc = clm.main(["--config", str(_REAL_LOOP_CONFIG)])
    return {"name": "SI-2 check_loop_mode", "ok": rc == 0, "exit_code": rc}


# ---------------------------------------------------------------------------
# One pass = all six rails, in an isolated temp workspace.
# ---------------------------------------------------------------------------


def run_all_drills(work_dir: Path) -> dict[str, Any]:
    """Run one pass of all six rail drills; return {"ok", "results"}."""
    work_dir.mkdir(parents=True, exist_ok=True)
    results = [
        drill_break_glass(work_dir),
        drill_quiet_hours(work_dir),
        drill_budget_caps(work_dir),
        drill_max_concurrent(work_dir),
        drill_never_auto_approve(work_dir),
        drill_loop_mode(),
    ]
    return {"ok": all(r["ok"] for r in results), "results": results}


def run_drills(*, iterations: int, tmp_root: Path) -> int:
    """Run ``iterations`` full drill passes; return a process exit code (0 = all held)."""
    print(f"kill-switch-drill: running {iterations} pass(es) of the 6 safety rails...")
    failures: list[str] = []
    for i in range(iterations):
        outcome = run_all_drills(tmp_root / f"pass-{i:03d}")
        status = "ok" if outcome["ok"] else "FAIL"
        rails = " ".join(f"{r['name'].split()[0]}={'ok' if r['ok'] else 'FAIL'}"
                         for r in outcome["results"])
        print(f"  pass[{i:03d}] {status}: {rails}")
        if not outcome["ok"]:
            for r in outcome["results"]:
                if not r["ok"]:
                    failures.append(f"pass[{i}] {r['name']}: {r}")

    if failures:
        sys.stderr.write(
            "kill-switch-drill FAILED:\n" + "\n".join(f"  - {f}" for f in failures) + "\n"
        )
        return 1
    print("kill-switch-drill: OK — every safety rail held on every pass "
          "(zero gate/approval violations, loop off).")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--smoke", action="store_true",
                       help="cheap CI variant: 1 full drill pass (every PR)")
    group.add_argument("--iterations", type=int, default=None,
                       help="expensive scheduled variant: run N full drill passes (>=20)")
    ap.add_argument("--keep", action="store_true", help="keep the temp drill directory (debug)")
    args = ap.parse_args(argv)

    iterations = 1 if args.smoke else (args.iterations if args.iterations is not None else 1)
    if iterations < 1:
        sys.stderr.write("--iterations must be >= 1\n")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="daslab-kill-switch-drill-"))
    try:
        return run_drills(iterations=iterations, tmp_root=tmp_root)
    finally:
        if not args.keep:
            import shutil
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
