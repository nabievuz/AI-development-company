"""Deterministic verifier — cto / adr-gate-check.

Recomputes the AADL GATE-2/GATE-3 pass verdict and missing-section set per RFC
in ``fixtures/rfcs.json`` from the gate requirements stated in ``task.md``.
The expected answer is derived from the SAME fixture the agent was given —
applying the gate checklist correctly reproduces it, so nothing is leaked.
Deterministic (no clock/model). An empty submission scores 0.0 because the
`pass` gate must be matched before any partial credit for `missing` is
awarded (a blank/omitted `pass` never matches `True` or `False`).
"""

from __future__ import annotations

import json
from pathlib import Path

GATE2_REQUIRED = {"problem_statement", "architecture_diagram", "risk_analysis"}
GATE3_REQUIRED = GATE2_REQUIRED | {"security_review", "rollback_plan"}


def _required(gate_level: int) -> set[str]:
    return GATE3_REQUIRED if int(gate_level) >= 3 else GATE2_REQUIRED


def _expected(fixtures: Path) -> dict[str, tuple[bool, set[str]]]:
    data = json.loads((fixtures / "rfcs.json").read_text(encoding="utf-8"))
    expected: dict[str, tuple[bool, set[str]]] = {}
    for rfc in data:
        present = set(rfc.get("sections_present", []))
        required = _required(rfc.get("gate_level", 2))
        missing = required - present
        expected[str(rfc["id"])] = (len(missing) == 0, missing)
    return expected


def _rfc_credit(exp_pass: bool, exp_missing: set[str], entry: object) -> float:
    if not isinstance(entry, dict):
        return 0.0
    submitted_pass = entry.get("pass")
    if submitted_pass is not exp_pass:
        return 0.0

    submitted_missing = entry.get("missing", [])
    if not isinstance(submitted_missing, list):
        submitted_missing = []
    submitted_set = {str(x) for x in submitted_missing}

    if not exp_missing:
        return 1.0 if not submitted_set else 0.5

    hits = len(submitted_set & exp_missing)
    false_pos = len(submitted_set - exp_missing)
    missing_credit = max(0.0, (hits - false_pos) / len(exp_missing))
    return 0.5 + 0.5 * missing_credit


def verify(submission: dict, fixtures: Path) -> float:
    """Return fractional credit in [0.0, 1.0] for one submission."""
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    results = submission.get("results", {})
    if not isinstance(results, dict):
        return 0.0

    total = sum(
        _rfc_credit(exp_pass, exp_missing, results.get(rid))
        for rid, (exp_pass, exp_missing) in expected.items()
    )
    return total / len(expected)
