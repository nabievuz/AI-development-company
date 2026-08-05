#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import flow_router as fr


def _run_start(rid: str) -> dict:
    return {"event_type": "run_start", "ticket_id": "DAS-0001", "run_id": rid,
            "goal": "g", "engine_version": "1", "created_at": "2026-07-03T00:00:00Z"}


def _run_end(rid: str) -> dict:
    return {"event_type": "run_end", "ticket_id": "DAS-0001", "run_id": rid,
            "outcome": "done", "model": "sonnet", "merged_pr": True,
            "ci_status": "green", "t7_pass": True, "t7_score": 0.95,
            "created_at": "2026-07-03T00:10:00Z"}


def _n_completed_runs(n: int) -> list[dict]:
    events: list[dict] = []
    for i in range(n):
        rid = f"run-{i:04d}"
        events.append(_run_start(rid))
        events.append(_run_end(rid))
    return events


class TestDecisionAlphabet:
    def test_decisions_are_exactly_three(self) -> None:
        assert {"dispatch", "validate", "idle"} == fr.DECISIONS

    def test_no_answer_or_approve_action_exists(self) -> None:
        for forbidden in ("answer", "approve", "resume", "sign", "gate"):
            assert forbidden not in fr.DECISIONS

    def test_triggers_are_the_five_spec_triggers(self) -> None:
        assert {
            "ticket_created", "wave_completed", "interrupt_answered",
            "after_n_runs", "cron_tick",
        } == fr.TRIGGERS

    def test_decision_as_dict(self) -> None:
        d = fr.Decision("idle", "cron_tick", "why")
        assert d.as_dict() == {"action": "idle", "trigger": "cron_tick", "reason": "why"}


class TestTriggerTicketCreated:
    def test_dispatches_when_idle(self) -> None:
        d = fr.route(fr.TickContext(trigger="ticket_created", events=[]))
        assert d.action == fr.DISPATCH

    def test_idle_when_wave_in_flight(self) -> None:
        d = fr.route(fr.TickContext(trigger="ticket_created", events=[_run_start("r1")]))
        assert d.action == fr.IDLE
        assert "SI-6" in d.reason


class TestTriggerWaveCompleted:
    def test_validates(self) -> None:
        d = fr.route(fr.TickContext(trigger="wave_completed", events=_n_completed_runs(1)))
        assert d.action == fr.VALIDATE

    def test_validate_is_safe_even_with_wave_in_flight(self) -> None:
        events = [*_n_completed_runs(1), _run_start("live")]
        d = fr.route(fr.TickContext(trigger="wave_completed", events=events))
        assert d.action == fr.VALIDATE


class TestTriggerInterruptAnswered:
    def test_dispatches_to_resume_when_idle(self) -> None:
        d = fr.route(fr.TickContext(trigger="interrupt_answered", events=[]))
        assert d.action == fr.DISPATCH
        assert "SI-7" in d.reason

    def test_idle_when_wave_in_flight(self) -> None:
        d = fr.route(fr.TickContext(trigger="interrupt_answered", events=[_run_start("r1")]))
        assert d.action == fr.IDLE

    def test_never_auto_answers_only_dispatches(self) -> None:
        idle = fr.route(fr.TickContext(trigger="interrupt_answered", events=[_run_start("r")]))
        disp = fr.route(fr.TickContext(trigger="interrupt_answered", events=[]))
        assert {idle.action, disp.action} <= fr.DECISIONS
        assert idle.action == fr.IDLE
        assert disp.action == fr.DISPATCH


class TestTriggerAfterNRuns:
    def test_validates_on_multiple_of_n(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="after_n_runs", events=_n_completed_runs(10), checkpoint_every=10))
        assert d.action == fr.VALIDATE

    def test_idle_between_checkpoints(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="after_n_runs", events=_n_completed_runs(7), checkpoint_every=10))
        assert d.action == fr.IDLE

    def test_idle_at_zero_runs(self) -> None:
        d = fr.route(fr.TickContext(trigger="after_n_runs", events=[], checkpoint_every=10))
        assert d.action == fr.IDLE


class TestTriggerCronTick:
    def test_dispatches_pending_work(self) -> None:
        d = fr.route(fr.TickContext(trigger="cron_tick", events=[], pending_work=True))
        assert d.action == fr.DISPATCH

    def test_validate_when_checkpoint_due_and_no_pending(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="cron_tick", events=_n_completed_runs(10), checkpoint_every=10))
        assert d.action == fr.VALIDATE

    def test_idle_when_nothing_pending(self) -> None:
        d = fr.route(fr.TickContext(trigger="cron_tick", events=_n_completed_runs(3)))
        assert d.action == fr.IDLE

    def test_pending_dispatch_withheld_when_wave_in_flight(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="cron_tick", events=[_run_start("r1")], pending_work=True))
        assert d.action == fr.IDLE


class TestDispatchSafetyGates:
    def test_break_glass_forces_idle(self) -> None:
        d = fr.route(fr.TickContext(trigger="ticket_created", events=[], break_glass_active=True))
        assert d.action == fr.IDLE
        assert "SI-3" in d.reason

    def test_quiet_hours_forces_idle(self) -> None:
        d = fr.route(fr.TickContext(trigger="ticket_created", events=[], in_quiet_hours=True))
        assert d.action == fr.IDLE
        assert "SI-4" in d.reason

    def test_budget_exceeded_forces_idle(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="interrupt_answered", events=[], per_day_budget_exceeded=True))
        assert d.action == fr.IDLE
        assert "SI-5" in d.reason

    def test_monthly_credit_exhausted_forces_idle(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="ticket_created", events=[], monthly_credit_exhausted=True))
        assert d.action == fr.IDLE
        assert "SI-5" in d.reason and "FR-004" in d.reason
        assert "sanctioned pause" in d.reason

    def test_monthly_credit_exhausted_is_a_reason_never_a_fourth_action(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="interrupt_answered", events=[], monthly_credit_exhausted=True))
        assert d.action in fr.DECISIONS
        assert d.action == fr.IDLE
        assert frozenset({"dispatch", "validate", "idle"}) == fr.DECISIONS

    def test_monthly_credit_exhausted_never_blocks_validate(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="wave_completed", events=[], monthly_credit_exhausted=True))
        assert d.action == fr.VALIDATE

    def test_monthly_credit_exhausted_never_raises_or_errors(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="cron_tick", events=[], pending_work=True, monthly_credit_exhausted=True))
        assert d.action == fr.IDLE

    def test_gates_do_not_block_validate(self) -> None:
        d = fr.route(fr.TickContext(
            trigger="wave_completed", events=[], break_glass_active=True,
            in_quiet_hours=True, per_day_budget_exceeded=True, monthly_credit_exhausted=True))
        assert d.action == fr.VALIDATE


class TestInFlightDetection:
    def test_runs_in_flight_pairs_by_run_id(self) -> None:
        events = [_run_start("a"), _run_start("b"), _run_end("a")]
        assert fr._runs_in_flight(events) == {"b"}

    def test_completed_run_count(self) -> None:
        assert fr._completed_run_count(_n_completed_runs(4)) == 4

    def test_max_concurrent_waves_is_one(self) -> None:
        assert fr.MAX_CONCURRENT_WAVES == 1


class TestDeterminism:
    def test_same_stream_same_decision(self) -> None:
        events = _n_completed_runs(10)
        results = {
            fr.route(fr.TickContext(trigger="after_n_runs", events=events)).action
            for _ in range(25)
        }
        assert results == {"validate"}

    def test_all_triggers_deterministic(self) -> None:
        events = [_run_start("live")]
        for trig in fr.TRIGGERS:
            a = fr.route(fr.TickContext(trigger=trig, events=events)).action
            b = fr.route(fr.TickContext(trigger=trig, events=events)).action
            assert a == b
            assert a in fr.DECISIONS


class TestFailureIsolation:
    def test_unknown_trigger_degrades_to_idle(self) -> None:
        d = fr.route(fr.TickContext(trigger="not_a_trigger", events=[]))
        assert d.action == fr.IDLE

    def test_malformed_events_do_not_crash(self) -> None:
        junk = [None, 42, "string", [], {"no": "type"}, {"event_type": "run_start"}]

        d = fr.route(fr.TickContext(trigger="ticket_created", events=junk))
        assert d.action in fr.DECISIONS

    def test_handler_exception_degrades_to_idle(self, monkeypatch) -> None:
        def boom(_ctx):
            raise RuntimeError("kaboom")

        monkeypatch.setitem(fr._HANDLERS, "cron_tick", boom)
        d = fr.route(fr.TickContext(trigger="cron_tick", events=[]))
        assert d.action == fr.IDLE
        assert "degraded to idle" in d.reason

    def test_reader_error_yields_empty_stream(self, monkeypatch) -> None:
        import wave_kpi

        def boom(*_a, **_k):
            raise OSError("disk gone")

        monkeypatch.setattr(wave_kpi, "read_events", boom)

        d = fr.route_from_store("ticket_created")
        assert d.action in fr.DECISIONS


class TestStoreReader:
    def test_read_event_stream_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert fr.read_event_stream(str(tmp_path / "nope.jsonl")) == []

    def test_route_from_store_reads_via_wave_kpi(self, tmp_path: Path, monkeypatch) -> None:
        import wave_kpi

        called: dict[str, object] = {}
        sentinel = [_run_start("live")]

        def fake_read_events(path=None):
            called["path"] = path
            return sentinel

        monkeypatch.setattr(wave_kpi, "read_events", fake_read_events)
        d = fr.route_from_store("ticket_created", path="X")
        assert called["path"] == "X"

        assert d.action == fr.IDLE

    def test_route_from_store_end_to_end_with_real_reader(self, tmp_path: Path) -> None:
        store = tmp_path / "events.jsonl"
        import json as _json
        with open(store, "w", encoding="utf-8") as fh:
            for ev in _n_completed_runs(10):
                fh.write(_json.dumps(ev) + "\n")
        d = fr.route_from_store("after_n_runs", path=str(store), checkpoint_every=10)
        assert d.action == fr.VALIDATE


class TestCLI:
    def test_cli_prints_decision_exit_zero(self, capsys, tmp_path: Path) -> None:
        rc = fr.main(["--trigger", "cron_tick", "--events", str(tmp_path / "none.jsonl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "cron_tick ->" in out
        assert "idle" in out

    def test_cli_json_output(self, capsys, tmp_path: Path) -> None:
        rc = fr.main(["--trigger", "ticket_created", "--events", str(tmp_path / "none.jsonl"), "--json"])
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out)
        assert payload["action"] == "dispatch"
        assert payload["trigger"] == "ticket_created"

    def test_cli_pending_work_flag_dispatches(self, capsys, tmp_path: Path) -> None:
        rc = fr.main(["--trigger", "cron_tick", "--events", str(tmp_path / "none.jsonl"),
                      "--pending-work", "--json"])
        assert rc == 0
        import json as _json
        assert _json.loads(capsys.readouterr().out)["action"] == "dispatch"

    def test_cli_credit_exhausted_flag_withholds_dispatch(self, capsys, tmp_path: Path) -> None:
        rc = fr.main(["--trigger", "cron_tick", "--events", str(tmp_path / "none.jsonl"),
                      "--pending-work", "--credit-exhausted", "--json"])
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out)
        assert payload["action"] == "idle"
        assert "FR-004" in payload["reason"]


class TestRouteFromStoreCreditKwarg:
    def test_credit_exhausted_kwarg_withholds_dispatch(self, tmp_path: Path) -> None:
        d = fr.route_from_store("ticket_created", path=str(tmp_path / "none.jsonl"),
                                credit_exhausted=True)
        assert d.action == fr.IDLE
        assert "FR-004" in d.reason
