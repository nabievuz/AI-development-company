
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc
from dgox.events import (
    EventStore,
    build_ticket_completion,
    iter_events,
    validate_checkpoint,
    validate_ticket_completion,
)

FIXED_TS = "2026-07-03T12:00:00Z"
FIXED_TS2 = "2026-07-03T12:41:00Z"
RUN_ID = "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"
ANCHOR = "DAS-1443"


def _write_ticket(tickets_dir: Path, name: str, content: str) -> Path:
    p = tickets_dir / name
    p.write_text(content, encoding="utf-8")
    return p


class TestGenerateULID:
    def test_length_is_26(self):
        assert len(pc.generate_ulid()) == 26

    def test_all_crockford_chars(self):
        crockford = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        ulid = pc.generate_ulid()
        assert all(c in crockford for c in ulid), f"Invalid chars in ULID: {ulid!r}"

    def test_unique_on_successive_calls(self):
        ids = {pc.generate_ulid() for _ in range(20)}
        assert len(ids) == 20, "ULID collision detected"

    def test_lexicographic_sort_reflects_time_order(self):

        a = pc.generate_ulid()
        time.sleep(0.002)
        b = pc.generate_ulid()
        assert a < b, f"ULID not monotonic: {a!r} >= {b!r}"


class TestComputeBoardHash:
    def test_deterministic_same_files(self, tmp_path):
        tdir = tmp_path / "tickets"
        tdir.mkdir()
        _write_ticket(tdir, "DAS-0001-foo.md", "# ticket 1\nstatus: todo\n")
        h1 = pc.compute_board_hash(tdir)
        h2 = pc.compute_board_hash(tdir)
        assert h1 == h2

    def test_starts_with_sha256(self, tmp_path):
        tdir = tmp_path / "tickets"
        tdir.mkdir()
        h = pc.compute_board_hash(tdir)
        assert h.startswith("sha256:")

    def test_changes_when_content_changes(self, tmp_path):
        tdir = tmp_path / "tickets"
        tdir.mkdir()
        p = _write_ticket(tdir, "DAS-0001.md", "status: todo")
        h1 = pc.compute_board_hash(tdir)
        p.write_text("status: done", encoding="utf-8")
        h2 = pc.compute_board_hash(tdir)
        assert h1 != h2

    def test_changes_when_file_added(self, tmp_path):
        tdir = tmp_path / "tickets"
        tdir.mkdir()
        _write_ticket(tdir, "DAS-0001.md", "status: todo")
        h1 = pc.compute_board_hash(tdir)
        _write_ticket(tdir, "DAS-0002.md", "status: backlog")
        h2 = pc.compute_board_hash(tdir)
        assert h1 != h2

    def test_empty_dir_is_stable(self, tmp_path):
        tdir = tmp_path / "tickets"
        tdir.mkdir()
        h1 = pc.compute_board_hash(tdir)
        h2 = pc.compute_board_hash(tdir)
        assert h1 == h2

    def test_nonexistent_dir_is_stable(self, tmp_path):
        tdir = tmp_path / "nonexistent"
        h1 = pc.compute_board_hash(tdir)
        h2 = pc.compute_board_hash(tdir)
        assert h1 == h2


class TestGetEventOffset:
    def test_returns_zero_for_nonexistent_file(self, tmp_path):
        assert pc.get_event_offset(tmp_path / "no.jsonl") == 0

    def test_returns_byte_count_after_append(self, tmp_path):
        store_path = tmp_path / "events.jsonl"
        store = EventStore(store_path)
        from dgox.events import build_routing_decision

        ev = build_routing_decision(
            ticket_id="DAS-0001",
            from_status="todo",
            to_status="in_progress",
            assignee="backend-eng-1",
            model="sonnet",
            reason="test",
            confidence=0.9,
            policy_checks=["check"],
            fallback="block",
            created_at=FIXED_TS,
        )
        store.append(ev)
        offset = pc.get_event_offset(store_path)
        assert offset == store_path.stat().st_size
        assert offset > 0


class TestComputeDelta:
    def test_unchanged_states_not_in_delta(self):
        prev = {"DAS-1": "todo", "DAS-2": "in_progress"}
        curr = {"DAS-1": "todo", "DAS-2": "in_progress"}
        assert pc.compute_delta(prev, curr) == {}

    def test_changed_state_in_delta(self):
        prev = {"DAS-1": "todo", "DAS-2": "in_progress"}
        curr = {"DAS-1": "done", "DAS-2": "in_progress"}
        delta = pc.compute_delta(prev, curr)
        assert delta == {"DAS-1": "done"}

    def test_new_ticket_in_delta(self):
        prev = {"DAS-1": "todo"}
        curr = {"DAS-1": "todo", "DAS-2": "in_progress"}
        delta = pc.compute_delta(prev, curr)
        assert delta == {"DAS-2": "in_progress"}

    def test_empty_prev_all_curr_are_delta(self):
        curr = {"DAS-1": "todo", "DAS-2": "done"}
        delta = pc.compute_delta({}, curr)
        assert delta == curr

    def test_empty_curr_gives_empty_delta(self):
        prev = {"DAS-1": "todo"}
        assert pc.compute_delta(prev, {}) == {}

    def test_mixed_changes_and_unchanged(self):
        prev = {"DAS-1": "todo", "DAS-2": "in_progress", "DAS-3": "done"}
        curr = {"DAS-1": "in_progress", "DAS-2": "in_progress", "DAS-3": "in_review"}
        delta = pc.compute_delta(prev, curr)
        assert delta == {"DAS-1": "in_progress", "DAS-3": "in_review"}
        assert "DAS-2" not in delta


class TestComputeLedgerHash:
    def _sample_cp(self) -> dict:
        return {
            "run_id": RUN_ID,
            "wave": 1,
            "created_at": FIXED_TS,
            "board_hash": "sha256:aabb",
            "event_offset": 100,
            "ticket_states": {"DAS-1": "done"},
            "pending_interrupts": [],
            "ledger_hashes": {"prev": "sha256:" + "0" * 64, "self": ""},
        }

    def test_deterministic(self):
        cp = self._sample_cp()
        h1 = pc.compute_ledger_hash(cp)
        h2 = pc.compute_ledger_hash(cp)
        assert h1 == h2

    def test_starts_with_sha256(self):
        assert pc.compute_ledger_hash(self._sample_cp()).startswith("sha256:")

    def test_changes_when_content_changes(self):
        cp1 = self._sample_cp()
        cp2 = dict(self._sample_cp())
        cp2["event_offset"] = 9999
        assert pc.compute_ledger_hash(cp1) != pc.compute_ledger_hash(cp2)

    def test_self_key_excluded_from_preimage(self):
        cp_a = self._sample_cp()
        cp_a["ledger_hashes"]["self"] = "sha256:aaaa"
        cp_b = self._sample_cp()
        cp_b["ledger_hashes"]["self"] = "sha256:bbbb"
        assert pc.compute_ledger_hash(cp_a) == pc.compute_ledger_hash(cp_b)

    def test_prev_key_included_in_preimage(self):
        cp_a = self._sample_cp()
        cp_b = self._sample_cp()
        cp_b["ledger_hashes"]["prev"] = "sha256:different"
        assert pc.compute_ledger_hash(cp_a) != pc.compute_ledger_hash(cp_b)


class TestWriteWaveCheckpoint:
    def _write_cp(self, tmp_path, wave=1, curr_states=None, prev_wave_cp=None, **kw):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir(exist_ok=True)

        if curr_states is None:
            curr_states = {"DAS-1443": "done", "DAS-1444": "in_review"}

        cp = pc.write_wave_checkpoint(
            run_id=RUN_ID,
            wave=wave,
            ticket_id=ANCHOR,
            curr_ticket_states=curr_states,
            created_at=FIXED_TS,
            store_path=store_path,
            tickets_dir=tickets_dir,
            runs_dir=runs_dir,
            **kw,
        )
        cp_path = runs_dir / RUN_ID / f"wave-{wave:03d}.checkpoint.json"
        return cp, cp_path, runs_dir, store_path

    def test_file_written_at_correct_path(self, tmp_path):
        _, cp_path, _, _ = self._write_cp(tmp_path)
        assert cp_path.exists(), f"Checkpoint file not found: {cp_path}"

    def test_file_is_valid_json(self, tmp_path):
        _, cp_path, _, _ = self._write_cp(tmp_path)
        data = json.loads(cp_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_checkpoint_has_required_fields(self, tmp_path):
        cp, cp_path, _, _ = self._write_cp(tmp_path)
        for field in ("run_id", "wave", "created_at", "board_hash", "event_offset",
                      "ticket_states", "pending_interrupts", "ledger_hashes"):
            assert field in cp, f"Missing field: {field!r}"

    def test_run_id_matches(self, tmp_path):
        cp, _, _, _ = self._write_cp(tmp_path)
        assert cp["run_id"] == RUN_ID

    def test_wave_number_matches(self, tmp_path):
        cp, _, _, _ = self._write_cp(tmp_path, wave=3)
        assert cp["wave"] == 3

    def test_ledger_hashes_has_prev_and_self(self, tmp_path):
        cp, _, _, _ = self._write_cp(tmp_path)
        lh = cp["ledger_hashes"]
        assert "prev" in lh
        assert "self" in lh
        assert lh["self"].startswith("sha256:")
        assert len(lh["self"]) > 7

    def test_first_wave_uses_genesis_sentinel(self, tmp_path):
        cp, _, _, _ = self._write_cp(tmp_path, wave=1)
        assert cp["ledger_hashes"]["prev"] == pc._GENESIS_PREV_HASH

    def test_checkpoint_event_emitted_to_store(self, tmp_path):
        _, _, _, store_path = self._write_cp(tmp_path, emit_event=True)
        events = list(iter_events(store_path, event_type="checkpoint"))
        assert len(events) == 1
        ev = events[0]
        assert ev["run_id"] == RUN_ID
        assert ev["wave"] == 1

    def test_no_event_when_emit_false(self, tmp_path):
        _, _, _, store_path = self._write_cp(tmp_path, emit_event=False)
        assert not store_path.exists() or list(iter_events(store_path)) == []

    def test_emitted_checkpoint_event_is_valid(self, tmp_path):
        _, _, _, store_path = self._write_cp(tmp_path, emit_event=True)
        events = list(iter_events(store_path, event_type="checkpoint"))
        assert len(events) == 1
        errors = validate_checkpoint(events[0])
        assert errors == [], f"Validation errors: {errors}"

    def test_pending_interrupts_stored(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        cp = pc.write_wave_checkpoint(
            run_id=RUN_ID,
            wave=1,
            ticket_id=ANCHOR,
            curr_ticket_states={"DAS-1": "done"},
            pending_interrupts=["DAS-1445"],
            created_at=FIXED_TS,
            store_path=store_path,
            tickets_dir=tickets_dir,
            runs_dir=runs_dir,
        )
        assert cp["pending_interrupts"] == ["DAS-1445"]


class TestDeltaEncoding:

    def test_wave2_delta_omits_unchanged_states(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        wave1_states = {
            "DAS-1443": "done",
            "DAS-1444": "in_review",
            "DAS-1445": "todo",
        }

        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states=wave1_states,
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )

        wave2_states = {
            "DAS-1443": "done",
            "DAS-1444": "done",
            "DAS-1445": "in_progress",
        }
        cp2 = pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=2, ticket_id=ANCHOR,
            curr_ticket_states=wave2_states,
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )


        delta = cp2["ticket_states"]
        assert "DAS-1443" not in delta, (
            "DAS-1443 was unchanged between wave-1 and wave-2 "
            "but appeared in the delta — full snapshot stored instead of delta"
        )
        assert delta.get("DAS-1444") == "done"
        assert delta.get("DAS-1445") == "in_progress"

    def test_reconstruct_yields_full_state(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        wave1_states = {"DAS-1": "done", "DAS-2": "todo", "DAS-3": "blocked"}
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states=wave1_states,
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )
        wave2_states = {"DAS-1": "done", "DAS-2": "done", "DAS-3": "blocked"}
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=2, ticket_id=ANCHOR,
            curr_ticket_states=wave2_states,
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )


        full = pc.reconstruct_ticket_states(RUN_ID, 2, runs_dir)
        assert full == wave2_states

    def test_reconstruct_up_to_wave1_gives_wave1_state(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        wave1_states = {"DAS-1": "done", "DAS-2": "in_review"}
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states=wave1_states,
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )
        wave2_states = {"DAS-1": "done", "DAS-2": "done"}
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=2, ticket_id=ANCHOR,
            curr_ticket_states=wave2_states,
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )


        full = pc.reconstruct_ticket_states(RUN_ID, 1, runs_dir)
        assert full == wave1_states


class TestLedgerHashChaining:
    def test_wave2_prev_equals_wave1_self(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        cp1 = pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states={"DAS-1": "done"},
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )
        cp2 = pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=2, ticket_id=ANCHOR,
            curr_ticket_states={"DAS-1": "done", "DAS-2": "done"},
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )


        assert cp2["ledger_hashes"]["prev"] == cp1["ledger_hashes"]["self"], (
            "Ledger chain broken: wave-2.prev != wave-1.self"
        )

    def test_self_hash_is_recomputable(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        cp = pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states={"DAS-1": "done"},
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )

        recomputed = pc.compute_ledger_hash(cp)
        assert recomputed == cp["ledger_hashes"]["self"]

    def test_three_wave_chain_is_consistent(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        states = [
            {"DAS-1": "done"},
            {"DAS-1": "done", "DAS-2": "done"},
            {"DAS-1": "done", "DAS-2": "done", "DAS-3": "in_review"},
        ]
        cps = []
        for i, s in enumerate(states, 1):
            cps.append(pc.write_wave_checkpoint(
                run_id=RUN_ID, wave=i, ticket_id=ANCHOR,
                curr_ticket_states=s,
                created_at=FIXED_TS,
                store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
            ))


        assert cps[1]["ledger_hashes"]["prev"] == cps[0]["ledger_hashes"]["self"]
        assert cps[2]["ledger_hashes"]["prev"] == cps[1]["ledger_hashes"]["self"]


class TestTicketCompletion:
    def test_append_writes_to_completions_jsonl(self, tmp_path):
        runs_dir = tmp_path / "runs"
        pc.append_ticket_completion(
            run_id=RUN_ID,
            ticket_id="DAS-1443",
            status="done",
            wave=1,
            created_at=FIXED_TS,
            runs_dir=runs_dir,
        )
        completions_path = runs_dir / RUN_ID / "completions.jsonl"
        assert completions_path.exists()

    def test_completions_file_is_valid_jsonl(self, tmp_path):
        runs_dir = tmp_path / "runs"
        for tid in ("DAS-1443", "DAS-1444"):
            pc.append_ticket_completion(
                run_id=RUN_ID, ticket_id=tid, status="done", wave=1,
                created_at=FIXED_TS, runs_dir=runs_dir,
            )
        completions_path = runs_dir / RUN_ID / "completions.jsonl"
        for line in completions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                assert isinstance(obj, dict)

    def test_completions_use_ticket_completion_event_type(self, tmp_path):
        runs_dir = tmp_path / "runs"
        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id="DAS-1443", status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )
        completions_path = runs_dir / RUN_ID / "completions.jsonl"
        records = [json.loads(ln) for ln in completions_path.read_text().splitlines() if ln.strip()]
        assert all(r["event_type"] == "ticket_completion" for r in records)

    def test_completion_record_passes_validation(self, tmp_path):
        runs_dir = tmp_path / "runs"
        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id="DAS-1443", status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )
        completions_path = runs_dir / RUN_ID / "completions.jsonl"
        for line in completions_path.read_text().splitlines():
            if line.strip():
                ev = json.loads(line)
                errors = validate_ticket_completion(ev)
                assert errors == [], f"Validation errors: {errors}"

    def test_get_completed_tickets_returns_correct_set(self, tmp_path):
        runs_dir = tmp_path / "runs"
        tickets = ["DAS-1443", "DAS-1444", "DAS-1445"]
        for tid in tickets:
            pc.append_ticket_completion(
                run_id=RUN_ID, ticket_id=tid, status="done",
                wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
            )
        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        assert completed == set(tickets)

    def test_get_completed_tickets_empty_when_no_file(self, tmp_path):
        runs_dir = tmp_path / "runs"
        assert pc.get_completed_tickets("NO-SUCH-RUN", runs_dir) == set()

    def test_multiple_appends_accumulate(self, tmp_path):
        runs_dir = tmp_path / "runs"
        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id="DAS-1443", status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )
        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id="DAS-1444", status="in_review",
            wave=1, created_at=FIXED_TS2, runs_dir=runs_dir,
        )
        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        assert "DAS-1443" in completed
        assert "DAS-1444" in completed

    def test_run_scoping_isolates_different_runs(self, tmp_path):
        runs_dir = tmp_path / "runs"
        run_a = "RUN-A00000000000000000000000"
        run_b = "RUN-B00000000000000000000000"
        pc.append_ticket_completion(
            run_id=run_a, ticket_id="DAS-1443", status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )

        pc.append_ticket_completion(
            run_id=run_b, ticket_id="DAS-1444", status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )
        assert pc.get_completed_tickets(run_a, runs_dir) == {"DAS-1443"}
        assert pc.get_completed_tickets(run_b, runs_dir) == {"DAS-1444"}

    def test_build_ticket_completion_builder(self):
        ev = build_ticket_completion(
            ticket_id="DAS-1443",
            run_id=RUN_ID,
            status="done",
            wave=1,
            created_at=FIXED_TS,
        )
        assert ev["event_type"] == "ticket_completion"
        assert ev["ticket_id"] == "DAS-1443"
        assert ev["run_id"] == RUN_ID
        assert ev["status"] == "done"
        assert ev["wave"] == 1
        assert ev["created_at"] == FIXED_TS


class TestSimulatedCrashResume:

    M = 5
    N = 3

    def _ticket_ids(self) -> list[str]:
        return [f"DAS-{1000 + i}" for i in range(self.M)]

    def test_crash_leaves_exactly_n_recorded(self, tmp_path):
        runs_dir = tmp_path / "runs"
        all_tickets = self._ticket_ids()
        completed_tickets = all_tickets[: self.N]


        for tid in completed_tickets:
            pc.append_ticket_completion(
                run_id=RUN_ID, ticket_id=tid, status="done",
                wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
            )


        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        assert len(completed) == self.N, (
            f"Expected {self.N} completed tickets, got {len(completed)}: {completed}"
        )
        assert completed == set(completed_tickets)

    def test_resume_dispatches_only_remaining_tickets(self, tmp_path):
        runs_dir = tmp_path / "runs"
        all_tickets = self._ticket_ids()
        completed_tickets = all_tickets[: self.N]
        remaining_tickets = all_tickets[self.N :]


        for tid in completed_tickets:
            pc.append_ticket_completion(
                run_id=RUN_ID, ticket_id=tid, status="done",
                wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
            )


        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        to_dispatch = [t for t in all_tickets if t not in completed]

        assert len(to_dispatch) == self.M - self.N
        assert set(to_dispatch) == set(remaining_tickets)

    def test_none_of_completed_tickets_re_dispatched(self, tmp_path):
        runs_dir = tmp_path / "runs"
        all_tickets = self._ticket_ids()
        completed_tickets = all_tickets[: self.N]

        for tid in completed_tickets:
            pc.append_ticket_completion(
                run_id=RUN_ID, ticket_id=tid, status="done",
                wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
            )

        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        to_dispatch = [t for t in all_tickets if t not in completed]


        re_runs = set(to_dispatch) & completed
        assert re_runs == set(), (
            f"Idempotency violated: these already-complete tickets would be re-dispatched: {re_runs}"
        )

    def test_idempotent_append_doesnt_break_completed_set(self, tmp_path):
        runs_dir = tmp_path / "runs"
        tid = "DAS-1443"

        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id=tid, status="done",
            wave=1, created_at=FIXED_TS, runs_dir=runs_dir,
        )

        pc.append_ticket_completion(
            run_id=RUN_ID, ticket_id=tid, status="done",
            wave=1, created_at=FIXED_TS2, runs_dir=runs_dir,
        )

        completed = pc.get_completed_tickets(RUN_ID, runs_dir)
        assert completed == {tid}, "Duplicate append changed the completed set"


class TestReconstructTicketStates:
    def test_empty_run_gives_empty_states(self, tmp_path):
        runs_dir = tmp_path / "runs"
        result = pc.reconstruct_ticket_states("NO-CHECKPOINTS", 0, runs_dir)
        assert result == {}

    def test_single_wave_gives_wave_states(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        states = {"DAS-1": "done", "DAS-2": "in_review"}
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states=states,
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )
        result = pc.reconstruct_ticket_states(RUN_ID, 1, runs_dir)
        assert result == states

    def test_two_waves_merge_correctly(self, tmp_path):
        runs_dir = tmp_path / "runs"
        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        wave1 = {"DAS-1": "done", "DAS-2": "todo"}
        wave2 = {"DAS-1": "done", "DAS-2": "in_review", "DAS-3": "in_progress"}

        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states=wave1,
            created_at=FIXED_TS,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )
        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=2, ticket_id=ANCHOR,
            curr_ticket_states=wave2,
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )

        result = pc.reconstruct_ticket_states(RUN_ID, 2, runs_dir)
        assert result == wave2


class TestReplayQACompatibility:

    def test_checkpoint_events_do_not_affect_replay_qa(self, tmp_path):
        import replay_qa
        import wave_kpi

        store_path = tmp_path / "events.jsonl"
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        runs_dir = tmp_path / "runs"


        from dgox.events import build_routing_decision

        store = EventStore(store_path)
        store.append(build_routing_decision(
            ticket_id=ANCHOR, from_status="todo", to_status="in_progress",
            assignee="backend-eng-1", model="sonnet",
            reason="dispatch", confidence=0.9,
            policy_checks=["gate"], fallback="block",
            created_at=FIXED_TS, run_id=RUN_ID,
        ))
        store.append(build_routing_decision(
            ticket_id=ANCHOR, from_status="in_progress", to_status="done",
            assignee="backend-em", model="sonnet",
            reason="review merged", confidence=0.99,
            policy_checks=["ci_green"], fallback="block",
            created_at=FIXED_TS2, run_id=RUN_ID,
        ))


        pc.write_wave_checkpoint(
            run_id=RUN_ID, wave=1, ticket_id=ANCHOR,
            curr_ticket_states={ANCHOR: "done"},
            created_at=FIXED_TS2,
            store_path=store_path, tickets_dir=tickets_dir, runs_dir=runs_dir,
        )


        events = wave_kpi.read_events(str(store_path))
        summary = replay_qa.drill(events)
        assert summary["corrupted"] == [], (
            f"replay_qa found corrupted resumes: {summary['corrupted']}"
        )
        assert summary["replayable"] == summary["runs"]


class TestGitignore:
    def test_run_checkpoint_is_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet",
             "board/runs/01J9Z8QK3M7Q0W9E4R5T6Y7U8I/wave-001.checkpoint.json"],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "board/runs/<run_id>/wave-001.checkpoint.json is NOT gitignored — "
            "add 'board/runs/**' to .gitignore per ADR-0023 §5"
        )

    def test_completions_jsonl_is_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet",
             "board/runs/01J9Z8QK3M7Q0W9E4R5T6Y7U8I/completions.jsonl"],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "board/runs/<run_id>/completions.jsonl is NOT gitignored"
        )

    def test_run_summary_is_NOT_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet",
             "board/runs/01J9Z8QK3M7Q0W9E4R5T6Y7U8I/run-summary.md"],
            cwd=_REPO_ROOT,
            capture_output=True,
        )

        assert result.returncode == 1, (
            "board/runs/*/run-summary.md IS gitignored but should be retained — "
            "check the negation rule (!board/runs/*/run-summary.md) in .gitignore"
        )
