from __future__ import annotations

import json
from pathlib import Path

EXPECTED_ISSUES = frozenset(
    {"breaking_change", "missing_pagination", "missing_versioning"}
)


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _normalize(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(v).strip().lower().replace(" ", "_").replace("-", "_") for v in values if str(v).strip()}


def verify(submission: dict, fixtures: Path) -> float:


    _ = _document(fixtures / "api_proposal.json")

    found = _normalize(submission.get("issues"))
    if not found:
        return 0.0

    tp = len(found & EXPECTED_ISSUES)
    fp = len(found - EXPECTED_ISSUES)
    fn = len(EXPECTED_ISSUES - found)

    if tp == 0:
        return 0.0

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    f1 = 2 * precision * recall / (precision + recall)
    return f1
