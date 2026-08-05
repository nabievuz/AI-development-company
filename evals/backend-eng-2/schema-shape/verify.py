from __future__ import annotations

import json
from pathlib import Path

_TYPE_MAP = {
    "string": str,
    "array": list,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
}


def _conforms(body: dict, schema: dict) -> bool:
    for field, type_name in schema.items():
        if field not in body:
            return False
        expected_type = _TYPE_MAP.get(type_name)
        if expected_type is None:
            continue
        value = body[field]

        if type_name == "number" and isinstance(value, bool):
            return False
        if not isinstance(value, expected_type):
            return False
    return True


def verify(submission: dict, fixtures: Path) -> float:
    contract = json.loads((fixtures / "contract.json").read_text(encoding="utf-8"))
    schema = contract["schema"]
    responses = contract["responses"]
    answers = submission.get("valid")
    if not isinstance(answers, dict) or not responses:
        return 0.0
    correct = 0
    for resp in responses:
        expected = _conforms(resp["body"], schema)
        if answers.get(resp["id"]) is expected:
            correct += 1
    return correct / len(responses)
