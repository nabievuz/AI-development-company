
from __future__ import annotations

import os
import shutil
from pathlib import Path


def _resolve_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess

        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass

    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()
DEFAULT_RUNS_DIR: Path = _ROOT / "board" / "runs"


WORKSPACE_DIRNAME = "workspace"


def workspace_path(run_id: str, runs_dir: Path | None = None) -> Path:
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    return rd / run_id / WORKSPACE_DIRNAME


def create_workspace(run_id: str, runs_dir: Path | None = None) -> Path:
    ws = workspace_path(run_id, runs_dir)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def gc_workspace(run_id: str, runs_dir: Path | None = None) -> bool:
    ws = workspace_path(run_id, runs_dir)
    if not ws.exists():
        return False
    shutil.rmtree(ws)
    return True
