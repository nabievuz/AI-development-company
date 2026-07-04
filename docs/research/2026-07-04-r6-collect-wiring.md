# R6 Collect-Step Wiring: Token Usage to DispatchRecord to Span

**Ticket:** DAS-1540  
**Date:** 2026-07-04  
**Scope:** Document the token-usage collect-step wiring for live cost observability chain  

---

## Overview

The `/daslab-cycle` collect step must populate real per-dispatch token usage into each wave's `DispatchRecord`, so live waves emit non-zero span tokens and the R6 chain fills real dollars end-to-end:

```
agent run (usage block) 
  → token_usage.parse_usage() / usage_token_fields()
  → DispatchRecord token fields
  → dispatch_emitter span + run_end token_total
  → check_spans reconciliation + cost_ledger pricing
```

This note specifies the exact wiring from source to sink.

---

## 1. Source: Agent Usage Blocks

After an agent run completes, the Claude Code harness returns a `usage` object (a mapping) with up to four token counts:

| Field | Spelling Variant | Meaning |
|-------|-----------------|---------|
| **input_tokens** | `prompt_tokens` (OpenAI alias) | Base input tokens, billed at full rate |
| **output_tokens** | `completion_tokens` (OpenAI alias) | Output completion tokens |
| **cache_read_input_tokens** | `cached_input_tokens` (alias) | Tokens read from cache, billed at cached rate (~10% of input) |
| **cache_creation_input_tokens** | `cache_creation_tokens` (alias) | Tokens written to cache, billed at creation premium (~25% above input) |

**Obtain the usage block** at collect time by:
- Reading the agent run's `usage` field from the task result or task metadata (the exact location depends on the harness's dispatch/result struct)
- Passing it to `scripts/token_usage.usage_token_fields(usage)` — which handles all four spellings and coercion rules

The usage block may be:
- A present mapping with one or more counts
- `None` (no usage captured)
- An empty mapping `{}`
- A mapping with partial counts (some keys absent)

All are valid; the parser handles them per the Truth-Oath rule below.

---

## 2. Parse & Map: usage_token_fields()

**Call signature** (from `scripts/token_usage.py`):

```python
def usage_token_fields(usage: Mapping[str, Any] | None) -> dict[str, int]:
    """Return the token kwargs a ``DispatchRecord`` / ``build_span`` expects."""
    ...
```

**Input:**
- `usage` — the raw usage block from the agent run (a mapping or `None`)

**Output:**
- A dict with exactly three keys: `input_tokens`, `output_tokens`, `cached_input_tokens`
- Each value is a non-negative integer (no floats, no bools)

**Bucket mapping logic** (from `scripts/token_usage.py`, lines 17–28):

| Destination Bucket | Source Field(s) | Logic | Example |
|-------------------|-----------------|-------|---------|
| `output_tokens` | `output_tokens` | Direct mapping | `output: 50` → `output_tokens: 50` |
| `cached_input_tokens` | `cache_read_input_tokens` | Direct mapping; billed at cached rate | `cache_read: 100` → `cached_input_tokens: 100` |
| `input_tokens` | `input_tokens` + `cache_creation_input_tokens` | Sum; cache-creation (premium) folds into base input | `input: 200, cache_create: 50` → `input_tokens: 250` |

**Why the sum?** Cache-creation tokens are billed at a premium (~25% above input), but the cost ledger has only three rates: `input`, `cached_input`, and `output`. Cache-creation has no dedicated ledger bucket, so we fold it into `input` (conservative: we under-count the creation premium rather than inventing a bucket the ledger cannot price).

**Use in collect step:**

```python
from scripts.token_usage import usage_token_fields

# After agent run completes:
usage = agent_result.usage  # or extract from task metadata
token_kwargs = usage_token_fields(usage)

# token_kwargs is now a dict like:
# {
#   "input_tokens": 200,
#   "output_tokens": 50,
#   "cached_input_tokens": 0,
# }
```

---

## 3. DispatchRecord Token Fields

**Target fields** (from `scripts/dispatch_emitter.py`, lines 155–157):

```python
@dataclass(frozen=True)
class DispatchRecord:
    ...
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    ...
```

**Set these three fields** when constructing the `DispatchRecord` in the collect step:

```python
record = DispatchRecord(
    ticket_id="DAS-1234",
    run_id="run-abc123",
    goal="daslab-cycle",
    engine_version=VERSION,
    model="claude-opus-4-1",
    role_key="engineering",
    start="2026-07-04T10:00:00Z",
    end="2026-07-04T10:05:00Z",
    outcome="success",
    merged_pr=True,
    ci_status="GREEN",
    t7_pass=True,
    t7_score=0.95,
    # Token usage from agent — pass the parsed kwargs directly:
    **usage_token_fields(agent_result.usage),
    # ... other required fields
)
```

Or equivalently:

```python
token_kwargs = usage_token_fields(agent_result.usage)
record = DispatchRecord(
    ...,
    input_tokens=token_kwargs["input_tokens"],
    output_tokens=token_kwargs["output_tokens"],
    cached_input_tokens=token_kwargs["cached_input_tokens"],
)
```

---

## 4. Downstream: dispatch_emitter → Span + run_end

Once the `DispatchRecord` is populated with token fields, `scripts/dispatch_emitter.build_dispatch_events()` threads them into two places:

### 4a. The Span Event

**Fields set** (from `scripts/dispatch_emitter.py`, lines 232–234):

```python
span = build_span(
    ...
    input_tokens=record.input_tokens,
    output_tokens=record.output_tokens,
    cached_input_tokens=record.cached_input_tokens,
    ...
)
```

The span carries all three buckets as-is. This is what `metrics_lib.py` and `wave_kpi.py` read to compute cost.

### 4b. The run_end Event

**Token reconciliation field** (from `scripts/dispatch_emitter.py`, line 220):

```python
run_end = build_run_end(
    ...
    token_total=(record.input_tokens + record.output_tokens) or None,
)
```

**Key detail:** `token_total` is the SUM of base input + output only (not cached). Why?
- Cached-read tokens are cheaper (~10% of input rate) and already accounted in `cached_input_tokens`
- Summing all three would double-count and distort the total
- The formula `(sum) or None` emits `None` if the sum is zero (honest "unknown"), ensuring a zero-token record leaves the reconciliation seam inert and never perturbs a zero-token fixture

**Reconciliation seam** (per `scripts/dispatch_emitter.py` line 215, comment):

```
check_spans reconciles:  span.input + span.output == run_end.token_total
```

This ensures consistency between the span (which will be priced) and the run event (which anchors the observability record).

---

## 5. Truth-Oath Rule: Zero vs. Error

**Canonical rule** (from `scripts/token_usage.py`, lines 12–15):

> Unknown / missing usage maps to `0` — never a fabricated non-zero count — and a present-but-malformed count (negative, non-integer) *raises* rather than silently coercing garbage into a dollar figure. A wrong non-zero cost is worse than an honest `0`.

**Application in collect:**

| Scenario | Action | Result |
|----------|--------|--------|
| `usage` is `None` | Call `usage_token_fields(None)` | Returns `{input_tokens: 0, output_tokens: 0, cached_input_tokens: 0}` |
| `usage` is `{}` | Call `usage_token_fields({})` | Returns `{input_tokens: 0, output_tokens: 0, cached_input_tokens: 0}` |
| `usage` has `{"output_tokens": 50}` | Call `usage_token_fields({...})` | Returns `{input_tokens: 0, output_tokens: 50, cached_input_tokens: 0}` |
| `usage` has `{"output_tokens": -50}` | Call `usage_token_fields({...})` | **Raises `ValueError`** — negative count rejected |
| `usage` has `{"output_tokens": true}` | Call `usage_token_fields({...})` | **Raises `ValueError`** — bool rejected explicitly (bool is an int subclass but never a token count) |
| `usage` has `{"output_tokens": 50.5}` | Call `usage_token_fields({...})` | **Raises `ValueError`** — non-integer float rejected |
| `usage` has `{"output_tokens": 50.0}` | Call `usage_token_fields({...})` | Returns `{..., output_tokens: 50}` — integral float coerced to int |

**Implication for collect:** Always call `usage_token_fields()` rather than hand-parsing; let it enforce the coercion rules. If the call raises, log the error and escalate (do not fabricate a zero or a guess).

---

## 6. Example: Complete Wiring

```python
# In /daslab-cycle collect step:
from scripts.token_usage import usage_token_fields
from scripts.dispatch_emitter import DispatchRecord, emit_dispatch

# After agent dispatch completes:
agent_result = ...  # result from the run
usage = agent_result.usage  # or extract from task metadata

# Parse usage into the three span buckets:
try:
    token_kwargs = usage_token_fields(usage)
except (TypeError, ValueError) as e:
    # Malformed usage block — escalate, do not fabricate:
    logger.error(f"Malformed usage for {ticket_id}: {e}")
    raise

# Construct DispatchRecord with token fields:
record = DispatchRecord(
    ticket_id=ticket.id,
    run_id=task_run_id,
    goal="daslab-cycle",
    engine_version=VERSION,
    model=agent_model,
    role_key=agent_role,
    start=dispatch_start_iso,
    end=dispatch_end_iso,
    outcome=agent_outcome,
    merged_pr=pr_merged,
    ci_status=ci_result,
    t7_pass=t7_outcome,
    t7_score=t7_score_float,
    **token_kwargs,  # Unpack: input_tokens, output_tokens, cached_input_tokens
)

# Emit events (run_start, run_end with token_total, span with tokens):
events = emit_dispatch(record)

# Events now carry real costs:
# - span has input_tokens + output_tokens + cached_input_tokens
# - run_end has token_total = input_tokens + output_tokens (for reconciliation)
# - downstream metrics_lib / cost_ledger read these fields and compute dollars
```

---

## 7. Related Code & Tests

- **Parser:** `scripts/token_usage.py` — `parse_usage()`, `usage_token_fields()`, `TokenUsage` dataclass, `_coerce()` validation
- **Emitter:** `scripts/dispatch_emitter.py` — `DispatchRecord`, `build_dispatch_events()`, `emit_dispatch()`, `emit_wave()`
- **Event builders:** `scripts/dgox/events.py` — `build_run_end()`, `build_span()`, shape validators
- **Readers:** `scripts/metrics_lib.py`, `scripts/wave_kpi.py` — consume span tokens for cost/KPI computation
- **Reconciliation:** `scripts/check_spans.py` — verifies `span.input + span.output == run_end.token_total`
- **Pricing:** `scripts/cost/cost_ledger.py` — applies rates from `config/budgets.yaml` to span buckets

---

## 8. Gate Checklist (for R6 Wiring, DAS-1452)

Before flipping `dgox_emit` to live mode:
- [ ] Collect step parses real usage blocks from all agent runs
- [ ] Calls `usage_token_fields()` for all three buckets (not hand-parsing)
- [ ] Populates `DispatchRecord` token fields (input/output/cached_input)
- [ ] Handles malformed usage by raising (not fabricating zeros)
- [ ] DispatchRecord is passed to `dispatch_emitter.emit_dispatch()` or `emit_wave()`
- [ ] Emitted span carries all three token fields
- [ ] Emitted run_end carries `token_total = input + output`
- [ ] Live sample wave spans show non-zero token counts
- [ ] `check_spans` reconciliation passes
- [ ] Cost ledger computes real dollars end-to-end
