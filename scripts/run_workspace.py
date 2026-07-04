"""run_workspace.py — Run-workspace scratch-dir helper (DAS-1477 / ORGANISM WS4 P16).

Provides the workspace lifecycle for autonomous runs:

  1. **create_workspace(run_id, runs_dir)** — creates
     ``board/runs/<run_id>/workspace/`` at run start.  Idempotent
     (``mkdir(parents=True, exist_ok=True)``).

  2. **gc_workspace(run_id, runs_dir)** — called on run close; deletes the
     entire ``board/runs/<run_id>/workspace/`` subtree while leaving every
     other artifact (notably ``run-summary.md``) intact.

  3. **workspace_path(run_id, runs_dir)** — returns the ``Path`` of the
     workspace directory without creating it.

Design invariants (EXTEND, do not fork):
- Reuses the ``board/runs/<run_id>/`` layout from DAS-1444 (ADR-0023 §2).
- Self-locating root via ``DASLAB_ROOT`` env var or git rev-parse fallback
  (same pattern as ``scripts/pulse_checkpoint.py``).
- ``workspace/`` is scratch-only: it is gitignored by the existing
  ``board/runs/**`` rule and is *never* retained across run close.
- ``run-summary.md`` is NEVER touched by these helpers.
- ``created_at`` is always caller-supplied; these helpers are pure side-effect
  functions (no timestamps generated internally).

Public API
----------
    workspace_path(run_id, runs_dir=None) -> Path
    create_workspace(run_id, runs_dir=None) -> Path
    gc_workspace(run_id, runs_dir=None) -> bool
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Self-locating root (same pattern as scripts/pulse_checkpoint.py)
# ---------------------------------------------------------------------------


def _resolve_root() -> Path:
    """Resolve the repo root (DASLAB_ROOT env → git → relative fallback)."""
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
    # Fallback: scripts/run_workspace.py → scripts/ → repo root
    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()
DEFAULT_RUNS_DIR: Path = _ROOT / "board" / "runs"

# Scratch sub-directory name inside a run's artifact tree.
WORKSPACE_DIRNAME = "workspace"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def workspace_path(run_id: str, runs_dir: Path | None = None) -> Path:
    """Return the workspace path for *run_id* (does not create it).

    Args:
        run_id:   ULID run identifier (ADR-0023 §1).
        runs_dir: Path to ``board/runs/`` (default: canonical).

    Returns:
        ``board/runs/<run_id>/workspace/`` as a ``Path``.
    """
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    return rd / run_id / WORKSPACE_DIRNAME


def create_workspace(run_id: str, runs_dir: Path | None = None) -> Path:
    """Create ``board/runs/<run_id>/workspace/`` at run start.

    Idempotent — safe to call even if the workspace already exists
    (uses ``mkdir(parents=True, exist_ok=True)``).  Also ensures the
    parent run directory exists.

    Args:
        run_id:   ULID run identifier.
        runs_dir: Path to ``board/runs/`` (default: canonical).

    Returns:
        The ``Path`` of the created (or already-existing) workspace directory.
    """
    ws = workspace_path(run_id, runs_dir)
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def gc_workspace(run_id: str, runs_dir: Path | None = None) -> bool:
    """Garbage-collect ``board/runs/<run_id>/workspace/`` on run close.

    Deletes the entire workspace subtree while leaving every other artifact
    in ``board/runs/<run_id>/`` intact — notably ``run-summary.md``.
    Idempotent: returns ``False`` if the workspace did not exist; ``True``
    if it was deleted.

    Args:
        run_id:   ULID run identifier.
        runs_dir: Path to ``board/runs/`` (default: canonical).

    Returns:
        ``True`` if the workspace was deleted, ``False`` if it was not present.
    """
    ws = workspace_path(run_id, runs_dir)
    if not ws.exists():
        return False
    shutil.rmtree(ws)
    return True
