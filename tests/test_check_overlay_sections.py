#!/usr/bin/env python3
"""tests/test_check_overlay_sections.py — role-overlay contract (ADR-0018 / ADR-0002, P3)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_overlay_sections as cos  # noqa: E402  (import after path manipulation)

FULL = (
    "# Role\n\n## Mission\n" + "m" * 50 + "\n\n## Scope\n" + "s" * 50 +
    "\n\n## Definition of Done\n" + "d" * 50 + "\n\n## Escalation\n" + "e" * 50 + "\n"
)


def _overlay(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "AGENTS.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_real_overlays_pass_strict():
    # the live overlays were filled to the contract — strict must pass on the real tree
    assert cos.main(["--strict"]) == 0


def test_complete_overlay_has_no_gaps(tmp_path):
    assert cos.scan([_overlay(tmp_path, FULL)]) == []


def test_when_to_escalate_is_accepted(tmp_path):
    body = FULL.replace("## Escalation", "## When to escalate")
    assert cos.scan([_overlay(tmp_path, body)]) == []


def test_thin_overlay_is_flagged(tmp_path):
    gaps = cos.scan([_overlay(tmp_path, "# Role\n## Identity\nx\n## When to escalate\nesc\n")])
    reasons = " ".join(r for _, r in gaps)
    assert "Mission" in reasons and "Scope" in reasons and "Definition of Done" in reasons


def test_short_section_is_flagged_as_thin(tmp_path):
    body = "## Mission\nshort\n## Scope\n" + "s" * 50 + "\n## Definition of Done\n" + "d" * 50 + "\n## Escalation\n" + "e" * 50 + "\n"
    gaps = cos.scan([_overlay(tmp_path, body)])
    assert any("thin" in r for _, r in gaps)
