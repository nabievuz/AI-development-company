from __future__ import annotations

from datetime import datetime
from typing import Any


CREATED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_created_at(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.strptime(ts, CREATED_AT_FORMAT)
    except (ValueError, TypeError):
        return None


def is_valid_created_at(value: Any) -> bool:
    return isinstance(value, str) and parse_created_at(value) is not None


def count_invalid(events: list[dict[str, Any]]) -> int:
    return sum(1 for e in events if not is_valid_created_at(e.get("created_at", "")))


class DropCounter:

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0

    def bump(self) -> None:
        self.count += 1

    def __repr__(self) -> str:
        return f"DropCounter(count={self.count})"
