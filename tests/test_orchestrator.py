from __future__ import annotations

import json
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import orchestrator as orch
import wave_planner as wp
import wave_runner as wr

_ORG = wp.OrgModel(
    role_models={"backend-eng-1": "sonnet", "backend-eng-2": "sonnet", "cto": "opus"},
    gate_order=("GATE-1", "GATE-2", "GATE-3"),
)

_RUN_ID = "01JORCH000000000000000001"


def _plan(*ticket_ids: str) -> wp.WavePlan:
    tickets = [
        wp.Ticket(ticket_id=tid, role="backend-eng-1", status="todo", zone=f"zone-{tid}")
        for tid in ticket_ids
    ]
    return wp.plan_wave(tickets, _ORG, [], goal="ship-it")


def _orchestrator(invoke, tmp_path: Path, **config_kwargs) -> orch.Orchestrator:
    config = orch.OrchestratorConfig(**config_kwargs) if config_kwargs else None
    return orch.Orchestrator(
        invoke,
        config=config,
        journal_path=tmp_path / "journal.jsonl",
        clock=lambda: "2026-07-04T12:00:00Z",
    )


def test_dispatch_runs_every_planned_ticket_once(tmp_path: Path) -> None:
    seen: list[str] = []

    def invoke(request: orch.DispatchRequest) -> str:
        seen.append(request.ticket_id)
        return f"done {request.ticket_id}"

    run = _orchestrator(invoke, tmp_path).dispatch(_plan("DAS-1", "DAS-2"), run_id=_RUN_ID)
    assert sorted(seen) == ["DAS-1", "DAS-2"]
    assert run.all_succeeded
    assert [o.ticket_id for o in run.outcomes] == ["DAS-1", "DAS-2"]
    assert run.by_ticket()["DAS-1"].result.output == "done DAS-1"


def test_the_model_the_planner_chose_reaches_the_invoker(tmp_path: Path) -> None:
    models: dict[str, str] = {}

    def invoke(request: orch.DispatchRequest) -> str:
        models[request.ticket_id] = request.model
        return "ok"

    _orchestrator(invoke, tmp_path).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    assert models == {"DAS-1": "sonnet"}


def test_bounded_concurrency_is_respected(tmp_path: Path) -> None:
    lock = threading.Lock()
    live = 0
    peak = 0

    def invoke(_request: orch.DispatchRequest) -> str:
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep(0.02)
        with lock:
            live -= 1
        return "ok"

    plan = _plan(*[f"DAS-{i}" for i in range(1, 9)])
    run = _orchestrator(invoke, tmp_path, max_parallel=2).dispatch(plan, run_id=_RUN_ID)
    assert run.all_succeeded
    assert peak <= 2
    assert peak > 1


def test_a_failing_ticket_is_retried_up_to_the_cap(tmp_path: Path) -> None:
    attempts: list[int] = []

    def invoke(request: orch.DispatchRequest) -> str:
        attempts.append(request.attempt)
        raise RuntimeError("agent blew up")

    run = _orchestrator(invoke, tmp_path, max_attempts=3).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    assert attempts == [1, 2, 3]
    outcome = run.by_ticket()["DAS-1"]
    assert outcome.status is orch.DispatchStatus.FAILED
    assert outcome.attempts == 3
    assert "agent blew up" in outcome.error
    assert not run.all_succeeded


def test_a_retry_that_recovers_reports_success(tmp_path: Path) -> None:
    def invoke(request: orch.DispatchRequest) -> str:
        if request.attempt == 1:
            raise RuntimeError("transient")
        return "recovered"

    run = _orchestrator(invoke, tmp_path, max_attempts=2).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    outcome = run.by_ticket()["DAS-1"]
    assert outcome.status is orch.DispatchStatus.OK
    assert outcome.attempts == 2
    assert outcome.result.output == "recovered"


def test_a_hung_ticket_hits_the_per_task_timeout(tmp_path: Path) -> None:
    release = threading.Event()

    def invoke(_request: orch.DispatchRequest) -> str:
        release.wait(timeout=10)
        return "too late"

    try:
        run = _orchestrator(
            invoke, tmp_path, task_timeout_seconds=0.05, max_attempts=1
        ).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
        outcome = run.by_ticket()["DAS-1"]
        assert outcome.status is orch.DispatchStatus.TIMEOUT
        assert "exceeded" in outcome.error
    finally:
        release.set()


def test_rerunning_after_a_kill_neither_duplicates_nor_loses_work(tmp_path: Path) -> None:
    calls: list[str] = []

    def crashing(request: orch.DispatchRequest) -> str:
        calls.append(request.ticket_id)
        if request.ticket_id == "DAS-2":
            raise RuntimeError("killed mid-wave")
        return f"done {request.ticket_id}"

    plan = _plan("DAS-1", "DAS-2", "DAS-3")
    first = _orchestrator(crashing, tmp_path, max_parallel=1, max_attempts=1).dispatch(
        plan, run_id=_RUN_ID
    )
    assert not first.all_succeeded
    assert sorted(calls) == ["DAS-1", "DAS-2", "DAS-3"]

    calls.clear()

    def healthy(request: orch.DispatchRequest) -> str:
        calls.append(request.ticket_id)
        return f"done {request.ticket_id}"

    second = _orchestrator(healthy, tmp_path, max_parallel=1, max_attempts=1).dispatch(
        plan, run_id=_RUN_ID
    )
    assert calls == ["DAS-2"]
    assert second.all_succeeded
    assert {o.ticket_id for o in second.outcomes} == {"DAS-1", "DAS-2", "DAS-3"}
    assert second.by_ticket()["DAS-1"].resumed is True
    assert second.by_ticket()["DAS-1"].result.output == "done DAS-1"
    assert second.by_ticket()["DAS-2"].resumed is False


def test_a_second_identical_run_invokes_no_agent_at_all(tmp_path: Path) -> None:
    calls: list[str] = []

    def invoke(request: orch.DispatchRequest) -> str:
        calls.append(request.ticket_id)
        return "ok"

    plan = _plan("DAS-1", "DAS-2")
    _orchestrator(invoke, tmp_path).dispatch(plan, run_id=_RUN_ID)
    assert len(calls) == 2
    calls.clear()
    run = _orchestrator(invoke, tmp_path).dispatch(plan, run_id=_RUN_ID)
    assert calls == []
    assert run.all_succeeded
    assert all(o.resumed for o in run.outcomes)


def test_a_new_run_id_is_not_deduplicated(tmp_path: Path) -> None:
    calls: list[str] = []

    def invoke(request: orch.DispatchRequest) -> str:
        calls.append(request.run_id)
        return "ok"

    plan = _plan("DAS-1")
    orchestrator = _orchestrator(invoke, tmp_path)
    orchestrator.dispatch(plan, run_id=_RUN_ID)
    orchestrator.dispatch(plan, run_id="01JORCH000000000000000002")
    assert calls == [f"{_RUN_ID}-DAS-1", "01JORCH000000000000000002-DAS-1"]


def test_the_journal_is_durable_jsonl(tmp_path: Path) -> None:
    def invoke(_request: orch.DispatchRequest) -> str:
        return "ok"

    _orchestrator(invoke, tmp_path).dispatch(_plan("DAS-1", "DAS-2"), run_id=_RUN_ID)
    lines = [
        json.loads(ln)
        for ln in (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(lines) == 2
    assert {e["ticket_id"] for e in lines} == {"DAS-1", "DAS-2"}
    assert all(e["schema"] == orch.JOURNAL_SCHEMA for e in lines)


def test_journal_entries_from_concurrent_tickets_are_never_interleaved(tmp_path: Path) -> None:
    def invoke(_request: orch.DispatchRequest) -> str:
        return "x" * 4096

    plan = _plan(*[f"DAS-{i}" for i in range(1, 17)])
    _orchestrator(invoke, tmp_path, max_parallel=16).dispatch(plan, run_id=_RUN_ID)
    lines = [
        ln
        for ln in (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(lines) == 16
    for line in lines:
        json.loads(line)


def test_a_non_callable_invoker_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="callable agent invoker"):
        orch.Orchestrator("not-a-callable", journal_path=tmp_path / "j.jsonl")


def test_an_invoker_returning_junk_is_a_failed_ticket_not_a_crash(tmp_path: Path) -> None:
    def invoke(_request: orch.DispatchRequest) -> str:
        return 42

    run = _orchestrator(invoke, tmp_path, max_attempts=1).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    outcome = run.by_ticket()["DAS-1"]
    assert outcome.status is orch.DispatchStatus.FAILED
    assert "TypeError" in outcome.error


def test_config_validates_its_bounds() -> None:
    with pytest.raises(ValueError):
        orch.OrchestratorConfig(max_parallel=0)
    with pytest.raises(ValueError):
        orch.OrchestratorConfig(max_attempts=0)
    with pytest.raises(ValueError):
        orch.OrchestratorConfig(task_timeout_seconds=0)


def test_structured_agent_output_is_carried_into_ticket_results(tmp_path: Path) -> None:
    def invoke(_request: orch.DispatchRequest) -> orch.AgentOutput:
        return orch.AgentOutput(
            output="ran pytest: 12 passed",
            merged_pr=True,
            ci_status="green",
            t7_pass=True,
            t7_score=0.9,
            input_tokens=10,
            output_tokens=5,
        )

    run = _orchestrator(invoke, tmp_path).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    results = orch.ticket_results_from_run(run)
    assert len(results) == 1
    result = results[0]
    assert result.outcome == "success"
    assert result.merged_pr is True
    assert result.ci_status == "green"
    assert result.final_status == "done"
    assert result.output == "ran pytest: 12 passed"


def test_unverified_output_is_not_reported_as_merged(tmp_path: Path) -> None:
    def invoke(_request: orch.DispatchRequest) -> str:
        return "did the thing"

    run = _orchestrator(invoke, tmp_path).dispatch(_plan("DAS-1"), run_id=_RUN_ID)
    result = orch.ticket_results_from_run(run)[0]
    assert result.merged_pr is False
    assert result.t7_pass is False
    assert result.ci_status == "unverified"


def test_wave_executor_drives_run_wave_end_to_end(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    board.mkdir(parents=True, exist_ok=True)
    for tid in ("DAS-9001", "DAS-9002"):
        (board / f"{tid}-work.md").write_text(
            "---\n"
            f"id: {tid}\n"
            "status: in_progress\n"
            "assignee: backend-eng-1\n"
            "author: cto\n"
            "dept: engineering\n"
            "---\n\nbody\n",
            encoding="utf-8",
        )

    def invoke(request: orch.DispatchRequest) -> orch.AgentOutput:
        return orch.AgentOutput(
            output=f"implemented {request.ticket_id}; ran pytest: 12 passed",
            merged_pr=True,
            ci_status="green",
            t7_pass=True,
            t7_score=0.9,
        )

    orchestrator = _orchestrator(invoke, tmp_path)
    runner_plan = wr.WavePlan(
        run_id=_RUN_ID,
        wave=1,
        goal="ship-it",
        engine_version="1.0.0",
        tickets=[
            wr.TicketPlan("DAS-9001", role="backend-eng-1", model="sonnet"),
            wr.TicketPlan("DAS-9002", role="backend-eng-2", model="sonnet"),
        ],
    )
    attestation = wr.run_wave(
        runner_plan,
        orch.wave_executor(orchestrator),
        created_at="2026-07-04T12:00:00Z",
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        run_guardrails=False,
    )
    assert attestation is not None
    assert attestation.payload["counts"] == {"dispatched": 2, "counted_completions": 2}
    assert wr.verify_wave_ledger(
        tmp_path / "board" / "wave-ledger.jsonl", attest_dir=tmp_path / "attest"
    ) == []


def test_to_runner_plan_keeps_the_planned_models() -> None:
    plan = _plan("DAS-1", "DAS-2")
    runner_plan = orch.to_runner_plan(
        plan, run_id=_RUN_ID, wave=1, goal="ship-it", engine_version="1.0.0"
    )
    assert [tp.ticket_id for tp in runner_plan.tickets] == ["DAS-1", "DAS-2"]
    assert {tp.model for tp in runner_plan.tickets} == {"sonnet"}


def _write_board(tmp_path: Path) -> tuple[Path, Path]:
    board = tmp_path / "tickets"
    board.mkdir(parents=True, exist_ok=True)
    (board / "DAS-1-a.md").write_text(
        "---\nid: DAS-1\nstatus: todo\nassignee: backend-eng-1\nzone: scripts\n"
        "priority: p1\n---\n\nbody\n",
        encoding="utf-8",
    )
    (board / "DAS-2-b.md").write_text(
        "---\nid: DAS-2\nstatus: todo\nassignee: backend-eng-1\nzone: scripts\n"
        "priority: p2\n---\n\nbody\n",
        encoding="utf-8",
    )
    (board / "DAS-3-c.md").write_text(
        "---\nid: DAS-3\nstatus: todo\nassignee: backend-eng-1\nzone: tools\n"
        "priority: p2\ndepends_on: [DAS-1]\n---\n\nbody\n",
        encoding="utf-8",
    )
    org = tmp_path / "org.yaml"
    org.write_text(
        textwrap.dedent(
            """\
            gates: [GATE-1, GATE-2]
            roles:
              backend-eng-1: {model: sonnet}
            """
        ),
        encoding="utf-8",
    )
    return board, org


def test_dry_run_prints_the_plan_and_writes_nothing(tmp_path: Path, capsys) -> None:
    board, org = _write_board(tmp_path)
    before = sorted(p.name for p in tmp_path.rglob("*"))
    rc = orch.main(["--dry-run", "--board", str(board), "--org", str(org), "--goal", "g"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DISPATCH DAS-1" in out
    assert "REFUSE   DAS-2 zone_conflict" in out
    assert "REFUSE   DAS-3 unmet_dependency" in out
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_dry_run_json_is_machine_readable(tmp_path: Path, capsys) -> None:
    board, org = _write_board(tmp_path)
    rc = orch.main(["--dry-run", "--json", "--board", str(board), "--org", str(org)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [t["ticket_id"] for t in payload["dispatch"]] == ["DAS-1"]
    assert payload["dispatch"][0]["model"] == "sonnet"


def test_dispatch_without_an_invoker_refuses(tmp_path: Path, capsys) -> None:
    board, org = _write_board(tmp_path)
    rc = orch.main(
        ["--dispatch", "--run-id", _RUN_ID, "--board", str(board), "--org", str(org)]
    )
    assert rc == 2
    assert "requires --invoker" in capsys.readouterr().err


def test_dispatch_without_a_run_id_refuses(tmp_path: Path, capsys) -> None:
    board, org = _write_board(tmp_path)
    rc = orch.main(["--dispatch", "--board", str(board), "--org", str(org)])
    assert rc == 2
    assert "requires --run-id" in capsys.readouterr().err


def test_dispatch_resolves_an_injected_invoker(tmp_path: Path, monkeypatch, capsys) -> None:
    board, org = _write_board(tmp_path)
    module_dir = tmp_path / "fake_pkg"
    module_dir.mkdir()
    (module_dir / "fake_invoker.py").write_text(
        "def invoke(request):\n"
        "    return f'ran {request.ticket_id} on {request.model}'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(module_dir))
    rc = orch.main(
        [
            "--dispatch",
            "--json",
            "--run-id",
            _RUN_ID,
            "--board",
            str(board),
            "--org",
            str(org),
            "--invoker",
            "fake_invoker:invoke",
            "--journal",
            str(tmp_path / "journal.jsonl"),
            "--no-evidence",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["all_succeeded"] is True
    assert payload["attestation"] == ""
    assert [o["ticket_id"] for o in payload["outcomes"]] == ["DAS-1"]


def test_dispatch_writes_a_wave_ledger_entry_and_attestation(tmp_path: Path) -> None:
    board, _org = _write_board(tmp_path)

    def invoke(request: orch.DispatchRequest) -> orch.AgentOutput:
        return orch.AgentOutput(
            output=f"did {request.ticket_id}",
            merged_pr=True,
            ci_status="green",
            t7_pass=True,
            t7_score=0.9,
        )

    orchestrator = orch.Orchestrator(invoke, journal_path=tmp_path / "journal.jsonl")
    ledger = tmp_path / "wave-ledger.jsonl"
    attest = tmp_path / "attest"
    run, attestation = orch.dispatch_with_evidence(
        orch.build_plan_from_board(
            board_dir=board,
            org_path=_org,
            goal="ship-it",
            occupied_zones=(),
            closed_gates=(),
            max_wave_size=None,
        ),
        orchestrator,
        run_id=_RUN_ID,
        wave=1,
        goal="ship-it",
        board_dir=board,
        evidence_paths={
            "ledger_path": ledger,
            "attest_dir": attest,
            "store_path": tmp_path / "events.jsonl",
            "runs_dir": tmp_path / "runs",
            "evidence_dir": tmp_path / "evidence",
        },
    )

    assert run.all_succeeded
    assert attestation is not None
    assert ledger.read_text(encoding="utf-8").strip()
    assert wr.verify_wave_ledger(ledger, attest_dir=attest) == []


def test_next_wave_number_is_gap_free_from_the_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "wave-ledger.jsonl"
    assert orch.next_wave_number(ledger) == 1

    ledger.write_text(
        json.dumps({"run_id": "a", "wave": 1, "ticket_ids": []}) + "\n",
        encoding="utf-8",
    )
    assert orch.next_wave_number(ledger) == 2

    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": "b", "wave": 2, "ticket_ids": []}) + "\n")
    assert orch.next_wave_number(ledger) == 3
    assert orch.recorded_waves(ledger) == [1, 2]


def test_next_wave_number_rejects_a_corrupt_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "wave-ledger.jsonl"
    ledger.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt wave ledger"):
        orch.next_wave_number(ledger)


def test_resolve_invoker_reports_a_bad_spec() -> None:
    with pytest.raises(orch.AgentInvokerUnavailable, match="module:callable"):
        orch.resolve_invoker("nocolon")
    with pytest.raises(orch.AgentInvokerUnavailable, match="cannot import"):
        orch.resolve_invoker("no_such_module_at_all:invoke")
    with pytest.raises(orch.AgentInvokerUnavailable, match="no attribute"):
        orch.resolve_invoker("orchestrator:not_a_real_attribute")
    with pytest.raises(orch.AgentInvokerUnavailable, match="not callable"):
        orch.resolve_invoker("orchestrator:JOURNAL_SCHEMA")
