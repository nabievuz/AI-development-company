"""dgox/created_at.py — single source of truth for the ``created_at`` contract.

DAS-1633 (found by SRE Lead in the DAS-1618 round-2 re-review): ``events.py``'s
``validate_envelope`` used to accept *any non-empty string* as ``created_at``,
while every downstream consumer (``cost_ledger``, ``metrics_history_feeder``,
``wave_kpi``, ``metrics_lib``, ``trends``) had each independently re-implemented
a strict ``%Y-%m-%dT%H:%M:%SZ`` parser and silently skipped anything that did not
match — with no error, no warning, no dropped-record count. A caller emitting
``datetime.now(UTC).isoformat()`` (``+00:00``, possibly with microseconds)
therefore wrote an event that *validated* at the seam and then vanished from
every KPI, invisibly under-counting the budget ceiling and the clean-day
evidence window.

This module is the ONE place the format is defined and the ONE place a
timestamp is parsed against it. ``dgox.events.validate_envelope`` imports
``is_valid_created_at`` to REJECT (not silently normalise — see the module
docstring in ``events.py``) any envelope whose ``created_at`` does not conform,
closing the write seam. Every consumer that used to carry its own
``_parse_iso``/``_parse_created_at`` now delegates to ``parse_created_at`` here,
so a widened/narrowed contract is a one-line change, not five.

``count_invalid`` is the shared counting helper consumers use to surface how
many records in a batch they are about to (or did) exclude — turning a silent
drop into an observable number (DAS-1633 acceptance criterion #2).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

#: The one canonical ``created_at`` shape every producer must emit and every
#: consumer requires — UTC, second-resolution, zero-offset ``Z`` suffix.
#: No microseconds, no ``+00:00``, no other timezone spelling.
CREATED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_created_at(ts: str) -> datetime | None:
    """Strictly parse *ts* against ``CREATED_AT_FORMAT``; ``None`` if it does not match.

    Deliberately strict (``datetime.strptime``, not ``fromisoformat``) — a
    trailing ``+00:00`` offset, fractional seconds, or any other ISO-8601
    variant is REJECTED, not coerced. That strictness is what makes a mismatch
    loud enough to write-seam-reject instead of silently drifting downstream.
    """
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.strptime(ts, CREATED_AT_FORMAT)
    except (ValueError, TypeError):
        return None


def is_valid_created_at(value: Any) -> bool:
    """``True`` iff *value* is a string conforming exactly to ``CREATED_AT_FORMAT``."""
    return isinstance(value, str) and parse_created_at(value) is not None


def count_invalid(events: list[dict[str, Any]]) -> int:
    """Count events whose ``created_at`` is missing, empty, or non-conforming.

    Shared counting helper (DAS-1633 #2) — every consumer that filters events
    by ``created_at`` calls this over the same batch it is about to filter and
    surfaces the result, instead of letting the skip pass silently.
    """
    return sum(1 for e in events if not is_valid_created_at(e.get("created_at", "")))


class DropCounter:
    """Mutable counter a streaming filter bumps once per skipped record.

    Used where events are filtered one at a time (rather than counted over an
    already-materialised list via :func:`count_invalid`) so the caller can
    still observe a running total after the pass completes. Optional and
    additive: functions accepting a ``drop_counter`` default it to ``None`` and
    skip the bump entirely when the caller does not care to observe it —
    existing call sites are unaffected.
    """

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0

    def bump(self) -> None:
        self.count += 1

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"DropCounter(count={self.count})"
