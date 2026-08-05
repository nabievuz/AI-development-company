#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import loop_controller as lc
from flow_router import DECISIONS, DISPATCH, IDLE, VALIDATE

_ROOT = _SCRIPTS.parent
_REAL_LOOP_CONFIG = _ROOT / "config" / "loop.yaml"
_REAL_BUDGETS = _ROOT / "config" / "budgets.yaml"


_T_NOON = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)

_T_QUIET = datetime(2026, 7, 3, 23, 30, 0, tzinfo=UTC)


ALLOWED_HUMAN_ACTORS: frozenset[str] = frozenset({"founder"})


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


_NOT_GRANTED = frozenset({
    "rejected", "denied", "declined", "revoked", "withdrawn",
    "pending", "deferred", "blocked", "waiting",
    "open", "unanswered", "unresolved", "raised",
})


_GRANTED = frozenset({"approved", "signed", "passed", "granted", "answered", "resumed"})


_HEARTBEAT_FLAG_KEYS = frozenset({"heartbeat_enabled"})


_EVENT_TYPE_ALIASES: dict[str, str] = {
    "gate_check": "gate_check",
    "gate-check": "gate_check",
    "gatecheck": "gate_check",
    "gate_decision": "gate_check",
    "gate-decision": "gate_check",
    "gatedecision": "gate_check",
    "aadl_gate": "gate_check",
    "aadl-gate": "gate_check",
    "aadlgate": "gate_check",
    "approval": "approval",
    "interrupt_answer": "interrupt_answer",
    "interrupt-answer": "interrupt_answer",
    "interruptanswer": "interrupt_answer",
    "interrupt_card": "interrupt_card",
    "interrupt-card": "interrupt_card",
    "interruptcard": "interrupt_card",
    "config_write": "config_write",
    "config-write": "config_write",
    "configwrite": "config_write",
}


def _normalize_event_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _EVENT_TYPE_ALIASES.get(raw, raw)


def _actor_is_human(value: Any) -> bool:
    return str(value or "").strip().lower() in ALLOWED_HUMAN_ACTORS


def _actor_is_auto(value: Any) -> bool:
    return not _actor_is_human(value)


def _approval_value_is_auto(value: Any) -> bool:
    return str(value or "").strip().lower().startswith("auto")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


_FALSY_STRINGS = frozenset({"false", "0", "no", "off"})
_TRUTHY_STRINGS = frozenset({"true", "1", "yes", "on"})


def _parse_flag_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, int | float):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _TRUTHY_STRINGS:
            return True
        if s in _FALSY_STRINGS:
            return False
        return None

    return None


def _resolved_flag_value(d: dict[str, Any]) -> Any:
    if "value" in d and d["value"] is not None:
        return d["value"]
    return d.get("new_value")


def _config_write_flips_heartbeat_on(ev: dict[str, Any]) -> bool:
    key = str(ev.get("key") or ev.get("field") or ev.get("setting") or "").strip().lower()
    if key in _HEARTBEAT_FLAG_KEYS:
        parsed = _parse_flag_bool(_resolved_flag_value(ev))
        if parsed is not False:
            return True

    changes = ev.get("changes")
    if isinstance(changes, dict):
        for flag_key in _HEARTBEAT_FLAG_KEYS:
            if flag_key in changes:
                parsed = _parse_flag_bool(changes[flag_key])
                if parsed is not False:
                    return True
    return False


def scan_gate_approval_violations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        et = _normalize_event_type(ev.get("event_type"))
        approver = ev.get("approved_by", ev.get("operator"))
        approval_val = ev.get("approval")
        decided = str(ev.get("decision") or ev.get("status") or "").strip().lower()

        auto = False
        if et in ("approval", "gate_check", "interrupt_answer", "interrupt_card"):
            auto = (
                bool(ev.get("auto_approved"))
                or _approval_value_is_auto(approval_val)


                or (decided not in _NOT_GRANTED and not _actor_is_human(approver))

                or (et == "approval" and not _actor_is_human(approver))
            )


        answered_by = ev.get("interrupt_answered_by") or ev.get("resumed_by")
        if answered_by is not None and not _actor_is_human(answered_by):
            auto = True


        if et == "config_write" and _config_write_flips_heartbeat_on(ev):
            auto = True

        if auto:
            violations.append(ev)
    return violations


def decision_alphabet_is_closed() -> bool:
    forbidden = {"approve", "answer", "sign", "auto_approve", "grant"}
    return frozenset({DISPATCH, VALIDATE, IDLE}) == DECISIONS and not DECISIONS & forbidden


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
        "caps:\n"
        f"  per_run:\n    max_cost_usd: {per_day_usd}\n"
        f"  per_day:\n    max_cost_usd: {per_day_usd}\n"
        "mustaqil:\n"
        "  caps:\n"
        f"    per_day:\n      max_cost_usd: {per_day_usd}\n"
        "tiers:\n"
        "  opus:\n"
        "    input_per_1m: 5.00\n"
        "    cached_input_per_1m: 0.50\n"
        "    output_per_1m: 25.00\n"
        "  sonnet:\n"
        "    input_per_1m: 3.00\n"
        "    cached_input_per_1m: 0.30\n"
        "    output_per_1m: 15.00\n"
        "  haiku:\n"
        "    input_per_1m: 1.00\n"
        "    cached_input_per_1m: 0.10\n"
        "    output_per_1m: 5.00\n",
        encoding="utf-8",
    )
    return path


def _tick(work_dir: Path, *, schedule: Path, budgets: Path, flags: Path, events: Path,
          trigger: str, pending: bool, now: datetime) -> dict[str, Any]:
    return lc.tick(
        schedule_path=schedule,
        loop_config=_REAL_LOOP_CONFIG,
        experiments=work_dir / "experiments",
        metrics_history=work_dir / ".metrics-history.jsonl",
        events_path=events,
        budgets_path=budgets,
        feature_flags_path=flags,
        trigger=trigger,
        pending_work=pending,
        now=now,
    )


def drill_break_glass(work_dir: Path) -> dict[str, Any]:
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
    events = work_dir / "qh.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    quiet = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                  trigger="ticket_created", pending=True, now=_T_QUIET)
    ok = quiet["safety_rails"]["in_quiet_hours"] is True and quiet["decision"]["action"] == IDLE
    return {"name": "SI-4 quiet_hours", "ok": ok, "action": quiet["decision"]["action"]}


def drill_budget_caps(work_dir: Path) -> dict[str, Any]:
    import yaml
    from dgox.events import EventStore, build_span

    events = work_dir / "budget.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)

    budgets = _write_budgets(work_dir, per_day_usd=0.01)

    store = EventStore(events)
    store.append(
        build_span(
            ticket_id="DAS-DRILL",
            span_id="span-budget-1",
            parent_span_id=None,
            kind="invoke_agent",
            agent_name="qa-lead",
            model="opus",
            start="2026-07-03T12:00:00Z",
            end="2026-07-03T12:00:01Z",
            created_at="2026-07-03T12:00:01Z",
            input_tokens=1_000_000,
            output_tokens=0,
            run_id="run-budget",
        )
    )

    over = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                 trigger="cron_tick", pending=True, now=_T_NOON)


    real = yaml.safe_load(_REAL_BUDGETS.read_text(encoding="utf-8")) or {}
    _real_mustaqil_caps = (real.get("mustaqil") or {}).get("caps") or {}
    per_run = (_real_mustaqil_caps.get("per_run") or {})
    per_day = (_real_mustaqil_caps.get("per_day") or {})
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
    from dgox.events import EventStore, build_run_start

    events = work_dir / "concurrent.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir, max_concurrent=1)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)


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

    ok = stacked["decision"]["action"] == IDLE and "SI-6" in stacked["decision"]["reason"]
    return {
        "name": "SI-6 max_concurrent_waves",
        "ok": ok,
        "action": stacked["decision"]["action"],
        "reason": stacked["decision"]["reason"],
    }


def _synthetic_event_log() -> list[dict[str, Any]]:
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

        {"event_type": "gate_check", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:02Z", "gate": "GATE-5",
         "decision": "pending", "approved_by": ""},

        {"event_type": "interrupt_card", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:03Z", "status": "open"},

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
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)


    alphabet_ok = decision_alphabet_is_closed()


    clean_log = _synthetic_event_log()
    clean_violations = scan_gate_approval_violations(clean_log)


    dirty_log = [
        *clean_log,
        {"event_type": "approval", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:06:00Z", "approval": "auto",
         "approved_by": "heartbeat", "decision": "approved"},
    ]
    dirty_violations = scan_gate_approval_violations(dirty_log)


    import contextlib

    from dgox.events import EventStore
    events = work_dir / "nse.events.jsonl"
    store = EventStore(events)
    for ev in clean_log:


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
    import json
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def drill_loop_mode() -> dict[str, Any]:
    import check_loop_mode as clm

    rc = clm.main(["--config", str(_REAL_LOOP_CONFIG)])
    return {"name": "SI-2 check_loop_mode", "ok": rc == 0, "exit_code": rc}


def run_all_drills(work_dir: Path) -> dict[str, Any]:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='kill_switch_drill.py — ORGANISM WS4 HEARTBEAT kill-switch + safety-rail drill (DAS-1478).')
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
