"""Deterministic verifier — board-member / charter-scope-classify."""
from __future__ import annotations

import json
from pathlib import Path


def _expected(fixtures: Path) -> dict[str, dict]:
    data = json.loads((fixtures / "charters.json").read_text(encoding="utf-8"))
    charters = data["charters"]
    out: dict[str, dict] = {}
    for prop in data["proposals"]:
        charter = charters[prop["dept"]]
        item = prop["item"]
        if item in charter["authority"]:
            out[prop["id"]] = {"status": "within_authority", "escalate_to": None}
            continue
        owner = next(
            (e["owner"] for e in charter["out_of_scope"] if e["item"] == item), None
        )
        if owner is not None:
            out[prop["id"]] = {"status": "escalate", "escalate_to": owner}
        else:
            # Not in either list under our fixture design — should not occur.
            out[prop["id"]] = {"status": "unknown", "escalate_to": None}
    return out


def _norm(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def verify(submission: dict, fixtures: Path) -> float:
    expected = _expected(fixtures)
    classifications = submission.get("classifications")
    if not isinstance(classifications, dict) or not classifications:
        return 0.0
    correct = 0
    for prop_id, want in expected.items():
        got = classifications.get(prop_id)
        if not isinstance(got, dict):
            continue
        if _norm(got.get("status")) == _norm(want["status"]) and _norm(
            got.get("escalate_to")
        ) == _norm(want["escalate_to"]):
            correct += 1
    return correct / len(expected)
