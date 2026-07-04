#!/usr/bin/env python3
"""tests/test_check_clarifications.py — Definition-of-Ready clarify gate (ADR-0014 / ADR-0002).

Proves the marker is caught in active statuses, allowed in pre-dispatch statuses,
the > 3 cap, that code-fenced/backticked markers are treated as documentation,
warn-only vs --strict behaviour, the IO error path, and that the REAL repo board
passes under --strict.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_clarifications as cc  # noqa: E402  (import after path manipulation)

MARKER = "[NEEDS CLARIFICATION: which auth provider?]"


def _tickets(tmp_path: Path, *rows: tuple[str, str]) -> Path:
    """rows = (status, body). Writes one DAS-*.md per row, returns the tickets dir."""
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    for i, (status, body) in enumerate(rows):
        fm = f"---\nid: DAS-{3000 + i}\nstatus: {status}\nauthor: senior-pm\n---\n\n## Description\n{body}\n"
        (tickets / f"DAS-{3000 + i}-t.md").write_text(fm, encoding="utf-8")
    return tickets


def _run(tmp_path: Path, *rows: tuple[str, str], strict: bool = False) -> int:
    argv = ["--tickets", str(_tickets(tmp_path, *rows))]
    if strict:
        argv.append("--strict")
    return cc.main(argv)


# --------------------------------------------------------------------------- #
# Clean / allowed
# --------------------------------------------------------------------------- #

def test_clean_board_passes(tmp_path):
    assert _run(tmp_path, ("done", "all clear, no markers")) == 0


def test_marker_in_todo_is_allowed(tmp_path):
    # todo may carry a marker — the cycle selection step routes it, not a violation here
    assert _run(tmp_path, ("todo", MARKER), strict=True) == 0


def test_marker_in_backlog_is_allowed(tmp_path):
    assert _run(tmp_path, ("backlog", f"{MARKER} {MARKER} {MARKER} {MARKER} {MARKER}"), strict=True) == 0


def test_backticked_marker_is_documentation(tmp_path):
    # a marker shown as a code example must not trip the gate, even when active
    assert _run(tmp_path, ("in_review", f"the `{MARKER}` syntax is documented here"), strict=True) == 0


def test_fenced_marker_is_documentation(tmp_path):
    body = f"example:\n```\n{MARKER}\n```\nend"
    assert _run(tmp_path, ("done", body), strict=True) == 0


# --------------------------------------------------------------------------- #
# Violations under --strict
# --------------------------------------------------------------------------- #

def test_strict_active_marker_fails(tmp_path):
    assert _run(tmp_path, ("in_progress", f"do the thing {MARKER}"), strict=True) == 1


def test_strict_in_review_marker_fails(tmp_path):
    assert _run(tmp_path, ("in_review", MARKER), strict=True) == 1


def test_strict_done_marker_fails(tmp_path):
    assert _run(tmp_path, ("done", MARKER), strict=True) == 1


def test_strict_too_many_markers_on_todo_fails(tmp_path):
    body = " ".join([MARKER] * 4)  # 4 > 3 cap, dispatch-candidate
    assert _run(tmp_path, ("todo", body), strict=True) == 1


# --------------------------------------------------------------------------- #
# Warn-only never fails
# --------------------------------------------------------------------------- #

def test_warn_only_active_marker_passes(tmp_path):
    assert _run(tmp_path, ("in_progress", MARKER), strict=False) == 0


def test_warn_only_too_many_markers_passes(tmp_path):
    assert _run(tmp_path, ("todo", " ".join([MARKER] * 5)), strict=False) == 0


# --------------------------------------------------------------------------- #
# Error path + real board
# --------------------------------------------------------------------------- #

def test_missing_tickets_dir_exit_2(tmp_path):
    assert cc.main(["--tickets", str(tmp_path / "nope")]) == 2


def test_real_repo_board_strict_is_clean():
    assert cc.main(["--tickets", str(REPO_ROOT / "board" / "tickets"), "--strict"]) == 0


# --------------------------------------------------------------------------- #
# Boundary contract (A4): the scanner's heuristic is an INTENTIONAL, tested rule —
# a live marker is plain prose in the body; backticked/fenced markers and the title
# are documentation. These lock that contract so the boundary can't silently drift.
# --------------------------------------------------------------------------- #

def test_mixed_ticket_plain_marker_still_caught(tmp_path):
    # a ticket may DOCUMENT the syntax in backticks AND carry a real plain marker;
    # the real one must still be caught (the documented one is correctly ignored).
    body = f"the `{MARKER}` syntax is shown here. But really: {MARKER}"
    assert _run(tmp_path, ("in_progress", body), strict=True) == 1


def test_marker_only_in_title_is_not_a_live_request(tmp_path):
    # the ADR-0014 tracking ticket names the marker in its TITLE; frontmatter is
    # excluded, so a clean body must pass even when the title mentions the marker.
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "DAS-3100-t.md").write_text(
        f'---\nid: DAS-3100\ntitle: "Clarify gate ({MARKER})"\nstatus: done\nauthor: senior-pm\n---\n\n'
        "## Description\nfully specified body, no live markers\n",
        encoding="utf-8",
    )
    assert cc.main(["--tickets", str(tickets), "--strict"]) == 0
