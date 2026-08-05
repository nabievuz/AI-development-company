
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTICS = REPO_ROOT / "scripts" / "diagnostics.py"
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_diagnostics():
    spec = importlib.util.spec_from_file_location("diagnostics_ssot_test", DIAGNOSTICS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_board_lint():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("board_lint_ssot_test", SCRIPTS_DIR / "board_lint.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_diagnostics_status_enum_matches_board_lint_ssot() -> None:
    diagnostics = _load_diagnostics()
    board_lint = _load_board_lint()

    assert set(board_lint.VALID_STATUSES) == diagnostics.VALID_STATUS, (
        "scripts/diagnostics.py's status enum has drifted from "
        "scripts/board_lint.py's VALID_STATUSES (the SSOT). "
        f"diagnostics only: {diagnostics.VALID_STATUS - set(board_lint.VALID_STATUSES)}; "
        f"board_lint only: {set(board_lint.VALID_STATUSES) - diagnostics.VALID_STATUS}"
    )


def test_diagnostics_status_enum_is_sourced_from_board_lint_not_redeclared() -> None:
    diagnostics = _load_diagnostics()
    board_lint = _load_board_lint()

    assert diagnostics._board_lint is not None, (
        "diagnostics.py failed to import board_lint — the status enum fell "
        "back to fail-closed (empty set) instead of being sourced from the SSOT"
    )
    assert diagnostics._board_lint.VALID_STATUSES is board_lint.VALID_STATUSES or (
        frozenset(board_lint.VALID_STATUSES) == diagnostics.VALID_STATUS
    )


def test_interrupted_ticket_passes_diagnostics_status_enum_check(tmp_path, monkeypatch) -> None:
    diagnostics = _load_diagnostics()

    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    (board_dir / "DAS-9001-example.md").write_text(
        "---\n"
        "id: DAS-9001\n"
        "title: example interrupted ticket\n"
        "status: interrupted\n"
        "assignee: sre-eng\n"
        "author: security-lead\n"
        "dept: engineering\n"
        "priority: p2\n"
        "created: 2026-08-04\n"
        "updated: 2026-08-04\n"
        "---\n\n"
        "## Description\nparked pending a founder answer\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(diagnostics, "TICKETS_DIR", board_dir)
    results = diagnostics.check_consistency()
    status_enum = next(r for r in results if r.name == "status-enum")
    assert status_enum.passed, status_enum.detail
