"""tests/test_cost_ledger.py — pytest suite for scripts/cost/cost_ledger.py.

Coverage (DAS-1459 acceptance criteria):

    1. Inert test: empty / missing store → aggregate_spans returns None, no crash.
    2. Single-span aggregation: tokens and cost computed correctly.
    3. Reconciliation invariant: per-ticket, per-agent, per-tier, per-run token
       totals each sum back to the raw span totals (ledger re-buckets only).
    4. Multi-span, mixed tiers: each tier priced correctly; unknown tier contributes
       tokens with $0.00 cost and is surfaced in ledger.unknown_tiers.
    5. Cached-read discount: cached_input_tokens priced at cached_input_per_1m rate.
    6. No run_id → bucketed under the sentinel key "(no run_id)".
    7. check_reconciliation returns [] on a correct ledger (no false positives).
    8. Pricing loader reads config/budgets.yaml and extracts correct values.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable (scripts/cost/ is a sub-package).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cost.cost_ledger import (  # noqa: E402
    NO_RUN_ID_KEY,
    _load_pricing,
    _normalise_tier,
    aggregate_spans,
    check_reconciliation,
)

# ---------------------------------------------------------------------------
# Helpers to build minimal span events compatible with dgox/events.py
# ---------------------------------------------------------------------------

_TS = "2026-07-03T12:00:00Z"


def _span(
    ticket_id: str = "DAS-9999",
    run_id: str | None = "run-001",
    agent: str = "backend-eng-2",
    model: str = "sonnet",
    input_tokens: int = 100,
    cached_input_tokens: int = 0,
    output_tokens: int = 50,
) -> dict[str, Any]:
    """Build a minimal span event dict (Shape H, dgox/events.py build_span)."""
    ev: dict[str, Any] = {
        "event_type": "span",
        "ticket_id": ticket_id,
        "trace_id": ticket_id,
        "span_id": "span-001",
        "parent_span_id": None,
        "kind": "invoke_agent",
        "gen_ai.agent.name": agent,
        "gen_ai.request.model": model,
        "start": _TS,
        "end": _TS,
        "duration_ms": 0,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.cached_input_tokens": cached_input_tokens,
        "cached": cached_input_tokens > 0,
        "status": "ok",
        "created_at": _TS,
    }
    if run_id is not None:
        ev["run_id"] = run_id
    return ev


def _write_store(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


# ---------------------------------------------------------------------------
# Minimal budgets.yaml for tests (avoids touching config/budgets.yaml)
# ---------------------------------------------------------------------------

_BUDGETS_YAML = """\
version: 1
tiers:
  opus:
    model_id: claude-opus-4-8
    input_per_1m: 5.00
    cached_input_per_1m: 0.50
    output_per_1m: 25.00

  sonnet:
    model_id: claude-sonnet-4-6
    input_per_1m: 3.00
    cached_input_per_1m: 0.30
    output_per_1m: 15.00

  haiku:
    model_id: claude-haiku-4-5
    input_per_1m: 1.00
    cached_input_per_1m: 0.10
    output_per_1m: 5.00

caps:
  per_run:
    max_cost_usd: 50.00
  per_day:
    max_cost_usd: 500.00
"""


@pytest.fixture()
def budgets_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "config" / "budgets.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(_BUDGETS_YAML)
    return p


# ---------------------------------------------------------------------------
# 1. Inert test: missing store → None, no crash
# ---------------------------------------------------------------------------


def test_inert_missing_store(tmp_path: Path, budgets_yaml: Path) -> None:
    """aggregate_spans returns None when the store file does not exist."""
    ledger = aggregate_spans(
        store_path=tmp_path / "board" / ".events.jsonl",
        budgets_path=budgets_yaml,
    )
    assert ledger is None


def test_inert_empty_store(tmp_path: Path, budgets_yaml: Path) -> None:
    """aggregate_spans returns None when the store exists but has no spans."""
    store = tmp_path / "board" / ".events.jsonl"
    # Write a non-span event — should be ignored.
    _write_store(store, [{"event_type": "run_start", "ticket_id": "DAS-0001", "run_id": "r1", "created_at": _TS}])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is None


def test_inert_truly_empty_file(tmp_path: Path, budgets_yaml: Path) -> None:
    """aggregate_spans returns None on a zero-byte store file."""
    store = tmp_path / "board" / ".events.jsonl"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text("")
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is None


# ---------------------------------------------------------------------------
# 2. Single-span aggregation: cost computed correctly
# ---------------------------------------------------------------------------


def test_single_span_sonnet_cost(tmp_path: Path, budgets_yaml: Path) -> None:
    """A single sonnet span produces the correct estimated cost."""
    store = tmp_path / "board" / ".events.jsonl"
    # 1000 input, 0 cached, 200 output on sonnet
    # cost = (1000 * 3.00 + 0 * 0.30 + 200 * 15.00) / 1_000_000
    #      = (3000 + 0 + 3000) / 1_000_000 = 0.006
    _write_store(store, [_span(model="sonnet", input_tokens=1000, cached_input_tokens=0, output_tokens=200)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert ledger.raw_span_count == 1
    assert ledger.raw_input_tokens == 1000
    assert ledger.raw_output_tokens == 200
    assert ledger.raw_cached_input_tokens == 0
    expected_cost = (1000 * 3.00 + 0 * 0.30 + 200 * 15.00) / 1_000_000
    assert abs(ledger.raw_estimated_cost_usd - expected_cost) < 1e-9


def test_single_span_opus_cost(tmp_path: Path, budgets_yaml: Path) -> None:
    """A single opus span produces the correct estimated cost."""
    store = tmp_path / "board" / ".events.jsonl"
    # 500 input, 100 cached, 50 output on opus
    # cost = (500 * 5.00 + 100 * 0.50 + 50 * 25.00) / 1_000_000
    #      = (2500 + 50 + 1250) / 1_000_000 = 0.0038
    _write_store(store, [_span(model="opus", input_tokens=500, cached_input_tokens=100, output_tokens=50)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    expected_cost = (500 * 5.00 + 100 * 0.50 + 50 * 25.00) / 1_000_000
    assert abs(ledger.raw_estimated_cost_usd - expected_cost) < 1e-9


def test_single_span_haiku_cost(tmp_path: Path, budgets_yaml: Path) -> None:
    """A single haiku span produces the correct estimated cost."""
    store = tmp_path / "board" / ".events.jsonl"
    # 2000 input, 0 cached, 300 output on haiku
    # cost = (2000 * 1.00 + 0 * 0.10 + 300 * 5.00) / 1_000_000
    #      = (2000 + 0 + 1500) / 1_000_000 = 0.0035
    _write_store(store, [_span(model="haiku", input_tokens=2000, cached_input_tokens=0, output_tokens=300)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    expected_cost = (2000 * 1.00 + 0 * 0.10 + 300 * 5.00) / 1_000_000
    assert abs(ledger.raw_estimated_cost_usd - expected_cost) < 1e-9


# ---------------------------------------------------------------------------
# 3. Reconciliation invariant (core DAS-1459 requirement)
# ---------------------------------------------------------------------------


def test_reconciliation_single_span(tmp_path: Path, budgets_yaml: Path) -> None:
    """check_reconciliation returns [] for a single-span ledger."""
    store = tmp_path / "board" / ".events.jsonl"
    _write_store(store, [_span()])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert check_reconciliation(ledger) == []


def test_reconciliation_multi_span(tmp_path: Path, budgets_yaml: Path) -> None:
    """check_reconciliation returns [] for a multi-span ledger."""
    store = tmp_path / "board" / ".events.jsonl"
    spans = [
        _span(ticket_id="DAS-0001", run_id="run-A", agent="be2", model="sonnet",
              input_tokens=100, cached_input_tokens=10, output_tokens=50),
        _span(ticket_id="DAS-0001", run_id="run-A", agent="be2", model="opus",
              input_tokens=200, cached_input_tokens=0, output_tokens=80),
        _span(ticket_id="DAS-0002", run_id="run-B", agent="fe-eng", model="haiku",
              input_tokens=300, cached_input_tokens=50, output_tokens=120),
        _span(ticket_id="DAS-0002", run_id="run-B", agent="be2", model="sonnet",
              input_tokens=150, cached_input_tokens=0, output_tokens=60),
    ]
    _write_store(store, spans)
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    errors = check_reconciliation(ledger)
    assert errors == [], f"Reconciliation failed: {errors}"


def test_reconciliation_raw_totals(tmp_path: Path, budgets_yaml: Path) -> None:
    """Raw token totals must equal the sum over each axis independently."""
    store = tmp_path / "board" / ".events.jsonl"
    spans = [
        _span(ticket_id="DAS-0001", run_id="run-A", agent="be2", model="sonnet",
              input_tokens=100, cached_input_tokens=10, output_tokens=50),
        _span(ticket_id="DAS-0002", run_id="run-A", agent="fe-eng", model="haiku",
              input_tokens=200, cached_input_tokens=20, output_tokens=80),
        _span(ticket_id="DAS-0003", run_id="run-B", agent="be2", model="opus",
              input_tokens=300, cached_input_tokens=30, output_tokens=120),
    ]
    _write_store(store, spans)
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None

    total_in = 100 + 200 + 300
    total_ci = 10 + 20 + 30
    total_out = 50 + 80 + 120

    assert ledger.raw_input_tokens == total_in
    assert ledger.raw_cached_input_tokens == total_ci
    assert ledger.raw_output_tokens == total_out

    for axis_name, groups in (
        ("by_ticket", ledger.by_ticket),
        ("by_agent", ledger.by_agent),
        ("by_tier", ledger.by_tier),
        ("by_run", ledger.by_run),
    ):
        assert sum(g.input_tokens for g in groups.values()) == total_in, axis_name
        assert sum(g.cached_input_tokens for g in groups.values()) == total_ci, axis_name
        assert sum(g.output_tokens for g in groups.values()) == total_out, axis_name


# ---------------------------------------------------------------------------
# 4. Unknown tier: tokens counted, cost = $0.00, surfaced in unknown_tiers
# ---------------------------------------------------------------------------


def test_unknown_tier_zero_cost(tmp_path: Path, budgets_yaml: Path) -> None:
    """An unknown tier contributes tokens but zero estimated cost."""
    store = tmp_path / "board" / ".events.jsonl"
    _write_store(store, [_span(model="claude-future-model-99", input_tokens=1000, output_tokens=100)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert ledger.raw_input_tokens == 1000
    assert ledger.raw_output_tokens == 100
    assert ledger.raw_estimated_cost_usd == 0.0
    assert ledger.unknown_tiers  # non-empty — unknown tier is surfaced
    assert check_reconciliation(ledger) == []


def test_unknown_tier_mixed_with_known(tmp_path: Path, budgets_yaml: Path) -> None:
    """Unknown tier tokens are counted; known tier tokens are priced normally."""
    store = tmp_path / "board" / ".events.jsonl"
    spans = [
        _span(model="unknown-xyz", input_tokens=500, output_tokens=50),
        _span(model="sonnet", input_tokens=100, output_tokens=20),
    ]
    _write_store(store, spans)
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert ledger.raw_input_tokens == 600
    assert ledger.raw_output_tokens == 70
    # Only the sonnet span contributes cost.
    expected = (100 * 3.00 + 20 * 15.00) / 1_000_000
    assert abs(ledger.raw_estimated_cost_usd - expected) < 1e-9
    assert ledger.unknown_tiers
    assert check_reconciliation(ledger) == []


# ---------------------------------------------------------------------------
# 5. Cached-read discount applied correctly
# ---------------------------------------------------------------------------


def test_cached_input_discount(tmp_path: Path, budgets_yaml: Path) -> None:
    """Cached tokens are priced at cached_input_per_1m, not input_per_1m."""
    store = tmp_path / "board" / ".events.jsonl"
    # sonnet: 200 input_tokens + 200 cached_input_tokens + 100 output_tokens
    # cost = (200 * 3.00 + 200 * 0.30 + 100 * 15.00) / 1_000_000
    #      = (600 + 60 + 1500) / 1_000_000 = 0.00216
    _write_store(store, [_span(model="sonnet", input_tokens=200, cached_input_tokens=200, output_tokens=100)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    expected = (200 * 3.00 + 200 * 0.30 + 100 * 15.00) / 1_000_000
    assert abs(ledger.raw_estimated_cost_usd - expected) < 1e-9


# ---------------------------------------------------------------------------
# 6. Missing run_id → bucketed under NO_RUN_ID_KEY sentinel
# ---------------------------------------------------------------------------


def test_no_run_id_sentinel(tmp_path: Path, budgets_yaml: Path) -> None:
    """A span without run_id is bucketed under the (no run_id) sentinel key."""
    store = tmp_path / "board" / ".events.jsonl"
    _write_store(store, [_span(run_id=None, model="sonnet", input_tokens=50, output_tokens=10)])
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert NO_RUN_ID_KEY in ledger.by_run
    assert ledger.by_run[NO_RUN_ID_KEY].input_tokens == 50
    assert check_reconciliation(ledger) == []


# ---------------------------------------------------------------------------
# 7. check_reconciliation returns [] on a correct ledger (no false positives)
# ---------------------------------------------------------------------------


def test_reconciliation_no_false_positive(tmp_path: Path, budgets_yaml: Path) -> None:
    """check_reconciliation returns [] for any well-formed ledger."""
    store = tmp_path / "board" / ".events.jsonl"
    spans = [_span(model=m, input_tokens=i, output_tokens=o)
             for m, i, o in [("opus", 100, 10), ("sonnet", 200, 20), ("haiku", 300, 30)]]
    _write_store(store, spans)
    ledger = aggregate_spans(store_path=store, budgets_path=budgets_yaml)
    assert ledger is not None
    assert check_reconciliation(ledger) == []


# ---------------------------------------------------------------------------
# 8. Pricing loader reads budgets.yaml correctly
# ---------------------------------------------------------------------------


def test_pricing_loader_opus(budgets_yaml: Path) -> None:
    """_load_pricing reads opus prices from budgets.yaml correctly."""
    pricing = _load_pricing(budgets_yaml)
    assert "opus" in pricing
    tp = pricing["opus"]
    assert tp.input_per_1m == 5.00
    assert tp.cached_input_per_1m == 0.50
    assert tp.output_per_1m == 25.00


def test_pricing_loader_sonnet(budgets_yaml: Path) -> None:
    pricing = _load_pricing(budgets_yaml)
    assert "sonnet" in pricing
    tp = pricing["sonnet"]
    assert tp.input_per_1m == 3.00
    assert tp.cached_input_per_1m == 0.30
    assert tp.output_per_1m == 15.00


def test_pricing_loader_haiku(budgets_yaml: Path) -> None:
    pricing = _load_pricing(budgets_yaml)
    assert "haiku" in pricing
    tp = pricing["haiku"]
    assert tp.input_per_1m == 1.00
    assert tp.cached_input_per_1m == 0.10
    assert tp.output_per_1m == 5.00


# ---------------------------------------------------------------------------
# Tier normalisation: full model ids accepted
# ---------------------------------------------------------------------------


def test_normalise_full_model_id_opus() -> None:
    assert _normalise_tier("claude-opus-4-8") == "opus"


def test_normalise_full_model_id_sonnet() -> None:
    assert _normalise_tier("claude-sonnet-4-6") == "sonnet"


def test_normalise_full_model_id_haiku() -> None:
    assert _normalise_tier("claude-haiku-4-5") == "haiku"


def test_normalise_short_slug() -> None:
    assert _normalise_tier("sonnet") == "sonnet"
    assert _normalise_tier("OPUS") == "opus"
    assert _normalise_tier("Haiku") == "haiku"


def test_normalise_unknown_returns_lowercased() -> None:
    assert _normalise_tier("claude-future-99") == "claude-future-99"
