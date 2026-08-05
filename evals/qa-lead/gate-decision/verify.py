
from __future__ import annotations

import json
from pathlib import Path

VALID_REASONS = frozenset(
    {"failing_tests_on_main", "open_p0_bug", "coverage_below_threshold"}
)


def _expected(fixtures: Path) -> tuple[str, set[str]]:
    data = json.loads((fixtures / "ci_report.json").read_text(encoding="utf-8"))

    reasons: set[str] = set()
    if data.get("failing_tests_on_main"):
        reasons.add("failing_tests_on_main")
    if any(b.get("severity") == "P0" for b in data.get("open_bugs", [])):
        reasons.add("open_p0_bug")
    if data.get("coverage_pct", 100) < data.get("coverage_threshold", 0):
        reasons.add("coverage_below_threshold")

    decision = "no_go" if reasons else "go"
    return decision, reasons


def verify(submission: dict, fixtures: Path) -> float:
    expected_decision, expected_reasons = _expected(fixtures)

    credit = 0.0

    decision = submission.get("decision")
    if isinstance(decision, str) and decision.strip().lower() == expected_decision:
        credit += 0.5

    reported = submission.get("blocking_reasons")
    if isinstance(reported, list) and expected_reasons:
        reported_set = {str(r).strip() for r in reported if str(r).strip() in VALID_REASONS}
        hits = len(reported_set & expected_reasons)
        false_pos = len(reported_set - expected_reasons)
        credit += 0.5 * max(0.0, (hits - false_pos) / len(expected_reasons))

    return max(0.0, min(1.0, credit))
