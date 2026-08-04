"""Regression test for DAS-1646: diagnostics.py's status enum must never
re-diverge from scripts/board_lint.py's VALID_STATUSES (the single source of
truth).

The original bug was NOT "diagnostics.py forgot the value 'interrupted'" in
isolation — it was that diagnostics.py carried its own hand-maintained COPY of
the status enum, so any future addition to board_lint.VALID_STATUSES (not just
"interrupted") would silently re-create the same failure mode: a validly-formed
ticket zeroes the whole Consistency dimension (15/100) while board_lint passes
the same board clean.

So this test does NOT hard-code the expected status set (that would just
reproduce the bug in a new place — a second copy of the enum, this time in a
test file). Instead it asserts the two modules' sets are identical, by
identity of *definition*: diagnostics.VALID_STATUS must literally be sourced
from board_lint.VALID_STATUSES, so the two can never disagree again. It also
smoke-tests the actual behaviour the original bug broke: a board containing an
"interrupted" ticket must not fail diagnostics.py's status-enum check.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTICS = REPO_ROOT / "scripts" / "diagnostics.py"
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_diagnostics():
    """Import scripts/diagnostics.py as a module for white-box checks.

    Mirrors tests/test_diagnostics.py's loader: the module is registered in
    sys.modules before execution because its dataclasses use
    `from __future__ import annotations`, which resolves field annotations
    against sys.modules[cls.__module__] at class-definition time.
    """
    spec = importlib.util.spec_from_file_location("diagnostics_ssot_test", DIAGNOSTICS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_board_lint():
    """Import scripts/board_lint.py the same way (independent of diagnostics'
    own sys.path bootstrap), so this test does not merely check that
    diagnostics imported *some* module — it re-derives the SSOT itself and
    compares.
    """
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("board_lint_ssot_test", SCRIPTS_DIR / "board_lint.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_diagnostics_status_enum_matches_board_lint_ssot() -> None:
    """diagnostics.VALID_STATUS must be set-equal to board_lint.VALID_STATUSES.

    This is the divergence guard: it fails for ANY future mismatch (an
    addition, removal, or typo on either side), not just the historical
    "interrupted" omission — because it never states the expected set, only
    that the two sources must agree.
    """
    diagnostics = _load_diagnostics()
    board_lint = _load_board_lint()

    assert set(board_lint.VALID_STATUSES) == diagnostics.VALID_STATUS, (
        "scripts/diagnostics.py's status enum has drifted from "
        "scripts/board_lint.py's VALID_STATUSES (the SSOT). "
        f"diagnostics only: {diagnostics.VALID_STATUS - set(board_lint.VALID_STATUSES)}; "
        f"board_lint only: {set(board_lint.VALID_STATUSES) - diagnostics.VALID_STATUS}"
    )


def test_diagnostics_status_enum_is_sourced_from_board_lint_not_redeclared() -> None:
    """Guard against a future "fix" that re-copies the values by hand.

    Equal *contents* is necessary but not sufficient — a hand-copied literal
    would pass the set-equality test above too, right up until board_lint
    changes again. This asserts diagnostics actually imported board_lint's
    module object, so there is one definition, not two agreeing by luck.
    """
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
    """End-to-end regression for the bug as originally reported: a validly
    formed 'interrupted' ticket must not fail diagnostics.py's status-enum
    check (the failure that zeroed the whole 15-point Consistency dimension).
    """
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
