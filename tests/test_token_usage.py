
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from token_usage import TokenUsage, parse_usage, usage_token_fields


def test_none_and_empty_are_zero() -> None:
    assert parse_usage(None).as_tuple() == (0, 0, 0)
    assert parse_usage({}).as_tuple() == (0, 0, 0)


def test_basic_input_output() -> None:
    tu = parse_usage({"input_tokens": 100, "output_tokens": 50})
    assert tu.as_tuple() == (100, 50, 0)
    assert tu.total == 150


def test_cache_read_maps_to_cached_bucket() -> None:
    tu = parse_usage(
        {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200}
    )
    assert tu.as_tuple() == (100, 50, 200)


def test_cache_creation_folds_into_input() -> None:
    tu = parse_usage(
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 30,
            "cache_read_input_tokens": 200,
        }
    )
    assert tu.input_tokens == 130
    assert tu.cached_input_tokens == 200
    assert tu.output_tokens == 50


def test_openai_style_aliases() -> None:
    tu = parse_usage({"prompt_tokens": 10, "completion_tokens": 7})
    assert tu.as_tuple() == (10, 7, 0)


def test_cached_input_tokens_alias() -> None:

    tu = parse_usage({"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 9})
    assert tu.cached_input_tokens == 9


def test_present_but_none_alias_falls_through() -> None:

    tu = parse_usage(
        {"cache_read_input_tokens": None, "cached_input_tokens": 200, "input_tokens": 100, "output_tokens": 50}
    )
    assert tu.cached_input_tokens == 200
    assert parse_usage({"input_tokens": None, "prompt_tokens": 7, "output_tokens": 1}).input_tokens == 7


def test_extra_keys_ignored() -> None:
    tu = parse_usage(
        {"input_tokens": 1, "output_tokens": 2, "service_tier": "standard", "foo": "bar"}
    )
    assert tu.as_tuple() == (1, 2, 0)


def test_integral_float_tolerated() -> None:
    assert parse_usage({"input_tokens": 100.0, "output_tokens": 50.0}).as_tuple() == (
        100,
        50,
        0,
    )


@pytest.mark.parametrize("bad", [-1, "12", 1.5, True, [1]])
def test_malformed_counts_raise(bad: object) -> None:
    with pytest.raises(ValueError):
        parse_usage({"input_tokens": bad, "output_tokens": 1})


def test_usage_token_fields_kwargs() -> None:
    fields = usage_token_fields(
        {"input_tokens": 5, "output_tokens": 6, "cache_read_input_tokens": 7}
    )
    assert fields == {"input_tokens": 5, "output_tokens": 6, "cached_input_tokens": 7}


def test_usage_token_fields_none_is_zero() -> None:
    assert usage_token_fields(None) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
    }


def test_non_mapping_raises() -> None:
    with pytest.raises(TypeError):
        parse_usage([1, 2, 3])


def test_token_usage_default_is_zero() -> None:
    assert TokenUsage().as_tuple() == (0, 0, 0)
    assert TokenUsage().total == 0
