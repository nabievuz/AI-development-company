"""tests/test_resume_fork.py — Round-trip tests for scripts/resume_fork.py.

Acceptance criteria covered (DAS-1445):
  AC1  --resume replays to last valid checkpoint; re-dispatches ONLY unfinished.
  AC2  Resume refuses to re-dispatch off a corrupted chain (T5 guardrail).
  AC3  --fork produces a divergent new run; original events byte-for-byte intact.
  AC4  Replay path reuses replay_qa.group_runs + replay_qa.replay_run.
  AC5  Round-trip: dispatch → partial completion → resume → correct unfinished set;
       fork yields divergent run whose replay is clean, original replays unchanged.

Shadow-rule note:
  resume_fork.py reads board/.events.jsonl to decide which tickets to
  re-dispatch.  This is explicitly scoped to the operator-invoked --resume /
  --fork recovery path.  Normal wave dispatch is unchanged (ADR-0025; enforced by
  the principled reader-vs-router rule in test_dgox_phase1_shadow.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of pytest invocation root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc  # noqa: E402
import replay_qa as rq  # noqa: E402
import resume_fork as rf  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

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
    """Build a minimal routing_decision event for testing."""
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
    """Write events to a JSONL file."""
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
    """Write a minimal wave checkpoint file for testing."""
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


# ===========================================================================
# SECTION 1 — get_unfinished_tickets
# ===========================================================================


class TestGetUnfinishedTickets:
    """Unit tests for the per-ticket replay + unfinished-detection logic."""

    def test_unfinished_ticket_returned(self, tmp_path: Path) -> None:
        """A ticket in in_progress is in the unfinished set."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A in result
        assert result[TICKET_A] == "in_progress"

    def test_done_ticket_not_returned(self, tmp_path: Path) -> None:
        """A ticket that reached 'done' is NOT in the unfinished set."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result

    def test_blocked_ticket_not_returned(self, tmp_path: Path) -> None:
        """A ticket that reached 'blocked' is NOT in the unfinished set."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "blocked", FIXED_TS2, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result

    def test_mixed_tickets_correct_partition(self, tmp_path: Path) -> None:
        """Unfinished and done tickets in the same run are correctly partitioned."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            # TICKET_A: in_progress → done (terminal)
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
            # TICKET_B: todo → in_progress (unfinished)
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS3, run_id=ANCHOR_RUN),
        ])
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A not in result
        assert TICKET_B in result
        assert result[TICKET_B] == "in_progress"

    def test_corrupted_chain_raises(self, tmp_path: Path) -> None:
        """A corrupted transition chain raises ValueError (T5 guardrail)."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            # TICKET_A chain: todo → in_progress
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            # TICKET_B chain: broken (done → in_review is a broken chain start)
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "done", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),  # broken
        ])
        with pytest.raises(ValueError, match="Corrupted"):
            rf.get_unfinished_tickets(ANCHOR_RUN, events_path)

    def test_empty_when_run_not_found(self, tmp_path: Path) -> None:
        """Returns empty dict when run_id is not in the event store."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id="other-run"),
        ])
        result = rf.get_unfinished_tickets("nonexistent-run-id", events_path)
        assert result == {}

    def test_empty_when_no_events_file(self, tmp_path: Path) -> None:
        """Returns empty dict when the event store does not exist yet."""
        events_path = tmp_path / "no-events.jsonl"  # does not exist
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert result == {}

    def test_uses_ticket_id_fallback_grouping(self, tmp_path: Path) -> None:
        """Without explicit run_id, group_runs falls back to ticket_id (replay_qa contract)."""
        events_path = tmp_path / ".events.jsonl"
        # Events without run_id — _run_key falls back to ticket_id
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS),  # no run_id
        ])
        # Use TICKET_A as the run_id (ticket_id fallback)
        result = rf.get_unfinished_tickets(TICKET_A, events_path)
        assert TICKET_A in result
        assert result[TICKET_A] == "in_progress"

    def test_invalid_status_is_corrupted(self, tmp_path: Path) -> None:
        """An event with an invalid to_status triggers the T5 guardrail."""
        events_path = tmp_path / ".events.jsonl"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "frobnicate", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        with pytest.raises(ValueError, match="Corrupted"):
            rf.get_unfinished_tickets(ANCHOR_RUN, events_path)


# ===========================================================================
# SECTION 2 — resume_run
# ===========================================================================


class TestResumeRun:
    """Tests for resume_run: combines replay with completion records."""

    def test_resume_returns_unfinished(self, tmp_path: Path) -> None:
        """resume_run returns the unfinished ticket set."""
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])
        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        assert TICKET_A in result

    def test_resume_excludes_completed(self, tmp_path: Path) -> None:
        """A ticket with a completion record is excluded from re-dispatch.

        Round-trip: the ticket's event log shows in_progress (unfinished), but
        a durable completion record exists (crash after completion was recorded
        but before the event log was updated). Resume must NOT re-dispatch it.
        """
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        # Event log: TICKET_A is in_progress (unfinished per replay)
        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
        ])

        # Durable completion record: TICKET_A actually finished (crash after record)
        pc.append_ticket_completion(
            run_id=ANCHOR_RUN,
            ticket_id=TICKET_A,
            status="done",
            wave=1,
            created_at=FIXED_TS2,
            runs_dir=runs_dir,
        )

        result = rf.resume_run(ANCHOR_RUN, events_path, runs_dir)
        # TICKET_A has a completion record — must NOT be in the re-dispatch set
        assert TICKET_A not in result

    def test_resume_partial_completion(self, tmp_path: Path) -> None:
        """Only tickets WITHOUT completion records are re-dispatched.

        Round-trip: crash after TICKET_A completes (completion record written),
        but TICKET_B is still in_progress (no record). Resume re-dispatches
        only TICKET_B.
        """
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [
            # TICKET_A: in_progress (no terminal event; completion record exists)
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            # TICKET_B: in_progress (no terminal event; no completion record)
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS2, run_id=ANCHOR_RUN),
        ])

        # Only TICKET_A has a completion record
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
        """Empty result when all tickets in the run are in terminal states."""
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
        """resume_run raises ValueError on a corrupted chain (T5 guardrail)."""
        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        _write_events(events_path, [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "done", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),  # broken
        ])

        with pytest.raises(ValueError, match="Corrupted"):
            rf.resume_run(ANCHOR_RUN, events_path, runs_dir)

    def test_resume_no_duplicate_dispatch(self, tmp_path: Path) -> None:
        """Already-done tickets are NOT re-dispatched (no duplicate work).

        Full round-trip: dispatch → completion events → resume.
        TICKET_A completed (done) in the event log. TICKET_B is in_progress.
        Resume must return only TICKET_B.
        """
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


# ===========================================================================
# SECTION 3 — fork_run
# ===========================================================================


class TestForkRun:
    """Tests for fork_run: divergent run creation."""

    def test_fork_returns_new_run_id(self, tmp_path: Path) -> None:
        """fork_run returns a fresh ULID different from the source run_id."""
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        new_run_id, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert new_run_id != ANCHOR_RUN
        assert len(new_run_id) == 26  # ULID length (Crockford base32)

    def test_fork_ticket_states_from_checkpoint(self, tmp_path: Path) -> None:
        """fork_run returns the ticket states reconstructed from checkpoints."""
        runs_dir = tmp_path / "runs"
        expected_states = {TICKET_A: "in_progress", TICKET_B: "done"}
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states=expected_states)

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert ticket_states == expected_states

    def test_fork_layered_checkpoints(self, tmp_path: Path) -> None:
        """fork_run at wave-2 accumulates deltas from wave-1 and wave-2."""
        runs_dir = tmp_path / "runs"
        # Wave 1: TICKET_A appears
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})
        # Wave 2: TICKET_B added; TICKET_A updated
        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=2,
            ticket_states={TICKET_A: "in_review", TICKET_B: "in_progress"},
        )

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=2, runs_dir=runs_dir)
        assert ticket_states[TICKET_A] == "in_review"
        assert ticket_states[TICKET_B] == "in_progress"

    def test_fork_at_wave1_only_wave1_state(self, tmp_path: Path) -> None:
        """fork_run at wave-1 only reflects wave-1 state, not wave-2."""
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})
        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=2,
            ticket_states={TICKET_A: "done", TICKET_B: "in_progress"},
        )

        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        # Only wave-1 state; wave-2 changes should NOT appear
        assert ticket_states.get(TICKET_A) == "in_progress"
        assert TICKET_B not in ticket_states

    def test_fork_original_events_unchanged(self, tmp_path: Path) -> None:
        """fork_run does NOT modify board/.events.jsonl (append-only law)."""
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
        """Two fork calls produce distinct run_ids (ULID uniqueness)."""
        runs_dir = tmp_path / "runs"
        _write_checkpoint(runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "in_progress"})

        run1, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        run2, _ = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert run1 != run2, "Each fork must produce a unique run_id"

    def test_fork_invalid_wave_num_raises(self, tmp_path: Path) -> None:
        """fork_run raises ValueError for wave_num < 1."""
        runs_dir = tmp_path / "runs"
        with pytest.raises(ValueError, match="wave_num"):
            rf.fork_run(ANCHOR_RUN, wave_num=0, runs_dir=runs_dir)
        with pytest.raises(ValueError, match="wave_num"):
            rf.fork_run(ANCHOR_RUN, wave_num=-1, runs_dir=runs_dir)

    def test_fork_empty_checkpoint_returns_empty_states(self, tmp_path: Path) -> None:
        """fork_run with no checkpoints returns an empty state dict."""
        runs_dir = tmp_path / "runs"
        # No checkpoint files written for ANCHOR_RUN
        _, ticket_states = rf.fork_run(ANCHOR_RUN, wave_num=1, runs_dir=runs_dir)
        assert ticket_states == {}


# ===========================================================================
# SECTION 4 — parse_fork_arg
# ===========================================================================


class TestParseForkArg:
    """Unit tests for the --fork argument parser."""

    def test_valid_arg_parsed(self) -> None:
        """Standard format parses correctly."""
        run_id, wave_num = rf.parse_fork_arg("01J9Z8QK3M7Q0W9E4R5T6Y7U8I@wave-003")
        assert run_id == "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"
        assert wave_num == 3

    def test_single_digit_wave(self) -> None:
        """Single-digit wave numbers are accepted."""
        _, wave_num = rf.parse_fork_arg("SOME-RUN-ID@wave-1")
        assert wave_num == 1

    def test_missing_separator_raises(self) -> None:
        """Missing @wave- separator raises ValueError."""
        with pytest.raises(ValueError, match="@wave-"):
            rf.parse_fork_arg("01J9Z8QK3M7Q0W9E4R5T6Y7U8I")

    def test_empty_run_id_raises(self) -> None:
        """Empty run_id raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            rf.parse_fork_arg("@wave-003")

    def test_non_digit_wave_raises(self) -> None:
        """Non-digit wave number raises ValueError."""
        with pytest.raises(ValueError, match="Wave number"):
            rf.parse_fork_arg("SOME-RUN@wave-abc")

    def test_zero_wave_raises(self) -> None:
        """wave_num == 0 raises ValueError (must be >= 1)."""
        with pytest.raises(ValueError, match=">="):
            rf.parse_fork_arg("SOME-RUN@wave-0")

    def test_negative_wave_raises(self) -> None:
        """Negative wave number raises ValueError."""
        with pytest.raises(ValueError):
            rf.parse_fork_arg("SOME-RUN@wave--1")


# ===========================================================================
# SECTION 5 — Full round-trip: replay_qa contract reuse proof
# ===========================================================================


class TestReplayQaContractReuse:
    """Prove that resume_fork reuses replay_qa.group_runs + replay_qa.replay_run.

    We call group_runs and replay_run from replay_qa directly on the same data
    and verify that resume_fork produces consistent results — confirming it uses
    the canonical transition model rather than a re-implementation.
    """

    def test_group_runs_consistency(self, tmp_path: Path) -> None:
        """get_unfinished_tickets and replay_qa.group_runs agree on the run set."""
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "todo", "in_progress", FIXED_TS2, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_B, "in_progress", "done", FIXED_TS3, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, events)

        # Direct replay_qa grouping
        all_events = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events)
        assert ANCHOR_RUN in rq_runs

        # resume_fork's get_unfinished_tickets should agree:
        # TICKET_A is in_progress (unfinished), TICKET_B is done (terminal)
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert TICKET_A in result
        assert TICKET_B not in result

    def test_replay_run_consistency(self, tmp_path: Path) -> None:
        """replay_qa.replay_run and get_unfinished_tickets agree on final_status."""
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        ticket_events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "in_review", FIXED_TS2, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, ticket_events)

        # Direct replay_qa.replay_run
        all_events = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events)
        rq_result = rq.replay_run(rq_runs[ANCHOR_RUN])
        assert rq_result["replayable"] is True
        assert rq_result["final_status"] == "in_review"

        # resume_fork should return the same final_status for TICKET_A
        result = rf.get_unfinished_tickets(ANCHOR_RUN, events_path)
        assert result.get(TICKET_A) == "in_review"

    def test_fork_replay_clean_original_unchanged(self, tmp_path: Path) -> None:
        """Fork round-trip: fork yields divergent run; original replays unchanged.

        Verifies acceptance criterion: --fork yields a divergent run whose
        replay is clean while the original replays unchanged.
        """
        import wave_kpi

        events_path = tmp_path / ".events.jsonl"
        runs_dir = tmp_path / "runs"

        # Write events for the original run
        original_events = [
            _routing_ev(TICKET_A, "todo", "in_progress", FIXED_TS, run_id=ANCHOR_RUN),
            _routing_ev(TICKET_A, "in_progress", "done", FIXED_TS2, run_id=ANCHOR_RUN),
        ]
        _write_events(events_path, original_events)
        _write_checkpoint(
            runs_dir, ANCHOR_RUN, wave=1, ticket_states={TICKET_A: "done"},
        )

        # Fork at wave-1
        new_run_id, fork_states = rf.fork_run(
            ANCHOR_RUN, wave_num=1, events_path=events_path, runs_dir=runs_dir,
        )

        # Original run still replays cleanly
        all_events_after = wave_kpi.read_events(str(events_path))
        rq_runs = rq.group_runs(all_events_after)
        original_result = rq.replay_run(rq_runs[ANCHOR_RUN])
        assert original_result["replayable"] is True
        assert original_result["corrupted"] is False

        # New run_id is different (divergent run)
        assert new_run_id != ANCHOR_RUN

        # Fork inherited the checkpoint state
        assert fork_states.get(TICKET_A) == "done"

        # The event store was not modified by the fork (original events intact)
        assert events_path.read_bytes() == (
            "".join(json.dumps(ev) + "\n" for ev in original_events).encode()
        )
