#!/usr/bin/env python3
"""tests/test_check_approved_goal_queue.py — QONUN-3 queue enforcement (ADR-0014 / ADR-0002).

Covers layer A (queue integrity) and layer B (local ticket→queue mapping): an approved
queue passes, an unapproved queue fails, a project without a queue is not a violation,
the empty/absent projects/ tree passes (CI state), a project-scoped past-backlog ticket
needs an approved queue, and the REAL repo passes.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_approved_goal_queue as q  # noqa: E402  (import after path manipulation)


def _projects(tmp_path: Path, **proj_to_queue: str | None) -> Path:
    """proj_to_queue: {project_name: queue_text or None}. None = project dir, no queue."""
    root = tmp_path / "projects"
    root.mkdir(exist_ok=True)
    for name, text in proj_to_queue.items():
        pdir = root / name
        pdir.mkdir()
        if text is not None:
            (pdir / "APPROVED-GOAL-QUEUE.md").write_text(text, encoding="utf-8")
    return root


def _board(tmp_path: Path, *tickets: tuple[str, str, str]) -> Path:
    """tickets: (id, status, project). project='' omits the field."""
    bdir = tmp_path / "board"
    bdir.mkdir(exist_ok=True)
    for tid, status, project in tickets:
        proj_line = f"project: {project}\n" if project else ""
        (bdir / f"{tid}-t.md").write_text(
            f"---\nid: {tid}\nstatus: {status}\n{proj_line}---\n\n## Description\nx\n",
            encoding="utf-8",
        )
    return bdir


def _empty_board(tmp_path: Path) -> Path:
    bdir = tmp_path / "emptyboard"
    bdir.mkdir(exist_ok=True)
    return bdir


def _run(projects_dir: Path, board_dir: Path) -> int:
    return q.main(["--projects", str(projects_dir), "--board", str(board_dir)])


# --------------------------------------------------------------------------- #
# Layer A — queue integrity
# --------------------------------------------------------------------------- #

def test_no_projects_dir_passes(tmp_path):
    assert q.main(["--projects", str(tmp_path / "nope"), "--board", str(_empty_board(tmp_path))]) == 0


def test_empty_projects_passes(tmp_path):
    assert _run(_projects(tmp_path), _empty_board(tmp_path)) == 0


def test_project_without_queue_passes(tmp_path):
    assert _run(_projects(tmp_path, someproj=None), _empty_board(tmp_path)) == 0


def test_tasdiqlandi_queue_passes(tmp_path):
    assert _run(_projects(tmp_path, qaqnuz="# Queue\n\nSTATUS: TASDIQLANDI 2026-06-24\n"), _empty_board(tmp_path)) == 0


def test_unapproved_queue_fails(tmp_path):
    assert _run(_projects(tmp_path, p="# Draft\n\nawaiting sign-off\n"), _empty_board(tmp_path)) == 1


# --------------------------------------------------------------------------- #
# Layer A — F-1 false-green regression: the queue's own NAME/TITLE is not approval
# --------------------------------------------------------------------------- #

def test_filename_header_alone_is_not_approval(tmp_path):
    """ORGANISM audit F-1: a queue whose only 'APPROVED' is the hyphenated filename
    header (`# APPROVED-GOAL-QUEUE`) is NOT authorized — the '-' word boundary used to
    false-green the naive `\\bAPPROVED\\b` regex."""
    text = "# APPROVED-GOAL-QUEUE\n\nDraft goals below. Awaiting Founder sign-off.\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 1


def test_title_word_alone_is_not_approval(tmp_path):
    """The prose title 'Approved Goal Queue' is template chrome, not a Founder signal."""
    text = "# Qaqnuz — Approved Goal Queue\n\nGoals drafted, not yet approved.\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 1


def test_approved_colon_marker_passes_even_with_header(tmp_path):
    """Canonical `APPROVED:` signal is load-bearing even alongside the filename header."""
    text = "# APPROVED-GOAL-QUEUE\n\nAPPROVED: 2026-07-04 by Founder (Akmaljon).\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 0


def test_founder_approved_field_passes(tmp_path):
    text = "---\nfounder_approved: true\n---\n\n# APPROVED-GOAL-QUEUE\n\ngoals\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 0


def test_backtick_tasdiqlandi_passes(tmp_path):
    """Real qaqnuz form: STATUS line with backtick-wrapped `TASDIQLANDI` is a valid signal."""
    text = "# Approved Goal Queue\n\n> **STATUS: APPROVED — Founder said `TASDIQLANDI` 2026-06-24.**\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 0


# --------------------------------------------------------------------------- #
# Layer A — F-1b residual: machine-writable `founder_approved` STATUS ≠ approval
# --------------------------------------------------------------------------- #

def test_founder_approved_table_cell_is_not_approval(tmp_path):
    """ORGANISM audit F-1b: `founder_approved` is a per-goal queue STATUS value an
    agent can write as table data — a queue whose ONLY 'approval' is a goal-row cell
    (no top-level Founder sign-off) must NOT self-authorize."""
    text = (
        "# Goal Queue\n\n"
        "| order | goal | owner | status |\n"
        "|--|--|--|--|\n"
        "| 1 | user-auth | cpo | founder_approved |\n"
    )
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 1


def test_founder_approved_status_value_is_not_approval(tmp_path):
    """`status: founder_approved` is a goal VALUE (colon precedes it), not a
    queue-level `founder_approved:` field — it must not authorize."""
    text = "# Goal Queue\n\n- goal: user-auth\n  status: founder_approved\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 1


def test_founder_approved_prose_mention_is_not_approval(tmp_path):
    """A prose backtick mention of `founder_approved` (describing the schema) is not
    a Founder sign-off."""
    text = "# Goal Queue\n\nEach goal below is marked `founder_approved` once signed off.\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 1


def test_founder_approved_colon_field_still_passes(tmp_path):
    """The anchored field form `founder_approved:` remains a valid marker."""
    text = "---\nfounder_approved: true\n---\n\n# Goal Queue\n\ngoals\n"
    assert _run(_projects(tmp_path, p=text), _empty_board(tmp_path)) == 0


def test_real_e2e_packs_pass_via_top_level_signoff():
    """Regression guard: the real evals/e2e sample-pack queues carry a genuine
    top-level `APPROVED: TASDIQLANDI` sign-off, so tightening `founder_approved`
    (F-1b) must NOT break them — they still pass check A."""
    for pack in ("sample-pack", "sample-pack-2"):
        queue = REPO_ROOT / "evals" / "e2e" / pack / "APPROVED-GOAL-QUEUE.md"
        if not queue.is_file():
            continue
        assert q.APPROVAL_RE.search(queue.read_text(encoding="utf-8")), (
            f"{pack}: real top-level sign-off must still match"
        )


# --------------------------------------------------------------------------- #
# Layer B — local ticket → queue mapping
# --------------------------------------------------------------------------- #

def test_project_ticket_with_approved_queue_passes(tmp_path):
    projects = _projects(tmp_path, qaqnuz="TASDIQLANDI\n")
    board = _board(tmp_path, ("DAS-2001", "todo", "qaqnuz"))
    assert _run(projects, board) == 0


def test_project_ticket_without_queue_fails(tmp_path):
    projects = _projects(tmp_path, qaqnuz="TASDIQLANDI\n")
    board = _board(tmp_path, ("DAS-2001", "todo", "ghostproject"))
    assert _run(projects, board) == 1


def test_project_ticket_unapproved_queue_fails(tmp_path):
    projects = _projects(tmp_path, draftproj="# draft, no approval\n")
    board = _board(tmp_path, ("DAS-2001", "in_progress", "draftproj"))
    assert _run(projects, board) == 1


def test_backlog_project_ticket_is_skipped(tmp_path):
    projects = _projects(tmp_path, qaqnuz="TASDIQLANDI\n")
    board = _board(tmp_path, ("DAS-2001", "backlog", "ghostproject"))  # backlog → not dispatchable
    assert _run(projects, board) == 0


def test_ticket_without_project_field_is_unaffected(tmp_path):
    projects = _projects(tmp_path, qaqnuz="TASDIQLANDI\n")
    board = _board(tmp_path, ("DAS-2001", "done", ""))  # org-engine ticket, no project
    assert _run(projects, board) == 0


# --------------------------------------------------------------------------- #
# Real repo
# --------------------------------------------------------------------------- #

def test_real_repo_passes():
    # projects/ gitignored: empty on CI (-> pass); locally every queue is approved and
    # no real ticket declares a project: field, so both layers pass.
    assert q.main(["--projects", str(REPO_ROOT / "projects"), "--board", str(REPO_ROOT / "board" / "tickets")]) == 0
