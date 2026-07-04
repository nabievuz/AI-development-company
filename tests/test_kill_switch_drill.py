#!/usr/bin/env python3
"""tests/test_kill_switch_drill.py — WS4 HEARTBEAT kill-switch + safety-rail drill (DAS-1478).

The CHEAP tier of the ORGANISM WS4 kill-switch/safety-rail proof (GATE-4 Testing).
Runs on every PR via `pytest -q`; the expensive >=20-iteration accumulation runs on
the scheduled `.github/workflows/kill-switch-drill.yml` job.

Asserts the ADR-0027 safety envelope the heartbeat operates inside:
  - SI-2  check_loop_mode.py stays exit 0 (loop never flips to live/auto_apply)
  - SI-3  break-glass halts the tick; the 60-min override auto-expires (bounded stop)
  - SI-4  quiet hours idle a dispatch tick
  - SI-5  per-day budget breach idles the tick; per-run cap is a hard ceiling
  - SI-6  a wave in flight idles a new dispatch tick (max_concurrent_waves=1)
  - SI-7  closed decision alphabet + a synthetic event log with ZERO gate/approval
          violations + a scanner that actually detects a seeded auto-approval +
          a live tick that writes NOTHING to the store (cannot sign a gate)

These import and call the real brakes (loop_controller/break_glass/flow_router/
cost-ledger/check_loop_mode) via scripts/kill_switch_drill.py — never a re-impl.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import kill_switch_drill as ksd  # noqa: E402
from flow_router import DISPATCH, IDLE, VALIDATE  # noqa: E402

# ---------------------------------------------------------------------------
# SI-7 — the gate/approval violation scanner (the "zero violations" proof).
# ---------------------------------------------------------------------------

class TestScanGateApprovalViolations:
    """scan_gate_approval_violations distinguishes human approvals from auto ones."""

    def test_clean_log_has_zero_violations(self):
        log = ksd._synthetic_event_log()
        assert ksd.scan_gate_approval_violations(log) == []

    def test_pending_gate_is_not_a_violation(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-1",
                "created_at": "t", "decision": "pending", "approved_by": ""}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_human_approval_is_not_a_violation(self):
        log = [{"event_type": "approval", "ticket_id": "DAS-1", "created_at": "t",
                "approval": "human:founder", "approved_by": "founder", "decision": "approved"}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_auto_approval_value_is_a_violation(self):
        log = [{"event_type": "approval", "ticket_id": "DAS-1", "created_at": "t",
                "approval": "auto", "approved_by": "founder"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_heartbeat_signed_gate_is_a_violation(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-1", "created_at": "t",
                "decision": "approved", "approved_by": "heartbeat"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_auto_approved_flag_is_a_violation(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-1", "created_at": "t",
                "auto_approved": True, "approved_by": "founder"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_auto_answered_interrupt_is_a_violation(self):
        log = [{"event_type": "interrupt_card", "ticket_id": "DAS-1", "created_at": "t",
                "interrupt_answered_by": "loop_controller"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_empty_approver_counts_as_auto(self):
        """A granted approval with no attributed human (empty approver) is auto."""
        log = [{"event_type": "approval", "ticket_id": "DAS-1", "created_at": "t",
                "approved_by": "", "decision": "approved"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_non_dict_entries_are_skipped(self):
        assert ksd.scan_gate_approval_violations(["nope", None, 42]) == []


# ---------------------------------------------------------------------------
# SI-7 — the closed decision alphabet (structural never-auto-approve).
# ---------------------------------------------------------------------------

class TestDecisionAlphabetClosed:
    def test_alphabet_is_exactly_dispatch_validate_idle(self):
        from flow_router import DECISIONS
        assert frozenset({DISPATCH, VALIDATE, IDLE}) == DECISIONS

    def test_no_approve_or_answer_action_exists(self):
        assert ksd.decision_alphabet_is_closed() is True

    def test_alphabet_helper_rejects_forbidden_actions(self):
        from flow_router import DECISIONS
        for forbidden in ("approve", "answer", "sign", "grant", "auto_approve"):
            assert forbidden not in DECISIONS


# ---------------------------------------------------------------------------
# Individual rail drills (cheap, deterministic — the SI-3..SI-7 + SI-2 proofs).
# ---------------------------------------------------------------------------

class TestRailDrills:
    """Each rail drill returns ok=True in an isolated temp workspace."""

    def test_break_glass_halts_and_auto_expires(self, tmp_path):
        r = ksd.drill_break_glass(tmp_path)
        assert r["ok"] is True
        assert r["engaged_action"] == IDLE       # SI-3: engaged → halt
        assert r["expired_action"] == DISPATCH   # bounded: auto-expiry restores dispatch

    def test_quiet_hours_idle(self, tmp_path):
        r = ksd.drill_quiet_hours(tmp_path)
        assert r["ok"] is True
        assert r["action"] == IDLE

    def test_budget_caps_fire(self, tmp_path):
        r = ksd.drill_budget_caps(tmp_path)
        assert r["ok"] is True
        assert r["per_day_action"] == IDLE       # SI-5 per-day breach → idle
        assert r["per_run_ceiling_ok"] is True   # SI-5 per-run cap present as hard ceiling

    def test_max_concurrent_rail(self, tmp_path):
        r = ksd.drill_max_concurrent(tmp_path)
        assert r["ok"] is True
        assert r["action"] == IDLE               # SI-6: a wave in flight → no stacked wave
        assert "SI-6" in r["reason"]

    def test_never_auto_approve(self, tmp_path):
        r = ksd.drill_never_auto_approve(tmp_path)
        assert r["ok"] is True
        assert r["alphabet_closed"] is True
        assert r["clean_violations"] == 0                 # zero gate/approval violations
        assert r["seeded_violation_detected"] is True     # scanner has teeth
        assert r["store_untouched"] is True               # tick never signs a gate
        assert r["post_tick_violations"] == 0

    def test_check_loop_mode_stays_exit_0(self):
        r = ksd.drill_loop_mode()
        assert r["ok"] is True
        assert r["exit_code"] == 0


# ---------------------------------------------------------------------------
# The full drill pass + CLI entrypoint (the scheduled job's unit).
# ---------------------------------------------------------------------------

class TestFullDrillPass:
    def test_run_all_drills_ok(self, tmp_path):
        outcome = ksd.run_all_drills(tmp_path / "pass")
        assert outcome["ok"] is True
        names = {r["name"].split()[0] for r in outcome["results"]}
        assert names == {"SI-3", "SI-4", "SI-5", "SI-6", "SI-7", "SI-2"}

    def test_smoke_cli_exits_0(self):
        assert ksd.main(["--smoke"]) == 0

    def test_iterations_cli_exits_0(self):
        assert ksd.main(["--iterations", "2"]) == 0

    def test_bad_iterations_is_usage_error(self):
        assert ksd.main(["--iterations", "0"]) == 2


# ---------------------------------------------------------------------------
# Isolation guarantee — the drill never touches real board/config state.
# ---------------------------------------------------------------------------

class TestDrillIsolation:
    def test_drill_does_not_touch_real_event_store(self, tmp_path):
        real_events = REPO_ROOT / "board" / ".events.jsonl"
        before = real_events.read_bytes() if real_events.exists() else None
        ksd.run_all_drills(tmp_path / "pass")
        after = real_events.read_bytes() if real_events.exists() else None
        assert before == after, "drill must never write board/.events.jsonl"

    def test_drill_does_not_touch_real_loop_config(self, tmp_path):
        import yaml
        loop_cfg = REPO_ROOT / "config" / "loop.yaml"
        before = loop_cfg.read_text(encoding="utf-8")
        ksd.run_all_drills(tmp_path / "pass")
        after = loop_cfg.read_text(encoding="utf-8")
        assert before == after, "drill must never edit config/loop.yaml (SI-2)"
        data = yaml.safe_load(after) or {}
        assert data.get("mode") == "shadow"
        assert data.get("auto_apply") is False
