"""Deterministic verifier — security-eng / authz-missing."""
from __future__ import annotations

import json
from pathlib import Path


def _unprotected(fixtures: Path) -> set[str]:
    routes = json.loads((fixtures / "routes.json").read_text(encoding="utf-8"))["routes"]
    return {
        str(r.get("name"))
        for r in routes
        if not r.get("auth", False) and not r.get("public", False)
    }


def verify(submission: dict, fixtures: Path) -> float:
    expected = _unprotected(fixtures)
    if not expected:
        return 0.0
    reported = submission.get("unprotected")
    if not isinstance(reported, list):
        return 0.0
    got = {str(x) for x in reported}
    hits = len(got & expected)
    false_pos = len(got - expected)
    return max(0.0, (hits - false_pos) / len(expected))
