
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


_INPUT_KEYS = ("input_tokens", "prompt_tokens")
_OUTPUT_KEYS = ("output_tokens", "completion_tokens")
_CACHE_READ_KEYS = (
    "cache_read_input_tokens",
    "cached_input_tokens",
    "cache_read_tokens",
)
_CACHE_CREATE_KEYS = ("cache_creation_input_tokens", "cache_creation_tokens")


@dataclass(frozen=True)
class TokenUsage:

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.input_tokens, self.output_tokens, self.cached_input_tokens)

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cached_input_tokens


def _coerce(value: Any, field: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer token count, not a bool: {value!r}")
    if not isinstance(value, int):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        else:
            raise ValueError(f"{field} must be an integer token count; got {value!r}")
    if value < 0:
        raise ValueError(f"{field} must be a non-negative token count; got {value!r}")
    return value


def _first(usage: Mapping[str, Any], keys: tuple[str, ...], field: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return _coerce(value, field)
    return 0


def parse_usage(usage: Mapping[str, Any] | None) -> TokenUsage:
    if usage is None:
        return TokenUsage()
    if not isinstance(usage, Mapping):
        raise TypeError(f"usage must be a mapping or None; got {type(usage).__name__}")
    if not usage:
        return TokenUsage()
    base_input = _first(usage, _INPUT_KEYS, "input_tokens")
    cache_create = _first(usage, _CACHE_CREATE_KEYS, "cache_creation_input_tokens")
    output = _first(usage, _OUTPUT_KEYS, "output_tokens")
    cache_read = _first(usage, _CACHE_READ_KEYS, "cache_read_input_tokens")
    return TokenUsage(
        input_tokens=base_input + cache_create,
        output_tokens=output,
        cached_input_tokens=cache_read,
    )


def usage_token_fields(usage: Mapping[str, Any] | None) -> dict[str, int]:
    tu = parse_usage(usage)
    return {
        "input_tokens": tu.input_tokens,
        "output_tokens": tu.output_tokens,
        "cached_input_tokens": tu.cached_input_tokens,
    }
