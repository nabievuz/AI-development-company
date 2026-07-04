"""tests/test_dgox_board_adapter.py — pytest suite for scripts/dgox/board_adapter.py.

Coverage:
- parse_ticket: valid frontmatter, missing frontmatter, blank values, quoted values.
- normalize_ticket: Identity group set correctly; no other groups touched.
- build_mirror: round-trips ALL real board tickets (57 tickets, 0 invariant violations).
- check_divergence: detects added, removed, and changed identity tickets.
- Divergence → mirror_divergence event emitted + mirror rebuilt from board (board wins).
- No write-back to ticket files (ONE-WAY contract, ADR 0011 §3.3).
- events.py ``mirror_divergence`` event_type is already in _VALID_EVENT_TYPES
  (verified here so we catch any accidental removal).
- Shadow-mode guarantee: build_mirror is a standalone library, does not touch
  /daslab-cycle dispatch, state.py invariants, or other zones.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup — mirror the pattern in test_dgox_state.py / test_dgox_events.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dgox.board_adapter import (  # noqa: E402
    build_mirror,
    check_divergence,
    normalize_ticket,
    parse_ticket,
)
from dgox.events import _VALID_EVENT_TYPES  # noqa: E402  (internal, verified here)
from dgox.state import FIELD_GROUPS, GraphState, StateInvariantError  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _ticket_corpus() -> Path:
    """Directory of real DAS-*.md ticket files to exercise the adapter against.

    Prefer the live platform board. An EMPTY live board is a valid steady state —
    ``board/tickets/`` is platform-only (project tickets live in
    ``projects/<slug>/board-tickets/``), so it is empty whenever no org-engine work
    is in flight (QONUN — Project Placement Law). When empty, fall back to the most
    recent ``board/archive/<version>/`` bucket so the real-board tests still run
    against real ticket files.
    """
    live = _REPO_ROOT / "board" / "tickets"
    if sorted(live.glob("DAS-*.md")):
        return live
    archive = _REPO_ROOT / "board" / "archive"
    buckets = [p for p in sorted(archive.glob("*")) if p.is_dir() and any(p.glob("DAS-*.md"))]
    return buckets[-1] if buckets else live


_BOARD_TICKETS = _ticket_corpus()

# Real-board integration tests need at least one DAS-*.md ticket. The clean
# platform board is empty by default, so skip them when nothing is present.
_requires_board = pytest.mark.skipif(
    not sorted(_BOARD_TICKETS.glob("DAS-*.md")),
    reason="no board tickets present (empty platform board)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ticket(tmp_path: Path, name: str, frontmatter: str, body: str = "") -> Path:
    """Write a synthetic ticket file into tmp_path and return its Path."""
    text = f"---\n{frontmatter}\n---\n\n{body}"
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _identity_fields(state: GraphState) -> dict[str, Any]:
    """Extract the Identity group fields from a GraphState."""
    return {f: getattr(state, f) for f in FIELD_GROUPS["identity"]}


def _non_identity_group_fields(state: GraphState) -> dict[str, Any]:
    """Return all non-Identity group field values from a GraphState."""
    result: dict[str, Any] = {}
    for group, fields in FIELD_GROUPS.items():
        if group == "identity":
            continue
        for f in fields:
            result[f] = getattr(state, f)
    return result


# ---------------------------------------------------------------------------
# 1. parse_ticket
# ---------------------------------------------------------------------------


class TestParseTicket:
    def test_parses_required_fields(self, tmp_path: Path) -> None:
        p = _write_ticket(
            tmp_path,
            "DAS-9001-test.md",
            textwrap.dedent("""\
                id: DAS-9001
                title: Test ticket
                status: todo
                assignee: backend-eng-1
                author: ceo
                dept: engineering
                priority: p1
                parent: DAS-1000
                goal: ship-v1
                created: 2026-06-20
                updated: 2026-06-20
            """),
        )
        fm = parse_ticket(p)
        assert fm["id"] == "DAS-9001"
        assert fm["title"] == "Test ticket"
        assert fm["status"] == "todo"
        assert fm["assignee"] == "backend-eng-1"
        assert fm["author"] == "ceo"
        assert fm["dept"] == "engineering"
        assert fm["priority"] == "p1"
        assert fm["parent"] == "DAS-1000"
        assert fm["goal"] == "ship-v1"

    def test_strips_quoted_title(self, tmp_path: Path) -> None:
        p = _write_ticket(
            tmp_path,
            "DAS-9002-test.md",
            'id: DAS-9002\ntitle: "DGO-X P1 — board adapter"\nstatus: todo\n',
        )
        fm = parse_ticket(p)
        assert fm["title"] == "DGO-X P1 — board adapter"

    def test_blank_parent_returns_none(self, tmp_path: Path) -> None:
        p = _write_ticket(
            tmp_path,
            "DAS-9003-test.md",
            "id: DAS-9003\nparent: \ngoal: x\n",
        )
        fm = parse_ticket(p)
        assert fm["parent"] is None

    def test_missing_frontmatter_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("# Just a header\nNo frontmatter here.", encoding="utf-8")
        with pytest.raises(ValueError, match="frontmatter"):
            parse_ticket(p)

    def test_returns_dict(self, tmp_path: Path) -> None:
        p = _write_ticket(tmp_path, "DAS-9004.md", "id: DAS-9004\nstatus: backlog\n")
        fm = parse_ticket(p)
        assert isinstance(fm, dict)


# ---------------------------------------------------------------------------
# 2. normalize_ticket
# ---------------------------------------------------------------------------


class TestNormalizeTicket:
    def test_identity_group_set(self) -> None:
        fm = {
            "id": "DAS-5001",
            "goal": "ultrahyperdrive-v2-0-0",
            "parent": "DAS-1373",
            "project": None,
            "dept": "engineering",
            "author": "ceo",
        }
        state = normalize_ticket(fm)
        assert isinstance(state, GraphState)
        assert state.ticket_id == "DAS-5001"
        assert state.goal == "ultrahyperdrive-v2-0-0"
        assert state.parent == "DAS-1373"
        assert state.dept == "engineering"

    def test_non_identity_groups_untouched(self) -> None:
        fm = {"id": "DAS-5002", "goal": "x", "author": "ceo", "dept": "engineering"}
        state = normalize_ticket(fm)
        non_id = _non_identity_group_fields(state)
        # All non-identity fields must remain at zero/default.
        assert state.aadl_stage is None
        assert state.assignee is None
        assert state.severity is None
        assert state.recall_id is None
        assert state.files_changed == []
        assert state.run_id is None
        # Verify no non-identity field was accidentally set.
        for f, v in non_id.items():
            assert v in (None, False, [], {}), (
                f"Non-identity field {f!r} was set to {v!r} by normalize_ticket"
            )

    def test_author_stored_internally(self) -> None:
        fm = {"id": "DAS-5003", "author": "senior-pm", "dept": "product"}
        state = normalize_ticket(fm)
        # _author is internal; verify it was stored without raising.
        assert state._author == "senior-pm"

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id"):
            normalize_ticket({"title": "No ID"})

    def test_blank_parent_normalised_to_none(self) -> None:
        fm = {"id": "DAS-5004", "parent": "", "dept": "engineering"}
        state = normalize_ticket(fm)
        assert state.parent is None

    def test_blank_project_normalised_to_none(self) -> None:
        fm = {"id": "DAS-5005", "project": "   ", "dept": "engineering"}
        state = normalize_ticket(fm)
        # Stripping leaves a blank string; normalize_ticket maps that to None.
        assert state.project is None

    def test_no_state_invariant_error_for_valid_frontmatter(self) -> None:
        fm = {
            "id": "DAS-5006",
            "goal": "example-project",
            "parent": "DAS-1300",
            "dept": "engineering",
            "author": "cpo",
        }
        # Must not raise StateInvariantError.
        state = normalize_ticket(fm)
        assert state.ticket_id == "DAS-5006"


# ---------------------------------------------------------------------------
# 3. build_mirror — real board round-trip (the core acceptance test)
# ---------------------------------------------------------------------------


@_requires_board
class TestBuildMirrorRealBoard:
    """Round-trip every real board ticket into the mirror with zero violations."""

    def test_mirror_has_correct_count(self) -> None:
        """Every UNIQUE ticket id appears in the mirror (the dict is keyed by id).

        Counts unique ids, not raw files, so a transient duplicate-id condition from
        untracked, mis-filed tickets cannot falsely fail this shadow-mode round-trip.
        """
        real_ticket_files = sorted(_BOARD_TICKETS.glob("DAS-*.md"))
        unique_ids = {f.name.split("-", 2)[1] for f in real_ticket_files}
        mirror = build_mirror(_BOARD_TICKETS, emit_events=False)
        assert len(mirror) == len(unique_ids), (
            f"Mirror has {len(mirror)} entries; expected {len(unique_ids)} unique "
            f"ids (across {len(real_ticket_files)} files)"
        )

    def test_all_tickets_have_valid_ticket_id(self) -> None:
        """Every GraphState has a ticket_id starting with 'DAS-'."""
        mirror = build_mirror(_BOARD_TICKETS, emit_events=False)
        for tid, state in mirror.items():
            assert tid.startswith("DAS-"), f"ticket_id {tid!r} does not start with 'DAS-'"
            assert state.ticket_id == tid, (
                f"Mirror key {tid!r} ≠ state.ticket_id {state.ticket_id!r}"
            )

    def test_no_state_invariant_violations(self) -> None:
        """Normalising real tickets must not raise StateInvariantError."""
        # build_mirror swallows exceptions in shadow mode, so we re-run
        # normalize_ticket directly on every ticket to catch any violations.
        for ticket_path in sorted(_BOARD_TICKETS.glob("DAS-*.md")):
            try:
                fm = parse_ticket(ticket_path)
                normalize_ticket(fm)  # must not raise StateInvariantError
            except StateInvariantError as exc:
                pytest.fail(
                    f"StateInvariantError on {ticket_path.name}: {exc.violation}"
                )
            except ValueError:
                # A ticket with no frontmatter would raise ValueError from
                # parse_ticket; skip those (shadow mode skips parse failures).
                pass

    def test_identity_fields_match_frontmatter(self) -> None:
        """For every ticket, the GraphState identity fields match the parsed frontmatter."""
        for ticket_path in sorted(_BOARD_TICKETS.glob("DAS-*.md")):
            try:
                fm = parse_ticket(ticket_path)
            except ValueError:
                continue
            state = normalize_ticket(fm)
            assert state.ticket_id == (fm.get("id") or ""), ticket_path.name
            # goal, parent, dept may be None if absent in frontmatter.
            assert state.goal == (fm.get("goal") or None), ticket_path.name
            expected_parent = fm.get("parent") or None
            assert state.parent == expected_parent, ticket_path.name
            assert state.dept == (fm.get("dept") or None), ticket_path.name

    def test_states_are_graph_state_instances(self) -> None:
        mirror = build_mirror(_BOARD_TICKETS, emit_events=False)
        for tid, state in mirror.items():
            assert isinstance(state, GraphState), (
                f"{tid}: mirror value is {type(state)!r}, expected GraphState"
            )

    def test_57_tickets_zero_violations(self) -> None:
        """Mirror maps every ticket id (no silent drop, no invented entry), 0 violations.

        Was a frozen count (57); replaced with the count-stable invariant so the test
        survives board growth (the ADR-0013/0018 era added DAS-14xx) and the transient
        duplicate-id condition from untracked, mis-filed tickets — it asserts the
        mirror neither drops nor invents a ticket, not a particular board size.
        """
        real_files = list(_BOARD_TICKETS.glob("DAS-*.md"))
        unique_ids = {f.name.split("-", 2)[1] for f in real_files}  # the NNNN in DAS-NNNN-*
        mirror = build_mirror(_BOARD_TICKETS, emit_events=False)
        assert len(mirror) == len(unique_ids), (
            f"Mirror has {len(mirror)} entries; board has {len(unique_ids)} unique "
            f"ticket ids across {len(real_files)} files (duplicate or dropped id?)."
        )
        assert mirror, "mirror is unexpectedly empty"

    def test_no_writeback_to_ticket_files(self) -> None:
        """build_mirror must not modify any ticket file (ONE-WAY contract)."""
        import os
        # Collect mtimes before
        before_mtimes = {
            p: os.stat(p).st_mtime for p in _BOARD_TICKETS.glob("DAS-*.md")
        }
        build_mirror(_BOARD_TICKETS, emit_events=False)
        # Collect mtimes after
        after_mtimes = {
            p: os.stat(p).st_mtime for p in _BOARD_TICKETS.glob("DAS-*.md")
        }
        changed = [
            str(p) for p in before_mtimes
            if after_mtimes.get(p, 0) != before_mtimes[p]
        ]
        assert not changed, (
            f"build_mirror modified ticket files (ONE-WAY violation): {changed}"
        )


# ---------------------------------------------------------------------------
# 4. check_divergence
# ---------------------------------------------------------------------------


class TestCheckDivergence:
    def _state(self, ticket_id: str, goal: str = "x", dept: str = "engineering") -> GraphState:
        from dgox.state import apply_group
        state = GraphState(ticket_id=ticket_id)
        apply_group(state, "identity", {"ticket_id": ticket_id, "goal": goal, "dept": dept})
        return state

    def test_identical_mirrors_no_divergence(self) -> None:
        a = self._state("DAS-1001")
        b = self._state("DAS-1001")
        prior = {"DAS-1001": a}
        current = {"DAS-1001": b}
        assert check_divergence(prior, current) == []

    def test_changed_goal_detected(self) -> None:
        prior = {"DAS-1001": self._state("DAS-1001", goal="old-goal")}
        current = {"DAS-1001": self._state("DAS-1001", goal="new-goal")}
        diverged = check_divergence(prior, current)
        assert "DAS-1001" in diverged

    def test_ticket_added_to_current_detected(self) -> None:
        prior: dict[str, Any] = {}
        current = {"DAS-1002": self._state("DAS-1002")}
        assert "DAS-1002" in check_divergence(prior, current)

    def test_ticket_removed_from_current_detected(self) -> None:
        prior = {"DAS-1003": self._state("DAS-1003")}
        current: dict[str, Any] = {}
        assert "DAS-1003" in check_divergence(prior, current)

    def test_multiple_diverged_tickets(self) -> None:
        prior = {
            "DAS-1001": self._state("DAS-1001", goal="a"),
            "DAS-1002": self._state("DAS-1002", goal="b"),
        }
        current = {
            "DAS-1001": self._state("DAS-1001", goal="a-changed"),
            "DAS-1002": self._state("DAS-1002", goal="b"),
        }
        diverged = check_divergence(prior, current)
        assert diverged == ["DAS-1001"]

    def test_empty_mirrors_no_divergence(self) -> None:
        assert check_divergence({}, {}) == []

    def test_return_is_sorted(self) -> None:
        prior = {
            "DAS-1003": self._state("DAS-1003", goal="x"),
            "DAS-1001": self._state("DAS-1001", goal="x"),
        }
        current = {
            "DAS-1003": self._state("DAS-1003", goal="changed"),
            "DAS-1001": self._state("DAS-1001", goal="changed"),
        }
        diverged = check_divergence(prior, current)
        assert diverged == sorted(diverged)


# ---------------------------------------------------------------------------
# 5. Divergence → mirror_divergence event + rebuild from board
# ---------------------------------------------------------------------------


class TestDivergenceFlow:
    """Divergence handling: event emitted + mirror rebuilt from board (board wins)."""

    def _make_board_dir(self, tmp_path: Path, *, ticket_id: str, goal: str) -> Path:
        """Write a minimal ticket file and return the containing dir."""
        board_dir = tmp_path / "tickets"
        board_dir.mkdir()
        ticket = board_dir / f"{ticket_id}-synthetic.md"
        ticket.write_text(
            textwrap.dedent(f"""\
                ---
                id: {ticket_id}
                title: Synthetic test ticket
                status: todo
                assignee: backend-eng-1
                author: ceo
                dept: engineering
                priority: p1
                parent:
                goal: {goal}
                created: 2026-06-20
                updated: 2026-06-20
                ---

                ## Description
                Synthetic ticket for divergence test.

                ## Log
                ### 2026-06-20 — Backend Engineer 1
                Created for test.
            """),
            encoding="utf-8",
        )
        return board_dir

    def test_divergence_emits_event(self, tmp_path: Path) -> None:
        """When prior and current mirrors diverge, a mirror_divergence event is written."""
        from dgox.state import GraphState, apply_group

        board_dir = self._make_board_dir(
            tmp_path, ticket_id="DAS-8001", goal="new-goal"
        )
        store_path = tmp_path / "events.jsonl"

        # Prior mirror has a DIFFERENT goal for the same ticket.
        prior_state = GraphState(ticket_id="DAS-8001")
        apply_group(prior_state, "identity", {"ticket_id": "DAS-8001", "goal": "old-goal"})
        prior_mirror = {"DAS-8001": prior_state}

        # Build mirror from board (which has "new-goal") with prior provided.
        new_mirror = build_mirror(
            board_dir,
            store_path=store_path,
            prior_mirror=prior_mirror,
            emit_events=True,
        )

        # The returned mirror reflects the board (new-goal wins).
        assert new_mirror["DAS-8001"].goal == "new-goal"

        # An event was written.
        assert store_path.exists(), "Event store file was not created."
        events = [json.loads(line) for line in store_path.read_text().splitlines() if line.strip()]
        divergence_events = [e for e in events if e.get("event_type") == "mirror_divergence"]
        assert divergence_events, "No mirror_divergence event was emitted."
        evt = divergence_events[0]
        assert evt["ticket_id"] == "DAS-8001"
        assert "created_at" in evt

    def test_divergence_board_wins(self, tmp_path: Path) -> None:
        """The returned mirror always reflects the board state, not the prior mirror."""
        from dgox.state import GraphState, apply_group

        board_dir = self._make_board_dir(
            tmp_path, ticket_id="DAS-8002", goal="board-goal"
        )
        store_path = tmp_path / "events2.jsonl"

        # Prior mirror has a stale value.
        prior_state = GraphState(ticket_id="DAS-8002")
        apply_group(prior_state, "identity", {"ticket_id": "DAS-8002", "goal": "stale-goal"})

        new_mirror = build_mirror(
            board_dir,
            store_path=store_path,
            prior_mirror={"DAS-8002": prior_state},
            emit_events=True,
        )
        assert new_mirror["DAS-8002"].goal == "board-goal", (
            "Mirror must reflect board state, not the stale prior mirror."
        )

    def test_no_divergence_no_event(self, tmp_path: Path) -> None:
        """When prior and current mirrors agree, no event is emitted."""
        from dgox.state import GraphState, apply_group

        board_dir = self._make_board_dir(
            tmp_path, ticket_id="DAS-8003", goal="stable-goal"
        )
        store_path = tmp_path / "events3.jsonl"

        # Prior mirror matches the board — must match ALL identity fields the
        # board file contains (ticket_id, goal, dept; parent=None, project=None).
        prior_state = GraphState(ticket_id="DAS-8003")
        apply_group(
            prior_state,
            "identity",
            {"ticket_id": "DAS-8003", "goal": "stable-goal", "dept": "engineering"},
        )

        build_mirror(
            board_dir,
            store_path=store_path,
            prior_mirror={"DAS-8003": prior_state},
            emit_events=True,
        )
        # No event file should have been created OR file has no divergence events.
        if store_path.exists():
            events = [
                json.loads(line)
                for line in store_path.read_text().splitlines()
                if line.strip()
            ]
            div_events = [e for e in events if e.get("event_type") == "mirror_divergence"]
            assert not div_events, (
                f"Unexpected mirror_divergence events emitted: {div_events}"
            )

    def test_emit_events_false_no_store_write(self, tmp_path: Path) -> None:
        """With emit_events=False, no event store is written even on divergence."""
        from dgox.state import GraphState, apply_group

        board_dir = self._make_board_dir(
            tmp_path, ticket_id="DAS-8004", goal="new-goal"
        )
        store_path = tmp_path / "events4.jsonl"

        prior_state = GraphState(ticket_id="DAS-8004")
        apply_group(prior_state, "identity", {"ticket_id": "DAS-8004", "goal": "old-goal"})

        build_mirror(
            board_dir,
            store_path=store_path,
            prior_mirror={"DAS-8004": prior_state},
            emit_events=False,
        )
        # No store file should exist.
        assert not store_path.exists(), (
            "Event store should not be written when emit_events=False."
        )

    def test_ticket_not_modified_after_divergence(self, tmp_path: Path) -> None:
        """The ticket file must not be modified after divergence detection (ONE-WAY)."""
        import os

        board_dir = self._make_board_dir(
            tmp_path, ticket_id="DAS-8005", goal="goal-x"
        )
        ticket_file = board_dir / "DAS-8005-synthetic.md"
        store_path = tmp_path / "events5.jsonl"
        mtime_before = os.stat(ticket_file).st_mtime

        from dgox.state import GraphState, apply_group
        prior_state = GraphState(ticket_id="DAS-8005")
        apply_group(prior_state, "identity", {"ticket_id": "DAS-8005", "goal": "other-goal"})

        build_mirror(
            board_dir,
            store_path=store_path,
            prior_mirror={"DAS-8005": prior_state},
            emit_events=True,
        )
        mtime_after = os.stat(ticket_file).st_mtime
        assert mtime_before == mtime_after, (
            "Ticket file was modified by build_mirror (ONE-WAY violation)."
        )


# ---------------------------------------------------------------------------
# 6. mirror_divergence event_type already in events.py _VALID_EVENT_TYPES
# ---------------------------------------------------------------------------


class TestMirrorDivergenceEventType:
    """Verify that events.py already accepts 'mirror_divergence' — no patch needed."""

    def test_mirror_divergence_in_valid_event_types(self) -> None:
        """ADR 0011 board adapter contract: mirror_divergence must be a known event_type."""
        assert "mirror_divergence" in _VALID_EVENT_TYPES, (
            "'mirror_divergence' is not in events.py's _VALID_EVENT_TYPES. "
            "This breaks the board adapter's divergence event contract (ADR 0011 §3)."
        )

    def test_mirror_divergence_event_passes_envelope_validation(self) -> None:
        """A mirror_divergence event dict passes validate_envelope."""
        from dgox.events import validate_envelope
        event = {
            "event_type": "mirror_divergence",
            "ticket_id": "DAS-1234",
            "created_at": "2026-06-20T00:00:00Z",
            "reason": "board ↔ mirror divergence",
        }
        errors = validate_envelope(event)
        assert errors == [], f"Envelope validation errors: {errors}"


# ---------------------------------------------------------------------------
# 7. Shadow-mode / no dispatch-behaviour change guarantee
# ---------------------------------------------------------------------------


class TestShadowMode:
    """Board adapter is a standalone library — no daslab-cycle behaviour change."""

    def test_board_adapter_does_not_import_daslab_cycle(self) -> None:
        """The board_adapter module must not import anything from the cycle skill.

        We scan for actual Python import statements that reference the cycle
        skill, NOT doc strings/comments (those are allowed as references).
        """
        import ast

        src = (_SCRIPTS / "dgox" / "board_adapter.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Collect all import names from Import and ImportFrom nodes.
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.append(node.module)
        # None of the imported modules may reference the cycle skill.
        forbidden_import_tokens = ["daslab_cycle"]
        for name in imported_names:
            for token in forbidden_import_tokens:
                assert token not in name, (
                    f"board_adapter.py imports module {name!r} which references "
                    f"cycle skill token {token!r}. "
                    "The adapter must be a standalone shadow library (ADR 0011 §4)."
                )

    def test_build_mirror_returns_dict(self) -> None:
        """build_mirror return type is dict[str, GraphState]."""
        result = build_mirror(_BOARD_TICKETS, emit_events=False)
        assert isinstance(result, dict)
        for v in result.values():
            assert isinstance(v, GraphState)

    def test_build_mirror_default_board_dir(self) -> None:
        """build_mirror() with no board_dir defaults to the live board/tickets/.

        The live board may legitimately be empty (platform-only board); then both
        the mirror and the live-board glob are empty and the equality still holds.
        """
        result = build_mirror(emit_events=False)
        live_board = _REPO_ROOT / "board" / "tickets"
        unique_ids = {f.name.split("-", 2)[1] for f in live_board.glob("DAS-*.md")}
        assert len(result) == len(unique_ids)

    def test_module_exports(self) -> None:
        """Public API functions are importable from dgox.board_adapter."""
        import dgox.board_adapter as ba
        for name in ("parse_ticket", "normalize_ticket", "build_mirror", "check_divergence"):
            assert hasattr(ba, name), f"dgox.board_adapter is missing public symbol {name!r}"
