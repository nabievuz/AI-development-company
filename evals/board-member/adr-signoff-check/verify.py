from __future__ import annotations

import json
import re
from pathlib import Path


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def _expected(fixtures: Path) -> dict[str, object]:
    rules = json.loads((fixtures / "rules.json").read_text(encoding="utf-8"))
    draft = _document(fixtures / "adr_draft.json")

    present_sections = set(re.findall(r"^##\s+(.+?)\s*$", draft, flags=re.MULTILINE))
    required_sections = set(rules["required_sections"])
    missing_sections = required_sections - present_sections

    signed_off = set()
    for line in draft.splitlines():
        m = re.match(r"^-\s*([\w-]+)\s*:\s*(\w+)\s*$", line.strip())
        if m and m.group(2).lower() == "approved":
            signed_off.add(m.group(1).lower())

    required_roles = set(rules["signoff_requirements"].get(rules["kind"], []))
    missing_signoffs = required_roles - signed_off

    return {
        "pass": not missing_sections and not missing_signoffs,
        "missing_sections": missing_sections,
        "missing_signoffs": missing_signoffs,
    }


def _as_str_set(value: object) -> set[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(v, str) for v in value):
        return None
    return {v.strip().lower() for v in value}


def verify(submission: dict, fixtures: Path) -> float:
    if not submission:
        return 0.0
    expected = _expected(fixtures)
    credit = 0.0

    got_pass = submission.get("pass")
    if isinstance(got_pass, bool) and got_pass == expected["pass"]:
        credit += 1.0 / 3.0

    got_missing_sections = _as_str_set(submission.get("missing_sections"))
    expected_sections = {s.lower() for s in expected["missing_sections"]}
    if got_missing_sections is not None and got_missing_sections == expected_sections:
        credit += 1.0 / 3.0

    got_missing_signoffs = _as_str_set(submission.get("missing_signoffs"))
    expected_signoffs = {s.lower() for s in expected["missing_signoffs"]}
    if got_missing_signoffs is not None and got_missing_signoffs == expected_signoffs:
        credit += 1.0 / 3.0

    return max(0.0, min(1.0, credit))
