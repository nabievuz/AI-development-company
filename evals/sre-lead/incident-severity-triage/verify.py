from __future__ import annotations

import json
from pathlib import Path


def _expected_severity(incident: dict) -> str:
    error_rate = incident["error_rate_pct"]
    revenue_impacting = bool(incident["revenue_impacting"])
    data_loss = bool(incident["data_loss"])

    if data_loss or (revenue_impacting and error_rate >= 50):
        return "SEV1"
    if revenue_impacting and error_rate >= 5:
        return "SEV2"
    if error_rate >= 1:
        return "SEV3"
    return "SEV4"


def verify(submission: dict, fixtures: Path) -> float:
    incidents = json.loads((fixtures / "incidents.json").read_text(encoding="utf-8"))
    if not incidents:
        return 0.0

    reported = submission.get("severities")
    if not isinstance(reported, dict):
        return 0.0

    hits = 0
    for incident in incidents:
        expected = _expected_severity(incident)
        if reported.get(incident["id"]) == expected:
            hits += 1
    return hits / len(incidents)
