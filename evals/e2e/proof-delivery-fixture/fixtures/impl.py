"""A small real implementation the D6 mutation probe gutts and re-tests.

This stands in for "the delivered code" of a proof delivery: it has genuine
behaviour, so a suite that actually exercises it MUST turn red when the bodies are
neutralised. Kept dependency-free so the probe runs it in an isolated tmp dir.
"""
from __future__ import annotations


def counted(events: list[dict]) -> int:
    """Number of completion events that carry a merged PR AND green CI."""
    return sum(
        1
        for e in events
        if e.get("merged_pr") and str(e.get("ci_status", "")).lower() == "green"
    )


def all_gates_closed(statuses: dict[str, str]) -> bool:
    """True iff all six AADL gates are marked ``closed``."""
    return all(statuses.get(f"gate-{g}") == "closed" for g in range(1, 7))
