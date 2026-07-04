"""Deterministic verifier — chairman / adr-ratify-gate."""
from __future__ import annotations

import re
from pathlib import Path

#: The mandatory ADR triple this repo's convention requires (see
#: docs/adr/0001-status-handoff-protocol.md and siblings — every ratified ADR
#: carries all three). This is the governance rule, not the answer — the
#: answer is which of the three are ABSENT from the specific draft under review.
MANDATORY_SECTIONS = ("Context", "Decision", "Consequences")


def _present_headings(draft_text: str) -> set[str]:
    headings = {
        m.group(1).strip()
        for m in re.finditer(r"^##\s+(.+)$", draft_text, flags=re.MULTILINE)
    }
    return headings


def verify(submission: dict, fixtures: Path) -> float:
    draft_text = (fixtures / "adr_draft.md").read_text(encoding="utf-8")
    present = _present_headings(draft_text)
    required = {s for s in MANDATORY_SECTIONS if s not in present}
    if not required:
        # Defensive: the fixture must always be missing at least one mandatory
        # section, or this task cannot discriminate. Treat as a task defect.
        raise ValueError("fixture draft is missing no mandatory sections")

    got_raw = submission.get("missing_sections")
    if not isinstance(got_raw, list):
        return 0.0
    got = {s.strip() for s in got_raw if isinstance(s, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
