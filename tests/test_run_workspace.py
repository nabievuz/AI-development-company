"""tests/test_run_workspace.py — pytest suite for scripts/run_workspace.py.

Coverage:
- workspace_path(): returns correct path without creating it
- create_workspace(): creates the directory; is idempotent; creates parents
- gc_workspace(): deletes workspace, leaves run-summary.md intact; is idempotent
- Workspace files are left untouched by gc_workspace beyond deletion
- board/runs/<run_id>/workspace/ is gitignored (ADR-0023 §5)
- run-summary.md is NOT gitignored (already tested in test_pulse_checkpoint.py;
  included here for completeness in the workspace context)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of pytest invocation root.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_workspace as rw  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

RUN_ID = "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"


# ---------------------------------------------------------------------------
# TestWorkspacePath
# ---------------------------------------------------------------------------


class TestWorkspacePath:
    def test_path_contains_run_id(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert RUN_ID in str(p)

    def test_path_ends_with_workspace(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert p.name == "workspace"

    def test_path_is_inside_runs_dir(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        # workspace_path should be a descendant of runs_dir
        assert str(p).startswith(str(runs_dir))

    def test_path_does_not_create_directory(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert not p.exists(), "workspace_path() must not create the directory"

    def test_structure_is_runs_runid_workspace(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert p == runs_dir / RUN_ID / "workspace"


# ---------------------------------------------------------------------------
# TestCreateWorkspace
# ---------------------------------------------------------------------------


class TestCreateWorkspace:
    def test_creates_directory(self, tmp_path):
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)
        assert ws.exists()
        assert ws.is_dir()

    def test_returns_workspace_path(self, tmp_path):
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)
        assert ws == rw.workspace_path(RUN_ID, runs_dir)

    def test_idempotent_second_call_succeeds(self, tmp_path):
        """Calling create_workspace twice on the same run must not raise."""
        runs_dir = tmp_path / "runs"
        ws1 = rw.create_workspace(RUN_ID, runs_dir)
        ws2 = rw.create_workspace(RUN_ID, runs_dir)
        assert ws1 == ws2
        assert ws1.exists()

    def test_idempotent_second_call_contents_preserved(self, tmp_path):
        """Files written to the workspace survive a second create_workspace call."""
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)
        scratch = ws / "intermediate.json"
        scratch.write_text('{"step": 1}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)  # second call
        assert scratch.exists(), "create_workspace() must not clear existing workspace"

    def test_creates_parent_run_dir(self, tmp_path):
        """Parent run dir (board/runs/<run_id>/) must be created along with workspace."""
        runs_dir = tmp_path / "runs"
        rw.create_workspace(RUN_ID, runs_dir)
        run_dir = runs_dir / RUN_ID
        assert run_dir.exists() and run_dir.is_dir()

    def test_works_when_runs_dir_does_not_exist(self, tmp_path):
        """The entire runs/<run_id>/workspace/ tree is created from scratch."""
        runs_dir = tmp_path / "totally" / "new" / "runs"
        assert not runs_dir.exists()
        ws = rw.create_workspace(RUN_ID, runs_dir)
        assert ws.exists()

    def test_different_run_ids_get_separate_workspaces(self, tmp_path):
        runs_dir = tmp_path / "runs"
        run_a = "01AAAAAAAAAAAAAAAAAAAAAAAA"
        run_b = "01BBBBBBBBBBBBBBBBBBBBBBBB"
        ws_a = rw.create_workspace(run_a, runs_dir)
        ws_b = rw.create_workspace(run_b, runs_dir)
        assert ws_a != ws_b
        assert ws_a.exists()
        assert ws_b.exists()


# ---------------------------------------------------------------------------
# TestGCWorkspace
# ---------------------------------------------------------------------------


class TestGCWorkspace:
    def test_deletes_workspace(self, tmp_path):
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)
        assert ws.exists()
        rw.gc_workspace(RUN_ID, runs_dir)
        assert not ws.exists()

    def test_returns_true_when_workspace_deleted(self, tmp_path):
        runs_dir = tmp_path / "runs"
        rw.create_workspace(RUN_ID, runs_dir)
        result = rw.gc_workspace(RUN_ID, runs_dir)
        assert result is True

    def test_returns_false_when_no_workspace(self, tmp_path):
        runs_dir = tmp_path / "runs"
        # No workspace created — gc should be a no-op
        result = rw.gc_workspace(RUN_ID, runs_dir)
        assert result is False

    def test_idempotent_second_gc_returns_false(self, tmp_path):
        runs_dir = tmp_path / "runs"
        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)  # first GC
        result = rw.gc_workspace(RUN_ID, runs_dir)  # second GC (no-op)
        assert result is False

    def test_gc_leaves_run_summary_intact(self, tmp_path):
        """GC must not touch run-summary.md alongside the workspace."""
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / RUN_ID
        run_dir.mkdir(parents=True)
        summary = run_dir / "run-summary.md"
        summary.write_text("# Run Summary\noutcome: success\n", encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)

        assert summary.exists(), "gc_workspace() must not delete run-summary.md"
        assert "outcome: success" in summary.read_text(encoding="utf-8")

    def test_gc_leaves_manifest_intact(self, tmp_path):
        """GC must not touch manifest.json alongside the workspace."""
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / RUN_ID
        run_dir.mkdir(parents=True)
        manifest = run_dir / "manifest.json"
        manifest.write_text('{"run_id": "test"}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)

        assert manifest.exists(), "gc_workspace() must not delete manifest.json"

    def test_gc_leaves_checkpoint_files_intact(self, tmp_path):
        """GC must not touch wave checkpoint files alongside the workspace."""
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / RUN_ID
        run_dir.mkdir(parents=True)
        cp = run_dir / "wave-001.checkpoint.json"
        cp.write_text('{"wave": 1}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)

        assert cp.exists(), "gc_workspace() must not delete checkpoint files"

    def test_gc_deletes_workspace_contents_recursively(self, tmp_path):
        """GC must delete the entire workspace subtree, not just the top dir."""
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)

        # Populate the workspace with nested files
        nested = ws / "step1" / "data"
        nested.mkdir(parents=True)
        (nested / "output.json").write_text('{}', encoding="utf-8")
        (ws / "log.txt").write_text("intermediate log", encoding="utf-8")

        rw.gc_workspace(RUN_ID, runs_dir)

        assert not ws.exists(), "gc_workspace() must remove the entire workspace tree"
        assert not (ws / "log.txt").exists()
        assert not nested.exists()

    def test_gc_does_not_affect_sibling_run(self, tmp_path):
        """GC'ing one run's workspace must not touch another run's files."""
        runs_dir = tmp_path / "runs"
        run_a = "01AAAAAAAAAAAAAAAAAAAAAAAA"
        run_b = "01BBBBBBBBBBBBBBBBBBBBBBBB"

        ws_a = rw.create_workspace(run_a, runs_dir)
        ws_b = rw.create_workspace(run_b, runs_dir)

        rw.gc_workspace(run_a, runs_dir)

        assert not ws_a.exists(), "run_a workspace should be GC'd"
        assert ws_b.exists(), "run_b workspace must be untouched"


# ---------------------------------------------------------------------------
# TestGitignore
# ---------------------------------------------------------------------------


class TestGitignore:
    def test_workspace_file_is_gitignored(self):
        """Files inside board/runs/<run_id>/workspace/ must be gitignored.

        The existing rule ``board/runs/**`` + ``!board/runs/*/`` keeps
        run-id sub-directories traversable while gitignoring everything inside
        them except ``run-summary.md``.  The workspace/ subdir and its contents
        are covered by this rule (ADR-0023 §5).
        """
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                f"board/runs/{RUN_ID}/workspace/scratch.json",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "board/runs/<run_id>/workspace/scratch.json is NOT gitignored — "
            "the board/runs/** rule should cover it (ADR-0023 §5)"
        )

    def test_workspace_directory_is_gitignored(self):
        """The workspace/ directory itself must be gitignored."""
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                f"board/runs/{RUN_ID}/workspace",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "board/runs/<run_id>/workspace is NOT gitignored — "
            "check the board/runs/** rule in .gitignore"
        )

    def test_run_summary_is_not_gitignored(self):
        """run-summary.md must remain tracked (NOT gitignored) per ADR-0023 §5."""
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                f"board/runs/{RUN_ID}/run-summary.md",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        # returncode 1 = "not ignored" — correct for run-summary.md
        assert result.returncode == 1, (
            "board/runs/*/run-summary.md IS gitignored but should be retained — "
            "check the !board/runs/*/run-summary.md negation in .gitignore"
        )
