from __future__ import annotations

from pathlib import Path

EXPECTED_ISSUES = frozenset(
    {"breaking_change", "missing_pagination", "missing_versioning"}
)


def _normalize(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(v).strip().lower().replace(" ", "_").replace("-", "_") for v in values if str(v).strip()}


def verify(submission: dict, fixtures: Path) -> float:


    _ = (fixtures / "api_proposal.md").read_text(encoding="utf-8")

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
