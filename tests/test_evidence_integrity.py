from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_evidence_gate as ceg
import check_feature_flags as cff
import check_ledger as cl
import check_never_auto_approve as cna
import e2e_run
import feature_flags
import gen_sample_attestation as gen
import wave_runner as wr

RISK_TAXONOMY = REPO_ROOT / "config" / "risk_taxonomy.yaml"
COMMITTED_LEDGER = REPO_ROOT / "board" / "wave-ledger.jsonl"
COMMITTED_ATTESTATIONS = REPO_ROOT / "metrics" / "attestations"

_TS = "2026-07-04T12:00:00Z"
_TS2 = "2026-07-04T13:00:00Z"
_END = "2026-07-04T12:10:00Z"


def _write_ticket(board: Path, ticket_id: str, assignee: str = "backend-eng-1") -> None:
    board.mkdir(parents=True, exist_ok=True)
    (board / f"{ticket_id}-t.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Real ticket\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\ndept: engineering\npriority: p1\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


def _results(ticket_ids: tuple[str, ...]) -> list[wr.TicketResult]:
    common = {
        "outcome": "success",
        "merged_pr": True,
        "ci_status": "green",
        "t7_pass": True,
        "t7_score": 0.9,
        "start": _TS,
        "end": _END,
        "final_status": "done",
        "output": "done",
    }
    return [wr.TicketResult(ticket_id=t, **common) for t in ticket_ids]


def _drive_wave(
    tmp: Path,
    run_id: str,
    ticket_ids: tuple[str, ...] = ("DAS-1001", "DAS-1002"),
    created_at: str = _TS,
    wave: int = 1,
) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    for tid in ticket_ids:
        _write_ticket(board, tid)
    plan = wr.WavePlan(
        run_id=run_id,
        wave=wave,
        goal="honest-wave",
        engine_version="1.0.0",
        tickets=[wr.TicketPlan(t, role="backend-eng-1", model="sonnet") for t in ticket_ids],
    )
    att = wr.run_wave(
        plan,
        wr.replay_executor(_results(ticket_ids)),
        created_at=created_at,
        store_path=tmp / "events.jsonl",
        runs_dir=tmp / "runs",
        attest_dir=tmp / "attest",
        ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board,
        board_dir=board,
        guardrails_dir=REPO_ROOT / "governance" / "guardrails",
    )
    assert att is not None
    return att


def _verify(tmp: Path) -> list[str]:
    return cl.verify_wave_ledger_evidence(
        tmp / "board" / "wave-ledger.jsonl",
        attest_dir=tmp / "attest",
        tickets_dir=tmp / "board" / "tickets",
    )


def _rewrite_ledger(tmp: Path, entries: list[dict]) -> None:
    path = tmp / "board" / "wave-ledger.jsonl"
    path.write_text(
        "".join(
            json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
            for e in entries
        ),
        encoding="utf-8",
    )


def _entries(tmp: Path) -> list[dict]:
    entries, problems = cl.read_wave_ledger(tmp / "board" / "wave-ledger.jsonl")
    assert problems == []
    return entries


def test_honest_wave_ledger_verifies_clean(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    assert _verify(tmp_path) == []


def test_forged_entry_is_rejected(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    entries = _entries(tmp_path)
    entries[0]["ticket_ids"] = ["DAS-1001", "DAS-1002", "DAS-1003"]
    _rewrite_ledger(tmp_path, entries)
    problems = _verify(tmp_path)
    assert any("self_hash" in p for p in problems), problems


def test_broken_chain_link_is_rejected(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001", wave=1, created_at=_TS)
    _drive_wave(tmp_path, "01JHONEST000000000000000002", wave=2, created_at=_TS2)
    entries = _entries(tmp_path)
    assert len(entries) == 2
    _rewrite_ledger(tmp_path, entries[1:])
    problems = _verify(tmp_path)
    assert any("broken chain" in p for p in problems), problems


def test_entry_referencing_a_nonexistent_ticket_is_rejected(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    board = tmp_path / "board" / "tickets"
    (board / "DAS-1002-t.md").unlink()
    problems = _verify(tmp_path)
    assert any("does not exist on the board" in p for p in problems), problems
    assert any("DAS-1002" in p for p in problems), problems


def test_entry_without_tickets_is_rejected(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    entries = _entries(tmp_path)
    entries[0]["ticket_ids"] = []
    entries[0]["self_hash"] = wr._ledger_self_hash(
        {k: v for k, v in entries[0].items() if k != "self_hash"}
    )
    _rewrite_ledger(tmp_path, entries)
    problems = _verify(tmp_path)
    assert any("carries no ticket_ids" in p for p in problems), problems


def test_missing_attestation_is_rejected(tmp_path: Path) -> None:
    att = _drive_wave(tmp_path, "01JHONEST000000000000000001")
    att.path.unlink()
    problems = _verify(tmp_path)
    assert any("no committed attestation" in p for p in problems), problems


def test_cli_exit_codes(tmp_path: Path, capsys) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    ledger = tmp_path / "board" / "wave-ledger.jsonl"
    argv = [
        "--wave-ledger", str(ledger),
        "--attest-dir", str(tmp_path / "attest"),
        "--tickets-dir", str(tmp_path / "board" / "tickets"),
    ]
    assert cl.main(argv) == 0

    entries = _entries(tmp_path)
    entries[0]["wave"] = 99
    _rewrite_ledger(tmp_path, entries)
    assert cl.main(argv) == 1

    assert cl.main(["--wave-ledger", str(tmp_path / "nope.jsonl")]) == 2


def test_empty_ledger_says_there_is_no_evidence(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "wave-ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    assert cl.main(["--wave-ledger", str(ledger), "--attest-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "ZERO attested waves" in out
    assert "NO wave evidence" in out


def test_committed_ledger_carries_no_unverifiable_evidence() -> None:
    entries, problems = cl.read_wave_ledger(COMMITTED_LEDGER)
    assert problems == []
    assert cl.verify_wave_ledger_evidence(
        COMMITTED_LEDGER, attest_dir=COMMITTED_ATTESTATIONS
    ) == []
    for entry in entries:
        for ticket_id in entry.get("ticket_ids", []):
            assert ticket_id in cl.board_ticket_ids(cl.DEFAULT_TICKETS_DIR)


def test_no_fixture_attestation_is_committed() -> None:
    committed = sorted(COMMITTED_ATTESTATIONS.glob("*.json")) if COMMITTED_ATTESTATIONS.is_dir() else []
    assert [p.name for p in committed if cl.is_fixture_run_id(p.stem)] == []
    assert not (COMMITTED_ATTESTATIONS / "01KWS8ATTEST00000000000001.json").exists()


def _fixture(tmp_path: Path) -> wr.WaveAttestation:
    return gen.generate_fixture(
        attest_dir=tmp_path / "attest",
        evidence_dir=tmp_path / "evidence",
        ledger_path=tmp_path / "wave-ledger.jsonl",
    )


def test_fixture_can_never_satisfy_the_real_ledger_verifier(tmp_path: Path) -> None:
    _fixture(tmp_path)
    problems = cl.verify_wave_ledger_evidence(
        tmp_path / "wave-ledger.jsonl",
        attest_dir=tmp_path / "attest",
        tickets_dir=tmp_path / "board",
    )
    assert any("never evidence" in p for p in problems), problems


def test_fixture_attestation_is_rejected_by_the_evidence_gate(tmp_path: Path) -> None:
    _fixture(tmp_path)
    problems = ceg.scan_committed_ledger(
        tmp_path / "wave-ledger.jsonl", tmp_path / "attest", tmp_path / "board"
    )
    assert any("can never satisfy this gate" in p for p in problems), problems


def test_evidence_gate_cli_refuses_a_fixture_ledger(tmp_path: Path) -> None:
    _fixture(tmp_path)
    rc = ceg.main([
        "--attest-dir", str(tmp_path / "attest"),
        "--evidence-dir", str(tmp_path / "evidence"),
        "--wave-ledger", str(tmp_path / "wave-ledger.jsonl"),
        "--tickets-dir", str(tmp_path / "board"),
    ])
    assert rc == 1


def test_evidence_gate_cli_refuses_a_forged_ledger(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    entries = _entries(tmp_path)
    entries[0]["run_id"] = "01JFORGED00000000000000001"
    _rewrite_ledger(tmp_path, entries)
    rc = ceg.main([
        "--attest-dir", str(tmp_path / "attest"),
        "--evidence-dir", str(tmp_path / "evidence"),
        "--wave-ledger", str(tmp_path / "board" / "wave-ledger.jsonl"),
        "--tickets-dir", str(tmp_path / "board" / "tickets"),
    ])
    assert rc == 1


def test_evidence_gate_cli_accepts_an_honest_ledger(tmp_path: Path) -> None:
    _drive_wave(tmp_path, "01JHONEST000000000000000001")
    rc = ceg.main([
        "--attest-dir", str(tmp_path / "attest"),
        "--evidence-dir", str(tmp_path / "evidence"),
        "--wave-ledger", str(tmp_path / "board" / "wave-ledger.jsonl"),
        "--tickets-dir", str(tmp_path / "board" / "tickets"),
    ])
    assert rc == 0


@pytest.mark.parametrize("target", ["attest_dir", "evidence_dir", "ledger_path"])
def test_fixture_generator_refuses_to_write_committed_evidence(tmp_path: Path, target: str) -> None:
    kwargs = {
        "attest_dir": tmp_path / "attest",
        "evidence_dir": tmp_path / "evidence",
        "ledger_path": tmp_path / "wave-ledger.jsonl",
    }
    kwargs[target] = {
        "attest_dir": REPO_ROOT / "metrics" / "attestations",
        "evidence_dir": REPO_ROOT / "metrics" / "evidence",
        "ledger_path": REPO_ROOT / "board" / "wave-ledger.jsonl",
    }[target]
    with pytest.raises(gen.FixtureNamespaceViolation):
        gen.generate_fixture(**kwargs)


def test_fixture_run_id_namespace_is_enforced(tmp_path: Path) -> None:
    with pytest.raises(gen.FixtureNamespaceViolation):
        gen.generate_fixture(
            attest_dir=tmp_path / "attest",
            evidence_dir=tmp_path / "evidence",
            ledger_path=tmp_path / "wave-ledger.jsonl",
            run_id="01JLOOKSREAL0000000000000001",
        )


def test_fixture_cli_requires_an_out_dir() -> None:
    with pytest.raises(SystemExit) as exc:
        gen.main([])
    assert exc.value.code == 2


def _board_with(tmp_path: Path, frontmatter: dict) -> Path:
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-3000-t.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\nBody.\n",
        encoding="utf-8",
    )
    return board


def _approval_rc(tmp_path: Path, frontmatter: dict) -> int:
    board = _board_with(tmp_path, frontmatter)
    return cna.main(["--board", str(board), "--config", str(RISK_TAXONOMY)])


def test_missing_approval_on_a_never_auto_approve_ticket_fails_closed(tmp_path: Path) -> None:
    assert _approval_rc(tmp_path, {"id": "DAS-3000", "ticket_type": "goal"}) == 1


@pytest.mark.parametrize("value", ["", "none", "pending", "TBD", "n/a", "false", True])
def test_placeholder_approvals_fail_closed(tmp_path: Path, value: object) -> None:
    assert _approval_rc(tmp_path, {"id": "DAS-3000", "ticket_type": "goal", "approval": value}) == 1


def test_named_human_approval_passes(tmp_path: Path) -> None:
    assert _approval_rc(
        tmp_path, {"id": "DAS-3000", "ticket_type": "goal", "approval": "human:founder"}
    ) == 0


def test_missing_approval_outside_a_never_auto_approve_category_passes(tmp_path: Path) -> None:
    assert _approval_rc(tmp_path, {"id": "DAS-3000", "ticket_type": "feature"}) == 0


def test_approval_state_classification() -> None:
    assert cna.approval_state({}) == cna.APPROVAL_MISSING
    assert cna.approval_state({"approval": "auto:classifier"}) == cna.APPROVAL_AUTO
    assert cna.approval_state({"approval": "human:founder"}) == cna.APPROVAL_HUMAN
    assert cna.lacks_human_approval({"approval": "auto"}) is True
    assert cna.lacks_human_approval({"approval": "founder"}) is False


def _features_copy(tmp_path: Path, mutate) -> Path:
    data = yaml.safe_load(cff.FEATURES_PATH.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "features.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_committed_feature_flags_match_their_declaration() -> None:
    assert cff.main([]) == 0


def test_declared_defaults_agree_with_feature_flags_module() -> None:
    for flag, default in feature_flags.DEFAULTS.items():
        assert cff.DECLARED_DEFAULTS[flag] == default
    assert set(cff.COMMITTED_OVERRIDES) <= set(cff.DECLARED_DEFAULTS)


def test_flipping_a_committed_flag_without_declaring_it_fails(tmp_path: Path) -> None:
    def flip(data: dict) -> None:
        data["ws_f_heartbeat"] = True

    assert cff.main(["--features", str(_features_copy(tmp_path, flip))]) == 1


def test_turning_a_declared_override_off_without_updating_code_fails(tmp_path: Path) -> None:
    def flip(data: dict) -> None:
        data["ws_g_proof"] = False

    assert cff.main(["--features", str(_features_copy(tmp_path, flip))]) == 1


def test_unknown_committed_flag_fails(tmp_path: Path) -> None:
    def add(data: dict) -> None:
        data["ws_z_undeclared"] = True

    assert cff.main(["--features", str(_features_copy(tmp_path, add))]) == 1


def test_dropping_a_flag_from_the_committed_file_fails(tmp_path: Path) -> None:
    def drop(data: dict) -> None:
        del data["ws_g_proof"]

    assert cff.main(["--features", str(_features_copy(tmp_path, drop))]) == 1


def test_missing_features_file_exits_2(tmp_path: Path) -> None:
    assert cff.main(["--features", str(tmp_path / "nope.yaml")]) == 2


def test_e2e_run_summary_is_labelled_as_a_simulation(tmp_path: Path) -> None:
    evidence = {"run_id": "e2e-x", "checks": e2e_run.CHECKS_GREEN}
    path = e2e_run._write_run_summary(tmp_path, "e2e-x", evidence)
    body = path.read_text(encoding="utf-8")
    document = json.loads(body.split("```json", 1)[1].rsplit("```", 1)[0])
    assert document["delivery_evidence"] is False
    assert document["evidence_class"] == e2e_run.EVIDENCE_CLASS
    assert "NOT delivery evidence" in document["claims"]["does_not_prove"]
    assert document["evidence"] == evidence


def test_simulated_gate_walk_records_that_it_only_rewrote_statuses(tmp_path: Path) -> None:
    board = tmp_path / "board-tickets"
    _write_ticket(board, "DAS-4001")
    walk = e2e_run._simulate_gate_walk(board)
    assert walk["simulated_status_rewrites"] >= 1
    assert walk["does_not_prove"] == e2e_run.GATE_WALK_DOES_NOT_PROVE
    assert "no PR was merged" in walk["does_not_prove"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
