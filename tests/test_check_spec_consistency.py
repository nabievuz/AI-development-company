#!/usr/bin/env python3
"""tests/test_check_spec_consistency.py — Phase 2 SPEC.md consistency (ADR-0015 / ADR-0002)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_spec_consistency as sc  # noqa: E402  (import after path manipulation)

GOOD_SPEC = (
    "# SPEC 001 — demo\n\n## User Scenarios\n- P1 — given/when/then\n\n"
    "## Functional Requirements\n- FR-001 — the system MUST do x\n- FR-002 — MUST do y\n\n"
    "## Success Criteria\n- SC-001 — measurable\n"
)


def _specs(tmp_path: Path, **slug_to_body: str) -> Path:
    root = tmp_path / "specs"
    root.mkdir(exist_ok=True)
    for slug, body in slug_to_body.items():
        d = root / slug
        d.mkdir()
        (d / "SPEC.md").write_text(body, encoding="utf-8")
    return root


def _board(tmp_path: Path, *tickets: tuple[str, str, str]) -> Path:
    """tickets: (id, spec, implements). '' omits a field; implements is an inline list body."""
    bdir = tmp_path / "board"
    bdir.mkdir(exist_ok=True)
    for tid, spec, impl in tickets:
        fm = f"---\nid: {tid}\nstatus: todo\nauthor: ceo\n"
        if spec:
            fm += f"spec: {spec}\n"
        if impl:
            fm += f"implements: {impl}\n"
        fm += "---\n\n## Description\nx\n"
        (bdir / f"{tid}-t.md").write_text(fm, encoding="utf-8")
    return bdir


def _run(tmp_path: Path, specs: Path, board: Path) -> int:
    return sc.main(["--specs", str(specs), "--projects", str(tmp_path / "noproj"), "--board", str(board)])


# --- structure ---

def test_no_specs_passes(tmp_path):
    assert _run(tmp_path, _specs(tmp_path), _board(tmp_path)) == 0


def test_well_formed_spec_passes(tmp_path):
    assert _run(tmp_path, _specs(tmp_path, **{"001-demo": GOOD_SPEC}), _board(tmp_path)) == 0


def test_missing_section_fails(tmp_path):
    bad = GOOD_SPEC.replace("## Success Criteria\n- SC-001 — measurable\n", "")
    assert _run(tmp_path, _specs(tmp_path, **{"001-demo": bad}), _board(tmp_path)) == 1


def test_no_functional_requirements_fails(tmp_path):
    bad = GOOD_SPEC.replace("- FR-001 — the system MUST do x\n- FR-002 — MUST do y\n", "- TBD\n")
    assert _run(tmp_path, _specs(tmp_path, **{"001-demo": bad}), _board(tmp_path)) == 1


def test_duplicate_fr_ids_fail(tmp_path):
    bad = GOOD_SPEC.replace("- FR-002 — MUST do y", "- FR-001 — MUST do y")
    assert _run(tmp_path, _specs(tmp_path, **{"001-demo": bad}), _board(tmp_path)) == 1


def test_templates_dir_is_skipped(tmp_path):
    root = tmp_path / "specs"
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "SPEC.md").write_text("# template\nFR-000 placeholder, no sections\n", encoding="utf-8")
    assert sc.main(["--specs", str(root), "--projects", str(tmp_path / "n"), "--board", str(_board(tmp_path))]) == 0


# --- ticket linkage ---

def test_valid_ticket_link_passes(tmp_path):
    specs = _specs(tmp_path, **{"001-demo": GOOD_SPEC})
    board = _board(tmp_path, ("DAS-2001", "001-demo", "[FR-001, FR-002]"))
    assert _run(tmp_path, specs, board) == 0


def test_dangling_spec_ref_fails(tmp_path):
    specs = _specs(tmp_path, **{"001-demo": GOOD_SPEC})
    board = _board(tmp_path, ("DAS-2001", "404-ghost", "[FR-001]"))
    assert _run(tmp_path, specs, board) == 1


def test_dangling_implements_ref_fails(tmp_path):
    specs = _specs(tmp_path, **{"001-demo": GOOD_SPEC})
    board = _board(tmp_path, ("DAS-2001", "001-demo", "[FR-999]"))
    assert _run(tmp_path, specs, board) == 1


def test_ticket_without_spec_field_unaffected(tmp_path):
    specs = _specs(tmp_path, **{"001-demo": GOOD_SPEC})
    board = _board(tmp_path, ("DAS-2001", "", ""))
    assert _run(tmp_path, specs, board) == 0


# --- real repo ---

def test_real_repo_passes():
    assert sc.main([]) == 0
