#!/usr/bin/env python3


from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


KNOWN_AGGREGATORS = frozenset({"sum", "union"})


_SCALAR_POLICIES = frozenset({"append-only", "owner-exclusive"})


class MergeError(Exception):
    pass


def parse_policy(policy: str) -> tuple[str, str | None]:
    p = (policy or "").strip()
    if not p:
        raise MergeError("empty merge_policy")
    if p in _SCALAR_POLICIES:
        return (p, None)
    if p.startswith("aggregate:"):
        name = p.split(":", 1)[1].strip()
        if not name:
            raise MergeError("aggregate: requires a reducer name")
        if name not in KNOWN_AGGREGATORS:
            raise MergeError(
                f"unknown aggregate reducer '{name}'; "
                f"known: {sorted(KNOWN_AGGREGATORS)}"
            )
        return ("aggregate", name)
    raise MergeError(
        f"unrecognized merge_policy '{policy}'; allowed: append-only, "
        "owner-exclusive, aggregate:<sum|union>"
    )


def is_valid_policy(policy: str) -> bool:
    try:
        parse_policy(policy)
        return True
    except MergeError:
        return False


Contribution = tuple[Any, Any]


def _ordered(contributions: Iterable[Contribution]) -> list[Contribution]:
    return sorted(contributions, key=lambda c: str(c[0]))


def append_only(contributions: Iterable[Contribution]) -> list[str]:
    merged: list[str] = []
    for _tid, payload in _ordered(contributions):
        merged.extend(list(payload))
    return merged


def owner_exclusive(contributions: Iterable[Contribution]) -> dict[Any, Any]:
    merged: dict[Any, Any] = {}
    owner: dict[Any, Any] = {}
    for tid, payload in _ordered(contributions):
        if isinstance(payload, Mapping):
            items = list(payload.items())
        else:
            items = [(unit, None) for unit in payload]
        for unit, value in items:
            if unit in merged:
                raise MergeError(
                    f"owner-exclusive overlap on unit {unit!r}: claimed by both "
                    f"{owner[unit]!r} and {tid!r}"
                )
            merged[unit] = value
            owner[unit] = tid
    return merged


def aggregate(contributions: Iterable[Contribution], reducer_name: str) -> Any:
    if reducer_name not in KNOWN_AGGREGATORS:
        raise MergeError(
            f"unknown aggregate reducer '{reducer_name}'; "
            f"known: {sorted(KNOWN_AGGREGATORS)}"
        )
    ordered = _ordered(contributions)
    if reducer_name == "sum":
        total: Any = 0
        for _tid, payload in ordered:
            total = total + payload
        return total

    out: set[Any] = set()
    for _tid, payload in ordered:
        out |= set(payload)
    return out


def merge(policy: str, contributions: Iterable[Contribution]) -> Any:
    kind, agg = parse_policy(policy)
    if kind == "append-only":
        return append_only(contributions)
    if kind == "owner-exclusive":
        return owner_exclusive(contributions)
    assert agg is not None
    return aggregate(contributions, agg)


__all__ = [
    "KNOWN_AGGREGATORS",
    "MergeError",
    "parse_policy",
    "is_valid_policy",
    "append_only",
    "owner_exclusive",
    "aggregate",
    "merge",
]
