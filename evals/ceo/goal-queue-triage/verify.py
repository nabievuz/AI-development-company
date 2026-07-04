"""Deterministic verifier — ceo / goal-queue-triage.

Fractional credit is classification accuracy over the fixture's candidate
goals:

    credit = (# ids classified correctly) / (total # ids)

The correct label per id is derived from the SAME fixture the agent was
given, by re-applying the Founder-Approved Goal Queue rule stated in
task.md — so nothing is leaked into fixtures/: the fixture is the input, and
applying the rule correctly is the graded skill. Deterministic (no
clock/model). An empty submission scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path

_SIGNAL_MARKERS = ("APPROVED", "TASDIQLANDI")


def _expected(fixtures: Path) -> dict[str, str]:
    data = json.loads((fixtures / "goal_queue.json").read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for rec in data.get("goals", []):
        rec_id = str(rec.get("id"))
        questions_ok = (
            int(rec.get("founder_questions_answered", 0)) >= 10
            or bool(rec.get("founder_waived_questions", False))
        )
        signal = rec.get("founder_signal")
        signal_ok = isinstance(signal, str) and any(m in signal for m in _SIGNAL_MARKERS)
        labels[rec_id] = "approved" if (questions_ok and signal_ok) else "blocked"
    return labels


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("decisions", {})
    if not isinstance(reported, dict):
        return 0.0

    correct = 0
    for rec_id, label in expected.items():
        got = reported.get(rec_id)
        if isinstance(got, str) and got.strip().lower() == label:
            correct += 1

    return max(0.0, correct / len(expected))
