"""Deterministic verifier — WS-G proof-delivery FIXTURE (DAS-1591).

Reuses the landed ``verify(submission, fixtures) -> float`` contract so this delivery
golden-set participates in the SAME anti-gaming boundary as every other eval task: the
committed ``fixtures/`` are the ground truth, the recorded ``submissions/`` are the
CLAIMED per-dimension verdict, and an EMPTY/degenerate submission earns 0.0.

The delivery scorecard itself is computed DETERMINISTICALLY from the committed artifacts
by ``agent_eval.score_delivery`` (the runner). Credit is earned only for a claim that
MATCHES the deterministic result AND is a real ``pass`` — a forged "all pass" claim over
this deliberately-incomplete fixture cannot reach 1.0.
"""
from __future__ import annotations

from pathlib import Path

import agent_eval


def verify(submission: dict, fixtures: Path) -> float:
    claimed = submission.get("dimensions") or {}
    if not claimed:
        return 0.0  # degenerate/empty submission earns no credit
    card = agent_eval.score_delivery(fixtures.parent, enabled=True)
    real = {d.dimension: d.status for d in card.dimensions}
    hits = sum(
        1
        for dim, status in claimed.items()
        if real.get(dim) == "pass" and str(status).lower() == "pass"
    )
    return agent_eval.clamp01(hits / len(agent_eval.ED1_DIMENSIONS))
