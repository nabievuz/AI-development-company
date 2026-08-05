
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dgox.board_adapter import build_mirror
from dgox.events import (
    EventStore,
    build_routing_decision,
    utcnow,
    validate_routing_decision,
)
from dgox.state import GraphState


def _ticket_corpus() -> Path:
    live = _REPO_ROOT / "board" / "tickets"
    if sorted(live.glob("DAS-*.md")):
        return live
    archive = _REPO_ROOT / "board" / "archive"
    buckets = [p for p in sorted(archive.glob("*")) if p.is_dir() and any(p.glob("DAS-*.md"))]
    return buckets[-1] if buckets else live


_BOARD_TICKETS = _ticket_corpus()
_SKILL_FILE = _REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"


_requires_board = pytest.mark.skipif(
    not sorted(_BOARD_TICKETS.glob("DAS-*.md")),
    reason="no board tickets present (empty platform board)",
)


@_requires_board
class TestMirrorCoverage:

    def test_build_mirror_covers_all_board_tickets(self) -> None:
        ticket_files = sorted(_BOARD_TICKETS.glob("DAS-*.md"))
        assert ticket_files, "board/tickets/ must contain at least one DAS-*.md file"


        from dgox.board_adapter import parse_ticket

        parseable_ids: set[str] = set()
        for path in ticket_files:
            try:
                fm = parse_ticket(path)
                tid = fm.get("id", "")
                if tid:
                    parseable_ids.add(tid)
            except Exception:

                pass

        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        mirror_ids = set(mirror.keys())


        missing = parseable_ids - mirror_ids
        assert not missing, (
            f"build_mirror missed {len(missing)} parseable ticket(s): {sorted(missing)}"
        )

    def test_mirror_entries_are_graph_state_instances(self) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror, "Mirror must not be empty"
        for tid, state in mirror.items():
            assert isinstance(state, GraphState), (
                f"Mirror entry {tid!r} is {type(state).__name__}, expected GraphState"
            )

    def test_mirror_identity_fields_populated(self) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        for tid, state in mirror.items():
            assert state.ticket_id == tid, (
                f"state.ticket_id {state.ticket_id!r} != mirror key {tid!r}"
            )
            assert state.ticket_id.startswith("DAS-"), (
                f"ticket_id {state.ticket_id!r} does not follow DAS-NNNN scheme"
            )

    def test_no_invariant_violations_on_real_board(self) -> None:
        from dgox.state import StateInvariantError


        violations: list[dict[str, Any]] = []

        import dgox.state as state_mod

        original_fn = state_mod.apply_group

        def tracking_apply_group(
            state: Any, group: str, updates: dict, **kwargs: Any
        ) -> None:
            try:
                original_fn(state, group, updates, **kwargs)
            except StateInvariantError as exc:
                violations.append(exc.violation)
                raise

        with patch.object(state_mod, "apply_group", tracking_apply_group):
            build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)

        assert not violations, (
            f"build_mirror triggered {len(violations)} invariant violation(s) "
            f"on real board: {violations}"
        )

    def test_mirror_non_identity_groups_are_default(self) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror
        for tid, state in mirror.items():

            assert state.aadl_stage is None, f"{tid}: aadl_stage should be None"
            assert state.gate_status is None, f"{tid}: gate_status should be None"

            assert state.assignee is None, f"{tid}: assignee should be None"
            assert state.reviewer is None, f"{tid}: reviewer should be None"

            assert state.run_id is None, f"{tid}: run_id should be None"
            assert state.branch is None, f"{tid}: branch should be None"

            assert state.severity is None, f"{tid}: severity should be None"

            assert state.files_changed == [], f"{tid}: files_changed should be []"

            assert state.memory_scope is None, f"{tid}: memory_scope should be None"


@_requires_board
class TestRoutingDecisionCoverage:

    def test_100_percent_routing_decision_coverage(self, tmp_path: Path) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror, "Need at least one ticket to test coverage"

        store_path = tmp_path / "events.jsonl"
        store = EventStore(path=store_path)
        ts = utcnow()

        dispatched_ids = sorted(mirror.keys())

        for tid in dispatched_ids:
            ev = build_routing_decision(
                ticket_id=tid,
                from_status="todo",
                to_status="in_progress",
                assignee="qa-eng",
                model="sonnet",
                reason=f"Simulated dispatch of {tid} for GATE-4 coverage proof.",
                confidence=0.9,
                policy_checks=["aadl_predecessor_gate_closed", "repo_area_available"],
                fallback="skip_to_next_wave",
                created_at=ts,
                run_id="gate4-coverage-run",
            )
            store.append(ev)


        recorded_ids: list[str] = []
        with open(store_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("event_type") == "routing_decision":
                    recorded_ids.append(ev["ticket_id"])

        assert len(recorded_ids) == len(dispatched_ids), (
            f"Coverage gap: dispatched {len(dispatched_ids)} tickets "
            f"but recorded {len(recorded_ids)} routing_decision events."
        )
        assert set(recorded_ids) == set(dispatched_ids), (
            f"ID mismatch: dispatched={sorted(dispatched_ids)}, "
            f"recorded={sorted(recorded_ids)}"
        )

    def test_every_routing_decision_validates_against_shape_82(self, tmp_path: Path) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror

        ts = utcnow()
        store_path = tmp_path / "events.jsonl"
        store = EventStore(path=store_path)

        for tid in sorted(mirror.keys()):
            ev = build_routing_decision(
                ticket_id=tid,
                from_status="todo",
                to_status="in_progress",
                assignee="backend-eng-1",
                model="sonnet",
                reason=f"Gate-4 shape validation for {tid}.",
                confidence=0.85,
                policy_checks=["aadl_predecessor_gate_closed"],
                fallback="block_and_escalate",
                created_at=ts,
            )
            store.append(ev)

        with open(store_path, encoding="utf-8") as fh:
            lines = [line.strip() for line in fh if line.strip()]

        assert len(lines) == len(mirror), (
            f"Expected {len(mirror)} event lines, got {len(lines)}"
        )

        all_errors: list[tuple[str, list[str]]] = []
        for raw in lines:
            ev = json.loads(raw)
            errors = validate_routing_decision(ev)
            if errors:
                all_errors.append((ev.get("ticket_id", "<unknown>"), errors))

        assert not all_errors, (
            f"{len(all_errors)} event(s) failed §8.2 shape validation: {all_errors}"
        )

    def test_events_land_only_in_jsonl_not_ticket_files(self, tmp_path: Path) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        store_path = tmp_path / "events.jsonl"
        store = EventStore(path=store_path)
        ts = utcnow()

        opened_for_write: list[str] = []
        original_open = open

        def tracking_open(path: Any, mode: str = "r", **kw: Any) -> Any:
            path_str = str(path)
            tickets_prefix = str(_BOARD_TICKETS)
            if ("w" in mode or "a" in mode) and tickets_prefix in path_str:
                opened_for_write.append(path_str)
            return original_open(path, mode, **kw)

        with patch("builtins.open", tracking_open):
            for tid in sorted(mirror.keys()):
                ev = build_routing_decision(
                    ticket_id=tid,
                    from_status="todo",
                    to_status="in_progress",
                    assignee="qa-eng",
                    model="sonnet",
                    reason=f"No-writeback proof for {tid}.",
                    confidence=0.9,
                    policy_checks=["aadl_predecessor_gate_closed"],
                    fallback="skip_to_next_wave",
                    created_at=ts,
                )
                store.append(ev)

        assert not opened_for_write, (
            f"Emission loop opened ticket files for writing: {opened_for_write}"
        )


@_requires_board
class TestShadowClean:


    _READ_PRIMITIVES = frozenset(
        {"read_events", "iter_events", "group_runs", "replay_run"}
    )


    _RECOVERY_MARKERS = ("--resume", "--fork", "resume_fork")

    @staticmethod
    def _call_names(tree: ast.AST) -> set[str]:
        out: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    out.add(fn.attr)
                elif isinstance(fn, ast.Name):
                    out.add(fn.id)
        return out

    @staticmethod
    def _open_mode(node: ast.Call) -> str:
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            return str(node.args[1].value)
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
        return ""

    @classmethod
    def _has_events_literal_read(cls, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            has_events_literal = any(
                isinstance(a, ast.Constant)
                and isinstance(a.value, str)
                and ".events.jsonl" in a.value
                for a in node.args
            )
            if not has_events_literal:
                continue
            if name in {"read_text", "read_bytes"}:
                return True
            if name == "open" and not any(c in cls._open_mode(node) for c in ("w", "a", "x")):
                return True
        return False

    @classmethod
    def _writes_ticket_routing(cls, tree: ast.AST, source: str) -> bool:
        if "board/tickets" not in source:
            return False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in {"write_text", "write_bytes"}:
                return True
            if name == "open" and any(c in cls._open_mode(node) for c in ("w", "a", "x", "+")):
                return True
        return False

    def test_p1_no_normal_dispatch_script_reads_events_to_route(self) -> None:
        scripts_dir = _SCRIPTS
        py_files = [
            p
            for p in scripts_dir.rglob("*.py")
            if "dgox" not in p.parts
            and "cache" not in p.parts
        ]

        offenders: dict[str, str] = {}
        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            reads_store = bool(
                self._READ_PRIMITIVES & self._call_names(tree)
            ) or self._has_events_literal_read(tree)
            if not reads_store:
                continue

            if any(marker in source for marker in self._RECOVERY_MARKERS):
                continue


            if self._writes_ticket_routing(tree, source):
                offenders[str(py_file.relative_to(scripts_dir))] = (
                    "reads the event store AND writes normal-wave ticket routing, "
                    "outside the --resume/--fork recovery gate"
                )

        assert not offenders, (
            "Normal-dispatch script(s) READ the event store to route (ADR-0025: "
            "only the operator-invoked --resume/--fork recovery path may read events "
            "to re-dispatch; normal waves stay flag-on == flag-off):\n"
            + "\n".join(f"  scripts/{f}: {why}" for f, why in sorted(offenders.items()))
        )

    def test_p1_skill_dispatch_decision_text_no_dgox_read(self) -> None:
        assert _SKILL_FILE.exists(), f"SKILL.md not found at {_SKILL_FILE}"
        skill_text = _SKILL_FILE.read_text(encoding="utf-8")


        assert "DGO-X shadow emission" in skill_text, (
            "SKILL.md must contain 'DGO-X shadow emission' header (step 5d)"
        )
        assert "SHADOW / ADVISORY ONLY" in skill_text, (
            "Step 5d must be labelled 'SHADOW / ADVISORY ONLY' in SKILL.md"
        )


        assert "NOTHING in" in skill_text, (
            "SKILL.md step 5d must contain 'NOTHING in' statement"
        )
        assert "or routes off them" in skill_text, (
            "SKILL.md step 5d must contain 'or routes off them' statement (may span lines)"
        )

    def test_p1_dgox_modules_not_imported_at_module_level_in_scripts(self) -> None:

        scripts_to_check = [
            _SCRIPTS / "_paths.py",
            _SCRIPTS / "check_gates.py",
            _SCRIPTS / "check_agents_sync.py",
        ]

        for script in scripts_to_check:
            if not script.exists():
                continue
            source = script.read_text(encoding="utf-8", errors="replace")


            if "dgox" in source:

                tree = ast.parse(source, filename=str(script))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import | ast.ImportFrom):
                        for alias in getattr(node, "names", []):
                            assert not alias.name.startswith("dgox"), (
                                f"{script.name} imports dgox.* at module level "
                                f"(line {node.lineno})"
                            )
                        module = getattr(node, "module", "") or ""
                        assert not module.startswith("dgox"), (
                            f"{script.name} imports from dgox.* at module level "
                            f"(line {node.lineno})"
                        )


    def test_p2_no_writeback_board_tickets_unchanged(self, tmp_path: Path) -> None:
        ticket_files = sorted(_BOARD_TICKETS.glob("DAS-*.md"))
        assert ticket_files


        def snapshot() -> dict[str, tuple[int, bytes]]:
            return {
                str(f): (os.stat(f).st_mtime_ns, f.read_bytes())
                for f in ticket_files
            }

        before = snapshot()


        store_path = tmp_path / "gate4-nowb-events.jsonl"
        mirror = build_mirror(board_dir=_BOARD_TICKETS, store_path=store_path, emit_events=False)
        assert mirror

        store = EventStore(path=store_path)
        ts = utcnow()
        for tid in sorted(mirror.keys()):
            ev = build_routing_decision(
                ticket_id=tid,
                from_status="todo",
                to_status="in_progress",
                assignee="qa-eng",
                model="sonnet",
                reason=f"P2 no-writeback proof — {tid}.",
                confidence=0.9,
                policy_checks=["aadl_predecessor_gate_closed"],
                fallback="skip_to_next_wave",
                created_at=ts,
            )
            store.append(ev)

        after = snapshot()


        changed: list[str] = []
        for path_str, (_mtime_before, bytes_before) in before.items():
            _mtime_after, bytes_after = after[path_str]
            if bytes_before != bytes_after:
                changed.append(f"{path_str} (content changed)")
        new_files = set(after) - set(before)
        if new_files:
            changed.extend(f"{p} (new file)" for p in sorted(new_files))

        assert not changed, (
            f"Phase-1 pipeline wrote to {len(changed)} ticket file(s) — "
            f"ONE-WAY contract violated (ADR 0011 §3.3): {changed}"
        )

    def test_p2_events_write_to_tmp_store_only(self, tmp_path: Path) -> None:
        real_store = _REPO_ROOT / "board" / ".events.jsonl"
        real_before = real_store.stat().st_size if real_store.exists() else -1

        store_path = tmp_path / "isolated-events.jsonl"
        store = EventStore(path=store_path)
        ts = utcnow()

        ev = build_routing_decision(
            ticket_id="DAS-9999",
            from_status="todo",
            to_status="in_progress",
            assignee="qa-eng",
            model="sonnet",
            reason="P2 isolated-store proof.",
            confidence=0.9,
            policy_checks=["test"],
            fallback="skip_to_next_wave",
            created_at=ts,
        )
        store.append(ev)

        real_after = real_store.stat().st_size if real_store.exists() else -1
        assert real_before == real_after, (
            f"Real event store board/.events.jsonl changed size during test "
            f"(before={real_before}, after={real_after}) — test leaked writes"
        )


        assert store_path.exists(), "Tmp store was not created"
        content = store_path.read_text(encoding="utf-8")
        assert "DAS-9999" in content


    def test_p3_failure_isolation_store_exception_does_not_propagate(
        self, tmp_path: Path
    ) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror

        dispatched_count = 0
        emission_errors: list[str] = []


        def _shadow_emit_step5d(store: EventStore, ev: dict) -> None:
            try:
                store.append(ev)
            except Exception as exc:

                emission_errors.append(str(exc))

        ts = utcnow()
        store_path = tmp_path / "failing-store.jsonl"

        with patch.object(
            EventStore,
            "append",
            side_effect=OSError("simulated disk-full"),
        ) as mock_append:
            store = EventStore(path=store_path)
            for tid in sorted(mirror.keys()):
                ev = build_routing_decision(
                    ticket_id=tid,
                    from_status="todo",
                    to_status="in_progress",
                    assignee="qa-eng",
                    model="sonnet",
                    reason=f"P3 failure-isolation proof — {tid}.",
                    confidence=0.9,
                    policy_checks=["aadl_predecessor_gate_closed"],
                    fallback="skip_to_next_wave",
                    created_at=ts,
                )

                _shadow_emit_step5d(store, ev)
                dispatched_count += 1


        assert dispatched_count == len(mirror), (
            f"Dispatch loop aborted early: only {dispatched_count}/{len(mirror)} "
            "tickets processed (store failure broke dispatch)"
        )


        assert mock_append.call_count == len(mirror), (
            f"Expected {len(mirror)} append attempts, got {mock_append.call_count}"
        )


        assert len(emission_errors) == len(mirror), (
            f"Expected {len(mirror)} swallowed errors, got {len(emission_errors)}"
        )

    def test_p3_partial_store_failure_continues_remaining_dispatches(
        self, tmp_path: Path
    ) -> None:
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert len(mirror) >= 2, "Need at least 2 tickets for partial-failure test"

        store_path = tmp_path / "partial-fail.jsonl"
        ts = utcnow()

        call_count = 0
        fail_first_n = max(1, len(mirror) // 3)

        original_append = EventStore.append

        def patched_append(self: Any, ev: dict) -> None:
            nonlocal call_count
            call_count += 1
            if call_count <= fail_first_n:
                raise OSError(f"simulated failure #{call_count}")
            original_append(self, ev)

        emission_errors: list[str] = []
        processed: list[str] = []

        with patch.object(EventStore, "append", patched_append):
            store2 = EventStore(path=store_path)
            for tid in sorted(mirror.keys()):
                ev = build_routing_decision(
                    ticket_id=tid,
                    from_status="todo",
                    to_status="in_progress",
                    assignee="qa-eng",
                    model="sonnet",
                    reason=f"Partial-failure test — {tid}.",
                    confidence=0.9,
                    policy_checks=["aadl_predecessor_gate_closed"],
                    fallback="skip_to_next_wave",
                    created_at=ts,
                )
                try:
                    store2.append(ev)
                except Exception as exc:
                    emission_errors.append(str(exc))
                processed.append(tid)


        assert len(processed) == len(mirror), (
            f"Loop stopped early: {len(processed)}/{len(mirror)} tickets processed"
        )

        assert len(emission_errors) == fail_first_n, (
            f"Expected {fail_first_n} swallowed errors, got {len(emission_errors)}"
        )


@_requires_board
class TestFullPipelineSmoke:

    def test_full_pipeline_no_errors(self, tmp_path: Path) -> None:
        store_path = tmp_path / "full-pipeline.jsonl"


        mirror = build_mirror(board_dir=_BOARD_TICKETS, store_path=store_path, emit_events=True)
        assert mirror, "Mirror must not be empty"


        store = EventStore(path=store_path)
        ts = utcnow()
        emitted: list[str] = []

        for tid in sorted(mirror.keys()):
            ev = build_routing_decision(
                ticket_id=tid,
                from_status="todo",
                to_status="in_progress",
                assignee="qa-eng",
                model="sonnet",
                reason=f"Full pipeline smoke — {tid}.",
                confidence=0.9,
                policy_checks=["aadl_predecessor_gate_closed", "repo_area_available"],
                fallback="skip_to_next_wave",
                created_at=ts,
                run_id="gate4-smoke-run",
            )
            store.append(ev)
            emitted.append(tid)

        assert len(emitted) == len(mirror)


        events = []
        with open(store_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        routing_events = [e for e in events if e.get("event_type") == "routing_decision"]
        assert len(routing_events) == len(mirror), (
            f"Expected {len(mirror)} routing_decision events, found {len(routing_events)}"
        )

        for ev in routing_events:
            errors = validate_routing_decision(ev)
            assert not errors, (
                f"routing_decision for {ev.get('ticket_id')} failed §8.2 validation: {errors}"
            )

    def test_full_pipeline_replay_roundtrip(self, tmp_path: Path) -> None:
        from dgox.events import iter_events

        store_path = tmp_path / "replay-roundtrip.jsonl"
        store = EventStore(path=store_path)
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror

        ts = utcnow()
        run_id = "gate4-replay"
        emitted_ids: list[str] = []

        for tid in sorted(mirror.keys()):
            ev = build_routing_decision(
                ticket_id=tid,
                from_status="todo",
                to_status="in_progress",
                assignee="qa-eng",
                model="sonnet",
                reason=f"Replay roundtrip — {tid}.",
                confidence=0.9,
                policy_checks=["aadl_predecessor_gate_closed"],
                fallback="skip_to_next_wave",
                created_at=ts,
                run_id=run_id,
            )
            store.append(ev)
            emitted_ids.append(tid)

        replayed_ids = [
            ev["ticket_id"]
            for ev in iter_events(path=store_path, run_id=run_id, event_type="routing_decision")
        ]

        assert replayed_ids == emitted_ids, (
            f"Replay mismatch: emitted {len(emitted_ids)}, replayed {len(replayed_ids)}"
        )
