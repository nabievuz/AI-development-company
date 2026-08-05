
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import run_workspace as rw

RUN_ID = "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"


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

        assert str(p).startswith(str(runs_dir))

    def test_path_does_not_create_directory(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert not p.exists(), "workspace_path() must not create the directory"

    def test_structure_is_runs_runid_workspace(self, tmp_path):
        runs_dir = tmp_path / "runs"
        p = rw.workspace_path(RUN_ID, runs_dir)
        assert p == runs_dir / RUN_ID / "workspace"


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
        runs_dir = tmp_path / "runs"
        ws1 = rw.create_workspace(RUN_ID, runs_dir)
        ws2 = rw.create_workspace(RUN_ID, runs_dir)
        assert ws1 == ws2
        assert ws1.exists()

    def test_idempotent_second_call_contents_preserved(self, tmp_path):
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)
        scratch = ws / "intermediate.json"
        scratch.write_text('{"step": 1}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        assert scratch.exists(), "create_workspace() must not clear existing workspace"

    def test_creates_parent_run_dir(self, tmp_path):
        runs_dir = tmp_path / "runs"
        rw.create_workspace(RUN_ID, runs_dir)
        run_dir = runs_dir / RUN_ID
        assert run_dir.exists() and run_dir.is_dir()

    def test_works_when_runs_dir_does_not_exist(self, tmp_path):
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

        result = rw.gc_workspace(RUN_ID, runs_dir)
        assert result is False

    def test_idempotent_second_gc_returns_false(self, tmp_path):
        runs_dir = tmp_path / "runs"
        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)
        result = rw.gc_workspace(RUN_ID, runs_dir)
        assert result is False

    def test_gc_leaves_run_summary_intact(self, tmp_path):
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
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / RUN_ID
        run_dir.mkdir(parents=True)
        manifest = run_dir / "manifest.json"
        manifest.write_text('{"run_id": "test"}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)

        assert manifest.exists(), "gc_workspace() must not delete manifest.json"

    def test_gc_leaves_checkpoint_files_intact(self, tmp_path):
        runs_dir = tmp_path / "runs"
        run_dir = runs_dir / RUN_ID
        run_dir.mkdir(parents=True)
        cp = run_dir / "wave-001.checkpoint.json"
        cp.write_text('{"wave": 1}', encoding="utf-8")

        rw.create_workspace(RUN_ID, runs_dir)
        rw.gc_workspace(RUN_ID, runs_dir)

        assert cp.exists(), "gc_workspace() must not delete checkpoint files"

    def test_gc_deletes_workspace_contents_recursively(self, tmp_path):
        runs_dir = tmp_path / "runs"
        ws = rw.create_workspace(RUN_ID, runs_dir)


        nested = ws / "step1" / "data"
        nested.mkdir(parents=True)
        (nested / "output.json").write_text('{}', encoding="utf-8")
        (ws / "log.txt").write_text("intermediate log", encoding="utf-8")

        rw.gc_workspace(RUN_ID, runs_dir)

        assert not ws.exists(), "gc_workspace() must remove the entire workspace tree"
        assert not (ws / "log.txt").exists()
        assert not nested.exists()

    def test_gc_does_not_affect_sibling_run(self, tmp_path):
        runs_dir = tmp_path / "runs"
        run_a = "01AAAAAAAAAAAAAAAAAAAAAAAA"
        run_b = "01BBBBBBBBBBBBBBBBBBBBBBBB"

        ws_a = rw.create_workspace(run_a, runs_dir)
        ws_b = rw.create_workspace(run_b, runs_dir)

        rw.gc_workspace(run_a, runs_dir)

        assert not ws_a.exists(), "run_a workspace should be GC'd"
        assert ws_b.exists(), "run_b workspace must be untouched"


class TestGitignore:
    def test_workspace_file_is_gitignored(self):
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

        assert result.returncode == 1, (
            "board/runs/*/run-summary.md IS gitignored but should be retained — "
            "check the !board/runs/*/run-summary.md negation in .gitignore"
        )
