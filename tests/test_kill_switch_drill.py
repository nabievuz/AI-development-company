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
# SI-7 — DAS-1637: deny-list → allow-list inversion, reviewer's positive-
# control battery. Every row must flag; every previously-caught control must
# still be caught; founder/pending must still NOT flag. This is the exact
# battery the QA Lead ran against the (buggy) real scanner in the DAS-1621
# review — do not weaken it to make the inversion look simpler than it is.
# ---------------------------------------------------------------------------

class TestAllowListInversion:
    """DAS-1637 — an agent role-key approval must now be flagged (was silently
    missed by the old deny-list, since it isn't heartbeat/scheduler/cron/bot)."""

    def test_gate_check_approved_by_qa_lead_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "gate": "GATE-5", "decision": "approved", "approved_by": "qa-lead"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_gate_check_approved_by_claude_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "gate": "GATE-5", "decision": "approved", "approved_by": "claude"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_gate_check_approved_by_subagent_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "gate": "GATE-5", "decision": "approved", "approved_by": "subagent"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_approval_approved_by_orchestrator_is_flagged(self):
        log = [{"event_type": "approval", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "approved", "approved_by": "orchestrator"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_interrupt_answer_answered_by_cto_is_flagged(self):
        log = [{"event_type": "interrupt_answer", "ticket_id": "DAS-X", "created_at": "t",
                "status": "answered", "approved_by": "cto"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_config_write_heartbeat_enabled_true_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": True}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_config_write_heartbeat_enabled_false_is_not_flagged(self):
        """Turning the flag OFF is not the dangerous direction — only ON is a violation."""
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": False}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_config_write_other_key_is_not_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "some_other_flag", "value": True}]
        assert ksd.scan_gate_approval_violations(log) == []

    # -- previously-caught controls must still be caught (no regression) -----

    def test_approval_auto_still_flagged(self):
        log = [{"event_type": "approval", "ticket_id": "DAS-X", "created_at": "t",
                "approval": "auto", "approved_by": "founder"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_approved_by_heartbeat_still_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "approved", "approved_by": "heartbeat"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_auto_approved_true_still_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "auto_approved": True, "approved_by": "founder"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_resumed_by_scheduler_still_flagged(self):
        log = [{"event_type": "interrupt_card", "ticket_id": "DAS-X", "created_at": "t",
                "resumed_by": "scheduler"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    # -- must still NOT flag a genuine human approval / pending gate ---------

    def test_approved_by_founder_still_not_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "gate": "GATE-5", "decision": "approved", "approved_by": "founder"}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_pending_gate_still_not_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "gate": "GATE-5", "decision": "pending", "approved_by": ""}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_synthetic_clean_log_unanswered_interrupt_still_not_flagged(self):
        """The raised-but-unanswered interrupt card in the synthetic clean log
        (status: open, no decision, no actor) must stay clean under the
        _NOT_GRANTED inversion — 'open' is a real not-yet-decided state."""
        log = ksd._synthetic_event_log()
        assert ksd.scan_gate_approval_violations(log) == []


# ---------------------------------------------------------------------------
# SI-7 — DAS-1638: `_GRANTED` allow-list → `_NOT_GRANTED` clearly-not-granted
# set, unknown verbs treated as GRANTED (fail closed), plus `event_type`
# normalisation. Seeded battery per the DAS-1638 ticket — every slipping case
# must flag; `decision: "rejected"` by an agent must still NOT flag; every
# DAS-1637 case above must still flag (re-asserted in TestAllowListInversion).
# ---------------------------------------------------------------------------

class TestGrantVerbFailClosed:
    """Item 1 — unrecognised grant verbs and event_type spellings no longer slip."""

    def test_unrecognised_verb_accepted_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "accepted", "approved_by": "qa-lead"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_unrecognised_verb_ok_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "ok", "approved_by": "subagent"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_unrecognised_verb_signed_off_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "signed_off", "approved_by": "orchestrator"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_event_type_gate_check_uppercase_is_flagged(self):
        log = [{"event_type": "GATE_CHECK", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "approved", "approved_by": "claude"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_event_type_gate_decision_alias_is_flagged(self):
        log = [{"event_type": "gate_decision", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "approved", "approved_by": "cto"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_event_type_aadl_gate_alias_is_flagged(self):
        log = [{"event_type": "aadl_gate", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "approved", "approved_by": "heartbeat"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_missing_decision_field_by_agent_is_flagged(self):
        """No decision key at all + non-human actor: ambiguous ⇒ fail closed."""
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "approved_by": "subagent"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_empty_string_decision_by_agent_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "", "approved_by": "orchestrator"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_none_decision_by_agent_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": None, "approved_by": "qa-lead"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_non_string_decision_by_agent_is_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": True, "approved_by": "claude"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    # -- must NOT flag: genuine rejection by an agent -----------------------

    def test_rejected_by_agent_is_not_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "rejected", "approved_by": "subagent"}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_denied_by_agent_is_not_flagged(self):
        log = [{"event_type": "gate_check", "ticket_id": "DAS-X", "created_at": "t",
                "decision": "denied", "approved_by": "orchestrator"}]
        assert ksd.scan_gate_approval_violations(log) == []


class TestFlagFlipFailClosed:
    """Item 2 — `_config_write_flips_heartbeat_on` fails closed on an
    unparseable value; the `value: null` / `new_value` fallback is fixed."""

    def test_key_only_no_value_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_value_none_no_new_value_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": None}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_value_unparseable_string_enabled_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": "enabled"}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_changes_shape_true_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "changes": {"heartbeat_enabled": True}}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_changes_shape_unparseable_is_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "changes": {"heartbeat_enabled": "enabled"}}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_value_null_new_value_true_fallback_is_flagged(self):
        """The DAS-1638 wart: `ev.get("value", ev.get("new_value"))` only
        fell back when `value` was ABSENT, not when it was present-but-null."""
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": None, "new_value": True}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    def test_event_type_case_variant_config_write_is_flagged(self):
        log = [{"event_type": "CONFIG_WRITE", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": True}]
        assert len(ksd.scan_gate_approval_violations(log)) == 1

    # -- must NOT flag: OFF is still safe, unrelated key still safe ---------

    def test_value_false_is_not_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": False}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_value_string_off_is_not_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": "off"}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_unrelated_key_is_not_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "some_other_flag", "value": "enabled"}]
        assert ksd.scan_gate_approval_violations(log) == []

    def test_value_null_new_value_false_is_not_flagged(self):
        log = [{"event_type": "config_write", "ticket_id": "DAS-X", "created_at": "t",
                "key": "heartbeat_enabled", "value": None, "new_value": False}]
        assert ksd.scan_gate_approval_violations(log) == []


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
