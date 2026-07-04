#!/usr/bin/env python3
"""tests/test_e2e_run.py — spec->build end-to-end driver (R12 / DAS-1538).

Exercises ``scripts/e2e_run.py`` against a throwaway copy of
``evals/e2e/sample-pack`` in ``tmp_path`` with a tmp runs-dir, and proves the
driver's binding claims:

- the pack compiles to >= 25 self-contained stage-gated tickets (zero hand-written);
- all six AADL gates (GATE-1..GATE-6) are walked to ``done`` in order with ZERO
  gate-order / prod-deploy violations across the walk;
- a ``run-summary.md`` is written with the evidence JSON INLINED in a fenced block;
- the D-5 health-check is recorded HONESTLY (real board_lint result, real probe
  exit code, and ``pack_tests.present == False`` for the docs-only pack); and
- the driver writes NOTHING under the real repo ``board/runs/`` or ``evals/e2e/``.

Every run targets ``tmp_path`` (pack copy + runs-dir), so the committed pack and
the org board are never mutated.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import e2e_run  # noqa: E402

SAMPLE_PACK = REPO_ROOT / "evals" / "e2e" / "sample-pack"
REAL_RUNS_DIR = REPO_ROOT / "board" / "runs"
E2E_DIR = REPO_ROOT / "evals" / "e2e"


def _copy_pack(tmp_path: Path) -> Path:
    """Copy the committed sample-pack into tmp so the driver never sees the original."""
    dst = tmp_path / "pack-src" / "acme-tasks"
    shutil.copytree(SAMPLE_PACK, dst)
    return dst


def _extract_inlined_evidence(summary_text: str) -> dict:
    """Pull the fenced ```json ... ``` evidence block out of run-summary.md."""
    assert "```json" in summary_text, "run-summary.md has no inlined ```json evidence block"
    block = summary_text.split("```json", 1)[1].split("```", 1)[0].strip()
    return json.loads(block)


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    """Map of relative-path -> file bytes for every file under *root* (or {} if absent)."""
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------------------------- #
# The happy path: one pack driven spec->build end to end
# --------------------------------------------------------------------------- #

def test_e2e_run_drives_sample_pack_end_to_end(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    summary = e2e_run.e2e_run(pack, run_id="e2e-test-1", runs_dir=runs_dir)

    # >= 25 compiled tickets (acme-tasks = 4 goals * (1 epic + 6 stages) = 28).
    assert summary["ticket_count"] >= 25
    assert summary["ticket_count"] == 28
    assert summary["pack"] == "acme-tasks"

    # all six gates walked, zero gate-order / deploy violations.
    assert summary["gates_walked"] == [1, 2, 3, 4, 5, 6]
    assert summary["violations"] == []

    # the run passed and the health-check passed honestly.
    assert summary["health_check"] is True
    assert summary["result"] == "PASS"


# --------------------------------------------------------------------------- #
# run-summary.md is written with the evidence inlined, under the tmp runs-dir
# --------------------------------------------------------------------------- #

def test_run_summary_written_with_inlined_evidence(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    summary = e2e_run.e2e_run(pack, run_id="e2e-test-2", runs_dir=runs_dir)

    summary_path = Path(summary["run_summary_path"])
    assert summary_path == runs_dir / "e2e-test-2" / "run-summary.md"
    assert summary_path.is_file()

    text = summary_path.read_text(encoding="utf-8")
    # evidence is inlined (workspace/evidence.json would be gitignored).
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
    # the gate-order checker is proven to DISCRIMINATE (fires on a forced out-of-order
    # state) — so the clean walk above is meaningful, not vacuously empty.
    assert evidence["gate_walk"]["negative_probe"]["fired"] is True
    assert evidence["gate_walk"]["negative_probe"]["forced_stage"] >= 2

    # every compiled goal reached done on all six gates.
    for stages in evidence["gate_walk"]["gate_states"].values():
        assert {stages[str(n)] for n in range(1, 7)} == {"done"}

    # the summary names the actual gate order in prose too.
    assert "GATE-1..GATE-6" in text


# --------------------------------------------------------------------------- #
# The D-5 health-check is recorded HONESTLY (Truth Oath)
# --------------------------------------------------------------------------- #

def test_d5_health_check_recorded_honestly(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    e2e_run.e2e_run(pack, run_id="e2e-test-3", runs_dir=runs_dir)
    text = (runs_dir / "e2e-test-3" / "run-summary.md").read_text(encoding="utf-8")
    health = _extract_inlined_evidence(text)["d5_health_check"]

    assert health["passed"] is True
    # real board_lint result on the DELIVERED board.
    assert health["board_lint"]["clean"] is True
    assert health["board_lint"]["violations"] == []
    assert health["board_lint"]["tickets"] == 28
    # workspace was really created, and the probe really exited 0.
    assert health["workspace_created"] is True
    assert health["probe"]["exit_ok"] is True
    assert health["probe"]["returncode"] == 0
    # the docs-only pack ships no tests — recorded honestly, not fabricated.
    assert health["pack_tests"]["present"] is False
    assert health["pack_tests"]["passed"] is None
    # the checklist labels EXACTLY what was checked, and every applicable check passed.
    checklist = health["checklist"]
    assert len(checklist) == 6  # + the gate-order negative probe
    assert all(item["ok"] in (True, None) for item in checklist)
    assert any("board_lint on the delivered board" in item["label"] for item in checklist)
    assert any("gate-walk" in item["label"] for item in checklist)
    assert any("negative probe" in item["label"] for item in checklist)
    # the gate-order checker is proven able to fire (not a vacuous always-empty check).
    assert health["negative_probe"]["fired"] is True
    # the recorded probe command is the REAL (ephemeral) argv, honestly flagged — not
    # a fabricated non-runnable "(delivered)" label.
    assert health["probe"]["ephemeral"] is True
    assert "(delivered)" not in " ".join(health["probe"]["command"])

    # the rendered checklist marks the not-run pack tests as an unticked box.
    assert "- [ ] pack-shipped tests: pack ships no runnable test suite" in text


# --------------------------------------------------------------------------- #
# The workspace scratch is gc'd; only run-summary.md survives
# --------------------------------------------------------------------------- #

def test_workspace_gc_leaves_only_run_summary(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    e2e_run.e2e_run(pack, run_id="e2e-test-4", runs_dir=runs_dir)

    run_dir = runs_dir / "e2e-test-4"
    assert (run_dir / "run-summary.md").is_file()
    # the scratch workspace is gc'd on close (run_workspace invariant).
    assert not (run_dir / "workspace").exists()


# --------------------------------------------------------------------------- #
# The driver never touches the real board/runs/ or evals/e2e/ in place
# --------------------------------------------------------------------------- #

def test_driver_never_writes_real_board_runs_or_evals(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    before_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    before_e2e = _snapshot_tree(E2E_DIR)

    e2e_run.e2e_run(pack, run_id="e2e-test-5", runs_dir=runs_dir)

    after_runs = sorted(p.name for p in REAL_RUNS_DIR.iterdir()) if REAL_RUNS_DIR.exists() else []
    after_e2e = _snapshot_tree(E2E_DIR)

    # the real org run tree is untouched (the run landed in the tmp runs-dir).
    assert before_runs == after_runs
    # the committed packs are byte-for-byte unchanged (no compile-in-place).
    assert before_e2e == after_e2e
    # and specifically, the committed sample-pack never got a board-tickets/ dir.
    assert not (SAMPLE_PACK / "board-tickets").exists()

    # the run really did land under the tmp runs-dir, not the real one.
    assert (runs_dir / "e2e-test-5" / "run-summary.md").is_file()


# --------------------------------------------------------------------------- #
# The importable driver and CLI agree
# --------------------------------------------------------------------------- #

def test_cli_returns_0_and_writes_summary(tmp_path: Path, capsys) -> None:
    pack = _copy_pack(tmp_path)
    runs_dir = tmp_path / "runs"

    rc = e2e_run.main([str(pack), "--run-id", "e2e-cli-1", "--runs-dir", str(runs_dir), "--json"])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "PASS"
    assert out["run_id"] == "e2e-cli-1"
    assert Path(out["run_summary_path"]).is_file()
