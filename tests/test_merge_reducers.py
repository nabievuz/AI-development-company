"""tests/test_merge_reducers.py — pytest suite for scripts/merge_reducers.py.

Covers the three merge policies (append-only / owner-exclusive / aggregate),
their determinism guarantees, and the failure modes required by DAS-1448:
owner-exclusive FAILS on overlap; aggregate FAILS on an unknown reducer name;
the policy grammar accepts exactly the allowed forms.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import pytest  # noqa: E402
from merge_reducers import (  # noqa: E402
    MergeError,
    aggregate,
    append_only,
    is_valid_policy,
    merge,
    owner_exclusive,
    parse_policy,
)

# ---------------------------------------------------------------------------
# Grammar — parse_policy / is_valid_policy
# ---------------------------------------------------------------------------


def test_grammar_accepts_allowed_forms() -> None:
    assert parse_policy("append-only") == ("append-only", None)
    assert parse_policy("owner-exclusive") == ("owner-exclusive", None)
    assert parse_policy("aggregate:sum") == ("aggregate", "sum")
    assert parse_policy("aggregate:union") == ("aggregate", "union")
    for p in ("append-only", "owner-exclusive", "aggregate:sum", "aggregate:union"):
        assert is_valid_policy(p), p


def test_grammar_rejects_bad_forms() -> None:
    for bad in ("", "   ", "appendonly", "aggregate", "aggregate:", "aggregate:max",
                "owner_exclusive", "project"):
        assert not is_valid_policy(bad), bad
        with pytest.raises(MergeError):
            parse_policy(bad)


# ---------------------------------------------------------------------------
# append-only — deterministic lexical-by-ticket-id concat
# ---------------------------------------------------------------------------


def test_append_only_orders_by_ticket_id() -> None:
    contribs = [
        ("DAS-1002", ["b1", "b2"]),
        ("DAS-1001", ["a1", "a2"]),
    ]
    assert append_only(contribs) == ["a1", "a2", "b1", "b2"]


def test_append_only_is_input_order_independent() -> None:
    a = ("DAS-1001", ["a1", "a2"])
    b = ("DAS-1002", ["b1"])
    assert append_only([a, b]) == append_only([b, a]) == ["a1", "a2", "b1"]


def test_append_only_preserves_within_block_order() -> None:
    # Lines inside one contributor's block are never reordered.
    contribs = [("DAS-1001", ["z", "y", "x"])]
    assert append_only(contribs) == ["z", "y", "x"]


# ---------------------------------------------------------------------------
# owner-exclusive — disjoint union, FAIL on overlap
# ---------------------------------------------------------------------------


def test_owner_exclusive_unions_disjoint_mappings() -> None:
    contribs = [
        ("DAS-1001", {"a.py": 1}),
        ("DAS-1002", {"b.py": 2}),
    ]
    assert owner_exclusive(contribs) == {"a.py": 1, "b.py": 2}


def test_owner_exclusive_accepts_iterables_of_units() -> None:
    contribs = [("DAS-1001", ["a.py"]), ("DAS-1002", ["b.py"])]
    merged = owner_exclusive(contribs)
    assert set(merged.keys()) == {"a.py", "b.py"}


def test_owner_exclusive_is_input_order_independent() -> None:
    a = ("DAS-1001", {"a.py": 1})
    b = ("DAS-1002", {"b.py": 2})
    assert owner_exclusive([a, b]) == owner_exclusive([b, a])


def test_owner_exclusive_fails_on_overlap() -> None:
    contribs = [("DAS-1001", {"shared.py": 1}), ("DAS-1002", {"shared.py": 2})]
    with pytest.raises(MergeError, match="overlap"):
        owner_exclusive(contribs)


# ---------------------------------------------------------------------------
# aggregate — sum / union, FAIL on unknown reducer
# ---------------------------------------------------------------------------


def test_aggregate_sum() -> None:
    contribs = [("DAS-1001", 3), ("DAS-1002", 4), ("DAS-1003", 5)]
    assert aggregate(contribs, "sum") == 12


def test_aggregate_sum_is_input_order_independent() -> None:
    a, b, c = ("DAS-1001", 3), ("DAS-1002", 4), ("DAS-1003", 5)
    assert aggregate([a, b, c], "sum") == aggregate([c, a, b], "sum") == 12


def test_aggregate_union() -> None:
    contribs = [("DAS-1001", {1, 2}), ("DAS-1002", {2, 3})]
    assert aggregate(contribs, "union") == {1, 2, 3}


def test_aggregate_union_is_input_order_independent() -> None:
    a, b = ("DAS-1001", {1, 2}), ("DAS-1002", {2, 3})
    assert aggregate([a, b], "union") == aggregate([b, a], "union") == {1, 2, 3}


def test_aggregate_fails_on_unknown_reducer() -> None:
    with pytest.raises(MergeError, match="unknown aggregate reducer"):
        aggregate([("DAS-1001", 1)], "max")


# ---------------------------------------------------------------------------
# merge() dispatch
# ---------------------------------------------------------------------------


def test_merge_dispatches_by_policy() -> None:
    assert merge("append-only", [("DAS-1001", ["x"])]) == ["x"]
    assert merge("owner-exclusive", [("DAS-1001", {"a": 1})]) == {"a": 1}
    assert merge("aggregate:sum", [("DAS-1001", 2), ("DAS-1002", 3)]) == 5
    assert merge("aggregate:union", [("DAS-1001", {1}), ("DAS-1002", {2})]) == {1, 2}


def test_merge_raises_on_bad_policy() -> None:
    with pytest.raises(MergeError):
        merge("aggregate:max", [("DAS-1001", 1)])
    with pytest.raises(MergeError):
        merge("", [("DAS-1001", 1)])
