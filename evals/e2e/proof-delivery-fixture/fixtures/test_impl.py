"""HONEST suite for impl.py — it genuinely exercises the implementation.

Baseline: green against the real impl. Under the D6 mutant (every body ->
``return None``), ``counted`` returns None and ``all_gates_closed`` returns None, so
these assertions turn RED — which is exactly what the mutation probe requires of a
non-gaming suite. Compare fixtures-only-in-tests/ variants built by the test file for
the gaming case (a suite that stays green against the mutant).
"""
from __future__ import annotations

import impl


def test_counted_matches_merged_and_green() -> None:
    events = [
        {"merged_pr": True, "ci_status": "green"},
        {"merged_pr": True, "ci_status": "red"},
        {"merged_pr": False, "ci_status": "green"},
    ]
    assert impl.counted(events) == 1


def test_counted_empty_is_zero() -> None:
    assert impl.counted([]) == 0


def test_all_gates_closed_true() -> None:
    assert impl.all_gates_closed({f"gate-{g}": "closed" for g in range(1, 7)}) is True


def test_all_gates_closed_false_when_one_open() -> None:
    statuses = {f"gate-{g}": "closed" for g in range(1, 7)}
    statuses["gate-4"] = "open"
    assert impl.all_gates_closed(statuses) is False
