#!/usr/bin/env python3
"""tests/test_check_never_auto_approve.py — QONUN-5 never-auto-approve (R-4 / ADR-004).

Proves every never-auto-approve category is caught when auto-approved, that a
non-category auto-approval is allowed, the missing-config / missing-board error
paths, and that the REAL repo board passes the gate as-is.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_never_auto_approve as na  # noqa: E402  (import after path manipulation)

REAL_CONFIG = REPO_ROOT / "config" / "risk_taxonomy.yaml"


def _board(tmp_path: Path, *tickets: dict) -> Path:
    board = tmp_path / "board"
    board.mkdir()
    for i, fm in enumerate(tickets):
        body = "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n## Description\nx\n"
        (board / f"DAS-{2000 + i}-t.md").write_text(body, encoding="utf-8")
    return board


def _run(tmp_path: Path, *tickets: dict) -> int:
    board = _board(tmp_path, *tickets)
    return na.main(["--board", str(board), "--config", str(REAL_CONFIG)])


# --------------------------------------------------------------------------- #
# Clean / skipped
# --------------------------------------------------------------------------- #

def test_clean_board_passes(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "human:founder", "ticket_type": "goal"}) == 0


def test_no_approval_field_is_skipped(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "ticket_type": "goal"}) == 0


def test_non_category_auto_is_allowed(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "ticket_type": "feature"}) == 0


# --------------------------------------------------------------------------- #
# Each never-auto-approve category, auto-approved -> violation (exit 1)
# --------------------------------------------------------------------------- #

def test_new_goal_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "ticket_type": "goal"}) == 1


def test_security_label_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "labels": ["security"]}) == 1


def test_security_path_glob_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["src/auth/login.py"]}) == 1


def test_gate5_stage_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "stage": "GATE-5"}) == 1


def test_governance_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["board/ROUTING.md"]}) == 1


def test_migration_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["migrations/versions/0002_x.py"]}) == 1


def test_alembic_ini_auto_fails(tmp_path):
    # alembic.ini is apply-time migration config (holds sqlalchemy.url) -> schema_migration
    # never-auto-approve, so a repoint-the-DB edit cannot be auto-approved (E-004 R-13).
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["alembic.ini"]}) == 1


def test_secret_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["config/.env.prod"]}) == 1


def test_governance_config_path_auto_fails(tmp_path):
    # editing the loop mode / T7 rubric is governance -> never-auto-approve
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["config/loop.yaml"]}) == 1


# --- bypass-shape regression tests (review-found false negatives) ---

def test_toplevel_secret_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": [".env"]}) == 1


def test_bare_codeowners_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["CODEOWNERS"]}) == 1


def test_toplevel_auth_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["auth/login.py"]}) == 1


def test_toplevel_migration_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["migrations/001.sql"]}) == 1


def test_lowercase_charter_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["governance/charter.md"]}) == 1


def test_stage_as_list_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "stage": ["GATE-5"]}) == 1


def test_labels_as_scalar_string_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "labels": "security"}) == 1


def test_unparseable_frontmatter_fails_closed(tmp_path):
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-9-bad.md").write_text(
        "---\napproval: auto\nfoo: [unclosed\n: : :\n---\n\nbody\n", encoding="utf-8"
    )
    assert na.main(["--board", str(board), "--config", str(REAL_CONFIG)]) == 1


def test_smuggled_safety_fence_fails_closed(tmp_path):
    # approval/ticket_type hidden AFTER a premature second fence must not slip past
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-9.md").write_text(
        "---\nid: DAS-9\nnotes: harmless\n---\napproval: auto\nticket_type: goal\n---\n\nbody\n",
        encoding="utf-8",
    )
    assert na.main(["--board", str(board), "--config", str(REAL_CONFIG)]) == 1


def test_empty_frontmatter_is_clean(tmp_path):
    board = tmp_path / "board"
    board.mkdir()
    (board / "DAS-9.md").write_text("---\n---\n\nbody\n", encoding="utf-8")
    assert na.main(["--board", str(board), "--config", str(REAL_CONFIG)]) == 0


def test_bare_directory_path_auto_fails(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto", "paths": ["auth"]}) == 1


def test_auto_prefix_variants_detected(tmp_path):
    assert _run(tmp_path, {"id": "DAS-2000", "approval": "auto:classifier", "ticket_type": "epic-root"}) == 1


# --------------------------------------------------------------------------- #
# Error paths + real board
# --------------------------------------------------------------------------- #

def test_missing_config_exit_2(tmp_path):
    board = _board(tmp_path, {"id": "DAS-2000"})
    assert na.main(["--board", str(board), "--config", str(tmp_path / "nope.yaml")]) == 2


def test_missing_board_exit_2(tmp_path):
    assert na.main(["--board", str(tmp_path / "nope"), "--config", str(REAL_CONFIG)]) == 2


def test_real_repo_board_is_clean():
    assert na.main(["--board", str(REPO_ROOT / "board"), "--config", str(REAL_CONFIG)]) == 0
