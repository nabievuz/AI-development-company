
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
