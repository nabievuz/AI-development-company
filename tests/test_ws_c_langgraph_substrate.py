
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wave_runner as wr
from dgox import langgraph_loop as lg
from dgox.state import GraphState, Severity, StateInvariantError, apply_group

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_WAVE_TS = "2026-07-24T12:00:00Z"


def _closed_gate_state(ticket_id: str = "DAS-9100") -> GraphState:
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


def test_projection_mirrors_field_groups_one_channel_per_group() -> None:
    state = _closed_gate_state()
    projected = lg.project(state)
    assert set(projected.channels) == set(lg.CHANNELS)

    assert lg.CHANNEL_WRITER["routing"] == "supervisor"

    assert projected.field("aadl_stage") == state.aadl_stage
    assert projected.run_id == state.run_id


def test_apply_channel_guards_fire_on_invariant_violating_projected_write() -> None:
    state = GraphState(ticket_id="DAS-9102")
    apply_group(state, "lifecycle", {"aadl_stage": "planning", "predecessor_gate": "closed"})


    with pytest.raises(StateInvariantError) as exc:
        lg.apply_channel(
            state, "lifecycle", {"aadl_stage": "deployment"}, writer="gate_engine"
        )
    assert exc.value.violation["rule"] == "cannot_skip_aadl_stage"

    assert state.aadl_stage.value == "planning"


    apply_group(state, "risk", {"severity": "high"})
    with pytest.raises(StateInvariantError) as exc2:
        lg.apply_channel(state, "risk", {"severity": "low"}, writer="gate_engine_or_security")
    assert exc2.value.violation["rule"] == "severity_up_only"

    lg.apply_channel(
        state, "risk", {"severity": "low"}, writer="gate_engine_or_security",
        review_authorized=True,
    )
    assert state.severity == Severity.low


def test_worker_routing_field_write_rejected() -> None:
    state = _closed_gate_state()

    with pytest.raises(StateInvariantError) as exc:
        lg.apply_channel(
            state, "routing", {"assignee": "backend-eng-1"}, writer="worker_or_ci"
        )
    assert exc.value.violation["rule"] == "wrong_group_writer_node"
    assert state.assignee is None


    lg.apply_channel(
        state, "artifacts", {"files_changed": ["scripts/dgox/langgraph_loop.py"]},
        writer="worker_or_ci",
    )
    assert state.files_changed == ["scripts/dgox/langgraph_loop.py"]


    state.set_author("ceo")
    lg.apply_channel(
        state, "routing", {"assignee": "backend-eng-1", "reviewer": "cto"},
        writer="supervisor",
    )
    assert state.assignee == "backend-eng-1"


def test_board_wins_on_injected_divergence_checkpoint_never_tiebreaker() -> None:

    board_state = _closed_gate_state("DAS-9103")
    board_state.set_author("ceo")
    apply_group(board_state, "routing", {"assignee": "backend-eng-1", "reviewer": "cto"})


    projected = lg.project(board_state)
    projected.channels["routing"]["assignee"] = "backend-eng-2"


    cp = lg.Checkpoint(run_id="R1", node="supervisor", channels=projected.channels)
    ckpt = lg.RunIdCheckpointer()
    ckpt.save(cp)

    result = lg.reconcile(projected, board_state)

    assert result.board_state.assignee == "backend-eng-1"
    assert ("routing", "assignee") in result.diverged
    assert result.event is not None
    assert result.event["event_type"] == "state_violation"
    assert "routing.assignee" in result.event["diverged"]

    assert ckpt.load("R1").channels["routing"]["assignee"] == "backend-eng-2"
    assert result.board_state.assignee != ckpt.load("R1").channels["routing"]["assignee"]


def test_gate_open_makes_worker_unreachable() -> None:
    state = GraphState(ticket_id="DAS-9104")
    apply_group(state, "lifecycle", {"aadl_stage": "development", "predecessor_gate": "open"})

    decision = lg.route_from_supervisor(state)
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)


    apply_group(state, "lifecycle", {"predecessor_gate": "closed"})
    assert lg.worker_reachable(lg.route_from_supervisor(state))


def test_never_auto_approve_category_interrupts_for_founder() -> None:
    state = _closed_gate_state("DAS-9105")
    decision = lg.route_from_supervisor(state, categories={"security_sensitive"})
    assert decision.target == lg.INTERRUPT
    assert "security_sensitive" in decision.categories

    card = lg.make_interrupt_card(state, decision, created_by="supervisor")
    assert card["ticket"] == "DAS-9105"
    assert card["created_by"] == "supervisor"
    assert card["options"]
    assert card["payload"]["categories"] == ["security_sensitive"]


def test_gate5_open_deployment_stays_machine_blocked() -> None:
    state = GraphState(ticket_id="DAS-9106")
    apply_group(state, "lifecycle", {"aadl_stage": "deployment", "predecessor_gate": "open"})
    decision = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)


def test_unclassifiable_gate_fails_closed() -> None:
    state = _closed_gate_state("DAS-9107")
    decision = lg.route_from_supervisor(state, unclassified=True)
    assert decision.target == lg.INTERRUPT
    assert decision.fail_closed is True


def test_idempotent_resume_no_double_apply_and_ledger_reconciles(tmp_path: Path) -> None:
    ckpt = lg.RunIdCheckpointer()
    kwargs = _run_wave_kwargs(tmp_path)
    run_id = "01JWSC000000000000000000C1"
    plan, results = _plan(run_id), _results()
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    attest_dir = tmp_path / "attest"


    att1 = lg.commit_wave(plan, wr.replay_executor(results.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **kwargs)
    assert att1 is not None
    assert ckpt.already_committed(run_id, f"wave:{run_id}:1")
    first_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(first_lines) == 1
    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []


    att2 = lg.commit_wave(plan, wr.replay_executor(results.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **kwargs)
    assert att2 is att1
    resume_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert resume_lines == first_lines

    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []


def test_checkpoint_is_keyed_by_run_id_and_subordinate() -> None:
    ckpt = lg.RunIdCheckpointer()
    ckpt.mark_committed("RUN-A", "merge:PR-1")
    assert ckpt.already_committed("RUN-A", "merge:PR-1")
    assert not ckpt.already_committed("RUN-A", "merge:PR-2")
    assert not ckpt.already_committed("RUN-B", "merge:PR-1")

    ckpt.mark_committed("RUN-A", "merge:PR-1")
    assert ckpt.already_committed("RUN-A", "merge:PR-1")


def test_substrate_is_the_only_producer_by_source_property() -> None:
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

    assert "wave_runner" in imported


def test_flag_off_substrate_is_inert(tmp_path: Path) -> None:
    off = _write_features(tmp_path, on=False)
    assert lg.drive_enabled(off) is False
    result = lg.run_loop(features_path=off)
    assert result.drove is False


    with pytest.raises(lg.SubstrateInertError):
        lg.run_loop(features_path=off, force_drive=True)


    ckpt = lg.RunIdCheckpointer()
    kwargs = _run_wave_kwargs(tmp_path)
    att = lg.commit_wave(
        _plan("01JWSC00000000000000000OFF"), wr.replay_executor(_results().tickets),
        created_at=_WAVE_TS, checkpointer=ckpt, organism_emit=False, **kwargs,
    )
    assert att is None
    assert not (tmp_path / "attest").exists() or not any((tmp_path / "attest").iterdir())
    assert not (tmp_path / "board" / "wave-ledger.jsonl").exists()


def test_flag_on_after_activation_but_loop_stays_shadow() -> None:
    assert lg.drive_enabled() is True
    assert lg.run_loop().drove is False


def test_absent_langgraph_is_unavailable_not_broken() -> None:
    if lg.langgraph_available():
        pytest.skip("langgraph installed in this environment; absence path not exercisable")

    with pytest.raises(lg.SubstrateUnavailableError):
        lg.build_graph()


    state = _closed_gate_state("DAS-9108")
    projected = lg.project(state)
    assert set(projected.channels) == set(lg.CHANNELS)
    assert lg.worker_reachable(lg.route_from_supervisor(state))
    assert lg.reconcile(projected, state).diverged == []
