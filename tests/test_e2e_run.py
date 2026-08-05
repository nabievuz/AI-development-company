#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import e2e_run

SAMPLE_PACK = REPO_ROOT / "evals" / "e2e" / "sample-pack"
REAL_RUNS_DIR = REPO_ROOT / "board" / "runs"
E2E_DIR = REPO_ROOT / "evals" / "e2e"


def _copy_pack(tmp_path: Path) -> Path:
    dst = tmp_path / "pack-src" / "acme-tasks"
    shutil.copytree(SAMPLE_PACK, dst)
    return dst


def _extract_inlined_evidence(summary_text: str) -> dict:
    assert "```json" in summary_text, "run-summary.md has no inlined ```json evidence block"
    block = summary_text.split("```json", 1)[1].split("```", 1)[0].strip()
    return json.loads(block)


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_e2e_run_drives_sample_pack_end_to_end(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    summary = e2e_run.e2e_run(pack, run_id="e2e-test-1", runs_dir=runs_dir)


    assert summary["ticket_count"] >= 25
    assert summary["ticket_count"] == 28
    assert summary["pack"] == "acme-tasks"


    assert summary["gates_walked"] == [1, 2, 3, 4, 5, 6]
    assert summary["violations"] == []


    assert summary["health_check"] is True
    assert summary["result"] == "PASS"


def test_run_summary_written_with_inlined_evidence(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    summary = e2e_run.e2e_run(pack, run_id="e2e-test-2", runs_dir=runs_dir)

    summary_path = Path(summary["run_summary_path"])
    assert summary_path == runs_dir / "e2e-test-2" / "run-summary.md"
    assert summary_path.is_file()

    text = summary_path.read_text(encoding="utf-8")

    evidence = _extract_inlined_evidence(text)
    assert evidence["run_id"] == "e2e-test-2"
    assert evidence["pack"] == "acme-tasks"
    assert evidence["result"] == "PASS"
    assert evidence["compiled"]["ticket_count"] == 28
    assert evidence["compiled"]["zero_hand_written"] is True
    assert evidence["compiled"]["hand_written_tickets"] == []
    assert evidence["gate_walk"]["gates_walked"] == [1, 2, 3, 4, 5, 6]
    assert evidence["gate_walk"]["all_goals_all_gates_done"] is True
    assert evidence["gate_walk"]["violations"] == []


    assert evidence["gate_walk"]["negative_probe"]["fired"] is True
    assert evidence["gate_walk"]["negative_probe"]["forced_stage"] >= 2


    for stages in evidence["gate_walk"]["gate_states"].values():
        assert {stages[str(n)] for n in range(1, 7)} == {"done"}


    assert "GATE-1..GATE-6" in text


def test_d5_health_check_recorded_honestly(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    e2e_run.e2e_run(pack, run_id="e2e-test-3", runs_dir=runs_dir)
    text = (runs_dir / "e2e-test-3" / "run-summary.md").read_text(encoding="utf-8")
    health = _extract_inlined_evidence(text)["d5_health_check"]

    assert health["passed"] is True

    assert health["board_lint"]["clean"] is True
    assert health["board_lint"]["violations"] == []
    assert health["board_lint"]["tickets"] == 28

    assert health["workspace_created"] is True
    assert health["probe"]["exit_ok"] is True
    assert health["probe"]["returncode"] == 0

    assert health["pack_tests"]["present"] is False
    assert health["pack_tests"]["passed"] is None

    checklist = health["checklist"]
    assert len(checklist) == 6
    assert all(item["ok"] in (True, None) for item in checklist)
    assert any("board_lint on the delivered board" in item["label"] for item in checklist)
    assert any("gate-walk" in item["label"] for item in checklist)
    assert any("negative probe" in item["label"] for item in checklist)

    assert health["negative_probe"]["fired"] is True


    assert health["probe"]["ephemeral"] is True
    assert "(delivered)" not in " ".join(health["probe"]["command"])


    assert "- [ ] pack-shipped tests: pack ships no runnable test suite" in text


def test_workspace_gc_leaves_only_run_summary(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    e2e_run.e2e_run(pack, run_id="e2e-test-4", runs_dir=runs_dir)

    run_dir = runs_dir / "e2e-test-4"
    assert (run_dir / "run-summary.md").is_file()

    assert not (run_dir / "workspace").exists()


def test_driver_never_writes_real_board_runs_or_evals(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    before_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    before_e2e = _snapshot_tree(E2E_DIR)

    e2e_run.e2e_run(pack, run_id="e2e-test-5", runs_dir=runs_dir)

    after_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    after_e2e = _snapshot_tree(E2E_DIR)


    assert before_runs == after_runs

    assert before_e2e == after_e2e

    assert not (SAMPLE_PACK / "board-tickets").exists()


    assert (runs_dir / "e2e-test-5" / "run-summary.md").is_file()


def test_cli_returns_0_and_writes_summary(tmp_path: Path, capsys) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    rc = e2e_run.main([str(pack), "--run-id", "e2e-cli-1", "--runs-dir", str(runs_dir), "--json"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "PASS"
    assert out["run_id"] == "e2e-cli-1"
    assert Path(out["run_summary_path"]).is_file()
