
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_ledger as cl
import task_ledger as tl
from dgox.events import iter_events, validate_replanned

FIXED_TS = "2026-07-03T12:00:00Z"
RUN_ID = "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"
ANCHOR = "DAS-1470"


def _good_ledger(**overrides: object) -> dict:
    base = {
        "request_satisfied": False,
        "in_loop": False,
        "progress_being_made": True,
        "next_tickets": ["DAS-1471", "DAS-1472"],
        "instruction": "Continue the wave.",
    }
    base.update(overrides)
    return base


def _stalled_ledger() -> dict:

    return _good_ledger(in_loop=True, progress_being_made=False)


def _build_seed_task_ledger(runs_dir: Path) -> None:
    tl.build_task_ledger(
        run_id=RUN_ID,
        facts=tl.Facts(given=["ship the inner loop"], known=["wave 0 baseline"]),
        plan=["DAS-1470"],
        created_at=FIXED_TS,
        runs_dir=runs_dir,
    )


class TestValidateLedger:
    def test_well_formed_ledger_has_no_errors(self):
        assert cl.validate_ledger(_good_ledger()) == []

    def test_satisfied_ledger_with_empty_instruction_ok(self):
        ledger = _good_ledger(request_satisfied=True, next_tickets=[], instruction="")
        assert cl.validate_ledger(ledger) == []

    @pytest.mark.parametrize("field", list(cl.LEDGER_FIELDS))
    def test_missing_field_is_error(self, field: str):
        ledger = _good_ledger()
        del ledger[field]
        errors = cl.validate_ledger(ledger)
        assert any(field in e for e in errors), errors

    def test_flag_must_be_bool_not_int(self):

        errors = cl.validate_ledger(_good_ledger(in_loop=1))
        assert any("in_loop" in e for e in errors)

    def test_next_tickets_must_be_list_of_nonempty_strings(self):
        assert any("next_tickets" in e for e in cl.validate_ledger(_good_ledger(next_tickets="DAS-1")))
        assert any("next_tickets" in e for e in cl.validate_ledger(_good_ledger(next_tickets=[""])))
        assert any("next_tickets" in e for e in cl.validate_ledger(_good_ledger(next_tickets=[1])))

    def test_instruction_must_be_string(self):
        assert any("instruction" in e for e in cl.validate_ledger(_good_ledger(instruction=42)))

    def test_non_dict_ledger_is_error(self):
        assert cl.validate_ledger(["not", "a", "dict"]) != []


class TestStallRule:
    def test_in_loop_increments(self):
        assert cl.update_stall(0, in_loop=True, progress_being_made=True) == 1

    def test_no_progress_increments(self):
        assert cl.update_stall(2, in_loop=False, progress_being_made=False) == 3

    def test_progress_and_not_looping_decrements(self):
        assert cl.update_stall(3, in_loop=False, progress_being_made=True) == 2

    def test_decrement_floors_at_zero(self):
        assert cl.update_stall(0, in_loop=False, progress_being_made=True) == 0


class TestWriteReadLedger:
    def test_round_trip(self, tmp_path: Path):
        runs = tmp_path / "runs"
        path = cl.write_progress_ledger(
            run_id=RUN_ID, runs_dir=runs, **_good_ledger()
        )
        assert path == cl.progress_ledger_path(RUN_ID, runs)
        assert cl.read_progress_ledger(RUN_ID, runs) == _good_ledger()

    def test_write_rejects_invalid(self, tmp_path: Path):
        with pytest.raises(ValueError):
            cl.write_progress_ledger(
                run_id=RUN_ID,
                runs_dir=tmp_path,
                request_satisfied=False,
                in_loop=False,
                progress_being_made=True,
                next_tickets=[""],
                instruction="x",
            )


class TestStepInnerLoop:
    def test_satisfied_terminates_without_touching_stall(self, tmp_path: Path):
        state = cl.LoopState(stall=2, max_replans=2)
        decision = cl.step_inner_loop(
            ledger=_good_ledger(request_satisfied=True),
            state=state,
            run_id=RUN_ID,
            anchor_ticket=ANCHOR,
            wave=1,
            created_at=FIXED_TS,
            runs_dir=tmp_path,
            store_path=tmp_path / "events.jsonl",
            interrupts_dir=tmp_path / "interrupts",
        )
        assert decision.action == "satisfied"
        assert state.stall == 2

    def test_progress_keeps_continuing(self, tmp_path: Path):
        state = cl.LoopState(stall=1, max_replans=2)
        decision = cl.step_inner_loop(
            ledger=_good_ledger(),
            state=state,
            run_id=RUN_ID,
            anchor_ticket=ANCHOR,
            wave=1,
            created_at=FIXED_TS,
            runs_dir=tmp_path,
            store_path=tmp_path / "events.jsonl",
            interrupts_dir=tmp_path / "interrupts",
        )
        assert decision.action == "continue"
        assert state.stall == 0

    def test_invalid_ledger_raises(self, tmp_path: Path):
        with pytest.raises(ValueError):
            cl.step_inner_loop(
                ledger={"in_loop": True},
                state=cl.LoopState(),
                run_id=RUN_ID,
                anchor_ticket=ANCHOR,
                wave=1,
                created_at=FIXED_TS,
                runs_dir=tmp_path,
            )


class TestStalledRunReplanThenPause:
    def test_replanned_within_two_waves(self, tmp_path: Path):
        runs = tmp_path / "runs"
        store = tmp_path / "events.jsonl"
        interrupts = tmp_path / "interrupts"
        _build_seed_task_ledger(runs)


        state = cl.LoopState(stall=cl.STALL_THRESHOLD - 1, max_replans=2)
        decisions = cl.run_inner_loop(
            [_stalled_ledger(), _stalled_ledger()],
            state=state,
            run_id=RUN_ID,
            anchor_ticket=ANCHOR,
            created_at=FIXED_TS,
            runs_dir=runs,
            store_path=store,
            interrupts_dir=interrupts,
        )

        replans = [d for d in decisions if d.action == "replanned"]
        assert replans, decisions
        assert len(decisions) <= 2


        after = tl.read_task_ledger(RUN_ID, runs)
        assert after["revision"] == 2
        assert after["plan"] == ["DAS-1471", "DAS-1472"]


        events = list(iter_events(store, event_type="replanned"))
        assert len(events) == 1
        assert validate_replanned(events[0]) == []
        assert events[0]["ticket_id"] == ANCHOR
        assert events[0]["max_replans_remaining"] == 1


        assert state.stall == 0
        assert state.max_replans == 1

    def test_pause_on_stall_when_budget_exhausted(self, tmp_path: Path):
        runs = tmp_path / "runs"
        store = tmp_path / "events.jsonl"
        interrupts = tmp_path / "interrupts"
        _build_seed_task_ledger(runs)


        state = cl.LoopState(stall=cl.STALL_THRESHOLD, max_replans=1)
        stalled = [_stalled_ledger() for _ in range(12)]
        decisions = cl.run_inner_loop(
            stalled,
            state=state,
            run_id=RUN_ID,
            anchor_ticket=ANCHOR,
            created_at=FIXED_TS,
            runs_dir=runs,
            store_path=store,
            interrupts_dir=interrupts,
        )

        actions = [d.action for d in decisions]
        assert "replanned" in actions
        assert actions[-1] == "paused"
        assert state.max_replans == 0

        paused = decisions[-1]
        assert paused.interrupt_card_path is not None
        card = json.loads(paused.interrupt_card_path.read_text())

        assert set(card) == {"question", "options", "ticket", "payload", "created_by"}
        assert card["ticket"] == ANCHOR
        assert card["options"]
        assert card["payload"]["run_id"] == RUN_ID


        assert len(list(iter_events(store, event_type="replanned"))) == 1

    def test_unique_card_ids_on_repeated_pauses(self, tmp_path: Path):
        interrupts = tmp_path / "interrupts"
        p1 = cl.raise_stall_interrupt_card(
            run_id=RUN_ID, anchor_ticket=ANCHOR, stall=4, wave=5,
            instruction="steer", interrupts_dir=interrupts,
        )
        p2 = cl.raise_stall_interrupt_card(
            run_id=RUN_ID, anchor_ticket=ANCHOR, stall=4, wave=9,
            instruction="steer", interrupts_dir=interrupts,
        )
        assert p1 != p2
        assert p1.name == f"{ANCHOR}-stall-1.json"
        assert p2.name == f"{ANCHOR}-stall-2.json"


class TestCli:
    def test_cli_accepts_valid_ledger(self, tmp_path: Path, capsys):
        path = tmp_path / "progress-ledger.json"
        path.write_text(json.dumps(_good_ledger()), encoding="utf-8")
        assert cl.main(["--path", str(path)]) == 0

    def test_cli_rejects_invalid_ledger(self, tmp_path: Path):
        path = tmp_path / "progress-ledger.json"
        bad = _good_ledger()
        del bad["instruction"]
        path.write_text(json.dumps(bad), encoding="utf-8")
        assert cl.main(["--path", str(path)]) == 1

    def test_cli_missing_file_is_usage_error(self, tmp_path: Path):
        assert cl.main(["--path", str(tmp_path / "nope.json")]) == 2

    def test_cli_run_id_resolves(self, tmp_path: Path):
        runs = tmp_path / "runs"
        cl.write_progress_ledger(run_id=RUN_ID, runs_dir=runs, **_good_ledger())
        assert cl.main(["--run-id", RUN_ID, "--runs-dir", str(runs)]) == 0


class TestALedgerEntryCarriesItsOwnBoard:
    def _entry(self, tmp_path, board):
        import wave_runner as wr

        att = tmp_path / "att"
        att.mkdir(exist_ok=True)
        (att / "a.json").write_bytes(b"{}")
        return wr.append_wave_ledger_entry(
            ledger_path=tmp_path / "wave-ledger.jsonl",
            run_id="R1",
            wave=1,
            ticket_ids=["DAS-9001"],
            attestation_out_path=att / "a.json",
            attestation_bytes=b"{}",
            created_at="2026-08-17T00:00:00Z",
            board_dir=board,
        )

    def test_the_board_is_recorded_and_covered_by_the_self_hash(self, tmp_path):
        import wave_runner as wr

        board = tmp_path / "projects" / "demo" / "board-tickets"
        board.mkdir(parents=True)
        entry = self._entry(tmp_path, board)

        assert entry["board"].endswith("projects/demo/board-tickets")
        assert entry["self_hash"] == wr._ledger_self_hash(entry)

    def test_an_entry_without_a_board_still_verifies(self, tmp_path):
        import wave_runner as wr

        att = tmp_path / "att"
        att.mkdir()
        (att / "a.json").write_bytes(b"{}")
        entry = wr.append_wave_ledger_entry(
            ledger_path=tmp_path / "wave-ledger.jsonl",
            run_id="R1", wave=1, ticket_ids=["DAS-9001"],
            attestation_out_path=att / "a.json", attestation_bytes=b"{}",
            created_at="2026-08-17T00:00:00Z",
        )
        assert "board" not in entry
        assert entry["self_hash"] == wr._ledger_self_hash(entry)

    def test_a_declared_board_resolves_relative_to_the_repo(self, tmp_path):
        board = cl.REPO_ROOT / "scripts"
        resolved = cl.entry_board({"board": "scripts"}, tmp_path)
        assert resolved.resolve() == board.resolve()

    def test_a_board_that_is_not_on_disk_falls_back(self, tmp_path):
        fallback = tmp_path / "fallback"
        assert cl.entry_board({"board": "no/such/board"}, fallback) == fallback
        assert cl.entry_board({}, fallback) == fallback


class TestAnOlderEntryWithoutABoardStillResolves:
    def test_the_known_boards_include_project_boards(self):
        boards = cl.known_boards(cl.DEFAULT_TICKETS_DIR)
        assert boards[0] == cl.DEFAULT_TICKETS_DIR

    def test_an_entry_with_no_board_searches_every_known_board(self, monkeypatch, tmp_path):
        platform = tmp_path / "board" / "tickets"
        project = tmp_path / "projects" / "demo" / "board-tickets"
        for d, tid in ((platform, "DAS-1"), (project, "DAS-2")):
            d.mkdir(parents=True)
            (d / f"{tid}-x.md").write_text(f"---\nid: {tid}\n---\nb\n", encoding="utf-8")
        monkeypatch.setattr(cl, "REPO_ROOT", tmp_path)

        ids, label = cl.resolvable_tickets({}, platform)

        assert ids == {"DAS-1", "DAS-2"}
        assert "known board" in label

    def test_a_declared_board_is_used_alone(self, monkeypatch, tmp_path):
        project = tmp_path / "projects" / "demo" / "board-tickets"
        project.mkdir(parents=True)
        (project / "DAS-2-x.md").write_text("---\nid: DAS-2\n---\nb\n", encoding="utf-8")
        monkeypatch.setattr(cl, "REPO_ROOT", tmp_path)

        ids, _label = cl.resolvable_tickets({"board": "projects/demo/board-tickets"}, tmp_path)

        assert ids == {"DAS-2"}
