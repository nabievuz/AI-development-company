"""token_usage.py — parse real agent token usage into DGO-X span token buckets.

R6 (observability). The cost-ledger math (``scripts/cost/cost_ledger.py``) is
real, but every live dispatch has emitted spans with token counts of ``0``
because **nothing parsed the actual agent run's usage** into them. This module
is that missing *source* seam: it maps a Claude / Anthropic usage block (as
reported by the Claude Code harness or the Messages API ``usage`` object) to the
three token fields a span carries — ``(input_tokens, output_tokens,
cached_input_tokens)`` — which ``dispatch_emitter.DispatchRecord`` already
threads end-to-end into the cost ledger and the T4 model-mix KPI.

Truth Oath (§0 of the FINALE program). Unknown / missing usage maps to ``0`` —
never a fabricated non-zero count — and a present-but-malformed count (negative,
non-integer) *raises* rather than silently coercing garbage into a dollar
figure. A wrong non-zero cost is worse than an honest ``0``.

Bucket mapping. The span and the ledger have three buckets, while Anthropic
reports up to four token counts::

    output_tokens        <- output_tokens
    cached_input_tokens  <- cache_read_input_tokens   (billed at the cached rate)
    input_tokens         <- input_tokens + cache_creation_input_tokens

Cache-*creation* tokens have no dedicated ledger rate (``config/budgets.yaml``
prices ``input`` / ``cached_input`` / ``output`` only), so they fold into the
full-price ``input`` bucket. That is conservative and honest: it under-counts
the ~1.25x cache-write premium rather than inventing a bucket the ledger cannot
price.

This module is pure: no clock, no network, no store read. It reuses the token
field names ``dispatch_emitter``/``dgox.events`` already define (it never forks
that contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Accepted key spellings for each logical count. Anthropic Messages API +
# Claude Code harness use the *_input_tokens names; the prompt/completion
# aliases let an OpenAI-shaped usage block map cleanly too (the engine is
# provider-abstracted per LAW 3).
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
    """The three token buckets a DGO-X span / the cost ledger understands."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    def as_tuple(self) -> tuple[int, int, int]:
        """Return ``(input_tokens, output_tokens, cached_input_tokens)``."""
        return (self.input_tokens, self.output_tokens, self.cached_input_tokens)

    @property
    def total(self) -> int:
        """Total tokens across all three buckets."""
        return self.input_tokens + self.output_tokens + self.cached_input_tokens


def _coerce(value: Any, field: str) -> int:
    """Return a non-negative int for one token count, else raise (never fabricate).

    ``None`` → ``0`` (an absent count is honestly zero). An integral float such
    as ``100.0`` (common after a JSON round-trip) is accepted; a ``bool`` is
    rejected explicitly (``bool`` is an ``int`` subclass but never a token
    count), and anything negative or non-integral raises ``ValueError``.
    """
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
    """Return the first present, non-null key's coerced value, or ``0`` if none.

    A present-but-``None`` value is treated as absent so a later same-group alias
    (e.g. ``cached_input_tokens`` after a null ``cache_read_input_tokens``) is not
    silently dropped to 0.
    """
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return _coerce(value, field)
    return 0


def parse_usage(usage: Mapping[str, Any] | None) -> TokenUsage:
    """Map a Claude / Anthropic ``usage`` block to the three span token buckets.

    Args:
        usage: The usage mapping from an agent run (``input_tokens``,
            ``output_tokens``, ``cache_read_input_tokens``,
            ``cache_creation_input_tokens`` — or the prompt/completion aliases),
            or ``None`` / empty when no usage was captured.

    Returns:
        A :class:`TokenUsage`. Missing / empty usage yields all zeros (honest
        "unknown", never fabricated).

    Raises:
        TypeError: If ``usage`` is a non-mapping, non-``None`` value.
        ValueError: If a present count is negative or non-integral.
    """
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
    """Return the token kwargs a ``DispatchRecord`` / ``build_span`` expects.

    Convenience for the collect step so a caller can write
    ``DispatchRecord(..., **usage_token_fields(usage))`` without re-deriving the
    bucket names — the single spelling of the token fields stays in
    ``dispatch_emitter``/``dgox.events``.
    """
    tu = parse_usage(usage)
    return {
        "input_tokens": tu.input_tokens,
        "output_tokens": tu.output_tokens,
        "cached_input_tokens": tu.cached_input_tokens,
    }
