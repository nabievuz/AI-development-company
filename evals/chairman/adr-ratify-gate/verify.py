from __future__ import annotations

import json
import re
from pathlib import Path

MANDATORY_SECTIONS = ("Context", "Decision", "Consequences")


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _present_headings(draft_text: str) -> set[str]:
    headings = {
        m.group(1).strip()
        for m in re.finditer(r"^##\s+(.+)$", draft_text, flags=re.MULTILINE)
    }
    return headings


def verify(submission: dict, fixtures: Path) -> float:
    draft_text = _document(fixtures / "adr_draft.json")
    present = _present_headings(draft_text)
    required = {s for s in MANDATORY_SECTIONS if s not in present}
    if not required:


        raise ValueError("fixture draft is missing no mandatory sections")

    got_raw = submission.get("missing_sections")
    if not isinstance(got_raw, list):
        return 0.0
    got = {s.strip() for s in got_raw if isinstance(s, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
