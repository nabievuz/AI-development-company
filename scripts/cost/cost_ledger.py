"""cost/cost_ledger.py — Per-ticket/agent/tier/run token and cost aggregation.

Reads ``span`` events from the DGO-X event store via
``scripts/dgox/events.py::iter_events`` (no re-implemented parsing) and rolls
up token counts and estimated USD cost four ways:

    * per ticket   (ticket_id / trace_id)
    * per agent    (gen_ai.agent.name)
    * per tier     (gen_ai.request.model, normalised to opus/sonnet/haiku)
    * per run      (run_id)

Pricing is loaded from ``config/budgets.yaml`` (SSOT — verified via the
claude-api skill, Current Models table cached 2026-06-04).  An unknown/unpriced
tier contributes its raw token counts but ``0.0`` estimated cost; it is surfaced
in the ``unknown_tiers`` set in the returned :class:`CostLedger`, never silently
dropped.

Inert-by-design
---------------
When the event store is absent or contains zero ``span`` events,
:func:`aggregate_spans` returns ``None`` — identical to the pattern in
``scripts/metrics_lib.py``.  This keeps the loop-off baseline clean and prevents
a fabricated cost from blocking the T7 gate.

Reconciliation invariant
------------------------
The per-ticket, per-agent, per-tier, and per-run groups each MUST re-bucket
all tokens — no span is added or dropped.  For each axis independently::

    sum(group.input_tokens for group in axis) == raw_input_tokens
    sum(group.output_tokens for group in axis) == raw_output_tokens
    sum(group.cached_input_tokens for group in axis) == raw_cached_input_tokens

``scripts/check_cost.py`` and ``tests/test_cost_ledger.py`` both assert this.

ORGANISM WS3 P12 / DAS-1459  |  AADL GATE-3 Development  |  owner: cost
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating root (LAW A — never a hardcoded path).
# cost_ledger.py lives at  scripts/cost/cost_ledger.py  → scripts/ is two
# levels up from __file__.  We insert scripts/ once so dgox.events imports
# as ``from dgox.events import iter_events`` regardless of cwd.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.events import iter_events  # noqa: E402

# ---------------------------------------------------------------------------
# Locate the repo root (same LAW A pattern as _paths.py).
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:  # noqa: BLE001
        pass
    return _SCRIPTS_DIR.parent


_ROOT = _repo_root()
_BUDGETS_PATH = _ROOT / "config" / "budgets.yaml"

# ---------------------------------------------------------------------------
# Tier normalisation  (model id → tier slug)
# ---------------------------------------------------------------------------

#: Short tier slugs → canonical tier key.  Both short slugs and full model ids
#: that CONTAIN the slug (lower-cased) map to the tier key.
_TIER_SLUGS: dict[str, str] = {
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
}


def _normalise_tier(model: str) -> str:
    """Map a raw ``gen_ai.request.model`` value to one of opus/sonnet/haiku.

    Accepts both short tier slugs (``"opus"``) and full model ids
    (``"claude-opus-4-8"``).  Returns the raw lower-cased string unchanged
    when no tier matches — callers detect unknowns via the ``unknown_tiers``
    field of :class:`CostLedger`.
    """
    lower = model.lower()
    for slug, tier in _TIER_SLUGS.items():
        if slug in lower:
            return tier
    return lower  # unknown; surfaced, not dropped


# ---------------------------------------------------------------------------
# Pricing loader  (config/budgets.yaml is the SSOT)
# ---------------------------------------------------------------------------

@dataclass
class TierPricing:
    """Unit prices (USD per 1 million tokens) for one model tier."""

    tier: str
    input_per_1m: float
    cached_input_per_1m: float
    output_per_1m: float


def _load_pricing(budgets_path: Path = _BUDGETS_PATH) -> dict[str, TierPricing]:
    """Parse ``config/budgets.yaml`` and return ``{tier: TierPricing}``.

    Uses only the stdlib ``re`` module — no third-party YAML dependency.
    Raises ``FileNotFoundError`` if the file is missing, ``ValueError`` on a
    parse error.
    """
    import re

    text = budgets_path.read_text(encoding="utf-8")
    pricing: dict[str, TierPricing] = {}

    # Line-by-line mini-parser: find a tier-slug heading (any indentation),
    # then collect its immediate child key-value pairs until the indentation
    # returns to the heading level or we hit a blank/comment line.
    #
    # This handles both flat  ``opus:\n  input_per_1m: ...``  and nested
    # ``tiers:\n  opus:\n    input_per_1m: ...`` without regex backtracking.
    kv_re = re.compile(r"^([ \t]*)(\w[\w_]*):\s*(.*)")
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = kv_re.match(line)
        if m:
            indent_level = len(m.group(1))
            slug = m.group(2)
            if slug in _TIER_SLUGS and m.group(3).strip() == "":
                # This line is a tier heading: collect child key-value pairs.
                children: dict[str, float] = {}
                j = i + 1
                while j < len(lines):
                    child_line = lines[j]
                    cm = kv_re.match(child_line)
                    if cm and len(cm.group(1)) > indent_level:
                        key, val = cm.group(2), cm.group(3).strip()
                        with contextlib.suppress(TypeError, ValueError):
                            children[key] = float(val)
                        j += 1
                    elif child_line.strip() == "" or child_line.lstrip().startswith("#"):
                        j += 1  # skip blanks and comments inside the block
                    else:
                        break  # back to parent indent — tier block ends
                # Extract the three required fields.
                if {
                    "input_per_1m",
                    "cached_input_per_1m",
                    "output_per_1m",
                } <= children.keys():
                    pricing[slug] = TierPricing(
                        tier=slug,
                        input_per_1m=children["input_per_1m"],
                        cached_input_per_1m=children["cached_input_per_1m"],
                        output_per_1m=children["output_per_1m"],
                    )
        i += 1
    if not pricing:
        raise ValueError(
            f"No tier pricing found in {budgets_path}; "
            "expected sections for opus, sonnet, haiku."
        )
    return pricing


# ---------------------------------------------------------------------------
# Per-group accumulator
# ---------------------------------------------------------------------------

@dataclass
class TokenGroup:
    """Accumulated token counts and estimated USD cost for one group key."""

    key: str                         # e.g. ticket_id, agent name, tier, run_id
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    span_count: int = 0
    estimated_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Main result type
# ---------------------------------------------------------------------------

@dataclass
class CostLedger:
    """Aggregated token-and-cost view over all span events.

    Each axis (``by_ticket``, ``by_agent``, ``by_tier``, ``by_run``) re-buckets
    the same raw token totals — never adds or drops them.  The four invariants::

        sum(g.input_tokens for g in by_ticket.values()) == raw_input_tokens
        sum(g.input_tokens for g in by_agent.values())  == raw_input_tokens
        sum(g.input_tokens for g in by_tier.values())   == raw_input_tokens
        sum(g.input_tokens for g in by_run.values())    == raw_input_tokens

    (and likewise for output_tokens and cached_input_tokens).

    Spans whose ``run_id`` field is absent are bucketed under the special key
    ``"(no run_id)"``.
    """

    by_ticket: dict[str, TokenGroup] = field(default_factory=dict)
    by_agent: dict[str, TokenGroup] = field(default_factory=dict)
    by_tier: dict[str, TokenGroup] = field(default_factory=dict)
    by_run: dict[str, TokenGroup] = field(default_factory=dict)

    #: Raw (un-bucketed) totals — used by reconciliation checks.
    raw_input_tokens: int = 0
    raw_cached_input_tokens: int = 0
    raw_output_tokens: int = 0
    raw_estimated_cost_usd: float = 0.0
    raw_span_count: int = 0

    #: Tier slugs that appeared in spans but had no pricing entry.
    unknown_tiers: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Core aggregation function
# ---------------------------------------------------------------------------

NO_RUN_ID_KEY = "(no run_id)"


def _add_to_group(
    groups: dict[str, TokenGroup],
    key: str,
    input_tok: int,
    cached_tok: int,
    output_tok: int,
    cost: float,
) -> None:
    if key not in groups:
        groups[key] = TokenGroup(key=key)
    g = groups[key]
    g.input_tokens += input_tok
    g.cached_input_tokens += cached_tok
    g.output_tokens += output_tok
    g.span_count += 1
    g.estimated_cost_usd += cost


def aggregate_spans(
    store_path: Path | str | None = None,
    budgets_path: Path = _BUDGETS_PATH,
) -> CostLedger | None:
    """Aggregate all ``span`` events from the DGO-X event store.

    Args:
        store_path:   Path to the JSONL event store (defaults to
                      ``board/.events.jsonl`` via ``iter_events``).
        budgets_path: Path to ``config/budgets.yaml`` (defaults to the
                      canonical config path).

    Returns:
        A :class:`CostLedger` when one or more span events exist, or ``None``
        when the store is absent / has no span events (inert — gate stays off
        until real waves produce real data).
    """
    pricing = _load_pricing(budgets_path)

    ledger = CostLedger()
    has_spans = False

    for ev in iter_events(store_path, event_type="span"):
        # --- extract fields (verbatim names from events.py SPAN_OTEL_ATTRS) ---
        ticket_id: str = str(ev.get("ticket_id") or ev.get("trace_id") or "")
        run_id: str = str(ev.get("run_id") or "") or NO_RUN_ID_KEY
        agent: str = str(ev.get("gen_ai.agent.name") or "(unknown agent)")
        model_raw: str = str(ev.get("gen_ai.request.model") or "")
        tier: str = _normalise_tier(model_raw) if model_raw else "(unknown tier)"

        input_tok: int = _safe_int(ev.get("gen_ai.usage.input_tokens"))
        output_tok: int = _safe_int(ev.get("gen_ai.usage.output_tokens"))
        cached_tok: int = _safe_int(ev.get("gen_ai.usage.cached_input_tokens"))

        # --- cost estimation ---
        tp = pricing.get(tier)
        if tp is None:
            ledger.unknown_tiers.add(tier)
            cost = 0.0
        else:
            cost = (
                input_tok * tp.input_per_1m
                + cached_tok * tp.cached_input_per_1m
                + output_tok * tp.output_per_1m
            ) / 1_000_000.0

        # --- raw totals ---
        ledger.raw_input_tokens += input_tok
        ledger.raw_cached_input_tokens += cached_tok
        ledger.raw_output_tokens += output_tok
        ledger.raw_estimated_cost_usd += cost
        ledger.raw_span_count += 1
        has_spans = True

        # --- bucket into the four axes ---
        key_ticket = ticket_id or "(no ticket_id)"
        _add_to_group(ledger.by_ticket, key_ticket, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_agent, agent, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_tier, tier, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_run, run_id, input_tok, cached_tok, output_tok, cost)

    if not has_spans:
        return None

    return ledger


def _safe_int(value: Any) -> int:
    """Coerce a span token field to int; silently return 0 on None/bad value."""
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Reconciliation helper (used by check_cost.py and tests)
# ---------------------------------------------------------------------------

def check_reconciliation(ledger: CostLedger) -> list[str]:
    """Return a list of reconciliation error strings (empty = invariants hold).

    Checks that the per-ticket, per-agent, per-tier, and per-run token totals
    each sum back to the raw span totals for input, cached_input, and output
    tokens independently.  An error means spans were added or dropped — a bug.
    """
    errors: list[str] = []
    for axis_name, groups in (
        ("by_ticket", ledger.by_ticket),
        ("by_agent", ledger.by_agent),
        ("by_tier", ledger.by_tier),
        ("by_run", ledger.by_run),
    ):
        in_sum = sum(g.input_tokens for g in groups.values())
        ci_sum = sum(g.cached_input_tokens for g in groups.values())
        out_sum = sum(g.output_tokens for g in groups.values())
        if in_sum != ledger.raw_input_tokens:
            errors.append(
                f"{axis_name}: input_tokens sum {in_sum} != raw {ledger.raw_input_tokens}"
            )
        if ci_sum != ledger.raw_cached_input_tokens:
            errors.append(
                f"{axis_name}: cached_input_tokens sum {ci_sum} "
                f"!= raw {ledger.raw_cached_input_tokens}"
            )
        if out_sum != ledger.raw_output_tokens:
            errors.append(
                f"{axis_name}: output_tokens sum {out_sum} != raw {ledger.raw_output_tokens}"
            )
    return errors
