"""Deterministic verifier — tech-writer / doc-link-check."""
from __future__ import annotations

import json
import re
from pathlib import Path

_LINK = re.compile(r"\]\(([^)]+)\)")


def verify(submission: dict, fixtures: Path) -> float:
    doc = (fixtures / "doc.md").read_text(encoding="utf-8")
    existing = set(json.loads((fixtures / "files.json").read_text(encoding="utf-8"))["files"])
    targets = set(_LINK.findall(doc))
    broken = targets - existing
    if not broken:
        return 0.0
    reported = submission.get("broken_links")
    if not isinstance(reported, list):
        return 0.0
    got = {str(x) for x in reported}
    hits = len(got & broken)
    false_pos = len(got - broken)
    return max(0.0, (hits - false_pos) / len(broken))
