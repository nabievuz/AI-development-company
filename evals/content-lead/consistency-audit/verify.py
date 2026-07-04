"""Deterministic verifier — content-lead / consistency-audit."""
from __future__ import annotations

import json
from pathlib import Path


def verify(submission: dict, fixtures: Path) -> float:
    guide = json.loads((fixtures / "style_guide.json").read_text(encoding="utf-8"))
    canonical_name = str(guide["canonical_name"])
    canonical_price = str(guide["canonical_price"])

    docs_dir = fixtures / "docs"
    required = set()
    for doc_path in sorted(docs_dir.glob("*.md")):
        text = doc_path.read_text(encoding="utf-8")
        if canonical_name not in text or canonical_price not in text:
            required.add(doc_path.name)

    if not required:
        # Task defect guard: a task with no real inconsistency can't discriminate.
        return 0.0

    inconsistent = submission.get("inconsistent_docs")
    if not isinstance(inconsistent, list):
        return 0.0
    got = {d.strip() for d in inconsistent if isinstance(d, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
