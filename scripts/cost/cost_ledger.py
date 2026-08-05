
from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.created_at import parse_created_at
from dgox.events import iter_events


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
    except Exception:
        pass
    return _SCRIPTS_DIR.parent


_ROOT = _repo_root()
_BUDGETS_PATH = _ROOT / "config" / "budgets.yaml"


_TIER_SLUGS: dict[str, str] = {
    "opus": "opus",
    "sonnet": "sonnet",
    "haiku": "haiku",
}


def _normalise_tier(model: str) -> str:
    lower = model.lower()
    for slug, tier in _TIER_SLUGS.items():
        if slug in lower:
            return tier
    return lower


@dataclass
class TierPricing:

    tier: str
    input_per_1m: float
    cached_input_per_1m: float
    output_per_1m: float


def _load_pricing(budgets_path: Path = _BUDGETS_PATH) -> dict[str, TierPricing]:
    import re

    text = budgets_path.read_text(encoding="utf-8")
    pricing: dict[str, TierPricing] = {}


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
                        j += 1
                    else:
                        break

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


@dataclass
class TokenGroup:

    key: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    span_count: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class CostLedger:

    by_ticket: dict[str, TokenGroup] = field(default_factory=dict)
    by_agent: dict[str, TokenGroup] = field(default_factory=dict)
    by_tier: dict[str, TokenGroup] = field(default_factory=dict)
    by_run: dict[str, TokenGroup] = field(default_factory=dict)


    raw_input_tokens: int = 0
    raw_cached_input_tokens: int = 0
    raw_output_tokens: int = 0
    raw_estimated_cost_usd: float = 0.0
    raw_span_count: int = 0


    unknown_tiers: set[str] = field(default_factory=set)


    dropped_undated: int = 0


NO_RUN_ID_KEY = "(no run_id)"


def _parse_created_at(ts: str) -> datetime | None:
    return parse_created_at(ts)


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
    *,
    since: datetime | None = None,
) -> CostLedger | None:
    pricing = _load_pricing(budgets_path)

    ledger = CostLedger()
    has_spans = False

    for ev in iter_events(store_path, event_type="span"):
        ts = _parse_created_at(str(ev.get("created_at", "")))
        if ts is None:


            ledger.dropped_undated += 1
        if since is not None and (ts is None or ts < since):
            continue


        ticket_id: str = str(ev.get("ticket_id") or ev.get("trace_id") or "")
        run_id: str = str(ev.get("run_id") or "") or NO_RUN_ID_KEY
        agent: str = str(ev.get("gen_ai.agent.name") or "(unknown agent)")
        model_raw: str = str(ev.get("gen_ai.request.model") or "")
        tier: str = _normalise_tier(model_raw) if model_raw else "(unknown tier)"

        input_tok: int = _safe_int(ev.get("gen_ai.usage.input_tokens"))
        output_tok: int = _safe_int(ev.get("gen_ai.usage.output_tokens"))
        cached_tok: int = _safe_int(ev.get("gen_ai.usage.cached_input_tokens"))


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


        ledger.raw_input_tokens += input_tok
        ledger.raw_cached_input_tokens += cached_tok
        ledger.raw_output_tokens += output_tok
        ledger.raw_estimated_cost_usd += cost
        ledger.raw_span_count += 1
        has_spans = True


        key_ticket = ticket_id or "(no ticket_id)"
        _add_to_group(ledger.by_ticket, key_ticket, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_agent, agent, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_tier, tier, input_tok, cached_tok, output_tok, cost)
        _add_to_group(ledger.by_run, run_id, input_tok, cached_tok, output_tok, cost)

    if not has_spans:
        return None

    return ledger


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def check_reconciliation(ledger: CostLedger) -> list[str]:
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
