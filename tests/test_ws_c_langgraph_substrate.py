"""tests/test_ws_c_langgraph_substrate.py — WS-C LangGraph substrate adapter (DAS-1564).

Development-stage (GATE-3) tests for ``scripts/dgox/langgraph_loop.py``, the
LangGraph substrate adapter under DGO-X (ADR-0035 LG-1…LG-5), against the
ratified design ``docs/design/ws-c-langgraph-loop.md``.  These exercise the
adapter's OWN surface; the full negative-path SC-001…SC-005 suite is DAS-1567's
(a separate file), so the two Development/Testing tickets don't collide.

Coverage (LG/FR → test):

  * LG-1/FR-001  apply_group guards fire on an invariant-violating projected write.
  * LG-1/FR-002/C2  the board wins an injected divergence; the checkpoint is never
                    a tiebreaker.
  * LG-2/FR-003/C4  a gate-open ticket makes the worker node unreachable; a
                    never-auto-approve category → interrupt() halt-for-Founder.
  * LG-4/FR-005  checkpoint keyed by run_id, idempotent guard-before-act resume
                 (no double-apply), ledger reconciles, run_wave the sole producer.
  * LG-3/FR-004/C3  a worker node's routing-field write is rejected.
  * LG-5/FR-007  flag OFF ⇒ substrate inert.
  * LG-5  LangGraph absent ⇒ substrate UNAVAILABLE, not broken.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wave_runner as wr  # noqa: E402
from dgox import langgraph_loop as lg  # noqa: E402
from dgox.state import GraphState, Severity, StateInvariantError, apply_group  # noqa: E402

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_WAVE_TS = "2026-07-24T12:00:00Z"


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #


def _closed_gate_state(ticket_id: str = "DAS-9100") -> GraphState:
    """A state whose predecessor gate is closed → the worker edge is reachable."""
    state = GraphState(ticket_id=ticket_id)
    apply_group(state, "lifecycle", {"aadl_stage": "development", "predecessor_gate": "closed"})
    return state


def _write_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic WS-C substrate fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\n## Description\nSynthetic ticket.\n",
        encoding="utf-8",
    )


def _plan(run_id: str) -> wr.WavePlan:
    return wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="mustaqil-ws-c-loop",
        engine_version="1.0.0",
        tickets=[wr.TicketPlan("DAS-9101", role="backend-eng-1", model="opus")],
    )


def _results() -> wr.WaveResults:
    return wr.WaveResults(
        tickets=[
            wr.TicketResult(
                ticket_id="DAS-9101",
                outcome="success",
                merged_pr=True,
                ci_status="green",
                t7_pass=True,
                t7_score=0.95,
                start=_WAVE_TS,
                end="2026-07-24T12:10:00Z",
                final_status="done",
                output="Implemented; tests green.",
            )
        ],
    )


def _run_wave_kwargs(tmp: Path) -> dict:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9101", "backend-eng-1")
    return {
        "store_path": tmp / "events.jsonl",
        "runs_dir": tmp / "runs",
        "attest_dir": tmp / "attest",
        "ledger_path": tmp / "board" / "wave-ledger.jsonl",
        "evidence_dir": tmp / "evidence",
        "tickets_dir": board,
        "board_dir": board,
        "routing_path": _ROUTING,
        "guardrails_dir": _GUARDRAILS,
    }


def _write_features(tmp: Path, *, on: bool) -> Path:
    p = tmp / "features.yaml"
    p.write_text(f"ws_c_langgraph_loop: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# §1 — Projection + invariant guards at the projection boundary (LG-1/FR-001)
# --------------------------------------------------------------------------- #


def test_projection_mirrors_field_groups_one_channel_per_group() -> None:
    """project() materialises exactly one channel per FIELD_GROUPS group (§1.2)."""
    state = _closed_gate_state()
    projected = lg.project(state)
    assert set(projected.channels) == set(lg.CHANNELS)
    # Each channel inherits its group's sole writer from GROUP_WRITER (ADR-0011 §1).
    assert lg.CHANNEL_WRITER["routing"] == "supervisor"
    # A field reads back through its channel.
    assert projected.field("aadl_stage") == state.aadl_stage
    assert projected.run_id == state.run_id


def test_apply_channel_guards_fire_on_invariant_violating_projected_write() -> None:
    """LG-1/FR-001: the four StateInvariantError guards fire at the projection
    boundary. A projected lifecycle write that SKIPS an AADL stage is rejected."""
    state = GraphState(ticket_id="DAS-9102")
    apply_group(state, "lifecycle", {"aadl_stage": "planning", "predecessor_gate": "closed"})

    # planning -> deployment skips design/development/testing → cannot_skip_aadl_stage.
    with pytest.raises(StateInvariantError) as exc:
        lg.apply_channel(
            state, "lifecycle", {"aadl_stage": "deployment"}, writer="gate_engine"
        )
    assert exc.value.violation["rule"] == "cannot_skip_aadl_stage"
    # The rejected write did not mutate the channel.
    assert state.aadl_stage.value == "planning"

    # Severity-up-only guard also fires through the same boundary.
    apply_group(state, "risk", {"severity": "high"})
    with pytest.raises(StateInvariantError) as exc2:
        lg.apply_channel(state, "risk", {"severity": "low"}, writer="gate_engine_or_security")
    assert exc2.value.violation["rule"] == "severity_up_only"
    # An explicit review authorises the downgrade — still routed through the boundary.
    lg.apply_channel(
        state, "risk", {"severity": "low"}, writer="gate_engine_or_security",
        review_authorized=True,
    )
    assert state.severity == Severity.low


# --------------------------------------------------------------------------- #
# §3 — Worker write-scope: routing stays supervisor-only (LG-3/FR-004/C3)
# --------------------------------------------------------------------------- #


def test_worker_routing_field_write_rejected() -> None:
    """LG-3/FR-004/C3: a worker node writing the routing channel is rejected by
    node authority — even though `assignee` IS a routing field (so apply_group
    alone would not stop it). The write is unrepresentable, not merely guarded."""
    state = _closed_gate_state()

    with pytest.raises(StateInvariantError) as exc:
        lg.apply_channel(
            state, "routing", {"assignee": "backend-eng-1"}, writer="worker_or_ci"
        )
    assert exc.value.violation["rule"] == "wrong_group_writer_node"
    assert state.assignee is None  # no routing value mutated

    # The SAME worker MAY write its own artifacts channel — a scoping rule, not a freeze.
    lg.apply_channel(
        state, "artifacts", {"files_changed": ["scripts/dgox/langgraph_loop.py"]},
        writer="worker_or_ci",
    )
    assert state.files_changed == ["scripts/dgox/langgraph_loop.py"]

    # The supervisor CAN write routing (positive control) — with a non-self reviewer.
    state.set_author("ceo")
    lg.apply_channel(
        state, "routing", {"assignee": "backend-eng-1", "reviewer": "cto"},
        writer="supervisor",
    )
    assert state.assignee == "backend-eng-1"


# --------------------------------------------------------------------------- #
# §1.3 — Reconciliation: the board wins, checkpoint never a tiebreaker (LG-1/C2)
# --------------------------------------------------------------------------- #


def test_board_wins_on_injected_divergence_checkpoint_never_tiebreaker() -> None:
    """LG-1/FR-002/C2: inject a LangGraph channel value that disagrees with the
    board; reconcile() overwrites it from the board-derived value (board wins).
    The checkpoint is never consulted as a tiebreaker."""
    # Board-derived truth: assignee is backend-eng-1.
    board_state = _closed_gate_state("DAS-9103")
    board_state.set_author("ceo")
    apply_group(board_state, "routing", {"assignee": "backend-eng-1", "reviewer": "cto"})

    # A stale projection disagrees (a drifted LangGraph channel).
    projected = lg.project(board_state)
    projected.channels["routing"]["assignee"] = "backend-eng-2"  # divergence injected

    # A checkpoint that ALSO disagrees must not act as a tiebreaker.
    cp = lg.Checkpoint(run_id="R1", node="supervisor", channels=projected.channels)
    ckpt = lg.RunIdCheckpointer()
    ckpt.save(cp)

    result = lg.reconcile(projected, board_state)
    # Board value wins; the diverged field is reported for the audit trail.
    assert result.board_state.assignee == "backend-eng-1"
    assert ("routing", "assignee") in result.diverged
    assert result.event is not None
    assert result.event["event_type"] == "state_violation"
    assert "routing.assignee" in result.event["diverged"]
    # The checkpoint held the SAME wrong value and was NOT used to resolve the tie.
    assert ckpt.load("R1").channels["routing"]["assignee"] == "backend-eng-2"
    assert result.board_state.assignee != ckpt.load("R1").channels["routing"]["assignee"]


# --------------------------------------------------------------------------- #
# §2 — Gates as conditional edges / interrupts (LG-2/FR-003/C4)
# --------------------------------------------------------------------------- #


def test_gate_open_makes_worker_unreachable() -> None:
    """LG-2/C4: with the predecessor gate open, the conditional edge routes to
    interrupt and no worker node is reachable (§2.1)."""
    state = GraphState(ticket_id="DAS-9104")
    apply_group(state, "lifecycle", {"aadl_stage": "development", "predecessor_gate": "open"})

    decision = lg.route_from_supervisor(state)
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)

    # A closed gate re-opens the worker edge (positive control).
    apply_group(state, "lifecycle", {"predecessor_gate": "closed"})
    assert lg.worker_reachable(lg.route_from_supervisor(state))


def test_never_auto_approve_category_interrupts_for_founder() -> None:
    """LG-2/§2.2: a never-auto-approve category halts at interrupt() for the
    Founder — surfaced as a DAS-1446 interrupt card / status interrupted."""
    state = _closed_gate_state("DAS-9105")  # gate closed — yet still must halt
    decision = lg.route_from_supervisor(state, categories={"security_sensitive"})
    assert decision.target == lg.INTERRUPT
    assert "security_sensitive" in decision.categories

    card = lg.make_interrupt_card(state, decision, created_by="supervisor")
    assert card["ticket"] == "DAS-9105"
    assert card["created_by"] == "supervisor"
    assert card["options"]  # non-empty legal answers
    assert card["payload"]["categories"] == ["security_sensitive"]


def test_gate5_open_deployment_stays_machine_blocked() -> None:
    """LG-2/§2.2: a GATE-5-open deployment parks at the interrupt and stays
    machine-blocked — the executable form of 'shipping GATE-5-open is FORBIDDEN'."""
    state = GraphState(ticket_id="DAS-9106")
    apply_group(state, "lifecycle", {"aadl_stage": "deployment", "predecessor_gate": "open"})
    decision = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)


def test_unclassifiable_gate_fails_closed() -> None:
    """§2.2: an unclassifiable gate/category resolves to HALT, never PASS."""
    state = _closed_gate_state("DAS-9107")
    decision = lg.route_from_supervisor(state, unclassified=True)
    assert decision.target == lg.INTERRUPT
    assert decision.fail_closed is True


# --------------------------------------------------------------------------- #
# §4 — Checkpoint / resume: idempotent, single producer, ledger reconciles
# --------------------------------------------------------------------------- #


def test_idempotent_resume_no_double_apply_and_ledger_reconciles(tmp_path: Path) -> None:
    """LG-4/FR-005/SC-001b: commit a wave through the single run_wave producer,
    then RESUME (re-commit the same run_id). The guard-before-act check detects
    the prior commit and does NOT double-apply — no duplicate ledger entry — and
    the wave-ledger still reconciles (no orphan, no chain gap)."""
    ckpt = lg.RunIdCheckpointer()
    kwargs = _run_wave_kwargs(tmp_path)
    run_id = "01JWSC000000000000000000C1"
    plan, results = _plan(run_id), _results()
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    attest_dir = tmp_path / "attest"

    # First commit — run_wave produces the attestation + one ledger entry.
    att1 = lg.commit_wave(plan, results, created_at=_WAVE_TS, checkpointer=ckpt, **kwargs)
    assert att1 is not None
    assert ckpt.already_committed(run_id, f"wave:{run_id}:1")
    first_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(first_lines) == 1
    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []

    # RESUME: re-commit the identical wave. The guard skips re-production and
    # returns the prior receipt; the ledger is UNCHANGED (no double-apply).
    att2 = lg.commit_wave(plan, results, created_at=_WAVE_TS, checkpointer=ckpt, **kwargs)
    assert att2 is att1  # prior attestation stands
    resume_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert resume_lines == first_lines  # byte-identical: no duplicate entry
    # The committed dispatch record still reconciles through the SSOT primitive.
    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []


def test_checkpoint_is_keyed_by_run_id_and_subordinate() -> None:
    """LG-4/§4.1: the checkpoint is keyed by run_id (ADR-0023 identity) and is a
    resumption index — a committed side effect is recorded once per run_id."""
    ckpt = lg.RunIdCheckpointer()
    ckpt.mark_committed("RUN-A", "merge:PR-1")
    assert ckpt.already_committed("RUN-A", "merge:PR-1")
    assert not ckpt.already_committed("RUN-A", "merge:PR-2")
    assert not ckpt.already_committed("RUN-B", "merge:PR-1")  # scoped by run_id
    # mark_committed is idempotent — re-marking does not duplicate.
    ckpt.mark_committed("RUN-A", "merge:PR-1")
    assert ckpt.already_committed("RUN-A", "merge:PR-1")


def test_substrate_is_the_only_producer_by_source_property() -> None:
    """LG-4/§4.2: the adapter never calls a second producer directly — it writes
    the event/attestation/ledger surface ONLY through wave_runner.run_wave. Proven
    by source property (parity with the WS-B runner), no allowlist entry."""
    src = (_SCRIPTS / "dgox" / "langgraph_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {"dispatch_emitter", "pulse_checkpoint", "check_ledger", "task_ledger", "snapshot_evidence"}
    assert not (imported & forbidden), (
        f"substrate must not import a second producer directly: {imported & forbidden}"
    )
    # It DOES route through the single seam.
    assert "wave_runner" in imported


# --------------------------------------------------------------------------- #
# §6 — Flag OFF ⇒ inert; LangGraph absent ⇒ unavailable, not broken (LG-5)
# --------------------------------------------------------------------------- #


def test_flag_off_substrate_is_inert(tmp_path: Path) -> None:
    """LG-5/FR-007/SC-004a: with ws_c_langgraph_loop OFF the substrate drives
    nothing — no wave, no attestation attributable to the substrate."""
    off = _write_features(tmp_path, on=False)
    assert lg.drive_enabled(off) is False
    result = lg.run_loop(features_path=off)
    assert result.drove is False

    # Forcing a drive against an OFF flag fails-closed.
    with pytest.raises(lg.SubstrateInertError):
        lg.run_loop(features_path=off, force_drive=True)

    # commit_wave with organism_emit False (the flag-off analogue) is a byte-clean
    # no-op: run_wave returns None and writes nothing.
    ckpt = lg.RunIdCheckpointer()
    kwargs = _run_wave_kwargs(tmp_path)
    att = lg.commit_wave(
        _plan("01JWSC00000000000000000OFF"), _results(),
        created_at=_WAVE_TS, checkpointer=ckpt, organism_emit=False, **kwargs,
    )
    assert att is None
    assert not (tmp_path / "attest").exists() or not any((tmp_path / "attest").iterdir())
    assert not (tmp_path / "board" / "wave-ledger.jsonl").exists()


def test_flag_default_is_off() -> None:
    """The live config default is OFF (ADR-0019 / ADR-0035 LG-5)."""
    assert lg.drive_enabled() is False


def test_absent_langgraph_is_unavailable_not_broken() -> None:
    """LG-5: LangGraph is an opt-in extra. Absent ⇒ the substrate is UNAVAILABLE
    (build_graph raises a clean SubstrateUnavailableError) — NOT broken: every
    governance function keeps working without the runtime."""
    if lg.langgraph_available():  # pragma: no cover — env-dependent
        pytest.skip("langgraph installed in this environment; absence path not exercisable")

    with pytest.raises(lg.SubstrateUnavailableError):
        lg.build_graph()

    # Not broken: projection, reconciliation, and routing all still work.
    state = _closed_gate_state("DAS-9108")
    projected = lg.project(state)
    assert set(projected.channels) == set(lg.CHANNELS)
    assert lg.worker_reachable(lg.route_from_supervisor(state))
    assert lg.reconcile(projected, state).diverged == []
