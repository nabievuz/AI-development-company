"""Deterministic verifier — chairman / never-auto-approve-audit."""
from __future__ import annotations

import json
from pathlib import Path

#: QONUN-5 floor categories — mirrors scripts/check_never_auto_approve.py's
#: hard-coded _QONUN5_FLOOR. This is the governance rule (given to the agent
#: in task.md); the answer is which specific fixture tickets trip it.
FLOOR = {
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
}


def _is_violation(ticket: dict) -> bool:
    approval = str(ticket.get("approval", ""))
    if not approval.startswith("auto"):
        return False
    ticket_type = ticket.get("ticket_type")
    labels = ticket.get("labels") or []
    if ticket_type in FLOOR:
        return True
    return any(label in FLOOR for label in labels)


def verify(submission: dict, fixtures: Path) -> float:
    tickets = json.loads((fixtures / "tickets.json").read_text(encoding="utf-8"))
    required = {t["id"] for t in tickets if _is_violation(t)}
    if not required:
        raise ValueError("fixture batch contains no violations")

    got_raw = submission.get("violations")
    if not isinstance(got_raw, list):
        return 0.0
    got = {v.strip() for v in got_raw if isinstance(v, str)}

    hits = len(got & required)
    false_pos = len(got - required)
    return max(0.0, (hits - false_pos) / len(required))
