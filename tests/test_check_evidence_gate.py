
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_evidence_gate as ceg
import wave_runner as wr

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "ws_g_evidence_gate"

_WAVE_TS = "2026-07-24T12:00:00Z"
_END_TS = "2026-07-24T12:10:00Z"
_CREATED_AT = "2026-07-24T12:41:00Z"


def _write_ticket(board: Path, ticket_id: str, assignee: str) -> None:
    board.mkdir(parents=True, exist_ok=True)
    (board / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\ndept: engineering\npriority: p1\n"
        "---\n\n## Description\nSynthetic.\n",
        encoding="utf-8",
    )


def _drive(tmp: Path, run_id: str, *, counted: bool = True) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9101", "backend-eng-1")
    _write_ticket(board, "DAS-9102", "backend-eng-2")
    common = {
        "outcome": "success",
        "merged_pr": counted,
        "ci_status": "green" if counted else "red",
        "t7_pass": counted,
        "t7_score": 0.95 if counted else 0.0,
        "start": _WAVE_TS,
        "end": _END_TS,
        "final_status": "done",
        "output": "done; tests green." if counted else "not merged.",
    }
    plan = wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="ws-g-evidence-gate-fixture",
        engine_version="1.0.0",
        tickets=[
            wr.TicketPlan("DAS-9101", "backend-eng-1", "opus"),
            wr.TicketPlan("DAS-9102", "backend-eng-2", "sonnet"),
        ],
    )
    results = wr.WaveResults(
        tickets=[
            wr.TicketResult(ticket_id="DAS-9101", **common),
            wr.TicketResult(ticket_id="DAS-9102", **common),
        ]
    )
    att = wr.run_wave(
        plan,
        results,
        created_at=_WAVE_TS,
        store_path=tmp / "events.jsonl",
        runs_dir=tmp / "runs",
        attest_dir=tmp / "attest",
        ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def _write_delivery_fixtures(
    tmp: Path,
    *,
    gates_closed: bool = True,
    diagnostics_ok: bool = True,
    golden_ok: bool = True,
    golden_present: bool = True,
    anti_gaming_ok: bool = True,
) -> None:
    fixtures = tmp / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)


    gate_lines = [f"Gate-{g}: {'closed' if gates_closed else 'open'}" for g in range(1, 7)]
    (fixtures / "stage-board.md").write_text("\n".join(gate_lines) + "\n", encoding="utf-8")


    (fixtures / "diagnostics.json").write_text(
        json.dumps({"score": 100 if diagnostics_ok else 90, "max": 100, "clean_tree": True}),
        encoding="utf-8",
    )


    if golden_present:
        (fixtures / "golden-eval.json").write_text(
            json.dumps({"accuracy": 0.95 if golden_ok else 0.5, "bar": 0.8}),
            encoding="utf-8",
        )


    (fixtures / "impl.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    if anti_gaming_ok:
        test_src = "from impl import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    else:
        test_src = "def test_add():\n    assert True\n"
    (fixtures / "test_impl.py").write_text(test_src, encoding="utf-8")


def _load_fixture(name: str, run_id: str | None = None) -> dict:
    payload = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    if run_id is not None:
        payload["run_id"] = payload["run_id"].replace("__RUN_ID__", run_id)
    return payload


def _write_scorecard(tmp: Path, name: str, run_id: str | None = None) -> Path:
    payload = _load_fixture(name, run_id)
    path = tmp / "scorecard.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _flag_on(tmp: Path) -> Path:
    path = tmp / "features.yaml"
    path.write_text("ws_g_proof: true\n", encoding="utf-8")
    return path


def _flag_off(tmp: Path) -> Path:
    path = tmp / "features.yaml"
    path.write_text("ws_g_proof: false\n", encoding="utf-8")
    return path


def _run(tmp: Path, scorecard: Path | None, flags: Path) -> int:
    argv = [
        "--attest-dir", str(tmp / "attest"),
        "--evidence-dir", str(tmp / "evidence"),
        "--created-at", _CREATED_AT,
        "--features", str(flags),
    ]
    if scorecard is not None:
        argv += ["--scorecard", str(scorecard)]
    return ceg.main(argv)


def test_flag_off_inert_even_with_a_scorecard(tmp_path: Path, capsys) -> None:
    att = _drive(tmp_path, "01JEVID0000000000000000001")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_off(tmp_path))
    assert rc == 0
    assert "inert" in capsys.readouterr().out
    assert not (tmp_path / "attest" / f"{att.run_id}.delivery.json").exists()


def test_no_scorecard_inert_on_empty_board(tmp_path: Path, capsys) -> None:
    rc = _run(tmp_path, None, _flag_on(tmp_path))
    assert rc == 0
    assert "inert" in capsys.readouterr().out


def test_uncorroborated_all_pass_self_report_never_reaches_complete(tmp_path: Path) -> None:
    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000002")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    assert receipt_path.is_file()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["schema"] == ceg.DELIVERY_SCHEMA
    assert payload["verdict"] == "incomplete"
    for dim in ("merged_pr_green_ci", "wave_attestation", "anti_gaming_probe"):
        assert payload["dimensions"][dim] == "pass"
    for dim in ("aadl_gates_closed", "diagnostics_100", "golden_eval"):
        assert payload["dimensions"][dim] == "skipped"
    assert payload["counts"]["counted_tickets"] == 2


    att_payload = wr.load_attestation(att.path)
    assert payload["attest_chain"]["prev"] == wr._sha256(att_payload)


    assert not ceg.verify_receipt(payload, tmp_path / "attest", tmp_path / "evidence")


_SINGLE_DIMENSION_DELIVERY_KWARGS: dict[str, dict[str, bool]] = {
    "missing_d1.json": {"gates_closed": False},
    "missing_d4.json": {"diagnostics_ok": False},
    "missing_d5_skipped.json": {"golden_present": False},
    "missing_d6.json": {"anti_gaming_ok": False},
}


@pytest.mark.parametrize(
    "fixture_name",
    [
        "missing_d1.json",
        "missing_d4.json",
        "missing_d5_skipped.json",
        "missing_d6.json",
    ],
)
def test_single_dimension_fail_or_skip_rejects_green(tmp_path: Path, fixture_name: str) -> None:
    _write_delivery_fixtures(tmp_path, **_SINGLE_DIMENSION_DELIVERY_KWARGS[fixture_name])
    att = _drive(tmp_path, "01JEVID0000000000000000003")
    scorecard = _write_scorecard(tmp_path, fixture_name, att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"


def test_d3_missing_attestation_rejects_green(tmp_path: Path) -> None:

    _write_delivery_fixtures(tmp_path)
    scorecard = _write_scorecard(tmp_path, "missing_d3_no_attestation.json")
    (tmp_path / "attest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    scorecard_payload = json.loads(scorecard.read_text(encoding="utf-8"))
    run_id = scorecard_payload["run_id"]
    receipt_path = tmp_path / "attest" / f"{run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"
    assert payload["dimensions"]["wave_attestation"] == "fail"
    assert payload["attest_chain"]["prev"] == wr._GENESIS_PREV_HASH


def test_d2_forged_cross_check_rejects_green(tmp_path: Path) -> None:

    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000004", counted=False)
    scorecard = _write_scorecard(tmp_path, "missing_d2_forged.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"
    assert payload["dimensions"]["merged_pr_green_ci"] == "fail"
    assert payload["counts"]["counted_tickets"] == 0


def test_forged_all_pass_scorecard_with_no_real_d1_d4_d5_d6_artifacts_rejected(
    tmp_path: Path,
) -> None:


    att = _drive(tmp_path, "01JEVIDFORGE00000000000001")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"

    assert payload["dimensions"]["merged_pr_green_ci"] == "pass"
    assert payload["dimensions"]["wave_attestation"] == "pass"


    for dim in ("aadl_gates_closed", "diagnostics_100", "golden_eval", "anti_gaming_probe"):
        assert payload["dimensions"][dim] == "skipped", (dim, payload["dimensions"][dim])


def test_forged_scorecard_disagreeing_with_real_artifacts_rejected(tmp_path: Path) -> None:
    _write_delivery_fixtures(tmp_path, gates_closed=False, diagnostics_ok=False)
    att = _drive(tmp_path, "01JEVIDFORGE00000000000002")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"
    assert payload["dimensions"]["aadl_gates_closed"] == "fail"
    assert payload["dimensions"]["diagnostics_100"] == "fail"


def test_das1594_fabricated_plausible_fixtures_forge_rejected(tmp_path: Path) -> None:


    _write_delivery_fixtures(
        tmp_path, gates_closed=True, diagnostics_ok=True, golden_ok=True, anti_gaming_ok=True
    )
    att = _drive(tmp_path, "01JEVIDFORGE00000000000003")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0, "a plausible-but-unattested D1/D4/D5 fixture forge MUST be rejected"

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"

    assert payload["dimensions"]["merged_pr_green_ci"] == "pass"
    assert payload["dimensions"]["wave_attestation"] == "pass"


    for dim in ("aadl_gates_closed", "diagnostics_100", "golden_eval"):
        assert payload["dimensions"][dim] == "skipped", (dim, payload["dimensions"][dim])


def test_empty_delivery_scores_zero(tmp_path: Path) -> None:
    scorecard = _write_scorecard(tmp_path, "empty_delivery.json")
    (tmp_path / "attest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    scorecard_payload = json.loads(scorecard.read_text(encoding="utf-8"))
    receipt_path = tmp_path / "attest" / f"{scorecard_payload['run_id']}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "incomplete"


    assert all(status != "pass" for status in payload["dimensions"].values())
    assert payload["dimensions"]["wave_attestation"] == "fail"


def test_dimension_statuses_defaults_missing_to_skipped() -> None:
    scorecard = {"schema": ceg.SCORECARD_SCHEMA, "run_id": "x", "dimensions": []}
    statuses = ceg.dimension_statuses(scorecard)
    assert set(statuses) == set(ceg.SIX_DIMENSIONS)
    assert all(v == "skipped" for v in statuses.values())


def test_verdict_of_any_skip_or_fail_is_incomplete() -> None:
    all_pass = dict.fromkeys(ceg.SIX_DIMENSIONS, "pass")
    assert ceg.verdict_of(all_pass) == "complete"
    for dim in ceg.SIX_DIMENSIONS:
        one_skip = dict(all_pass)
        one_skip[dim] = "skipped"
        assert ceg.verdict_of(one_skip) == "incomplete"
        one_fail = dict(all_pass)
        one_fail[dim] = "fail"
        assert ceg.verdict_of(one_fail) == "incomplete"


def test_tampered_receipt_self_hash_fails(tmp_path: Path) -> None:
    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000005")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    _run(tmp_path, scorecard, _flag_on(tmp_path))

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert not ceg.verify_receipt(payload, tmp_path / "attest", tmp_path / "evidence")
    payload["counts"]["counted_tickets"] = 99
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


    rc = _run(tmp_path, None, _flag_on(tmp_path))
    assert rc != 0


def test_tampered_prev_link_fails(tmp_path: Path) -> None:
    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000006")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    _run(tmp_path, scorecard, _flag_on(tmp_path))

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["attest_chain"]["prev"] = "sha256:" + "ab" * 32
    payload["attest_chain"]["self"] = ""
    payload["attest_chain"]["self"] = wr._attest_self_hash(payload)
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc = _run(tmp_path, None, _flag_on(tmp_path))
    assert rc != 0


def test_forged_counts_disagreeing_with_evidence_fails(tmp_path: Path) -> None:


    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000007")
    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    _run(tmp_path, scorecard, _flag_on(tmp_path))

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["counts"]["counted_tickets"] = 0
    payload["attest_chain"]["self"] = ""
    payload["attest_chain"]["self"] = wr._attest_self_hash(payload)
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    errs = ceg.verify_receipt(payload, tmp_path / "attest", tmp_path / "evidence")
    assert any("counted_tickets" in e for e in errs)
    rc = _run(tmp_path, None, _flag_on(tmp_path))
    assert rc != 0


def test_dangling_wave_chain_rejects_new_delivery(tmp_path: Path) -> None:

    _write_delivery_fixtures(tmp_path)
    att = _drive(tmp_path, "01JEVID0000000000000000008")
    att_payload = wr.load_attestation(att.path)
    att_payload["mechanics"]["checkpoint_open"] = False
    att.path.write_text(json.dumps(att_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    scorecard = _write_scorecard(tmp_path, "all_pass.json", att.run_id)
    rc = _run(tmp_path, scorecard, _flag_on(tmp_path))
    assert rc != 0

    receipt_path = tmp_path / "attest" / f"{att.run_id}.delivery.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["dimensions"]["wave_attestation"] == "fail"


def test_corrupt_scorecard_json_fails(tmp_path: Path) -> None:
    (tmp_path / "attest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)
    bad = tmp_path / "scorecard.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = _run(tmp_path, bad, _flag_on(tmp_path))
    assert rc == 1


def test_wrong_schema_scorecard_fails(tmp_path: Path) -> None:
    (tmp_path / "attest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)
    bad = tmp_path / "scorecard.json"
    bad.write_text(json.dumps({"schema": "not.the.right.schema"}), encoding="utf-8")
    rc = _run(tmp_path, bad, _flag_on(tmp_path))
    assert rc == 1


def test_six_dimension_names_are_fixed() -> None:
    assert ceg.SIX_DIMENSIONS == (
        "aadl_gates_closed",
        "merged_pr_green_ci",
        "wave_attestation",
        "diagnostics_100",
        "golden_eval",
        "anti_gaming_probe",
    )
    assert ceg.DELIVERY_SCHEMA == "daslab.delivery_attestation.v1"
    assert ceg.SCORECARD_SCHEMA == "daslab.delivery_scorecard.v1"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
