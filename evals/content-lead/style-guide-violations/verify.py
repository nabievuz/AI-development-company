from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    guide = json.loads((fixtures / "style_guide.json").read_text(encoding="utf-8"))
    draft = (fixtures / "draft.md").read_text(encoding="utf-8").lower()

    banned = [str(t).strip().lower() for t in guide.get("banned_terms", [])]
    required = {term for term in banned if term in draft}
    if not required:

        return 0.0

    violations = submission.get("violations")
    if not isinstance(violations, list):
        return 0.0
    got = {v.strip().lower() for v in violations if isinstance(v, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
