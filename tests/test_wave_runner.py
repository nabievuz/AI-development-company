
from __future__ import annotations

import ast
import json
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_ledger
import check_metric_gaming
import check_spans
import metrics_lib
import wave_kpi
import wave_runner as wr
from dgox.events import RUN_END_METRICS_FIELDS

_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"

_WAVE_TS = "2026-07-04T12:00:00Z"
_WAVE_TS2 = "2026-07-04T13:00:00Z"

_ROUTING_TABLE = textwrap.dedent(
    """\
    | Role key | Display name | Dept | Reports to (reviewer) |
    |---|---|---|---|
    | `backend-eng-1` | Backend Engineer 1 | engineering | Backend EM |
    | `backend-eng-2` | Backend Engineer 2 | engineering | Backend EM |
    | `backend-em` | Backend EM | engineering | CTO |
    | `cto` | CTO | engineering | CEO |
    """
)


def _routing(tmp: Path) -> Path:
    path = tmp / "ROUTING.md"
    path.write_text(_ROUTING_TABLE, encoding="utf-8")
    return path


def _write_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic wave-runner fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\n"
        "## Description\nSynthetic ticket for the wave_runner end-to-end test.\n",
        encoding="utf-8",
    )


def _plan(run_id: str) -> wr.WavePlan:
    return wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="organism-ws8-attest",
        engine_version="1.0.0",
        tickets=[
            wr.TicketPlan("DAS-9001", role="backend-eng-1", model="opus"),
            wr.TicketPlan("DAS-9002", role="backend-eng-2", model="sonnet"),
        ],
    )


def _ticket_results() -> list[wr.TicketResult]:
    common = {
        "outcome": "success", "merged_pr": True, "ci_status": "green",
        "t7_pass": True, "t7_score": 0.95, "start": _WAVE_TS, "end": "2026-07-04T12:10:00Z",
        "final_status": "done",
        "output": (
            "Implemented the change in scripts/wave_runner.py; ran pytest "
            "tests/test_wave_runner.py and got 23 passed, 0 failed."
        ),
    }
    return [
        wr.TicketResult(ticket_id="DAS-9001", **common),
        wr.TicketResult(ticket_id="DAS-9002", **common),
    ]


def _executor() -> wr.WaveExecutor:
    return wr.replay_executor(_ticket_results())


def _drive(tmp: Path, run_id: str, created_at: str) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    att = wr.run_wave(
        _plan(run_id),
        _executor(),
        created_at=created_at,
        store_path=tmp / "events.jsonl",
        runs_dir=tmp / "runs",
        attest_dir=tmp / "attest",
        ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp),
        guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def test_run_wave_omitted_guardrails_dir_does_not_crash(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    att = wr.run_wave(
        _plan("01KWS8ATTEST00000000000009"),
        _executor(),
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp_path),
        run_guardrails=False,

    )
    assert att is not None


    assert (tmp_path / "attest" / "01KWS8ATTEST00000000000009.json").exists()


def test_run_wave_end_to_end_all_mechanics_have_teeth(tmp_path: Path, capsys) -> None:
    run_id = "01JWAVE0000000000000000001"
    att = _drive(tmp_path, run_id, _WAVE_TS)
    store = tmp_path / "events.jsonl"
    evidence_dir = tmp_path / "evidence"


    rc = check_spans.main(["--events", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "coverage 100%" in out
    assert "2 dispatch(es)" in out and "2 span(s)" in out


    events = wave_kpi.read_events(str(store))
    run_ends = [e for e in events if e.get("event_type") == "run_end"]
    assert len(run_ends) == 2
    for e in run_ends:
        assert set(e) >= RUN_END_METRICS_FIELDS, "run_end missing a metrics-contract field"
    mix = metrics_lib.model_mix(events)
    assert mix == {"ratio": 0.0, "low_cost": 0, "total": 2}
    gaming = metrics_lib.gaming_violations(events)
    assert gaming == {"completions": 2, "violations": []}
    assert att.payload["counts"] == {"dispatched": 2, "counted_completions": 2}


    rc = check_metric_gaming.main(["--events", str(store), "--evidence-dir", str(evidence_dir)])
    assert rc == 0
    for rid in att.payload["evidence"]["run_ids"]:
        assert (evidence_dir / f"{rid}.json").is_file()


    ledger = json.loads(check_ledger.progress_ledger_path(run_id, tmp_path / "runs").read_text())
    assert check_ledger.validate_ledger(ledger) == []


    assert att.payload["schema"] == wr.ATTESTATION_SCHEMA
    assert att.payload["mechanics"] == {
        "checkpoint_open": True,
        "guardrails_run": True,
        "events_emitted": {"run_start": 2, "run_end": 2, "span": 2},
        "ledger_written": True,
        "evidence_written": True,
        "checkpoint_close": True,
    }
    assert att.payload["guardrail_verdicts"] == {"DAS-9001": "passed", "DAS-9002": "passed"}
    assert wr.verify_attestation(att.payload) == []
    assert att.prev_hash == wr._GENESIS_PREV_HASH
    assert wr.load_attestation(att.path) == att.payload


def test_attestation_chain_links_across_waves(tmp_path: Path) -> None:
    first = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    second = _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    assert wr.verify_attestation(second.payload) == []
    assert second.prev_hash == first.self_hash
    assert second.self_hash != first.self_hash


_LEDGER_FIELDS = {
    "run_id", "wave", "ticket_ids", "attestation_path",
    "attestation_hash", "prev_hash", "self_hash", "created_at",
}


def _read_ledger(ledger_path: Path) -> list[dict]:
    lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_run_wave_co_produces_chain_linked_ledger_entry(tmp_path: Path) -> None:
    run_id = "01JWAVE0000000000000000001"
    att = _drive(tmp_path, run_id, _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"


    assert att.path.is_file()
    assert ledger_path.is_file()

    entries = _read_ledger(ledger_path)
    assert len(entries) == 1
    entry = entries[0]


    assert set(entry) == _LEDGER_FIELDS
    assert entry["run_id"] == run_id
    assert entry["wave"] == att.payload["wave"] == 1
    assert entry["created_at"] == _WAVE_TS


    assert entry["ticket_ids"] == att.payload["tickets"] == ["DAS-9001", "DAS-9002"]


    assert entry["attestation_hash"] == wr._sha256_bytes(att.path.read_bytes())
    assert entry["attestation_path"].endswith(f"{run_id}.json")


    assert entry["prev_hash"] == wr._GENESIS_PREV_HASH
    assert entry["self_hash"] == wr._ledger_self_hash(entry)
    assert entry["self_hash"] != wr._GENESIS_PREV_HASH


def test_two_wave_run_writes_two_chain_linked_ledger_entries(tmp_path: Path) -> None:
    first = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    second = _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"

    entries = _read_ledger(ledger_path)
    assert len(entries) == 2
    e1, e2 = entries


    assert e1["prev_hash"] == wr._GENESIS_PREV_HASH
    assert e2["prev_hash"] == e1["self_hash"]
    assert e1["self_hash"] == wr._ledger_self_hash(e1)
    assert e2["self_hash"] == wr._ledger_self_hash(e2)
    assert e1["self_hash"] != e2["self_hash"]


    assert e1["attestation_hash"] == wr._sha256_bytes(first.path.read_bytes())
    assert e2["attestation_hash"] == wr._sha256_bytes(second.path.read_bytes())
    assert {e1["run_id"], e2["run_id"]} == {first.run_id, second.run_id}


def test_verify_wave_ledger_reconciles_a_clean_two_wave_run(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    assert wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest") == []


def test_verify_wave_ledger_empty_or_absent_is_inert(tmp_path: Path) -> None:
    assert wr.verify_wave_ledger(tmp_path / "board" / "wave-ledger.jsonl") == []


def test_verify_wave_ledger_detects_tampered_attestation_hash(tmp_path: Path) -> None:
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"


    payload = wr.load_attestation(att.path)
    att.path.write_text(json.dumps(payload, indent=4, sort_keys=True) + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("attestation_hash mismatch" in p for p in problems), problems


def test_verify_wave_ledger_detects_dropped_line_as_chain_gap(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    ledger_path.write_text(lines[1] + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("broken chain" in p for p in problems), problems


def test_verify_wave_ledger_detects_duplicate_entry(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    line = ledger_path.read_text(encoding="utf-8").strip()
    ledger_path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("duplicate ledger entry" in p for p in problems), problems


def test_verify_wave_ledger_detects_orphan_attestation(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"

    (tmp_path / "attest" / "01JWAVEORPHAN00000000000099.json").write_text(
        json.dumps({"schema": wr.ATTESTATION_SCHEMA, "run_id": "orphan"}), encoding="utf-8"
    )
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("orphan attestation" in p for p in problems), problems


def test_verify_wave_ledger_reconciles_the_committed_repo_sample() -> None:
    if not wr.LEDGER_PATH.exists():
        pytest.skip("no committed wave-ledger sample in this checkout")
    assert wr.verify_wave_ledger(wr.LEDGER_PATH, attest_dir=wr.ATTEST_DIR) == []


def test_organism_emit_off_is_a_byte_clean_noop(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    before = {p.name: p.read_text(encoding="utf-8") for p in board.glob("DAS-*.md")}
    store = tmp_path / "events.jsonl"
    attest = tmp_path / "attest"
    ledger = tmp_path / "board" / "wave-ledger.jsonl"
    result = wr.run_wave(
        _plan("01JWAVE0000000000000000009"),
        _executor(),
        created_at=_WAVE_TS,
        store_path=store,
        runs_dir=tmp_path / "runs",
        attest_dir=attest,
        ledger_path=ledger,
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp_path),
        guardrails_dir=_GUARDRAILS,
        organism_emit=False,
    )
    assert result is None
    assert not store.exists()
    assert not attest.exists()
    assert not ledger.exists()

    after = {p.name: p.read_text(encoding="utf-8") for p in board.glob("DAS-*.md")}
    assert after == before
    assert all("run_id:" not in text for text in after.values())


def test_run_wave_stamps_run_id_into_each_ticket(tmp_path: Path) -> None:
    run_id = "01JWAVE0000000000000000001"
    _drive(tmp_path, run_id, _WAVE_TS)
    board = tmp_path / "board" / "tickets"
    for tid in ("DAS-9001", "DAS-9002"):
        match = sorted(board.glob(f"{tid}-*.md"))[0]
        fm = match.read_text(encoding="utf-8")
        assert f"run_id: {run_id}" in fm
        assert fm.count("run_id:") == 1


def test_stamp_run_id_frontmatter_is_idempotent(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    path = sorted(board.glob("DAS-9001-*.md"))[0]

    changed1 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000001")
    text1 = path.read_text(encoding="utf-8")
    changed2 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000001")
    text2 = path.read_text(encoding="utf-8")
    assert changed1 is True
    assert changed2 is False
    assert text1 == text2
    assert text2.count("run_id:") == 1
    assert "run_id: 01JRUNID000000000000000001" in text2

    changed3 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000002")
    text3 = path.read_text(encoding="utf-8")
    assert changed3 is True
    assert text3.count("run_id:") == 1
    assert "run_id: 01JRUNID000000000000000002" in text3
    assert "01JRUNID000000000000000001" not in text3


def test_run_wave_missing_ticket_file_does_not_crash_the_wave(tmp_path: Path) -> None:
    run_id = "01JWAVE0000000000000000005"
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")

    att = wr.run_wave(
        _plan(run_id),
        _executor(),
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp_path),
        guardrails_dir=_GUARDRAILS,
        run_guardrails=False,
    )
    assert att is not None
    assert (tmp_path / "attest" / f"{run_id}.json").is_file()

    present = sorted(board.glob("DAS-9001-*.md"))[0].read_text(encoding="utf-8")
    assert f"run_id: {run_id}" in present
    assert sorted(board.glob("DAS-9002-*.md")) == []


def test_shadow_rule_holds_by_property(tmp_path: Path) -> None:
    tree = ast.parse((_SCRIPTS / "wave_runner.py").read_text(encoding="utf-8"))
    called: set[str] = set()
    events_literal_in_call = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        called.add(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", ""))

        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and ".events.jsonl" in arg.value:
                events_literal_in_call = True
    read_primitives = {"read_events", "iter_events", "group_runs", "replay_run"}
    assert not (read_primitives & called), "wave_runner must not read the event store"
    assert not events_literal_in_call, "wave_runner must not open a .events.jsonl literal"


def test_missing_result_for_planned_ticket_raises(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    plan = wr.WavePlan(
        run_id="01JWAVE0000000000000000003", wave=1, goal="g", engine_version="1.0.0",
        tickets=[wr.TicketPlan("DAS-9001", "backend-eng-1", "opus"),
                 wr.TicketPlan("DAS-9099", "backend-eng-2", "sonnet")],
    )
    partial = wr.replay_executor([wr.TicketResult(
        "DAS-9001", outcome="success", merged_pr=True, ci_status="green",
        t7_pass=True, t7_score=0.9, start=_WAVE_TS, end="2026-07-04T12:05:00Z",
        output="done")])
    with pytest.raises(ValueError, match="DAS-9099"):
        wr.run_wave(plan, partial, created_at=_WAVE_TS, store_path=tmp_path / "e.jsonl",
                    runs_dir=tmp_path / "runs", attest_dir=tmp_path / "att",
                    ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
                    evidence_dir=tmp_path / "ev", tickets_dir=board, board_dir=board,
                    routing_path=_routing(tmp_path), guardrails_dir=_GUARDRAILS, run_guardrails=False)


def test_run_wave_refuses_pre_computed_results(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    supplied = wr.WaveResults(tickets=_ticket_results())
    with pytest.raises(TypeError, match="no longer accepts pre-computed WaveResults"):
        wr.run_wave(
            _plan("01JWAVE0000000000000000011"),
            supplied,
            created_at=_WAVE_TS,
            store_path=tmp_path / "events.jsonl",
            runs_dir=tmp_path / "runs",
            attest_dir=tmp_path / "attest",
            ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
            evidence_dir=tmp_path / "evidence",
            tickets_dir=board,
            board_dir=board,
            routing_path=_routing(tmp_path),
            guardrails_dir=_GUARDRAILS,
            run_guardrails=False,
        )


def test_run_wave_produces_results_by_running_the_executor(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    seen: list[wr.WavePlan] = []

    def execute(plan: wr.WavePlan) -> list[wr.TicketResult]:
        seen.append(plan)
        return _ticket_results()

    att = wr.run_wave(
        _plan("01JWAVE0000000000000000012"),
        execute,
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp_path),
        guardrails_dir=_GUARDRAILS,
        run_guardrails=False,
    )
    assert att is not None
    assert len(seen) == 1
    assert [tp.ticket_id for tp in seen[0].tickets] == ["DAS-9001", "DAS-9002"]


def test_executor_is_not_run_when_organism_emit_is_off(tmp_path: Path) -> None:
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    calls: list[str] = []

    def execute(plan: wr.WavePlan) -> list[wr.TicketResult]:
        calls.append(plan.run_id)
        return _ticket_results()

    result = wr.run_wave(
        _plan("01JWAVE0000000000000000013"),
        execute,
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_routing(tmp_path),
        guardrails_dir=_GUARDRAILS,
        organism_emit=False,
    )
    assert result is None
    assert calls == []


def test_wave_results_are_derived_from_what_the_run_produced() -> None:
    failed = wr.TicketResult(
        ticket_id="DAS-9002", outcome="failed", merged_pr=False, ci_status="red",
        t7_pass=False, t7_score=0.0, start=_WAVE_TS, end=_WAVE_TS2,
        final_status="blocked", output="",
    )
    derived = wr.WaveResults.from_ticket_results([_ticket_results()[0], failed])
    assert derived.request_satisfied is False
    assert derived.progress_being_made is True
    assert derived.next_tickets == ["DAS-9002"]
    assert derived.instruction

    all_green = wr.WaveResults.from_ticket_results(_ticket_results())
    assert all_green.request_satisfied is True
    assert all_green.next_tickets == []
    assert all_green.instruction == ""


def test_ledger_chain_survives_concurrent_appends(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    attestation = tmp_path / "attest" / "a.json"
    attestation.parent.mkdir(parents=True, exist_ok=True)
    attestation.write_text("{}", encoding="utf-8")
    writers = 8

    def append(index: int) -> None:
        wr.append_wave_ledger_entry(
            ledger_path=ledger_path,
            run_id=f"01JWAVECONCURRENT{index:09d}",
            wave=index + 1,
            ticket_ids=[f"DAS-{9000 + index}"],
            attestation_out_path=attestation,
            attestation_bytes=b"{}",
            created_at=_WAVE_TS,
        )

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(append, range(writers)))

    entries = _read_ledger(ledger_path)
    assert len(entries) == writers
    expected_prev = wr._GENESIS_PREV_HASH
    for entry in entries:
        assert entry["prev_hash"] == expected_prev
        assert entry["self_hash"] == wr._ledger_self_hash(entry)
        expected_prev = entry["self_hash"]
