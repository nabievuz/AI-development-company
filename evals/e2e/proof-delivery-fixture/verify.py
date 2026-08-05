from __future__ import annotations

from pathlib import Path

import agent_eval


def verify(submission: dict, fixtures: Path) -> float:
    claimed = submission.get("dimensions") or {}
    if not claimed:
        return 0.0
    card = agent_eval.score_delivery(fixtures.parent, enabled=True)
    real = {d.dimension: d.status for d in card.dimensions}
    hits = sum(
        1
        for dim, status in claimed.items()
        if real.get(dim) == "pass" and str(status).lower() == "pass"
    )
    return agent_eval.clamp01(hits / len(agent_eval.ED1_DIMENSIONS))
