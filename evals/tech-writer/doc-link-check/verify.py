from __future__ import annotations

import json
import re
from pathlib import Path

_LINK = re.compile(r"\]\(([^)]+)\)")


def _document(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["document"])


def verify(submission: dict, fixtures: Path) -> float:
    doc = _document(fixtures / "doc.json")
    existing = set(json.loads((fixtures / "files.json").read_text(encoding="utf-8"))["files"])
    targets = set(_LINK.findall(doc))
    broken = targets - existing
    if not broken:
        raise ValueError(
            "fixture doc has no broken links — "
            "this task would grade every answer as wrong"
        )
    reported = submission.get("broken_links")
    if not isinstance(reported, list):
        return 0.0
    got = {str(x) for x in reported}
    hits = len(got & broken)
    false_pos = len(got - broken)
    return max(0.0, (hits - false_pos) / len(broken))
