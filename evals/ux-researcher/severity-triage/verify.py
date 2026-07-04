"""Deterministic verifier — ux-researcher / severity-triage.

Fractional credit rewards correctly-triaged findings:

    credit = (# findings whose reported severity matches the matrix) / (# findings)

The severity matrix (frequency = participants_affected / session_count):
    critical: task_blocking and frequency >= 0.5
    major:    task_blocking and frequency <  0.5
              or (not task_blocking) and frequency >= 0.5
    minor:    (not task_blocking) and frequency < 0.5

The answer key is computed from the SAME fixture the agent was given — nothing
is leaked into fixtures/. Deterministic (no clock/model). An empty submission
scores 0.0.
"""

from __future__ import annotations

import json
from pathlib import Path


def _expected_severities(fixtures: Path) -> dict[str, str]:
    data = json.loads((fixtures / "findings.json").read_text(encoding="utf-8"))
    session_count = data.get("session_count", 0)
    expected: dict[str, str] = {}
    for finding in data.get("findings", []):
        fid = str(finding.get("id"))
        blocking = bool(finding.get("task_blocking", False))
        affected = finding.get("participants_affected", 0)
        freq = (affected / session_count) if session_count else 0.0
        if blocking and freq >= 0.5:
            severity = "critical"
        elif blocking and freq < 0.5:
            severity = "major"
        elif (not blocking) and freq >= 0.5:
            severity = "major"
        else:
            severity = "minor"
        expected[fid] = severity
    return expected


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected_severities(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("severities")
    if not isinstance(reported, dict):
        return 0.0

    correct = 0
    for fid, severity in expected.items():
        got = reported.get(fid)
        if isinstance(got, str) and got.strip().lower() == severity:
            correct += 1
    return correct / len(expected)
