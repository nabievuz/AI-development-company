from __future__ import annotations

import json
from pathlib import Path


def _documents(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload["documents"]
    if not isinstance(documents, dict) or not documents:
        raise ValueError(f"{path}: fixture carries no documents to audit")
    return {str(name): str(text) for name, text in documents.items()}


def verify(submission: dict, fixtures: Path) -> float:
    guide = json.loads((fixtures / "style_guide.json").read_text(encoding="utf-8"))
    canonical_name = str(guide["canonical_name"])
    canonical_price = str(guide["canonical_price"])

    documents = _documents(fixtures / "docs.json")
    required = {
        name
        for name, text in sorted(documents.items())
        if canonical_name not in text or canonical_price not in text
    }
    if not required:
        raise ValueError(
            "fixture documents are all consistent with the style guide — "
            "this task would grade every answer as wrong"
        )

    inconsistent = submission.get("inconsistent_docs")
    if not isinstance(inconsistent, list):
        return 0.0
    got = {d.strip() for d in inconsistent if isinstance(d, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
