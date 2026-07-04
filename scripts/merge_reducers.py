#!/usr/bin/env python3
"""merge_reducers.py — deterministic reducers that merge parallel same-zone outputs.

Companion to the OPTIONAL ``merge_policy:`` ticket frontmatter field validated
by ``scripts/board_lint.py`` (rule R10).  The ``/daslab-cycle`` correctness
guard normally forbids two tickets touching the same repo ``zone:`` in one wave
(ADR-0016) — a merge-conflict brake.  When a zone opts in with a *permitting*
``merge_policy``, two same-zone tickets MAY run in one wave; these reducers then
deterministically combine the two parallel outputs into one merged result.

This module is **dependency-free** (stdlib only) so it is unit-testable in
isolation and importable by both the lint layer (``board_lint`` imports
``is_valid_policy``) and a future dispatch hook.

Contribution model
-------------------
A *contribution* is one parallel ticket's output for the shared zone, modelled
as a ``(ticket_id, payload)`` pair.  The payload shape depends on the policy:

- ``append-only``     — payload is an iterable of lines (str).  Merged output is
  the per-contributor blocks concatenated in **lexical ticket-id order**; no
  line is dropped or reordered within a contributor's block.
- ``owner-exclusive`` — payload is a mapping (owned-unit -> value) OR an
  iterable of owned units.  Merged output is the disjoint **union**; a
  ``MergeError`` is raised if two contributions own the same unit.
- ``aggregate:<r>``   — payload is a value combined by the named reducer.
  ``sum`` adds numerics; ``union`` unions sets/iterables.  An unknown reducer
  name raises ``MergeError``.

Determinism
-----------
Every reducer is deterministic.  Where the policy promises order-independence
(``owner-exclusive`` union, ``aggregate:sum``, ``aggregate:union``) the result
is identical regardless of input ordering.  ``append-only`` fixes a stable
concat order by ticket id, so it too is independent of the input list order.

Grammar authority
-----------------
``KNOWN_AGGREGATORS`` / ``parse_policy`` / ``is_valid_policy`` are the single
source of truth for the ``merge_policy`` grammar.  ``board_lint`` imports them
so the lint layer and the reducer library can never drift apart.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# ---------------------------------------------------------------------------
# Grammar (single source of truth, imported by board_lint R10)
# ---------------------------------------------------------------------------

#: Aggregation reducers recognised by ``aggregate:<name>``.
KNOWN_AGGREGATORS = frozenset({"sum", "union"})

#: Policy kinds that permit a same-zone pair (all of them, once valid).
_SCALAR_POLICIES = frozenset({"append-only", "owner-exclusive"})


class MergeError(Exception):
    """Raised when a merge is impossible or a merge_policy is malformed."""


def parse_policy(policy: str) -> tuple[str, str | None]:
    """Return ``(kind, aggregator)`` for a ``merge_policy`` string, else raise.

    ``kind`` is one of ``"append-only"``, ``"owner-exclusive"``, ``"aggregate"``.
    ``aggregator`` is the reducer name for ``aggregate:<name>``, else ``None``.
    Raises :class:`MergeError` on empty, unknown, or malformed input.
    """
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
    """True iff *policy* is a well-formed, recognised ``merge_policy`` value."""
    try:
        parse_policy(policy)
        return True
    except MergeError:
        return False


# ---------------------------------------------------------------------------
# Contribution helpers
# ---------------------------------------------------------------------------

Contribution = tuple[Any, Any]  # (ticket_id, payload)


def _ordered(contributions: Iterable[Contribution]) -> list[Contribution]:
    """Return contributions sorted by ticket id (stable, deterministic)."""
    return sorted(contributions, key=lambda c: str(c[0]))


# ---------------------------------------------------------------------------
# Reducers
# ---------------------------------------------------------------------------

def append_only(contributions: Iterable[Contribution]) -> list[str]:
    """Concatenate each contributor's lines in lexical ticket-id order.

    No line is dropped or reordered *within* a contributor's block; only the
    relative order of the blocks is fixed (by ticket id), so the result is
    independent of the order the contributions arrive in.
    """
    merged: list[str] = []
    for _tid, payload in _ordered(contributions):
        merged.extend(list(payload))  # preserve within-block order verbatim
    return merged


def owner_exclusive(contributions: Iterable[Contribution]) -> dict[Any, Any]:
    """Union of disjoint owned units; FAIL on overlap.

    Each payload is a mapping ``{owned-unit: value}`` or an iterable of owned
    units (value defaults to ``None``).  Raises :class:`MergeError` if two
    contributions claim the same owned unit.
    """
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
    """Combine payload values by the named aggregation reducer.

    ``sum`` numerically adds the payloads; ``union`` unions them into a set.
    Raises :class:`MergeError` on an unknown reducer name.
    """
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
    # union
    out: set[Any] = set()
    for _tid, payload in ordered:
        out |= set(payload)
    return out


def merge(policy: str, contributions: Iterable[Contribution]) -> Any:
    """Dispatch to the reducer named by *policy* and merge *contributions*.

    Raises :class:`MergeError` if *policy* is malformed/unknown, or if the
    chosen reducer fails (owner-exclusive overlap, unknown aggregator).
    """
    kind, agg = parse_policy(policy)
    if kind == "append-only":
        return append_only(contributions)
    if kind == "owner-exclusive":
        return owner_exclusive(contributions)
    assert agg is not None  # parse_policy guarantees a name for aggregate
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
