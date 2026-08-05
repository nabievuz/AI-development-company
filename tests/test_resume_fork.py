
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc
import replay_qa as rq
import resume_fork as rf

FIXED_TS = "2026-07-03T12:00:00Z"
FIXED_TS2 = "2026-07-03T12:01:00Z"
FIXED_TS3 = "2026-07-03T12:02:00Z"
ANCHOR_RUN = "TEST-RUN-01"
TICKET_A = "DAS-9001"
TICKET_B = "DAS-9002"
TICKET_C = "DAS-9003"


def _routing_ev(
    ticket_id: str,
    from_status: str,
    to_status: str,
    created_at: str,
    run_id: str | None = None,
) -> dict:
    ev: dict = {
        "event_type": "routing_decision",
        "ticket_id": ticket_id,
        "from_status": from_status,
        "to_status": to_status,
        "assignee": "backend-eng-1",
        "model": "sonnet",
        "reason": "test",
        "confidence": 0.9,
        "policy_checks": ["test"],
        "fallback": "skip",
        "created_at": created_at,
    }
    if run_id is not None:
        ev["run_id"] = run_id
    return ev


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _write_checkpoint(
    runs_dir: Path,
    run_id: str,
    wave: int,
    ticket_states: dict[str, str],
) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cp = {
        "run_id": run_id,
        "wave": wave,
        "created_at": FIXED_TS,
        "board_hash": f"sha256:{'0' * 64}",
        "event_offset": 0,
        "ticket_states": ticket_states,
        "pending_interrupts": [],
        "ledger_hashes": {"prev": f"sha256:{'0' * 64}", "self": f"sha256:{'1' * 64}"},
    }
    cp_path = run_dir / f"wave-{wave:03d}.checkpoint.json"
    cp_path.write_text(json.dumps(cp), encoding="utf-8")


class TestGetUnfinishedTickets:

    def test_unfinished_ticket_returned(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A in result
        assert result[TICKET_A] == "in_progress"

    def test_done_ticket_not_returned(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result

    def test_blocked_ticket_not_returned(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "blocked", FIXED_TS2, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result

    def test_mixed_tickets_correct_partition(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [

            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),

            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS3, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result
        assert TICKET_B in result
        assert result[TICKET_B] == "in_progress"

    def test_corrupted_chain_raises(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [

            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),

            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "done", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),
        ])
        with pytest.raises(ValueError, match="Corrupted"):
            rf.get_unfinished_tickets(ANCHOR_RUN, events_path)

    def test_empty_when_run_not_found(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id="other-run"),
        ])
        result = rf.get_unfinished_tickets("nonexistent-run-id", events_path)
        assert result == {}

    def test_empty_when_no_events_file(self, tmp_path: Path) -> None:
        events_path = tmp_path / "no-events.jsonl"
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert result == {}

    def test_uses_ticket_id_fallback_grouping(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"

        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS),
        ])

        result = rf.get_unfinished_tickets(TICKET_A, events_path)
        assert TICKET_A in result
        assert result[TICKET_A] == "in_progress"

    def test_invalid_status_is_corrupted(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "frobnicate", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        with pytest.raises(ValueError, match="Corrupted"):
            rf.get_unfinished_tickets(ANCHOR_RUN, events_path)


class TestResumeRun:

    def test_resume_returns_unfinished(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        assert TICKET_A in result

    def test_resume_excludes_completed(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"


        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])


        pc.append_ticket_completion(
            run_id=ANCHOR_RUN,
            ticket_id=TICKET_A,
            status="done",
            wave=1,
            created_at=FIXED_TS2,
            runs_dir=runs_dir,
        )

        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)

        assert TICKET_A not in result

    def test_resume_partial_completion(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [

            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),

            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS2, run_id=ANCHOR_RUN),
        ])


        pc.append_ticket_completion(
            run_id=ANCHOR_RUN,
            ticket_id=TICKET_A,
            status="in_review",
            wave=1,
            created_at=FIXED_TS3,
            runs_dir=runs_dir,
        )

        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        assert TICKET_A not in result, "TICKET_A has completion record; must not re-dispatch"
        assert TICKET_B in result, "TICKET_B has no completion record; must re-dispatch"

    def test_resume_empty_when_all_terminal(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS3, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "in_progress", "blocked", "2026-07-03T12:03:00Z", run_id=ANCHOR_RUN),
        ])

        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        assert result == {}

    def test_resume_refuses_corrupted_chain(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "done", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),
        ])

        with pytest.raises(ValueError, match="Corrupted"):
            rf.resume_run(ANCHOR_RUN, events_path, runs_dir)

    def test_resume_no_duplicate_dispatch(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS3, run_id=ANCHOR_RUN),
        ])

        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        assert TICKET_A not in result, "TICKET_A is done — must NOT be re-dispatched"
        assert TICKET_B in result, "TICKET_B is in_progress — must be re-dispatched"


class TestForkRun:

    def test_fork_returns_new_run_id(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        new_run_id, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert new_run_id != ANCHOR_RUN
        assert len(new_run_id) == 26

    def test_fork_ticket_states_from_checkpoint(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        expected_states = {TICKET_A: "in_progress", TICKET_B: "done"}
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states=expected_states)

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert ticket_states == expected_states

    def test_fork_layered_checkpoints(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"

        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=2,
            ticket_states={TICKET_A: "in_review", TICKET_B: "in_progress"},
        )

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=2, runs_dir=runs_dir)
        assert ticket_states[TICKET_A] == "in_review"
        assert ticket_states[TICKET_B] == "in_progress"

    def test_fork_at_wave1_only_wave1_state(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})
        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=2,
            ticket_states={TICKET_A: "done", TICKET_B: "in_progress"},
        )

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)

        assert ticket_states.get(TICKET_A) == "in_progress"
        assert TICKET_B not in ticket_states

    def test_fork_original_events_unchanged(self, tmp_path: Path) -> None:
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        original_events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, original_events)
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        before_bytes = events_path.read_bytes()
        rf.fork_run(ANCHOR_RUN, wave_num=1, events_path=events_path, runs_dir=runs_dir)
        after_bytes = events_path.read_bytes()

        assert before_bytes == after_bytes, (
            "fork_run must NOT modify board/.events.jsonl (append-only law)"
        )

    def test_fork_each_call_produces_unique_run_id(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        run1, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        run2, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert run1 != run2, "Each fork must produce a unique run_id"

    def test_fork_invalid_wave_num_raises(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"
        with pytest.raises(ValueError, match="wave_num"):
            rf.fork_run(ANCHOR_RUN, wave_num=0, runs_dir=runs_dir)
        with pytest.raises(ValueError, match="wave_num"):
            rf.fork_run(ANCHOR_RUN, wave_num=-1, runs_dir=runs_dir)

    def test_fork_empty_checkpoint_returns_empty_states(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / "runs"

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert ticket_states == {}


class TestParseForkArg:

    def test_valid_arg_parsed(self) -> None:
        run_id, wave_num = rf.parse_fork_arg("01J9Z8QK3M7Q0W9E4R5T6Y7U8I@wave-003")
        assert run_id == "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"
        assert wave_num == 3

    def test_single_digit_wave(self) -> None:
        _, wave_num = rf.parse_fork_arg("SOME-RUN-ID@wave-1")
        assert wave_num == 1

    def test_missing_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="@wave-"):
            rf.parse_fork_arg("01J9Z8QK3M7Q0W9E4R5T6Y7U8I")

    def test_empty_run_id_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            rf.parse_fork_arg("@wave-003")

    def test_non_digit_wave_raises(self) -> None:
        with pytest.raises(ValueError, match="Wave number"):
            rf.parse_fork_arg("SOME-RUN@wave-abc")

    def test_zero_wave_raises(self) -> None:
        with pytest.raises(ValueError, match=">="):
            rf.parse_fork_arg("SOME-RUN@wave-0")

    def test_negative_wave_raises(self) -> None:
        with pytest.raises(ValueError):
            rf.parse_fork_arg("SOME-RUN@wave--1")


class TestReplayQaContractReuse:

    def test_group_runs_consistency(self, tmp_path: Path) -> None:
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS2, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "in_progress", "done", FIXED_TS3, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, events)


        all_events = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events)
        assert ANCHOR_RUN in rq_runs


        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A in result
        assert TICKET_B not in result

    def test_replay_run_consistency(self, tmp_path: Path) -> None:
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        ticket_events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, ticket_events)


        all_events = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events)
        rq_result = rq.replay_run(rq_runs[ANCHOR_RUN])
        assert rq_result["replayable"] is True
        assert rq_result["final_status"] == "in_review"


        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert result.get(TICKET_A) == "in_review"

    def test_fork_replay_clean_original_unchanged(self, tmp_path: Path) -> None:
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"


        original_events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, original_events)
        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "done"},
        )


        new_run_id, fork_states = rf.fork_run(
            ANCHOR_RUN, wave_num=1, events_path=events_path, runs_dir=runs_dir,
        )


        all_events_after = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events_after)
        original_result = rq.replay_run(rq_runs[ANCHOR_RUN])
        assert original_result["replayable"] is True
        assert original_result["corrupted"] is False


        assert new_run_id != ANCHOR_RUN


        assert fork_states.get(TICKET_A) == "done"


        assert events_path.read_bytes() == (
            "".join(json.dumps(ev) + "\n" for ev in original_events).encode()
        )
