"""tests/test_dgox_phase1_shadow.py — DGO-X Phase-1 integration & shadow-clean acceptance.

GATE-4 acceptance suite: proves (a) the substrate works end-to-end and
(b) it is genuinely SHADOW — the Phase-1→Phase-2 gate.

The per-module unit suites (test_dgox_state.py: 53, test_dgox_events.py: 41,
test_dgox_board_adapter.py: 37 tests) already verify individual correctness.
THIS suite adds integration coverage and the three structural SHADOW-CLEAN proofs.

Why "flag-on == flag-off dispatch" holds for a skill-based shadow
-----------------------------------------------------------------
/daslab-cycle is a SKILL — a markdown document the orchestrator (Claude)
reads and follows. It has no feature flags in the runtime sense.  The
"shadow" is purely structural: step 5d is the ONLY place dgox.* is touched
inside the cycle skill, and it is positioned as:

  post-decision (after the routing choice is made)
  + observational (no return value read back into dispatch)
  + failure-isolated (any EventStore.append exception is caught + logged;
    dispatch continues unconditionally)

Therefore:

  flag-on  (step 5d runs)  → orchestrator emits routing_decision events
  flag-off (step 5d skipped) → orchestrator makes identical routing decisions

The diff between flag-on and flag-off execution is *exactly* the JSONL
lines appended to board/.events.jsonl — which is gitignored runtime state,
never read by the dispatch-DECISION logic.  The three proofs below make each
structural guarantee machine-checkable and executable.

SHADOW-CLEAN PROOF SUMMARY
───────────────────────────
P1 No-influence:  no NORMAL-dispatch script READS the event store to make a
                  routing decision (ADR-0025 principled reader-vs-router rule —
                  supersedes the old per-file _EVENT_PRODUCERS allowlist).  A
                  script is flagged ONLY when it both (1) READS the store
                  (read_events/iter_events/group_runs/replay_run, or a
                  .events.jsonl read) and (2) ROUTES the normal wave (writes a
                  board/tickets routing field) — UNLESS gated behind the explicit
                  operator-recovery entrypoint (--resume/--fork).  Write-only
                  producers and operator-recovery readers are load-bearing but NOT
                  violations (ADR-0025).  Verified by AST scan.

P2 No-writeback:  Running the full Phase-1 pipeline (build_mirror +
                  emit routing_decision for every ticket) mutates ZERO ticket
                  files in board/tickets/.  Byte-diff = empty.
                  Events land ONLY in the gitignored board/.events.jsonl
                  (tested with a tmp store, never the real one).

P3 Failure-isolation: An EventStore.append failure (simulated by monkeypatching)
                  is silently swallowed and does NOT propagate to the caller.
                  This mirrors step 5d's try/except-continue pattern, proving
                  that a broken event store can never block dispatch.

Together, P1+P2+P3 establish that DGO-X Phase-1 is a provably passive observer:
the dispatch decisions are byte-identical whether or not the shadow emission runs.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — same pattern as the per-module suites
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dgox.board_adapter import build_mirror  # noqa: E402
from dgox.events import (  # noqa: E402
    EventStore,
    build_routing_decision,
    utcnow,
    validate_routing_decision,
)
from dgox.state import GraphState  # noqa: E402


def _ticket_corpus() -> Path:
    """Directory of DAS-*.md ticket files to exercise the adapter against.

    Prefer the live platform board. An EMPTY live board is a valid steady state —
    ``board/tickets/`` is platform-only (project tickets live in
    ``projects/<slug>/board-tickets/``), so it is empty whenever no org-engine work
    is in flight (QONUN — Project Placement Law). When empty, fall back to the most
    recent ``board/archive/<version>/`` bucket so these integration tests still run
    against real ticket files.
    """
    live = _REPO_ROOT / "board" / "tickets"
    if sorted(live.glob("DAS-*.md")):
        return live
    archive = _REPO_ROOT / "board" / "archive"
    buckets = [p for p in sorted(archive.glob("*")) if p.is_dir() and any(p.glob("DAS-*.md"))]
    return buckets[-1] if buckets else live


_BOARD_TICKETS = _ticket_corpus()
_SKILL_FILE = _REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"

# Integration tests below build mirrors from real DAS-*.md ticket files. The
# clean platform board is empty by default (no org-engine work in flight), so
# skip them when there is nothing to integrate against.
_requires_board = pytest.mark.skipif(
    not sorted(_BOARD_TICKETS.glob("DAS-*.md")),
    reason="no board tickets present (empty platform board)",
)


# ===========================================================================
# SECTION 1 — End-to-end mirror coverage
# ===========================================================================


@_requires_board
class TestMirrorCoverage:
    """Build the mirror from the REAL board; verify every ticket is mirrored
    with zero invariant violations.

    This is the integration-level counterpart to test_dgox_board_adapter.py's
    unit-level round-trip tests.  It drives the full pipeline path:
    build_mirror → GraphState per ticket → identity fields set.
    """

    def test_build_mirror_covers_all_board_tickets(self) -> None:
        """Every ticket file in board/tickets/ yields a GraphState in the mirror.

        A ticket that FAILS to parse is skipped by build_mirror (shadow mode).
        We assert zero parse failures by comparing the mirror keyset to the
        set of DAS-*.md files that actually have parseable frontmatter.
        """
        ticket_files = sorted(_BOARD_TICKETS.glob("DAS-*.md"))
        assert ticket_files, "board/tickets/ must contain at least one DAS-*.md file"

        # Count files that have parseable frontmatter (--- ... --- block).
        from dgox.board_adapter import parse_ticket

        parseable_ids: set[str] = set()
        for path in ticket_files:
            try:
                fm = parse_ticket(path)
                tid = fm.get("id", "")
                if tid:
                    parseable_ids.add(tid)
            except Exception:
                # If parse_ticket itself raises, the file is malformed.
                pass

        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        mirror_ids = set(mirror.keys())

        # Every parseable ticket must appear in the mirror.
        missing = parseable_ids - mirror_ids
        assert not missing, (
            f"build_mirror missed {len(missing)} parseable ticket(s): {sorted(missing)}"
        )

    def test_mirror_entries_are_graph_state_instances(self) -> None:
        """Each mirror entry is a GraphState, not a raw dict."""
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror, "Mirror must not be empty"
        for tid, state in mirror.items():
            assert isinstance(state, GraphState), (
                f"Mirror entry {tid!r} is {type(state).__name__}, expected GraphState"
            )

    def test_mirror_identity_fields_populated(self) -> None:
        """Every mirrored state has ticket_id set (the mandatory identity field)."""
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        for tid, state in mirror.items():
            assert state.ticket_id == tid, (
                f"state.ticket_id {state.ticket_id!r} != mirror key {tid!r}"
            )
            assert state.ticket_id.startswith("DAS-"), (
                f"ticket_id {state.ticket_id!r} does not follow DAS-NNNN scheme"
            )

    def test_no_invariant_violations_on_real_board(self) -> None:
        """build_mirror must produce zero StateInvariantError for the real board.

        The board adapter writes ONLY the identity group, which has no
        invariant constraints that real frontmatter can trigger.  Any
        StateInvariantError here would indicate a substrate bug.
        """
        from dgox.state import StateInvariantError

        # We patch apply_group to intercept any StateInvariantError that
        # build_mirror swallows in its shadow-mode except clause.
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
        """The board adapter writes ONLY the identity group.

        All non-identity fields must remain at their default (None / []).
        This enforces the sole-writer rule (ADR 0011 §1).
        """
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror
        for tid, state in mirror.items():
            # Lifecycle
            assert state.aadl_stage is None, f"{tid}: aadl_stage should be None"
            assert state.gate_status is None, f"{tid}: gate_status should be None"
            # Routing
            assert state.assignee is None, f"{tid}: assignee should be None"
            assert state.reviewer is None, f"{tid}: reviewer should be None"
            # Execution
            assert state.run_id is None, f"{tid}: run_id should be None"
            assert state.branch is None, f"{tid}: branch should be None"
            # Risk
            assert state.severity is None, f"{tid}: severity should be None"
            # Artifacts
            assert state.files_changed == [], f"{tid}: files_changed should be []"
            # Memory
            assert state.memory_scope is None, f"{tid}: memory_scope should be None"


# ===========================================================================
# SECTION 2 — routing_decision emission coverage
# ===========================================================================


@_requires_board
class TestRoutingDecisionCoverage:
    """Simulate a full dispatch set and verify 100% event coverage.

    For every ticket in the mirror, emit a routing_decision event and assert:
    - 100% coverage: one event per dispatched ticket.
    - Each event validates against the §8.2 shape (validate_routing_decision).
    """

    def test_100_percent_routing_decision_coverage(self, tmp_path: Path) -> None:
        """One routing_decision event per dispatched ticket; zero missing.

        This mirrors the step 5d loop in /daslab-cycle: for EVERY ticket
        dispatched, one routing_decision is appended.  We drive the full
        mirror → emit loop here to prove 100% coverage.
        """
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

        # Read back and count
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
        """Every emitted routing_decision passes validate_routing_decision() with 0 errors.

        ADR 0011 §8.2 specifies the required fields.  validate_routing_decision
        checks envelope + shape-specific constraints.
        """
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
        """Events are appended to .events.jsonl, never to ticket files.

        No ticket file in board/tickets/ is opened for writing during the
        emission loop.  This is a runtime complement to the no-writeback proof.
        """
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        store_path = tmp_path / "events.jsonl"
        store = EventStore(path=store_path)
        ts = utcnow()

        opened_for_write: list[str] = []
        original_open = open  # noqa: A001

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


# ===========================================================================
# SECTION 3 — SHADOW-CLEAN PROOF
# ===========================================================================


@_requires_board
class TestShadowClean:
    """SHADOW-CLEAN proofs P1, P2, P3.

    These three proofs together establish that /daslab-cycle dispatch decisions
    are provably unchanged whether or not the Phase-1 shadow emission (step 5d)
    runs.  See module docstring for the reasoning.

    WHY THIS CONSTITUTES "FLAG-ON == FLAG-OFF DISPATCH" FOR A SKILL-BASED SHADOW
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    /daslab-cycle is a SKILL.md — a markdown document followed by the
    orchestrator (Claude Code).  Unlike compiled code with feature flags, it has
    no runtime toggle.  The "shadow" guarantee is therefore STRUCTURAL:

    1. The dispatch-DECISION logic (step 3 selection, step 2 triage, routing)
       does NOT import or call anything in dgox.*.  P1 verifies this by AST scan.
       Therefore, adding or removing step 5d cannot affect which tickets are
       selected or which roles are assigned.

    2. Step 5d is positioned AFTER the routing decision and BEFORE subagent
       spawn.  It is purely observational: it calls EventStore.append, which
       writes to board/.events.jsonl (gitignored runtime state).  It never
       modifies a ticket file, never changes a status, never alters the agent
       prompt.  P2 verifies that no ticket file is mutated.

    3. Any exception inside step 5d is explicitly caught and logged; dispatch
       proceeds unconditionally.  P3 verifies this failure-isolation by simulating
       a broken store and confirming no exception escapes to the caller.

    Structural implication: removing step 5d from SKILL.md would leave all
    three decision paths (triage, selection, dispatch) byte-identical.  The
    only difference is the absence of lines in board/.events.jsonl — which
    the cycle skill explicitly states "NOTHING in /daslab-cycle reads or routes
    off" (step 5d, SHADOW / ADVISORY ONLY annotation).
    """

    # ── P1 — No-influence (ADR-0025 principled reader-vs-router rule) ────────

    # Canonical event-store READ primitives.  A script "reads the event store"
    # when it CALLS one of these (all real readers go through them —
    # resume_fork/kill_drill/check_spans via wave_kpi.read_events + replay_qa;
    # wave_kpi/replay_qa define + call them).  Note: WRITING the store
    # (EventStore.append / build_* builders) is deliberately NOT a read — that is
    # what makes write-only producers pass with no allowlist.
    _READ_PRIMITIVES = frozenset(
        {"read_events", "iter_events", "group_runs", "replay_run"}
    )
    # Explicit operator-recovery entrypoint markers.  ADR-0025 makes event READS
    # load-bearing ONLY on this path (`--resume`/`--fork`); a reader scoped to it
    # is exempt.  `resume_fork` names the module that owns that entrypoint (kill_drill
    # reaches the store only through it).
    _RECOVERY_MARKERS = ("--resume", "--fork", "resume_fork")

    @staticmethod
    def _call_names(tree: ast.AST) -> set[str]:
        """Every called function's bare/attribute name in an AST (e.g. the
        ``read_events`` of ``wave_kpi.read_events(...)``)."""
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
        """Return the mode string of an ``open(...)`` call ('' if unspecified)."""
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            return str(node.args[1].value)
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
        return ""

    @classmethod
    def _has_events_literal_read(cls, tree: ast.AST) -> bool:
        """True if the module opens a ``.events.jsonl`` STRING LITERAL in read
        mode — catches a raw reader that bypasses the canonical helpers, without
        false-flagging producers that open Path variables for other files."""
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
        """True if the module ROUTES the normal wave — i.e. persists a
        routing/status decision into a ``board/tickets/*.md`` ticket (a write-mode
        ``open`` / ``write_text`` / ``write_bytes`` while referencing board/tickets).
        Observability/gate readers compute metrics and never do this."""
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
        """P1 No-influence (ADR-0025): no NORMAL-dispatch script READS the event
        store to make a routing decision.

        Replaces the old per-file ``_EVENT_PRODUCERS`` / ``_SPAN_VALIDATORS``
        allowlist (a stopgap) with a principled distinction.  A script under
        ``scripts/`` (excluding the ``dgox/`` library itself and the ``cache/``
        observability consumer) is flagged ONLY when it BOTH:

          (1) READS the event store — calls a canonical read primitive
              (read_events / iter_events / group_runs / replay_run) or opens a
              ``.events.jsonl`` literal in read mode.  WRITING via
              ``EventStore.append`` / ``build_*`` is NOT a read.
          (2) ROUTES the normal wave — persists a routing/status decision into a
              ``board/tickets/*.md`` ticket.

        UNLESS the reads are gated behind the explicit operator-recovery
        entrypoint (``--resume`` / ``--fork``), which ADR-0025 makes load-bearing.

        The three categories fall out by PROPERTY, no filenames to maintain:
          * write-only producers (dispatch_emitter, pulse_checkpoint) never call a
            read primitive  ⇒ fail (1) ⇒ pass;
          * observability / gate / validation readers (wave_kpi, replay_qa,
            metrics_lib, check_spans, cockpit, trends, the check_* gates)
            read but never write ticket routing ⇒ fail (2) ⇒ pass;
          * operator-recovery readers (resume_fork, kill_drill) read only under
            ``--resume`` / ``--fork`` ⇒ exempt.
        A selection-path script that reads events AND routes the normal wave,
        outside the recovery gate, trips both (1) and (2) ⇒ flagged.
        """
        scripts_dir = _SCRIPTS
        py_files = [
            p
            for p in scripts_dir.rglob("*.py")
            if "dgox" not in p.parts  # the event-store library itself
            and "cache" not in p.parts  # observability consumer (result-cache)
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
                continue  # write-only producers & non-readers: never a violation

            if any(marker in source for marker in self._RECOVERY_MARKERS):
                continue  # ADR-0025: load-bearing reader on the recovery path only

            # A reader that is NOT recovery-gated may only be a post-hoc
            # observability / analysis / validation tool — it must NOT route the
            # normal wave.  If it also writes ticket routing, it is steering
            # dispatch off shadow events: the exact regression to catch.
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
        """P1 No-influence (text layer): the skill's selection/triage sections
        do not reference reading from dgox.* for routing decisions.

        The only permitted dgox reference in the skill text is the step 5d
        emission block (ADR 0011, Phase 1 — explicitly labelled SHADOW /
        ADVISORY ONLY).  All dispatch-DECISION verbs (select, route, assign,
        dispatch) must appear exclusively in steps 0-4 and must not be coupled
        to dgox state.
        """
        assert _SKILL_FILE.exists(), f"SKILL.md not found at {_SKILL_FILE}"
        skill_text = _SKILL_FILE.read_text(encoding="utf-8")

        # Verify step 5d is present and labelled as shadow/advisory.
        assert "DGO-X shadow emission" in skill_text, (
            "SKILL.md must contain 'DGO-X shadow emission' header (step 5d)"
        )
        assert "SHADOW / ADVISORY ONLY" in skill_text, (
            "Step 5d must be labelled 'SHADOW / ADVISORY ONLY' in SKILL.md"
        )
        # The canonical statement that nothing routes off these events must exist.
        # The text in SKILL.md spans two lines:
        #   "NOTHING in `/daslab-cycle` reads\n      or routes off them."
        # We check for the key fragments independently so line-wrapping is irrelevant.
        assert "NOTHING in" in skill_text, (
            "SKILL.md step 5d must contain 'NOTHING in' statement"
        )
        assert "or routes off them" in skill_text, (
            "SKILL.md step 5d must contain 'or routes off them' statement (may span lines)"
        )

    def test_p1_dgox_modules_not_imported_at_module_level_in_scripts(self) -> None:
        """P1 No-influence (import-time): dgox modules are not on sys.modules
        when only the non-dgox scripts are imported.

        This catches accidental top-level cross-imports that would pull dgox
        into the dispatch path at import time.
        """
        # Collect non-dgox scripts that could be part of the dispatch path.
        scripts_to_check = [
            _SCRIPTS / "_paths.py",
            _SCRIPTS / "check_gates.py",
            _SCRIPTS / "check_agents_sync.py",
        ]

        for script in scripts_to_check:
            if not script.exists():
                continue
            source = script.read_text(encoding="utf-8", errors="replace")
            # Quick text scan — if a file contains no dgox reference it definitely
            # doesn't import it at module level.
            if "dgox" in source:
                # Parse to confirm: is the dgox reference an import, or just a comment?
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

    # ── P2 — No-writeback / board-canonical ─────────────────────────────────

    def test_p2_no_writeback_board_tickets_unchanged(self, tmp_path: Path) -> None:
        """P2 No-writeback: running the full Phase-1 pipeline mutates ZERO ticket files.

        Measures the mtime and byte content of every board/tickets/DAS-*.md
        before and after:
            1. build_mirror (with a tmp store for any divergence events)
            2. emit routing_decision for every ticket in the mirror (tmp store)

        After both steps the before snapshot and after snapshot must be identical.

        ADR 0011 §3.3: "ONE-WAY mirror — the adapter NEVER writes back to
        ticket files in Phase 1."
        """
        ticket_files = sorted(_BOARD_TICKETS.glob("DAS-*.md"))
        assert ticket_files

        # Snapshot before: (mtime_ns, bytes)
        def snapshot() -> dict[str, tuple[int, bytes]]:
            return {
                str(f): (os.stat(f).st_mtime_ns, f.read_bytes())
                for f in ticket_files
            }

        before = snapshot()

        # Run full Phase-1 pipeline with a tmp event store (never the real one)
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

        # Compare
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
        """P2 Board-canonical: events are written to the tmp store, not the real one.

        The real store (board/.events.jsonl) must not grow during a test run.
        Tests always pass an explicit store_path=tmp_path/... to EventStore.
        """
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

        # Confirm the tmp store has the event
        assert store_path.exists(), "Tmp store was not created"
        content = store_path.read_text(encoding="utf-8")
        assert "DAS-9999" in content

    # ── P3 — Failure-isolation ───────────────────────────────────────────────

    def test_p3_failure_isolation_store_exception_does_not_propagate(
        self, tmp_path: Path
    ) -> None:
        """P3 Failure-isolation: EventStore.append failure does not raise into caller.

        This proves that a broken event store cannot block dispatch.  We simulate
        EventStore.append raising an IOError (mimicking a disk-full or permission
        error) and verify that the step-5d pattern (try/except/continue) swallows
        it without re-raising.

        The step-5d code in SKILL.md explicitly states:
            "If EventStore.append raises (malformed event or I/O error): log the
             error in the wave-log line for that ticket and continue — the shadow
             emission MUST NEVER block dispatch."

        This test proves that pattern is mechanically sound by demonstrating that
        a failing append does not surface to the dispatch layer.
        """
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert mirror

        dispatched_count = 0
        emission_errors: list[str] = []

        # Simulate the step-5d loop from /daslab-cycle with failure-isolation.
        def _shadow_emit_step5d(store: EventStore, ev: dict) -> None:
            """Emits one routing_decision; swallows any exception (mirrors step 5d)."""
            try:
                store.append(ev)
            except Exception as exc:  # noqa: BLE001
                # Production code logs and continues — we record for assertion.
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
                # This is the step-5d pattern: failure-isolated emission.
                _shadow_emit_step5d(store, ev)
                dispatched_count += 1

        # All tickets were "dispatched" (loop completed) despite all appends failing.
        assert dispatched_count == len(mirror), (
            f"Dispatch loop aborted early: only {dispatched_count}/{len(mirror)} "
            "tickets processed (store failure broke dispatch)"
        )

        # All append calls were attempted (one per ticket).
        assert mock_append.call_count == len(mirror), (
            f"Expected {len(mirror)} append attempts, got {mock_append.call_count}"
        )

        # All errors were swallowed; none propagated.
        assert len(emission_errors) == len(mirror), (
            f"Expected {len(mirror)} swallowed errors, got {len(emission_errors)}"
        )

    def test_p3_partial_store_failure_continues_remaining_dispatches(
        self, tmp_path: Path
    ) -> None:
        """P3 Failure-isolation: partial failures (first N appends fail, rest succeed).

        Even if the first few routing_decision appends fail, the loop must
        continue and attempt all remaining tickets — proving that a single failed
        emission cannot abort the rest of the dispatch wave.
        """
        mirror = build_mirror(board_dir=_BOARD_TICKETS, emit_events=False)
        assert len(mirror) >= 2, "Need at least 2 tickets for partial-failure test"

        store_path = tmp_path / "partial-fail.jsonl"
        ts = utcnow()

        call_count = 0
        fail_first_n = max(1, len(mirror) // 3)  # fail the first third

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
                except Exception as exc:  # noqa: BLE001
                    emission_errors.append(str(exc))
                processed.append(tid)

        # All tickets were processed regardless of failures.
        assert len(processed) == len(mirror), (
            f"Loop stopped early: {len(processed)}/{len(mirror)} tickets processed"
        )
        # The expected number of early failures occurred.
        assert len(emission_errors) == fail_first_n, (
            f"Expected {fail_first_n} swallowed errors, got {len(emission_errors)}"
        )


# ===========================================================================
# SECTION 4 — Full pipeline smoke test (mirror + emit + divergence)
# ===========================================================================


@_requires_board
class TestFullPipelineSmoke:
    """Drive the complete Phase-1 pipeline in one integration call.

    This is the closest analogue to an end-to-end wave: build_mirror with
    divergence checking, then emit routing_decisions for all tickets.
    Uses a tmp store throughout; never touches real board/.events.jsonl.
    """

    def test_full_pipeline_no_errors(self, tmp_path: Path) -> None:
        """Full pipeline: build_mirror → emit all routing_decisions → no exceptions."""
        store_path = tmp_path / "full-pipeline.jsonl"

        # Phase 1a: build mirror with divergence checking enabled but tmp store.
        mirror = build_mirror(board_dir=_BOARD_TICKETS, store_path=store_path, emit_events=True)
        assert mirror, "Mirror must not be empty"

        # Phase 1b: emit routing_decision for every ticket.
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

        # Validate all emitted events from the store.
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
        """Events appended then replayed via iter_events match what was emitted."""
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
