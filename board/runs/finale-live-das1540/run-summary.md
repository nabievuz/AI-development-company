# Live wave evidence — R6 real cost (PASS)

One REAL org wave: the **tech-writer** role executed ticket **DAS-1540** (R6
collect-wiring design note) on **haiku**, and its REAL token usage was emitted
through the production dispatch path — producing the **first non-zero cost** and
a live `check_spans` reconciliation. Gated: no push, no PR, no merge.

- generated: `2026-07-04`
- ticket: `DAS-1540` (assignee tech-writer) → **done**, real artifact:
  `docs/research/2026-07-04-r6-collect-wiring.md`
- model/tier: `haiku` (claude-haiku-4-5) · 21 assistant calls
- run_id: `finale-live-das1540`

## Real token usage → cost (the R6 chain, end to end)

Usage aggregated from the dispatch transcript, mapped by
`token_usage.usage_token_fields` → `DispatchRecord` → span + `run_end.token_total`
→ `cost_ledger`:

| bucket | tokens |
|---|---|
| input (input 178 + cache-creation 156,704) | 156,882 |
| cached (cache-read) | 516,816 |
| output | 6,141 |

**cost = `$0.239269`** (per ticket / per agent `tech-writer` / per tier `haiku` /
per run — all agree).

- `check_spans`: **OK** — 1 dispatch, 1 span, 100% coverage, well-formed, and the
  token reconciliation seam is now **live** (`run_end.token_total` == span
  input+output sum). rc 0.
- `check_metric_gaming`: rc 0 — this run is honestly **not** a counted KPI
  completion (no merged PR / green CI / T7 in a gated build); reported as
  informational under human-oversight, never counted toward a KPI.

## Safety (gated promise held)

- `git ls-remote origin` → only `refs/heads/main`; `feat/finale-gated` **not**
  pushed (0 matches). No PR opened.
- The role agent touched only its deliverable doc + the DAS-1540 ticket.

## Honest scope

This proves the R6 cost chain works on **real data** (parse_usage → spans →
reconcile → priced $), and that R8's cost column **can** be filled from live
spans (real `$0.24` for `tech-writer`/`haiku`). It is ONE wave, not a burn-in:
the live event store `board/.events.jsonl` is gitignored runtime, so THIS
run-summary is the durable, git-tracked receipt. Filling the committed roster
cost column + reaching Σ=115 still needs sustained real waves over the burn-in
window (Founder-run).

```json
{
  "kind": "live_wave_cost_evidence",
  "run_id": "finale-live-das1540",
  "ticket": "DAS-1540",
  "role": "tech-writer",
  "tier": "haiku",
  "usage_buckets": {"input_tokens": 156882, "cached_input_tokens": 516816, "output_tokens": 6141},
  "cost_usd": 0.239269,
  "check_spans": "OK (100% coverage, token_total reconciliation live)",
  "counted_kpi_completion": false,
  "pushed": false,
  "pr_opened": false
}
```
