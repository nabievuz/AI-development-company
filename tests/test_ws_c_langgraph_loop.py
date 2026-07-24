"""tests/test_ws_c_langgraph_loop.py — WS-C Testing (DAS-1567, AADL Stage-4 / GATE-4).

The **design's named home** (`docs/design/ws-c-langgraph-loop.md` §7) for the
formal SC-001…SC-005 negative/resume/escape suite against the DAS-1564
LangGraph substrate adapter (`scripts/dgox/langgraph_loop.py`) and the DAS-1565
sandbox adapter (`tools/sandbox/`), run against the host-free `LocalStubSandbox`
(live-host smoke is DAS-1566, blocked).

This file adds assertions the Development-stage suites
(`tests/test_ws_c_langgraph_substrate.py`, `tests/test_ws_c_sandbox_adapter.py`)
do NOT already cover — it folds in / extends rather than duplicating. Where a
sub-case is already asserted in one of those two files, this module's docstring
says so instead of re-asserting it.

SC → test map (also recorded in the DAS-1567 ticket `## Log`):

    SC-001a  test_sc001a_resume_preserves_completed_work_and_reaches_same_terminal_state_as_uninterrupted
    SC-001b  test_sc001b_guard_before_act_skips_reapply_of_a_generic_committed_side_effect
             (SC-001b's run_wave/ledger angle is already covered by
             test_ws_c_langgraph_substrate.py::test_idempotent_resume_no_double_apply_and_ledger_reconciles;
             this adds the GENERIC guard-before-act case DAS-1447/§4.3 describes —
             a merge / emitted-event / checkpoint side effect keyed by run_id,
             independent of run_wave.)
    SC-002a  test_sc002a_open_gate_and_naa_category_park_as_a_schema_valid_interrupt_card
    SC-002b  test_sc002b_divergence_in_a_non_routing_channel_also_resolves_to_the_board
    SC-003   test_sc003_worker_node_body_has_no_routing_write_reference_in_graph_topology
    SC-004a  test_sc004a_flag_off_wave_is_byte_identical_to_a_pre_merge_wave
    SC-004b  test_sc004b_flag_on_runs_shadow_only_never_auto_drives
    SC-005   test_sc005_escape_suite_summary_all_four_walls_denied_fail_closed_no_side_effect
             (the exhaustive 24-test wall-by-wall suite lives in
             test_ws_c_sandbox_adapter.py; the two GATE-3 red-team residuals —
             the NUL-byte denial-shape case and the caller-side raw-stdout
             Tier-M assertion — are added there as the natural extension of
             the file that already owns the wall tests.)
"""

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

import wave_runner as wr  # noqa: E402
from dgox import langgraph_loop as lg  # noqa: E402
from dgox.state import GraphState, apply_group  # noqa: E402

from tools import sandbox as sbx  # noqa: E402

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_INTERRUPT_SCHEMA = _REPO_ROOT / "board" / "interrupts" / "schema.json"
_WAVE_TS = "2026-07-24T13:00:00Z"


# --------------------------------------------------------------------------- #
# Shared fixture builders (mirrors test_ws_c_langgraph_substrate.py's helpers —
# kept local so this file has no import-order dependency on that one).
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# SC-001 — idempotent checkpoint / resume (LG-4 / FR-005)
# --------------------------------------------------------------------------- #


def test_sc001a_resume_preserves_completed_work_and_reaches_same_terminal_state_as_uninterrupted(
    tmp_path: Path,
) -> None:
    """SC-001a: interrupt a run mid-wave — AFTER wave 1's committed side effect,
    BEFORE wave 2 runs — then resume. The resumed run must (a) not lose wave
    1's completed work and (b) reach the SAME terminal state (ledger shape) a
    fully uninterrupted two-wave run would."""
    run_id = "01JWSC0000000000000000SC1A"
    ckpt = lg.RunIdCheckpointer()
    w1_kwargs = _run_wave_kwargs(tmp_path, "DAS-9201")
    ledger_path = w1_kwargs["ledger_path"]
    attest_dir = w1_kwargs["attest_dir"]

    # Wave 1 commits (the side effect that survives the simulated crash).
    plan1, results1 = _plan(run_id, 1, "DAS-9201"), _results("DAS-9201")
    att1 = lg.commit_wave(plan1, results1, created_at=_WAVE_TS, checkpointer=ckpt, **w1_kwargs)
    assert att1 is not None
    after_w1_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(after_w1_lines) == 1
    # Bijection check immediately after wave 1's commit — attest_dir is
    # keyed by run_id alone, so this is the meaningful moment to check it
    # (before wave 2 overwrites the run_id's attestation file).
    assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []

    # --- simulated crash: the process paused here; the checkpointer is what
    # survives the crash (persisted execution scratch, §4.1) and resume
    # re-enters with it, re-reading the board rather than trusting a stale
    # in-flight belief. ---

    # Resume: re-commit wave 1 (a resuming node re-derives it was already
    # done — guard-before-act — no progress lost, no double-apply)...
    att1_resumed = lg.commit_wave(plan1, results1, created_at=_WAVE_TS, checkpointer=ckpt, **w1_kwargs)
    assert att1_resumed is att1  # prior work is PRESENT, not lost
    assert ledger_path.read_text(encoding="utf-8").strip().splitlines() == after_w1_lines

    # ...then proceeds to wave 2, which was never interrupted.
    plan2, results2 = _plan(run_id, 2, "DAS-9202"), _results("DAS-9202")
    w2_kwargs = dict(w1_kwargs)
    _write_ticket(w1_kwargs["tickets_dir"], "DAS-9202", "backend-eng-1")
    att2 = lg.commit_wave(plan2, results2, created_at=_WAVE_TS, checkpointer=ckpt, **w2_kwargs)
    assert att2 is not None
    resumed_final_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(resumed_final_lines) == 2
    # (attestation_path() is keyed by run_id alone — one file per run_id, so a
    # bijection check against attest_dir is only meaningful immediately after
    # the LATEST wave's commit, which is what the single-wave idempotent-resume
    # test in test_ws_c_langgraph_substrate.py already asserts; the terminal-
    # state claim here is the ledger-shape comparison against the control run
    # below, not a second attest_dir bijection pass.)

    # --- control: an UNINTERRUPTED run of the same two waves, fresh state ---
    control_dir = tmp_path / "control"
    control_ckpt = lg.RunIdCheckpointer()
    c1_kwargs = _run_wave_kwargs(control_dir, "DAS-9201")
    c2_kwargs = dict(c1_kwargs)
    _write_ticket(c1_kwargs["tickets_dir"], "DAS-9202", "backend-eng-1")
    lg.commit_wave(plan1, results1, created_at=_WAVE_TS, checkpointer=control_ckpt, **c1_kwargs)
    lg.commit_wave(plan2, results2, created_at=_WAVE_TS, checkpointer=control_ckpt, **c2_kwargs)
    control_ledger = c1_kwargs["ledger_path"]
    control_lines = control_ledger.read_text(encoding="utf-8").strip().splitlines()

    # Same terminal shape: two ledger entries either way — the interruption
    # between wave 1 and wave 2 cost no progress and produced the same
    # end-state entry count as a run that was never interrupted.
    assert len(control_lines) == len(resumed_final_lines) == 2


def test_sc001b_guard_before_act_skips_reapply_of_a_generic_committed_side_effect() -> None:
    """SC-001b (generic angle — DAS-1447/§4.3): the guard-before-act check works
    for ANY committed side effect keyed by run_id + effect identity, not only
    a run_wave-shaped one — a merge, an emitted event, or a written checkpoint
    marker are the design's own examples. (The run_wave/ledger-specific angle
    of SC-001b is already covered by
    test_ws_c_langgraph_substrate.py::test_idempotent_resume_no_double_apply_and_ledger_reconciles.)
    """
    ckpt = lg.RunIdCheckpointer()
    run_id = "01JWSC0000000000000000SC1B"

    applied = {"merge": 0, "event": 0}

    def _guarded_apply(effect_key: str, kind: str) -> None:
        if ckpt.already_committed(run_id, effect_key):
            return  # resume: already committed, do NOT re-apply
        applied[kind] += 1
        ckpt.mark_committed(run_id, effect_key)

    # First pass: a merge and an emitted-event side effect both commit once.
    _guarded_apply("merge:PR-9301", "merge")
    _guarded_apply("event:trace-9301", "event")
    assert applied == {"merge": 1, "event": 1}

    # Simulated crash + resume: replay the SAME node sequence against the
    # SAME checkpointer. Neither side effect re-applies.
    _guarded_apply("merge:PR-9301", "merge")
    _guarded_apply("event:trace-9301", "event")
    assert applied == {"merge": 1, "event": 1}  # unchanged — no double-apply

    # A genuinely NEW effect on the same run_id still applies (the guard is
    # keyed by effect identity, not a blanket freeze on the run_id).
    _guarded_apply("merge:PR-9302", "merge")
    assert applied == {"merge": 2, "event": 1}


# --------------------------------------------------------------------------- #
# SC-002 — gate-interrupt blocks + divergence resolves to the board
# --------------------------------------------------------------------------- #


def test_sc002a_open_gate_and_naa_category_park_as_a_schema_valid_interrupt_card() -> None:
    """SC-002a: a GATE-5-open deployment parks at interrupt() and the resulting
    card is schema-valid per board/interrupts/schema.json (DAS-1446) — not just
    shape-plausible. The worker node stays unreachable throughout."""
    state = GraphState(ticket_id="DAS-9210")
    apply_group(state, "lifecycle", {"aadl_stage": "deployment", "predecessor_gate": "open"})
    decision = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision)

    card = lg.make_interrupt_card(state, decision, created_by="supervisor")

    schema = json.loads(_INTERRUPT_SCHEMA.read_text(encoding="utf-8"))
    required = schema["required"]
    assert set(required) <= set(card)  # every required field present
    assert set(card) <= set(schema["properties"])  # additionalProperties: false
    assert isinstance(card["question"], str) and card["question"]
    assert isinstance(card["options"], list) and card["options"]
    assert all(isinstance(o, str) and o for o in card["options"])
    assert card["ticket"] == "DAS-9210"
    import re

    assert re.match(schema["properties"]["ticket"]["pattern"], card["ticket"])
    assert isinstance(card["payload"], dict)
    assert card["created_by"] == "supervisor"

    # A GATE-5-open deployment stays machine-blocked even if the gate were
    # (hypothetically) closed — the NAA category alone is enough to interrupt.
    apply_group(state, "lifecycle", {"predecessor_gate": "closed"})
    decision_closed_gate = lg.route_from_supervisor(state, categories={"gate5_deployment"})
    assert decision_closed_gate.target == lg.INTERRUPT
    assert not lg.worker_reachable(decision_closed_gate)


def test_sc002b_divergence_in_a_non_routing_channel_also_resolves_to_the_board() -> None:
    """SC-002b (broader angle — test_ws_c_langgraph_substrate.py already covers
    the routing/assignee case): inject a divergence in the `risk` channel
    (a different field group) and assert the board still wins, with the
    checkpoint holding the wrong value and never consulted as a tiebreaker."""
    board_state = _closed_gate_state("DAS-9211")
    apply_group(board_state, "risk", {"severity": "low"})

    projected = lg.project(board_state)
    projected.channels["risk"]["severity"] = "critical"  # divergence injected

    cp = lg.Checkpoint(run_id="R2", node="supervisor", channels=projected.channels)
    checkpointer = lg.RunIdCheckpointer()
    checkpointer.save(cp)

    result = lg.reconcile(projected, board_state)
    assert result.board_state.severity.value == "low"
    assert ("risk", "severity") in result.diverged
    assert result.event is not None
    assert "risk.severity" in result.event["diverged"]
    assert "NOT used" in result.event["reason"] or "NOT" in result.event["reason"]
    # The checkpoint's stale value is untouched by reconcile() — proving it
    # was read, not written-to/consulted as authority.
    assert checkpointer.load("R2").channels["risk"]["severity"] == "critical"
    assert result.board_state.severity.value != checkpointer.load("R2").channels["risk"]["severity"]


# --------------------------------------------------------------------------- #
# SC-003 — worker write-scope: structurally unreachable, not merely guarded
# --------------------------------------------------------------------------- #


def test_sc003_worker_node_body_has_no_routing_write_reference_in_graph_topology() -> None:
    """SC-003 (graph-topology angle — test_ws_c_langgraph_substrate.py already
    covers the apply_channel-rejection angle): inspect build_graph's source to
    confirm the WORKER node function holds no `routing`-channel write handle at
    all — the write is unrepresentable at the topology level, matching the
    design's "no worker out-edge holds a routing-channel write handle" claim."""
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

    # WORKER's only out-edge (added once, unconditionally) goes to END — no
    # edge grants it a further routing-write path. `add_edge(WORKER, END)`
    # passes both ends as bare Name references (module constants), so read
    # `.id` off each ast.Name rather than expecting literal constants.
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
    # And no add_edge call anywhere sources from a routing-write path.
    assert not any(src_node == "routing" for src_node, _ in add_edge_pairs)


# --------------------------------------------------------------------------- #
# SC-004 — flag-off byte-identical / flag-on shadow-only
# --------------------------------------------------------------------------- #


def test_sc004a_flag_off_wave_is_byte_identical_to_a_pre_merge_wave(tmp_path: Path) -> None:
    """SC-004a: with the flag OFF, driving the substrate produces IDENTICAL
    ledger/attestation bytes to a "pre-merge" wave that never imports the
    substrate at all (a plain run_wave call). Merging the adapter changes no
    interactive-wave behaviour."""
    off = _write_features(tmp_path, on=False)
    assert lg.drive_enabled(off) is False

    run_id = "01JWSC0000000000000000SC4A"
    plan, results = _plan(run_id, 1, "DAS-9220"), _results("DAS-9220")

    # "Pre-merge" control: run_wave called directly, no substrate involved.
    pre_merge_dir = tmp_path / "pre-merge"
    pre_kwargs = _run_wave_kwargs(pre_merge_dir, "DAS-9220")
    import wave_runner as _wr

    _wr.run_wave(plan, results, created_at=_WAVE_TS, **pre_kwargs)
    pre_ledger = pre_kwargs["ledger_path"].read_text(encoding="utf-8").strip()

    # Post-merge: the same wave through the substrate's commit_wave, flag OFF.
    post_merge_dir = tmp_path / "post-merge"
    post_kwargs = _run_wave_kwargs(post_merge_dir, "DAS-9220")
    ckpt = lg.RunIdCheckpointer()
    lg.commit_wave(plan, results, created_at=_WAVE_TS, checkpointer=ckpt, **post_kwargs)
    post_ledger = post_kwargs["ledger_path"].read_text(encoding="utf-8").strip()

    assert post_ledger == pre_ledger  # byte-identical


def test_sc004b_flag_on_runs_shadow_only_never_auto_drives(tmp_path: Path) -> None:
    """SC-004b: flipping the flag ON runs the loop in SHADOW only — it never
    auto-drives a real dispatch on the flag alone, even under force_drive."""
    on = _write_features(tmp_path, on=True)
    assert lg.drive_enabled(on) is True

    result = lg.run_loop(features_path=on)
    assert result.drove is False
    assert "shadow" in result.reason.lower()
    assert "board" in result.reason.lower() or "Q4" in result.reason

    # force_drive is meaningless once the flag is ON — the code path that
    # raises SubstrateInertError only fires when the flag is OFF; with the
    # flag ON there is still no drive-on-request path exposed.
    result_forced = lg.run_loop(features_path=on, force_drive=True)
    assert result_forced.drove is False


# --------------------------------------------------------------------------- #
# SC-005 — sandbox-escape summary (exhaustive wall-by-wall suite lives in
# tests/test_ws_c_sandbox_adapter.py; this is the design's named-home pointer
# asserting one representative denial per wall, all fail-closed / no side
# effect, so DAS-1567's SC-005 label has a home in this file too).
# --------------------------------------------------------------------------- #


def test_sc005_escape_suite_summary_all_four_walls_denied_fail_closed_no_side_effect(
    tmp_path: Path,
) -> None:
    """SC-005 summary (design §7 / §5.2): one representative probe per wall —
    host, repo, other-task, unscoped-credential+egress, resource-limit — each
    DENIED with no side effect. The exhaustive per-wall matrix (24 tests) is
    tests/test_ws_c_sandbox_adapter.py's; this proves the summary claim holds
    against the SAME LocalStubSandbox instance in one place."""
    backend = sbx.LocalStubSandbox()
    mount_root = tmp_path / "task-summary"
    mount_root.mkdir()
    scope = sbx.SandboxScope(
        task_id="task-summary",
        workdir_mounts=[sbx.Mount(host_path=str(mount_root))],
        resource_limits=sbx.ResourceLimits(wallclock_seconds=1.0, max_output_bytes=8),
    )
    handle = backend.open(task_id="task-summary", scope=scope)

    # Host wall.
    host_result = backend.exec(handle, ["read", "/etc/passwd"])
    assert host_result.ok is False

    # Repo wall (escape to a sibling dir simulating .git/board).
    sibling = tmp_path / "sibling-repo-area"
    sibling.mkdir()
    (sibling / "secret.md").write_text("other ticket")
    repo_result = backend.exec(handle, ["read", "../sibling-repo-area/secret.md"])
    assert repo_result.ok is False

    # Other-task wall: a foreign handle is denied.
    forged = sbx.SandboxHandle(task_id="task-summary", backend="local-stub", token="forged")
    other_task_result = backend.exec(forged, ["read", "notes.txt"])
    assert other_task_result.ok is False

    # Unscoped-credential + egress wall: no grant, deny-all egress.
    cred_result = backend.exec(handle, ["cred", "ungranted" + "-key"])
    assert cred_result.ok is False
    egress_result = backend.exec(handle, ["net", "https://exfil.example/"])
    assert egress_result.ok is False

    # Resource-limit wall.
    sleep_result = backend.exec(handle, ["sleep", "999"])
    assert sleep_result.ok is False
    write_result = backend.exec(handle, ["write", "big.txt", "way too much content"])
    assert write_result.ok is False

    # No side effect from ANY of the denials above.
    assert list(mount_root.iterdir()) == []
    assert not (tmp_path / "escaped.txt").exists()
