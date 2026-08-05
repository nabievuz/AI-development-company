
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import wave_runner as wr
from dgox import langgraph_loop as lg
from dgox.state import GraphState, apply_group

from tools import sandbox as sbx

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_INTERRUPT_SCHEMA = _REPO_ROOT / "board" / "interrupts" / "schema.json"
_WAVE_TS = "2026-07-24T13:00:00Z"


def _closed_gate_state(ticket_id: str) -> GraphState:
    state = GraphState(ticket_id=ticket_id)
    apply_group(state, "lifecycle", {"aadl_stage": "development", "predecessor_gate": "closed"})
    return state


def _write_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic WS-C Stage-4 fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\n## Description\nSynthetic ticket.\n",
        encoding="utf-8",
    )


def _plan(run_id: str, wave: int, ticket_id: str) -> wr.WavePlan:
    return wr.WavePlan(
        run_id=run_id,
        wave=wave,
        goal="mustaqil-ws-c-loop",
        engine_version="1.0.0",
        tickets=[wr.TicketPlan(ticket_id, role="backend-eng-1", model="opus")],
    )


def _results(ticket_id: str) -> wr.WaveResults:
    return wr.WaveResults(
        tickets=[
            wr.TicketResult(
                ticket_id=ticket_id,
                outcome="success",
                merged_pr=True,
                ci_status="green",
                t7_pass=True,
                t7_score=0.95,
                start=_WAVE_TS,
                end="2026-07-24T13:10:00Z",
                final_status="done",
                output="Implemented; tests green.",
            )
        ],
    )


def _run_wave_kwargs(tmp: Path, ticket_id: str) -> dict:
    board = tmp / "board" / "tickets"
    _write_ticket(board, ticket_id, "backend-eng-1")
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


def test_sc001a_resume_preserves_completed_work_and_reaches_same_terminal_state_as_uninterrupted(
    tmp_path: Path,
) -> None:
    run_id = "01JWSC0000000000000000SC1A"
    ckpt = lg.RunIdCheckpointer()
    w1_kwargs = _run_wave_kwargs(tmp_path, "DAS-9201")
    ledger_path = w1_kwargs["ledger_path"]
    attest_dir = w1_kwargs["attest_dir"]


    plan1, results1 = _plan(run_id, 1, "DAS-9201"), _results("DAS-9201")
    att1 = lg.commit_wave(plan1, wr.replay_executor(results1.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **w1_kwargs)
    assert att1 is not None
    after_w1_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(after_w1_lines) == 1


    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []


    att1_resumed = lg.commit_wave(plan1, wr.replay_executor(results1.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **w1_kwargs)
    assert att1_resumed is att1
    assert ledger_path.read_text(encoding="utf-8").strip().splitlines() == after_w1_lines


    plan2, results2 = _plan(run_id, 2, "DAS-9202"), _results("DAS-9202")
    w2_kwargs = dict(w1_kwargs)
    _write_ticket(w1_kwargs["tickets_dir"], "DAS-9202", "backend-eng-1")
    att2 = lg.commit_wave(plan2, wr.replay_executor(results2.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **w2_kwargs)
    assert att2 is not None
    resumed_final_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(resumed_final_lines) == 2


    control_dir = tmp_path / "control"
    control_ckpt = lg.RunIdCheckpointer()
    c1_kwargs = _run_wave_kwargs(control_dir, "DAS-9201")
    c2_kwargs = dict(c1_kwargs)
    _write_ticket(c1_kwargs["tickets_dir"], "DAS-9202", "backend-eng-1")
    lg.commit_wave(plan1, wr.replay_executor(results1.tickets), created_at=_WAVE_TS, checkpointer=control_ckpt, **c1_kwargs)
    lg.commit_wave(plan2, wr.replay_executor(results2.tickets), created_at=_WAVE_TS, checkpointer=control_ckpt, **c2_kwargs)
    control_ledger = c1_kwargs["ledger_path"]
    control_lines = control_ledger.read_text(encoding="utf-8").strip().splitlines()


    assert len(control_lines) == len(resumed_final_lines) == 2


def test_sc001b_guard_before_act_skips_reapply_of_a_generic_committed_side_effect() -> None:
    ckpt = lg.RunIdCheckpointer()
    run_id = "01JWSC0000000000000000SC1B"

    applied = {"merge": 0, "event": 0}

    def _guarded_apply(effect_key: str, kind: str) -> None:
        if ckpt.already_committed(run_id, effect_key):
            return
        applied[kind] += 1
        ckpt.mark_committed(run_id, effect_key)


    _guarded_apply("merge:PR-9301", "merge")
    _guarded_apply("event:trace-9301", "event")
    assert applied == {"merge": 1, "event": 1}


    _guarded_apply("merge:PR-9301", "merge")
    _guarded_apply("event:trace-9301", "event")
    assert applied == {"merge": 1, "event": 1}


    _guarded_apply("merge:PR-9302", "merge")
    assert applied == {"merge": 2, "event": 1}


def test_sc002a_open_gate_and_naa_category_park_as_a_schema_valid_interrupt_card() -> None:
    state = GraphState(ticket_id="DAS-9210")
    apply_group(state, "lifecycle", {"aadl_stage": "deployment", "predecessor_gate": "open"})
    decision = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)

    card = lg.make_interrupt_card(state, decision, created_by="supervisor")

    schema = json.loads(_INTERRUPT_SCHEMA.read_text(encoding="utf-8"))
    required = schema["required"]
    assert set(required) <= set(card)
    assert set(card) <= set(schema["properties"])
    assert isinstance(card["question"], str) and card["question"]
    assert isinstance(card["options"], list) and card["options"]
    assert all(isinstance(o, str) and o for o in card["options"])
    assert card["ticket"] == "DAS-9210"
    import re

    assert re.match(schema["properties"]["ticket"]["pattern"], card["ticket"])
    assert isinstance(card["payload"], dict)
    assert card["created_by"] == "supervisor"


    apply_group(state, "lifecycle", {"predecessor_gate": "closed"})
    decision_closed_gate = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision_closed_gate.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision_closed_gate)


def test_sc002b_divergence_in_a_non_routing_channel_also_resolves_to_the_board() -> None:
    board_state = _closed_gate_state("DAS-9211")
    apply_group(board_state, "risk", {"severity": "low"})

    projected = lg.project(board_state)
    projected.channels["risk"]["severity"] = "critical"

    cp = lg.Checkpoint(run_id="R2", node="supervisor", channels=projected.channels)
    checkpointer = lg.RunIdCheckpointer()
    checkpointer.save(cp)

    result = lg.reconcile(projected, board_state)
    assert result.board_state.severity.value == "low"
    assert ("risk", "severity") in result.diverged
    assert result.event is not None
    assert "risk.severity" in result.event["diverged"]
    assert "NOT used" in result.event["reason"] or "NOT" in result.event["reason"]


    assert checkpointer.load("R2").channels["risk"]["severity"] == "critical"
    assert result.board_state.severity.value != checkpointer.load("R2").channels["risk"]["severity"]


def test_sc003_worker_node_body_has_no_routing_write_reference_in_graph_topology() -> None:
    import ast

    src = (_SCRIPTS / "dgox" / "langgraph_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    build_graph_fn = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_graph"
    )
    worker_fn = next(
        n
        for n in ast.walk(build_graph_fn)
        if isinstance(n, ast.FunctionDef) and n.name == "_worker"
    )
    worker_src = ast.get_source_segment(src, worker_fn) or ""
    assert "routing" not in worker_src
    assert "apply_channel" not in worker_src
    assert "apply_group" not in worker_src


    def _name_or_none(node: ast.AST) -> str | None:
        return node.id if isinstance(node, ast.Name) else None

    add_edge_calls = [
        call
        for call in ast.walk(build_graph_fn)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_edge"
        and len(call.args) == 2
    ]
    assert add_edge_calls, "expected at least one graph.add_edge(...) call in build_graph"
    add_edge_pairs = [(_name_or_none(c.args[0]), _name_or_none(c.args[1])) for c in add_edge_calls]

    worker_out_edges = [dst for src_node, dst in add_edge_pairs if src_node == "WORKER"]
    assert worker_out_edges == ["END"]

    assert not any(src_node == "routing" for src_node, _ in add_edge_pairs)


def test_sc004a_flag_off_wave_is_byte_identical_to_a_pre_merge_wave(tmp_path: Path) -> None:
    off = _write_features(tmp_path, on=False)
    assert lg.drive_enabled(off) is False

    run_id = "01JWSC0000000000000000SC4A"
    plan, results = _plan(run_id, 1, "DAS-9220"), _results("DAS-9220")


    pre_merge_dir = tmp_path / "pre-merge"
    pre_kwargs = _run_wave_kwargs(pre_merge_dir, "DAS-9220")
    import wave_runner as _wr

    _wr.run_wave(plan, _wr.replay_executor(results.tickets), created_at=_WAVE_TS, **pre_kwargs)
    pre_ledger = pre_kwargs["ledger_path"].read_text(encoding="utf-8").strip()


    post_merge_dir = tmp_path / "post-merge"
    post_kwargs = _run_wave_kwargs(post_merge_dir, "DAS-9220")
    ckpt = lg.RunIdCheckpointer()
    lg.commit_wave(plan, _wr.replay_executor(results.tickets), created_at=_WAVE_TS, checkpointer=ckpt, **post_kwargs)
    post_ledger = post_kwargs["ledger_path"].read_text(encoding="utf-8").strip()

    assert post_ledger == pre_ledger


def test_sc004b_flag_on_runs_shadow_only_never_auto_drives(tmp_path: Path) -> None:
    on = _write_features(tmp_path, on=True)
    assert lg.drive_enabled(on) is True

    result = lg.run_loop(features_path=on)
    assert result.drove is False
    assert "shadow" in result.reason.lower()
    assert "board" in result.reason.lower() or "Q4" in result.reason


    result_forced = lg.run_loop(features_path=on, force_drive=True)
    assert result_forced.drove is False


def test_sc005_escape_suite_summary_all_four_walls_denied_fail_closed_no_side_effect(
    tmp_path: Path,
) -> None:
    backend = sbx.LocalStubSandbox()
    mount_root = tmp_path / "task-summary"
    mount_root.mkdir()
    scope = sbx.SandboxScope(
        task_id="task-summary",
        workdir_mounts=[sbx.Mount(host_path=str(mount_root))],
        resource_limits=sbx.ResourceLimits(wallclock_seconds=1.0, max_output_bytes=8),
    )
    handle = backend.open(task_id="task-summary", scope=scope)


    host_result = backend.exec(handle, ["read", "/etc/passwd"])
    assert host_result.ok is False


    sibling = tmp_path / "sibling-repo-area"
    sibling.mkdir()
    (sibling / "secret.md").write_text("other ticket")
    repo_result = backend.exec(handle, ["read", "../sibling-repo-area/secret.md"])
    assert repo_result.ok is False


    forged = sbx.SandboxHandle(task_id="task-summary", backend="local-stub", token="forged")
    other_task_result = backend.exec(forged, ["read", "notes.txt"])
    assert other_task_result.ok is False


    cred_result = backend.exec(handle, ["cred", "ungranted" + "-key"])
    assert cred_result.ok is False
    egress_result = backend.exec(handle, ["net", "https://exfil.example/"])
    assert egress_result.ok is False


    sleep_result = backend.exec(handle, ["sleep", "999"])
    assert sleep_result.ok is False
    write_result = backend.exec(handle, ["write", "big.txt", "way too much content"])
    assert write_result.ok is False


    assert list(mount_root.iterdir()) == []
    assert not (tmp_path / "escaped.txt").exists()
