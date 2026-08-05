
from __future__ import annotations

import json
from pathlib import Path


def _severity(vuln: dict) -> str:
    cvss = float(vuln.get("cvss_score", 0.0))
    if cvss >= 9.0 or (vuln.get("public_exploit_available") and vuln.get("internet_facing")):
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    return "low"


def _decision(severity: str, data_sensitivity: str) -> str:
    if severity in ("critical", "high"):
        return "block"
    if severity == "medium" and data_sensitivity == "pii":
        return "block"
    return "accept"


def _expected(fixtures: Path) -> dict[str, tuple[str, str]]:
    data = json.loads((fixtures / "vulns.json").read_text(encoding="utf-8"))
    expected: dict[str, tuple[str, str]] = {}
    for vuln in data:
        severity = _severity(vuln)
        decision = _decision(severity, vuln.get("data_sensitivity"))
        expected[str(vuln["id"])] = (severity, decision)
    return expected


def verify(submission: dict, fixtures: Path) -> float:
    expected = _expected(fixtures)
    if not expected:
        return 0.0

    triage = submission.get("triage", {})
    if not isinstance(triage, dict):
        return 0.0

    total = 0.0
    for vid, (exp_severity, exp_decision) in expected.items():
        entry = triage.get(vid)
        if not isinstance(entry, dict):
            continue
        credit = 0.0
        if entry.get("severity") == exp_severity:
            credit += 0.5
        if entry.get("decision") == exp_decision:
            credit += 0.5
        total += credit
    return total / len(expected)
