from __future__ import annotations

import json
from pathlib import Path


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def verify(submission: dict, fixtures: Path) -> float:
    guide = json.loads((fixtures / "style_guide.json").read_text(encoding="utf-8"))
    draft = _document(fixtures / "draft.json").lower()

    banned = [str(t).strip().lower() for t in guide.get("banned_terms", [])]
    required = {term for term in banned if term in draft}
    if not required:
        raise ValueError(
            "fixture draft contains none of the style guide's banned terms — "
            "this task would grade every answer as wrong"
        )

    violations = submission.get("violations")
    if not isinstance(violations, list):
        return 0.0
    got = {v.strip().lower() for v in violations if isinstance(v, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
