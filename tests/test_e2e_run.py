#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import e2e_run
import gateway_compile as gc
import stage_gate as sg

SAMPLE_PACK = REPO_ROOT / "evals" / "e2e" / "sample-pack"
REAL_RUNS_DIR = REPO_ROOT / "board" / "runs"
E2E_DIR = REPO_ROOT / "evals" / "e2e"


def _copy_pack(tmp_path: Path) -> Path:
    dst = tmp_path / "pack-src" / "acme-tasks"
    shutil.copytree(SAMPLE_PACK, dst)
    return dst


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _stage_ticket(board: Path, ticket_id: str, stage: int, status: str = "todo") -> None:
    board.mkdir(parents=True, exist_ok=True)
    approval_line = "approval: human:founder\n" if stage == 5 else ""
    (board / f"{ticket_id}-t.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        f"title: Stage {stage} ticket\n"
        f"status: {status}\n"
        "goal: acme-goal\n"
        f"stage: GATE-{stage}\n"
        f"{approval_line}"
        "assignee: backend-eng-1\n"
        "author: cto\ndept: engineering\npriority: p1\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )


def _six_stage_board_without_gate5_approval(tmp_path: Path) -> Path:
    board = tmp_path / "board-tickets"
    for stage in range(1, 7):
        _stage_ticket(board, f"DAS-40{stage:02d}", stage)
    gate5 = board / "DAS-4005-t.md"
    gate5.write_text(
        gate5.read_text(encoding="utf-8").replace("approval: human:founder\n", ""),
        encoding="utf-8",
    )
    return board


def _six_stage_board(tmp_path: Path) -> Path:
    board = tmp_path / "board-tickets"
    for stage in range(1, 7):
        _stage_ticket(board, f"DAS-40{stage:02d}", stage)
    return board


def test_committed_sample_pack_no_longer_compiles(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    result = gc.run_pipeline(pack, projects_dir=tmp_path / "projects")
    assert result.ok is False
    assert result.rejected_stage == "validate"
    assert any("docs/" in str(e) for e in result.errors)


def test_driver_refuses_an_incomplete_pack_instead_of_claiming_a_pass(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"
    with pytest.raises(RuntimeError) as exc:
        e2e_run.e2e_run(pack, run_id="e2e-test-1", runs_dir=runs_dir)
    assert "compile rejected" in str(exc.value)
    assert not (runs_dir / "e2e-test-1" / "run-summary.md").exists()


def test_cli_exits_2_and_writes_no_summary_for_an_uncompilable_pack(tmp_path: Path, capsys) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"
    rc = e2e_run.main([str(pack), "--run-id", "e2e-cli-1", "--runs-dir", str(runs_dir), "--json"])
    assert rc == 2
    assert not (runs_dir / "e2e-cli-1").exists()
    assert "ERROR" in capsys.readouterr().err


def test_missing_pack_dir_exits_2(tmp_path: Path) -> None:
    assert e2e_run.main([str(tmp_path / "nope")]) == 2


def test_driver_never_writes_real_board_runs_or_evals(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    before_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    before_e2e = _snapshot_tree(E2E_DIR)

    e2e_run.main([str(pack), "--run-id", "e2e-test-5", "--runs-dir", str(tmp_path / "runs")])

    after_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    assert before_runs == after_runs
    assert before_e2e == _snapshot_tree(E2E_DIR)
    assert not (SAMPLE_PACK / "board-tickets").exists()


def test_simulated_gate_walk_advances_every_stage_in_order(tmp_path: Path) -> None:
    board = _six_stage_board(tmp_path)
    walk = e2e_run._simulate_gate_walk(board)

    assert walk["gates_walked"] == [1, 2, 3, 4, 5, 6]
    assert walk["violations"] == []
    assert walk["all_goals_all_gates_done"] is True
    assert walk["simulated_status_rewrites"] == 6
    assert [s["tickets_advanced"] for s in walk["per_stage"]] == [1, 1, 1, 1, 1, 1]


def test_simulated_gate_walk_refuses_a_gate5_close_with_no_human_approval(
    tmp_path: Path,
) -> None:
    board = _six_stage_board_without_gate5_approval(tmp_path)
    walk = e2e_run._simulate_gate_walk(board)
    assert any(
        "DAS-4005" in v and "no named human approval" in v for v in walk["violations"]
    )


def test_simulated_gate_walk_declares_what_it_does_not_prove(tmp_path: Path) -> None:
    walk = e2e_run._simulate_gate_walk(_six_stage_board(tmp_path))
    assert walk["proves"] == e2e_run.GATE_WALK_PROVES
    assert walk["does_not_prove"] == e2e_run.GATE_WALK_DOES_NOT_PROVE
    assert "NOT delivery evidence" in walk["does_not_prove"]


def test_negative_probe_fires_on_a_forced_out_of_order_state(tmp_path: Path) -> None:
    board = _six_stage_board(tmp_path)
    probe = e2e_run._negative_gate_probe(board)
    assert probe["fired"] is True
    assert probe["forced_stage"] >= 2
    assert probe["sample_violation"]


def test_simulated_status_rewrite_only_touches_the_status_field(tmp_path: Path) -> None:
    board = _six_stage_board(tmp_path)
    path = board / "DAS-4003-t.md"
    before = path.read_text(encoding="utf-8")
    e2e_run._simulate_status_done(path)
    after = path.read_text(encoding="utf-8")
    assert before.replace("status: todo", "status: done") == after
    assert sg.stage_of({"stage": "GATE-3"}) == 3


def test_run_summary_is_json_only_and_marked_not_delivery_evidence(tmp_path: Path) -> None:
    evidence = {"run_id": "e2e-json", "checks": e2e_run.CHECKS_GREEN, "gate_walk": {}}
    path = e2e_run._write_run_summary(tmp_path, "e2e-json", evidence)

    text = path.read_text(encoding="utf-8")
    assert text.startswith("```json")
    document = json.loads(text.split("```json", 1)[1].rsplit("```", 1)[0])
    assert document["delivery_evidence"] is False
    assert document["evidence_class"] == e2e_run.EVIDENCE_CLASS
    assert document["kind"] == "e2e-gate-checker-simulation"
    assert "PASS" not in text
    assert "D-5 deploy" not in text


def test_render_never_presents_the_run_as_delivery_evidence() -> None:
    rendered = e2e_run._render(
        {
            "pack": "acme-tasks",
            "run_id": "e2e-x",
            "ticket_count": 3,
            "gates_walked": [1, 2, 3, 4, 5, 6],
            "violations": [],
            "health_check": True,
            "run_summary_path": "/tmp/run-summary.md",
            "checks": e2e_run.CHECKS_GREEN,
        }
    )
    assert "NOT DELIVERY EVIDENCE" in rendered
    assert "checks-green" in rendered
    assert "RESULT: PASS" not in rendered


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
