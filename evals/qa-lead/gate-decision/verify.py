"""Deterministic verifier — qa-lead / gate-decision.

Fractional credit:
  * 0.5 if `decision` matches the correct go/no-go call for the report.
  * 0.5 for `blocking_reasons` precision/recall against the expected reason
    set, both derived from `fixtures/ci_report.json` (never leaked into the
    prompt). Rule (release-gate policy):
      - "failing_tests_on_main" iff failing_tests_on_main is non-empty.
      - "open_p0_bug"           iff any open_bugs entry has severity == "P0".
      - "coverage_below_threshold" iff coverage_pct < coverage_threshold.
    A flaky test is NEVER a valid blocking reason (reliability debt, not a
    correctness gate) — this is the judgment probe of the task.

Deterministic: no clock, no randomness, no model call. An empty submission
scores 0.0 (anti-gaming: no reward for degenerate output).
"""

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
    """Return fractional credit in [0.0, 1.0] for one submission."""
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
