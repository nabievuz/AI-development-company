
from __future__ import annotations

import json
from pathlib import Path

GATE2_REQUIRED = {"data_flow_diagram", "trust_boundaries", "mitigations"}
GATE4_REQUIRED = GATE2_REQUIRED | {"redteam_report", "risk_acceptance_log"}
GATE5_REQUIRED = GATE4_REQUIRED | {"pen_test_results", "secrets_scan_clean"}


def _required(gate_level: int) -> set[str]:
    level = int(gate_level)
    if level >= 5:
        return GATE5_REQUIRED
    if level >= 4:
        return GATE4_REQUIRED
    return GATE2_REQUIRED


def _expected(fixtures: Path) -> dict[str, tuple[bool, set[str]]]:
    data = json.loads((fixtures / "reviews.json").read_text(encoding="utf-8"))
    expected: dict[str, tuple[bool, set[str]]] = {}
    for rfc in data:
        present = set(rfc.get("evidence_present", []))
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
