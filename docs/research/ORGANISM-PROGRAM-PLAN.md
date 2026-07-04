# ORGANISM — Program Plan (WS0 RECON output)

> **Status:** DRAFT awaiting Founder approval at the **§7 PLAN GATE**.
> **Zero tickets created.** No `board/tickets/` files exist for this program until the
> Founder replies with an explicit `APPROVED:` / `TASDIQLANDI:`.
> **Source of mission:** [`MASTER-PROMPT-ORGANISM.md`](MASTER-PROMPT-ORGANISM.md).
> **Source of mechanisms:** [`2026-07-03-donor-platforms-deepresearch.md`](2026-07-03-donor-platforms-deepresearch.md).
> **Produced by:** WS0 RECON — a 6-reader parallel audit + verification pass over DasLab v1.0.0.
> **Date:** 2026-07-03. **Engine version at kickoff:** 1.0.0. **Target:** 2.0.0.

---

## 0. Executive summary

DasLab v1.0.0 is a governance-first, file-native AI software org (32 agents) scoring
**100/100 on `diagnostics.py`** with an intact QONUN/AADL moat. Program **ORGANISM** turns
it into a *living ecosystem*: crash-safe (WS1), self-planning (WS2), observable and costed
(WS3), self-paced (WS4), operable (WS5), specialist-deep and self-improving (WS6), and able
to compile a Project-OS documentation pack into a delivered product 0→100 (WS7).

The audit's headline finding reframes the build order: **the highest-leverage single asset
in the entire program is a real dispatch event-emitter.** Today `board/.events.jsonl` does
not exist, `run_start`/`run_end` are *reserved but unimplemented*, and every T1–T7 gate is
therefore inert ("false green"). The metrics library already expects an extended event
schema — so building the typed emitter unblocks WS1 metrics, WS3 telemetry, WS4 tempo
signal, WS5 cockpit data, and WS6 eval cost **all at once**. This plan front-loads that
shared substrate as a WS1↔WS3 seam.

Everything else is disciplined *extension, not duplication*: the loop-promotion ladder,
replay/recovery contract, cockpit panels, metric validators, board linter, subagent
compiler, memory governance, and learn-skill all already exist and are named below with
`extend` verdicts. Only three artifacts are genuinely greenfield (`evals/`,
`scripts/agent_eval.py`, `governance/schemas/`) plus a handful of new config/board files.

**This document contains ticket-level decomposition as a *plan*.** Per §7.2 the tickets are
materialized by `/daslab-plan` **only after** the Founder approves, and only after the six
**§9 Founder decisions** below are ruled.

---

## 1. Baseline snapshot (WS0 acceptance — KPIs recorded)

| Signal | Value at kickoff | Note |
|---|---|---|
| `diagnostics.py` | **100/100** | all 8 buckets PASS |
| `git status` | clean | only untracked `docs/research/` (this program's docs) |
| VERSION | 1.0.0, branch `main` | |
| Board | **platform-empty** | cleared to `archive/v2.0.0`; only `.gitkeep`, `.wave-log`, `ROUTING.md`, `README.md` |
| `board/.events.jsonl` | **does not exist** | `dgox_emit` OFF; no live waves have emitted events |
| `check_cache_prefix.py` | exit 0 | ~5250 tok stable prefix, hash `9de5d0b9…` |
| `requirements*.txt` | clean | zero of the 5 banned donor libs (verified by grep) |

**T1–T7 baseline — CORRECTED.** The master prompt's "expected T1 0.11 / T2 0.70" are the
**registry baselines** in `metrics/registry.yaml`, *not live readings*:

| Metric | Registry baseline | **Live (measured 2026-07-03)** | Target |
|---|---|---|---|
| T1 busy_fraction | 0.11 | **unmeasured** (0 events, gate inert) | ≥ 0.60 |
| T2 idle_wave_rate | 0.70 | **0.000** (1 wave, 8 tickets dispatched) | ≤ 0.15 |
| T3 concurrency | — | unmeasured | ≥ 6 median |
| T4 model-mix | — | unmeasured | ≥ 0.25 haiku-eligible |
| T5 recovery | — | unmeasured | ≥ 0.99 |
| T6 review-eff / T7 quality | — | T6 unmeasured; **T7 OK** (rubric intact) | trend / no-degradation |

Only T1 and T2 carry a registry baseline; T3–T7 have targets only. **The plan must not
assert 0.11/0.70 as current readings** — they become live numbers only once WS1/WS3 emit
paired events from real waves.

---

## 2. Gap → Pattern → Workstream map (the program's spine)

Nine capability gaps (G1–G9) in v1.0.0, killed by 22 clean-room patterns (P1–P22) grouped
into 7 workstreams. All patterns are **re-derived from mechanism descriptions** — no donor
imports, no donor code, no donor product names (§2 Clean-Room Donor Protocol; verified
clean).

| WS | Name | Patterns | Kills | One-line outcome |
|---|---|---|---|---|
| **WS1** | PULSE | P1–P6 | G1 durable execution | crash-safe waves: checkpoint · resume · fork · interrupt · merge · fanout · cache |
| **WS2** | LOOM | P7–P10 | G3 planner, G4 typed contracts | dual-ledger planner · typed produces/consumes · schema-enforced routing · guardrails |
| **WS3** | BRIDGE | P11–P13 | G5 telemetry, G6 cost | OTel-named spans · cost-ledger · **committed** evidence |
| **WS4** | HEARTBEAT | P14–P16 | G2 tempo | flow-router · scheduler · run-workspaces — event-driven waves |
| **WS5** | COCKPIT | P17 | G7 static console | live ops console + Action Console for interrupts |
| **WS6** | GUILD | P18–P21 | G8 no evals | guild-templates · golden-evals · learned-loop · recall-ranking |
| **WS7** | GATEWAY | P22 | G9 no intake compiler | docs-pack → stage-gated story tickets → delivered 0→100 |

Build order (strict dependency): **WS1 → WS3(seam) → WS2 → WS4 → WS5 ∥ → WS6 → WS7**.
Rationale: durability before autonomy; **telemetry substrate is pulled forward** to sit
beside WS1 (shared emitter) because WS4/WS5/WS6 all need real event data; cockpit (WS5) may
run concurrently with WS4 (separate zones); GUILD before GATEWAY (strong specialists before
end-to-end delivery); GATEWAY last because it exercises everything.

---

## 3. What already exists (extend, don't duplicate)

Verified inventory (60 rows cross-checked; **zero false verdicts**). The load-bearing ones:

| Asset | Verdict | Serves | Extension point |
|---|---|---|---|
| `scripts/dgox/events.py` | **extend** | WS1/WS3 | `_VALID_EVENT_TYPES` reserves `run_start`/`run_end`/`tool_call` but has NO builder/validator — add typed `build_run_start/run_end/span/cost` + validators |
| `scripts/metrics_lib.py` | extend | WS3 | already reads `run_end.{outcome,merged_pr,ci_status,t7_pass,t7_score,model}` + `recovery_drill.{outcome,corrupted}` — **de-facto schema the emitter must match exactly** |
| `scripts/wave_kpi.py` | extend | WS3 | `busy_fraction_from_events` + shared `read_events()` — natural home to sum tokens/cost |
| `scripts/replay_qa.py` + `check_recovery.py` | extend/ref | WS1 | replay/recovery contract (`run_id` + ordered `routing_decision` → `recovery_drill` → T5) already exists; WS1 reuses it as the resume/kill-drill primitive |
| `scripts/loop_controller.py` | reference | WS4 | promotion **evaluator** (not a tick loop); WS4 heartbeat must *call* it as the governance gate, never reimplement the 7-clean-day/GATE-6 rule |
| `scripts/check_loop_mode.py` | reference | WS4 | tripwire: `mode ∉ {limited_live,full}` and `auto_apply==false` — hard boundary; WS4 stays under it |
| `scripts/feature_flags.py` | extend | WS4/WS7 | `load()` drops keys not in `DEFAULTS` — a new heartbeat/gateway flag must be added to `DEFAULTS`, default OFF |
| `scripts/cockpit.py` | extend | WS5 | 6 wired read-only panels + `NODATA`/`_render_panel`; WS5 **adds** panels + an HTML wrapper, reuses data-binding funcs |
| `scripts/board_lint.py` | extend | WS1/WS2 | `VALID_STATUSES` frozenset + R-rules; regex parser (not YAML) — typed fields need a tolerant structured parser |
| `scripts/check_dependency_graph.py` | extend | WS1/WS2 | optional `depends_on:`/`zone:` graph (acyclic, non-dangling) — WS2 typed edges extend it |
| `scripts/gen_subagents.py` + `check_agents_sync.py` | reference | WS6 | compiles overlays+model-table → `.claude/agents/*` + `ROUTING.md`; WS6 templates compile through this, guarded by `check_agents_sync` (**not** `check_org_drift`) |
| `scripts/memory_lib.py` | extend | WS6 | `recallable()` only **filters**; P21 adds a **ranking** fn beside it (reuse `jaccard()`+`trust_for()`) |
| `skills/daslab-learn/SKILL.md` | extend | WS6 | trust triad + per-record confidence exist; P20 adds a **distillation** step honoring the deny-boundary |
| `config/t7_rubric.yaml` + `check_t7_quality.py` | reference/extend | WS6 | existing quality scorer; golden-evals reuse these dimensions, never edit the immutable rubric |
| `.claude/skills/daslab-cycle/SKILL.md` | extend | WS1 | the dispatch/fanout/merge model; 4 selection guards are skill-token-tested — preserve verbatim |
| `governance/policies/ai-agent-lifecycle.md §2` | reference | WS7 | the **canonical** `docs/01-planning…06-maintenance` skeleton a GATEWAY scaffolder must emit |

**Genuinely missing (build-new):** `evals/`, `scripts/agent_eval.py`, `governance/schemas/`
(or use `config/`), `governance/communication-flows.yaml`, `governance/guardrails/`,
`governance/agent-templates/`, `config/budgets.yaml`, `board/runs/`, `board/interrupts/`,
`board/schedule.yaml`, `board/.cache/`, `board/.metrics-history.jsonl` feeder,
`metrics/evidence/`.

---

## 4. Workstream decomposition (epics → stage-gated tickets)

Each WS is **one AADL-stage-gated epic**. Tickets are tagged by stage
(`P`lanning · `D`esign · `Dev` · `T`est · `Dep`loy · `M`aint) and carry an owner-hint,
`produces/consumes` hint, and an extend/new flag. Ticket ids are symbolic (`O#-T##`);
`/daslab-plan` mints real `DAS-` ids (next free ≈ DAS-1440+). All tickets are org-engine →
`board/tickets/`, **no `project:` field**.

### WS1 — PULSE (durable execution core) · kills G1

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O1-T01 | P | ADR-0023 **run-model** (run_id=ULID, `board/runs/<id>/manifest.json`, gitignore policy, retained final summary) | cto | new | ADR merged + README row |
| O1-T02 | D | Typed `build_run_start/run_end/wave/checkpoint` + validators in `dgox/events.py`; register in `_VALID_EVENT_TYPES`; **match `metrics_lib` field names exactly** (`outcome,model,merged_pr,ci_status,t7_pass,t7_score`) | backend-em | extend | `pytest tests/test_dgox_events.py` green; `metrics_lib` reads them |
| O1-T03 | Dev | Wave-checkpoint writer (P1): `board/runs/<id>/wave-NNN.checkpoint.json` = board-hash + event offset + ticket states + pending interrupts + ledger hashes; **per-ticket completion record on finish** (pending-writes) | backend-eng-1 | new | crash after N tickets → those N not re-run |
| O1-T04 | Dev | Resume + time-travel (P2): `/daslab-cycle --resume <id>` replays `.events.jsonl` to last checkpoint, re-dispatches only unfinished; `--fork <id>@wave-NNN` copies checkpoint to new run, original untouched | backend-eng-2 | extend `daslab-cycle` | round-trip test |
| O1-T05 | D | Interrupt-cards schema (P3): `board/interrupts/<id>.json` `{question,options,ticket,payload,created_by}`; add **`interrupted`** to `VALID_STATUSES` (board_lint + `board/README.md` L27) + legal transitions | security-lead | extend | board_lint accepts; consumer sweep done |
| O1-T06 | Dev | Interrupt round-trip: gated ticket → `interrupted`; Founder writes `resume:<value>`; next cycle injects value into ticket context; **idempotency note + validator warning** on pre-interrupt side effects | backend-eng-1 | extend | create→answer→injected value visible |
| O1-T07 | Dev | Merge-policies (P4): frontmatter `merge_policy: append-only\|owner-exclusive\|aggregate:<reducer>` per zone; Python reducers; `board_lint` allows 2 same-zone tickets/wave **only** when policy permits | backend-em | extend board_lint | parallel-output merge test |
| O1-T08 | Dev | Fanout-tickets (P5): planner emits N child tickets + private payloads + one `defer:true` synthesis ticket; dispatcher refuses deferred launch until siblings closed | backend-eng-2 | extend `daslab-cycle` | defer-gating test |
| O1-T09 | Dev | Result-cache (P6): `board/.cache/<sha256(prompt+input-digests)>.json` + TTL; hits logged `cached:true`; **fix `check_cache_prefix._MIN_TOKENS`** to the Opus 4.8 minimum (verify current value via `claude-api` reference before setting) | backend-eng-1 | new + fix | cache hit short-circuits; cache-prefix gate corrected |
| O1-T10 | T | **Kill-drill** in `check_recovery.py`: 3-wave synthetic run, `kill -9` mid-wave-2, `--resume`, assert zero lost + zero dup; T5 ≥ 0.99 over ≥20 iterations; fork-drill divergence check | qa-lead | extend | drill green in scheduled CI |
| O1-T11 | Dep/M | Wire run-model into `daslab-cycle` step 0/5; preserve all 4 selection guards + `.claude/worktrees/<id>/` pure-id path | cto | extend | skill-token tests pass |

*Design constraints:* per-step **delta** storage (not full snapshots) from the start
(checkpoint-bloat mitigation); reuse the existing `routing_decision`+`recovery_drill`
event contract so `replay_qa`/`check_recovery` score it unchanged; **do not** flip the
"one operator invocation = one wave, no background timer" contract (WS4 owns tempo).

### WS3 — BRIDGE (observability & cost) · kills G5, G6 · *pulled forward, shares WS1 emitter*

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O3-T01 | P | ADR-0024 **span schema** — OTel GenAI semconv attribute *names* (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`, …) as JSONL; adapter-ready | cto | new | ADR merged |
| O3-T02 | D/Dev | Span-events (P11): every dispatch emits `trace_id=ticket`, `span_id`, `parent_span_id`, kind ∈ {invoke_agent,chat,execute_tool,wave,run}, tier, start/end, duration, in/out tokens, `cached`, `status` | backend-em | extend `dgox/events.py` | `check_spans.py` (new): 100% dispatches well-formed |
| O3-T03 | Dev | **Dispatch emitter** — the missing producer: instrument `daslab-cycle` step 5 to append `run_start/run_end/span` per ticket (this is the substrate that lights up T1/T3/T4/T6) | backend-em | new | live wave produces paired events; T1 leaves "inert" |
| O3-T04 | Dev | Cost-ledger (P12): `scripts/cost_ledger.py` per ticket/agent/tier/run token+$ aggregation; `config/budgets.yaml`; new `metrics/registry.yaml` entry + validator | finance-analyst + backend-eng-2 | new | totals reconcile with span sums |
| O3-T05 | Dev | `alerting.py` cost-breach alert on `budgets.yaml` thresholds; per-run budget governor consumed by WS4 | sre-eng | extend | breach fires |
| O3-T06 | T | Committed evidence (P13): snapshot each run's `wave_kpi` + span aggregates → **tracked** `metrics/evidence/<run_id>.json` (redacted); `check_metric_gaming.py` requires an evidence file | qa-lead | extend | run w/o evidence fails gate |
| O3-T07 | Dev | `wave_kpi.py` + T1–T7 validators recompute from spans (single `read_events` source of truth) | backend-eng-1 | extend | KPIs derive from spans |

*Constraints:* append-only (corrections = compensating events); `created_at` always
caller-supplied; anti-gaming R-9 binding — counted work needs `merged_pr`+green
`ci_status`+`t7_pass`; T7 rubric immutable.

### WS2 — LOOM (typed orchestration) · kills G3, G4

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O2-T01 | P | ADR-0025 **comm-flows format** + resolve the **GATE-1/6 owner reconciliation** (§9 Q1) and founder-node question (§9 Q2) | cto + ceo | new | ADR encodes canonical owners |
| O2-T02 | D | `governance/communication-flows.yaml` — directional `(sender,receiver)` edges seeded from `ROUTING.md` reporting lines + `schema.daslab.yaml` escalation ladder + `raci.md` consult edges (**do not invent topology**) | cpo | new | edges match 3 sources |
| O2-T03 | Dev | `gen_subagents.py` compiles each agent's ALLOWED routes into its generated def (undeclared route structurally unrepresentable); `check_comm_flows.py` fails any ticket/dispatch on an undeclared route (P9) | backend-em | extend | undeclared route impossible + caught |
| O2-T04 | D | Typed contracts (P8): frontmatter `produces:`/`consumes:` → schemas in `governance/schemas/*.yaml` (pydantic-backed); **unify the 3 frontmatter parsers** or add one tolerant structured reader | backend-em | extend board_lint + dep-graph | schema-mismatched wave plan fails lint |
| O2-T05 | Dev | `board_lint`/`check_dependency_graph` fail a wave plan when a consumer has no producer, or the dep graph is disconnected/cyclic | backend-eng-2 | extend | actionable error message |
| O2-T06 | Dev | Task-ledger (P7a): per-run `board/runs/<id>/task-ledger.md` (given/known/to-look-up/guesses + plan) | senior-pm | new | facts+plan present |
| O2-T07 | Dev | Progress-ledger (P7b): opus planner emits `progress-ledger.json` after every wave; `check_ledger.py` validates `{request_satisfied,in_loop,progress_being_made,next_tickets[],instruction}`; **stall rule** `in_loop\|\|!progress→stall+1 else max(0,stall-1)`; `stall>3`→regenerate task-ledger, `REPLANNED` event, bounded `max_replans`→interrupt-card | senior-pm + backend-em | new | stalled run replans ≤2 waves; pause-on-stall after budget |
| O2-T08 | Dev | Guardrail-tripwires (P10): per-role `governance/guardrails/<role>.py`→`(ok,feedback)`; dispatch wrapper re-dispatches SAME agent on trip (max 2) then escalates; input guardrails screen scope pre-accept | security-lead + qa-lead | new | failing ticket self-corrects ≤2 or escalates |

### WS4 — HEARTBEAT (autonomous tempo) · kills G2 · *activate, don't duplicate*

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O4-T01 | P | ADR-0026 **scheduler safety** — resolve daemon-vs-operator substrate (§9 Q3); encode budget caps, quiet hours, break-glass, never-auto-approve, `auto_apply:false` invariants | cto + coo | new | ADR merged; `check_loop_mode` stays green |
| O4-T02 | Dev | Flow-router (P14) — **pure-Python, no LLM** — over `.events.jsonl`: triggers on `ticket_created`/`wave_completed`/`interrupt_answered`/`after-N-runs`/cron → dispatch/validate/idle | sre-lead | new | deterministic routing test |
| O4-T03 | Dev | Scheduler (P15): `board/schedule.yaml` (cron + after-N-runs) → `loop_controller.py --tick`; **must call `loop_controller.evaluate_promotion` as the gate**, add heartbeat flag to `feature_flags DEFAULTS` (OFF), keep `loop.yaml` shadow/`auto_apply:false` | sre-eng | extend | `check_loop_mode` exit 0 |
| O4-T04 | Dev | `board/.metrics-history.jsonl` feeder (oldest→newest, exact `YYYY-MM-DDTHH:MM:SSZ`) so clean-day streak can build | backend-eng-1 | new | streak computes correctly |
| O4-T05 | Dev | Run-workspaces (P16): `board/runs/<id>/workspace/` scratch, GC on close, final summary retained | backend-eng-2 | new | GC test |
| O4-T06 | T | Kill-switch drill; safety-rail tests (budget/day caps, quiet hours, gates never auto-approved) | qa-lead | new | zero gate/approval violations in event log |
| O4-T07 | Dep | **Shadow-mode run ≥3 days**, then Founder flips flag shadow→live | Founder gate | — | T1≥0.60 ∧ T2≤0.15 ∧ T7 hold on rolling window |

*Hard boundary:* the heartbeat may READ metrics + dispatch waves but flipping `loop.yaml`
to live or `auto_apply:true` is **QONUN-5 human-only** and forbidden to automate; gates and
interrupt-cards **always** wait for the Founder.

### WS5 — COCKPIT (ops console) · kills G7 · *may run concurrently with WS4*

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O5-T01 | P | ADR-0027 cockpit form-factor (§9 Q4) — default: zero-infra local auto-refreshing HTML (stdlib `http.server` / static regen), no JS build, degrade to static | cto | new | ADR merged |
| O5-T02 | Dev | Extend `cockpit.render()` panels: live run feed, wave timeline, per-agent success/tokens/tier, per-tool usage, budget burn, T1–T7 sparklines (`trends.py`) — reuse `NODATA`/`_render_panel` | frontend-em | extend | panels update within one refresh |
| O5-T03 | Dev | **Action Console**: pending interrupt-cards + copy-paste answer stubs | frontend-eng-1 | new | Founder answers interrupt <60s |
| O5-T04 | T | HTML auto-refresh wrapper over the data-binding funcs; static-snapshot fallback | frontend-eng-2 | new | every §5 number visible on it |

### WS6 — GUILD (specialist depth) · kills G8

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O6-T01 | P | ADR-0028 guild model — resolve **guild=dept vs craft** (§9 Q5); default: guild-template = per-role file, grouped by dept (no new org unit) | cpo | new | ADR merged |
| O6-T02 | D | Guild-templates (P18): `governance/agent-templates/<role>.md` (identity/goal/behavioral-priors, toolkit allowlist, model+effort **verbatim** from allocation table, produces/consumes defaults, eval baseline ref) | cpo | new | compiles via `gen_subagents`; `check_agents_sync` guards drift |
| O6-T03 | Dev | Compile templates → `.claude/agents/` through `gen_subagents.py` (haiku omits `effort` line); no Tier-F/Fable | backend-em | extend | generate-and-diff clean |
| O6-T04 | D | Golden-eval harness (P19): `evals/<role>/<task>/{task.md,fixtures/,verify.py}` layout + `scripts/agent_eval.py` (k=3, fractional credit, accuracy×cost from cost-ledger, haiku-judge only for soft rubric tasks) | qa-lead | new | runner scores a sample role |
| O6-T05 | Dev | **≥3 golden tasks × 32 roles** — authored as a **fanout** (P5): 1 authoring child ticket per role (32), one `defer:true` rollup → `docs/AGENT-ROSTER.md` scorecards | fanout across dept ICs | new | every role ≥80% at assigned tier |
| O6-T06 | Dev | Learned-instructions (P20): `daslab-learn` distillation step — accepted Founder feedback → role template `## Learned` (bounded, deduped, dated) → regenerated agent | product-analyst | extend | round-trip on 2 roles |
| O6-T07 | Dev | Recall-ranking (P21): add ranking fn to `memory_lib.py` = semantic + recency half-life + importance; `prune_memory` hygiene job scheduled by WS4 | backend-eng-1 | extend | A/B ≥ baseline retrieval |
| O6-T08 | M | Eval dashboard green + ≥2 documented tier corrections driven by eval data | cpo | — | scorecards published |

### WS7 — GATEWAY (Project-OS compiler) · kills G9 · *exercises everything*

| # | Stage | Ticket | Owner | Extend/New | Acceptance hook |
|---|---|---|---|---|---|
| O7-T01 | P | ADR-0029 pack format; **spec first**: `docs/specs/PROJECT-OS-PACK.md` — `projects/<name>/PROJECT-OS.yaml` manifest + `docs/01-planning…06-maintenance` skeleton (**canonical** from lifecycle §2, not qaqnuz's divergent names) + discovery answers + `APPROVED-GOAL-QUEUE.md` | cpo + tech-writer | new | spec merged |
| O7-T02 | D/Dev | `scripts/gateway_compile.py` intake: validate pack (placeholder-lint/links/schema) → check discovery gate (≥10 Q&A or waiver, else generate questions) → research-enrichment ticket → verify `APPROVED:`/`TASDIQLANDI:` (wire existing `check_approved_goal_queue.py`) → compile **story tickets** into `projects/<name>/board-tickets/` (self-contained: embedded context, acceptance, produces/consumes, AADL tag, gate ref) | backend-em | new | broken pack rejected w/ actionable errors |
| O7-T03 | Dev | Stage-gated delivery: `/daslab-cycle` (WS4-driven) runs the project board through AADL gates; gates emit interrupt-cards; **GATE-5 open ⇒ no prod deploy** (machine-enforced) | cto | extend | gate-open blocks deploy |
| O7-T04 | T | E2E benchmark `evals/e2e/sample-pack/` — a small real Project-OS pack (CRUD SaaS + auth + 1 integration); org compiles ≥25 coherent story tickets, delivers through 6 gates to a deployable artifact, **zero hand-written tickets** | qa-lead | new | E2E run log green |
| O7-T05 | T | Generality check: a second, different sample pack passes with **no gateway code changes** | qa-eng | new | passes unchanged |

### Cross-cutting

| # | Stage | Ticket | Owner | Acceptance |
|---|---|---|---|---|
| OX-T01 | T | **Import-ban validator** (§2.3): fail CI if any of the 5 donor libs appears in `requirements*.txt`; run against the current clean baseline | security-eng | validator green, baseline clean |
| OX-T02 | M | **Self-audit** (post-WS7): multi-subagent adversarial atom-audit; target composite ≥ 9.5, "documented ≫ enforced" thesis closed | cto + qa-lead | audit report |

---

## 5. ADR list (append-only; start at 0023)

| ADR | Title | WS |
|---|---|---|
| 0023 | Run-model (run_id/ULID, `board/runs/`, checkpoint & delta storage) | WS1 |
| 0024 | Span-event schema (OTel GenAI semconv attribute names) | WS3 |
| 0025 | Communication-flows format + gate-owner reconciliation | WS2 |
| 0026 | Scheduler safety model (tempo substrate, budget/quiet/break-glass) | WS4 |
| 0027 | Cockpit form-factor (zero-infra local HTML) | WS5 |
| 0028 | Guild model + agent-template compilation | WS6 |
| 0029 | Project-OS pack format & gateway compile contract | WS7 |
| 0030 | `interrupted` status + legal transitions | WS1 |
| 0031 | Cost metric registry entry (hard-gate vs informational) | WS3 |
| 0032? | Cache-prefix re-target (only if Founder authorizes amending ADR-0006) | WS1 |

Each ADR adds a row to `docs/adr/README.md` (index + themes).

---

## 6. Risk register (from the audit)

1. **False-green metrics** — until the dispatch emitter (O3-T03) exists, every T-gate is
   inert; "progress" with zero live signal. *Mitigation:* O3-T03 is a critical-path
   dependency for the whole §5 contract; sequence it right after O1-T02.
2. **Schema drift** — `metrics_lib` reads 6+ `run_end` fields with no typed builder; an
   emitter with different names silently keeps gates inert. *Mitigation:* O1-T02 matches
   field names exactly; add a schema-conformance test.
3. **Checkpoint without resume is a false guarantee** — *Mitigation:* the kill-drill
   (O1-T10) is a hard gate, not optional.
4. **Interrupt re-run hazard** — the interrupted unit re-runs from its start; non-idempotent
   pre-interrupt side effects (a real merge, a spend, a send) double-fire. *Mitigation:*
   idempotency note in ticket template + validator warning (O1-T06).
5. **Daemon-vs-operator collision** — a true background timer contradicts the standing "NOT
   a daemon" law and QONUN-5. *Mitigation:* §9 Q3 Founder ruling before WS4; default keeps
   shadow/`auto_apply:false`.
6. **Three frontmatter parsers drift** — a typed field added to one reader but not others
   enforces inconsistently. *Mitigation:* O2-T04 unifies or adds one tolerant reader.
7. **Cache-prefix guards a proxy** — a dept-charter/overlay edit changes the real cached
   bytes but passes the check. *Mitigation:* §9 Q6 (re-target is an ADR-0006 amendment); the
   safe `_MIN_TOKENS` fix ships in O1-T09 regardless.
8. **Committed-evidence placement** — `board/.events.jsonl` is gitignored; evidence must be
   a *separate tracked* artifact (`metrics/evidence/`). *Mitigation:* O3-T06.
9. **Golden-eval judge calibration** — a cheap judge scoring accuracy×cost can misjudge.
   *Mitigation:* deterministic verifiers everywhere except soft rubric tasks; calibrate.
10. **Scope drift** — this program is org-engine; a stray `project:` field or a file under
    `projects/` breaks QONUN. *Mitigation:* every ticket lints against R9.

---

## 7. Budget & effort estimate

| Workstream | Tickets | ADRs | New files (approx) |
|---|---|---|---|
| WS1 PULSE | 11 | 2 | run-model, checkpoints, cache, drill |
| WS3 BRIDGE | 7 | 2 | spans, cost_ledger, budgets, evidence |
| WS2 LOOM | 8 | 1 | comm-flows, schemas, guardrails, ledgers |
| WS4 HEARTBEAT | 7 | 1 | flow-router, scheduler, workspaces |
| WS5 COCKPIT | 4 | 1 | HTML cockpit, action console |
| WS6 GUILD | 8 (+32 fanout) | 1 | templates, evals/, agent_eval |
| WS7 GATEWAY | 5 | 1 | pack spec, gateway_compile, e2e |
| Cross-cutting | 2 | — | import-ban, self-audit |
| **Total** | **~52 core (+32 eval fanout ≈ 84)** | **~10** | |

Rough execution envelope: **~12–18 waves** (no policy cap; zone-correctness + AADL gate
order are the only brakes). WS6's 32-role golden-eval authoring is the largest single fanout
and dominates the ticket count — it parallelizes cleanly via P5. Token/agent cost scales
with wave count and the eval fanout; the WS3 cost-ledger will make this self-measuring after
it lands (a nice recursion: the program instruments its own spend).

---

## 8. §5 contract → verification map (release gate for v2.0)

v2.0 ships only when every row is green, each by its named mechanism (unchanged from the
master prompt). The plan wires each to a ticket:

| # | Criterion | Verified by | Delivered in |
|---|---|---|---|
| 1 | T1 ≥ 0.60 (rolling, anti-gaming holds) | `check_busy_fraction` + evidence | O3-T03/T06, O4-T07 |
| 2 | T2 ≤ 0.15 | `check_idle_waves` + evidence | O4-T07 |
| 3 | T3 ≥ 6 median | `check_concurrency` | O3-T03 |
| 4 | T4 ≥ 0.25 haiku-eligible | `check_model_mix` + eval data | O3-T03, O6 |
| 5 | T5 ≥ 0.99 incl. kill-drill | `check_recovery` drill | O1-T10 |
| 6 | T6 downward / T7 no-degradation | `check_review_eff`/`check_t7_quality` | O3-T07 |
| 7 | 100% dispatches emit valid spans; cost reconciles | `check_spans` (new) | O3-T02/T04 |
| 8 | 32 roles ≥80% golden-eval at tier | `agent_eval` report | O6-T04/T05 |
| 9 | Undeclared route unrepresentable + caught | `check_comm_flows` | O2-T03 |
| 10 | E2E pack → deployed via 6 gates, zero hand-written | `evals/e2e/` run log | O7-T04 |
| 11 | Cockpit live; interrupt <60s; kill-switch drill | drill log | O5-T03, O4-T06 |
| 12 | `diagnostics` 100/100; zero QONUN viol.; no donor imports/code | `diagnostics`/`board_lint`/import-ban | OX-T01, all |

**§6 beat-the-donor scoreboard** stands as written — proof lives in our own repo's evidence
(kill-drill + fork, typed spans + routing + dual-ledger, evals + learned-loop, cockpit +
heartbeat, and the QONUN/AADL governance moat no donor has).

---

## 9. Founder decision gate (rule these before ticketing)

These are the genuine forks the audit surfaced — I recommend a default for each so approval
can be a single reply. **Answer inline (or `APPROVED: defaults`) and I proceed with the
recommendations.**

1. **GATE-1/6 owner reconciliation.** `org/schema.daslab.yaml` (GATE-1→founder+cpo,
   GATE-6→cto) disagrees with the AADL RACI (GATE-1 Accountable=cpo, GATE-6=coo).
   *Recommend:* treat AADL RACI as **Accountable** and schema as the **signer set**; encode
   both in ADR-0025. Or you name one canonical.
2. **Is `founder` a comm-flow node?** *Recommend:* model the Founder as an **external human
   gate above chairman**, not a node inside the 32-agent routing fleet.
3. **Scheduler substrate (daemon vs operator).** The "NOT a daemon" law vs "autonomous
   tempo." *Recommend:* a **shadow-mode operator-invoked heartbeat** (`loop_controller
   --tick` via an optional launchd/cron entry the Founder enables), staying
   `auto_apply:false`/shadow, honoring break-glass + quiet hours; live only on your flag
   flip after a ≥3-day clean shadow window.
4. **Cockpit form-factor.** *Recommend:* zero-infra **local auto-refreshing HTML** (stdlib
   server / static regen), degrade to static snapshot. (Could instead be a claude.ai
   Artifact — say the word.)
5. **Guild boundary.** *Recommend:* guild-template = **per-role** file grouped by dept; no
   new org unit — dissolves the ambiguity, respects the existing hierarchy.
6. **Cache-prefix re-target + cost gate.** *Recommend:* (a) ship the safe `_MIN_TOKENS`
   correction now; **defer** re-pointing the check at the real assembled preamble to a
   dedicated ADR-0006 amendment (it changes what a version bump means — your call). (b) Make
   the new cost metric **informational first** (like T6), promote to a hard gate after one
   clean window.

**Also confirm scope:** this 2026-07-03 ORGANISM directive is org-engine work and I am
treating it as an explicit lift of the 2026-06-23 "qaqnuz-only" scope. Confirm, and I'll
update that standing memory.

---

## 10. Next step

On `APPROVED:` / `TASDIQLANDI:` (with your §9 rulings), I run `/daslab-plan` to materialize
**WS1 + the WS3 emitter seam** first (they unblock all live metrics), stage-gated per AADL,
models passed explicitly, ADRs 0023–0024 authored in the Planning gate. WS2→WS7 follow in
dependency order. Each WS closes with its AADL gate checklist logged in the epic note; each
run snapshots committed evidence so the §5 contract is auditable in git history.

*Dushman kodi emas — dushman g'oyasi olinadi; kod 100% bizniki.*
