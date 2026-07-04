# Policy: Claude Model + Effort Allocation per Role

> **Status:** Binding board policy — precedence level 2 (root `AGENTS.md` §2).
> **Scope:** All 32 DasLab subagent roles + orchestrator sessions.
> **Principle:** the model follows **task complexity, not title** — AADL §6.2
> model cascading applied to the org itself. Light model first; escalate via
> the ticket (reassign to manager), never by raising your own model.
> **Plan reality:** Claude Max 20x ($200/mo) — sonnet is the workhorse, opus
> for judgment/gates. Host: the local machine. **No parallel cap and no opus wave-mix cap**
> as of 2026-06-14: observed Max-plan usage was barely moving, so both were
> pure throttle. Wave size = every actionable ticket; real concurrency is
> harness-bounded. The only remaining dispatch bounds are correctness guards
> (one ticket per repo area per wave) and the AADL gate order — see §2.
> **Adopted:** 2026-06-12. **Amended:** 2026-06-14 (parallel cap 4→6→10 then
> removed; default wave 2→4 then "all actionable"; opus wave-mix guard removed;
> Fable retired/disabled → cto/security-lead on opus permanently);
> **2026-06-26 (ADR 0013 — W-eff):** added the per-role **Effort** column; the
> fleet drops from uniform `max` to `high`/`medium`/`low` under an unchanged opus
> floor (the wave bottleneck — the dev ICs — goes `max → medium`).

## 1 — Canonical allocation table

This table is the **single source of truth**. `scripts/gen_subagents.py`
parses it (`| role | model | effort | rationale |` rows) and writes `model:`
and `effort:` into every `.claude/agents/<role>.md`. Aliases
(`opus`/`sonnet`/`haiku`) are used, not pinned ids — they auto-track the newest
model of each tier. **Effort** (Opus 4.5+ / Sonnet 4.5+) sets how many tokens a
model spends per response (text + tool calls + thinking); it is a SEPARATE axis
from the model. **Haiku does not support `effort`** (400 error) — its effort
cell is blank and its frontmatter omits the line. An explicit per-role effort
cell wins; a blank cell falls back to `opus → high`, `sonnet → medium`.

### Tier F — highest blast radius, deepest reasoning (retired)

> **Fable 5 is disabled in this environment — Tier F is retired.** Both Tier-F
> roles (`cto`, `security-lead`) run on `opus` permanently, the next-most-powerful
> tier. There is no restore path — `opus` is the canonical model for these roles.

| Role | Model | Effort | Task-based rationale |
|---|---|---|---|
| `cto` | opus | high | Architecture, RFC/ADR approval, AADL GATE-2/3 accountable — wrong calls here cost the whole program. `max→high` saves tokens, keeps judgment; a single unusually deep design may run `xhigh` per-task (never the role default). |
| `security-lead` | opus | high | Guardrails/OWASP sign-off, red-team risk acceptance (GATE-2/4/5) — an approved vulnerability is the most expensive failure. `xhigh` per-task for deep red-team review. |

### Tier O — `opus`, effort `high`: judgment-dense leadership and gates

| Role | Model | Effort | Task-based rationale |
|---|---|---|---|
| `ceo` | opus | high | Strategy, goal decomposition, cross-dept arbitration — low-frequency, down-tiering yields ~0 throughput. |
| `chairman` | opus | high | Charter/governance rulings, board minutes with binding effect — rare, judgment-dense. |
| `cpo` | opus | high | GATE-1 accountable — product scope and KPI definitions; ambiguity multiplies downstream. |
| `senior-pm` | opus | high | PRD authoring (GATE-1 responsible) — ambiguity here multiplies downstream. |
| `backend-em` | opus | high | Code review, merge decisions, GATE-3 responsible — the net that catches `medium` backend ICs. |
| `frontend-em` | opus | high | Code review, merge decisions, GATE-3 responsible — the net for `medium` frontend ICs. |
| `qa-lead` | opus | high | GATE-4 accountable — eval thresholds, release-blocking judgment; primary regression catch for the aggressive bands. |
| `sre-lead` | opus | high | GATE-5 accountable — production launch, observability sign-off; prod blast radius. |

### Tier S — `sonnet`, effort `medium`: the execution core

`medium` matches `high` success ~92% of the time at ~half the tokens; errors are
caught by the opus EM / lead gates. Insidious-error roles (numeric/analytic,
finance, legal, the safety-executor ICs) floor at `medium`, never `low`.

| Role | Model | Effort | Task-based rationale |
|---|---|---|---|
| `backend-eng-1` | sonnet | medium | Implementation tickets — Sonnet is the coding workhorse; backend-em (GATE-3) catches. |
| `backend-eng-2` | sonnet | medium | Implementation tickets. |
| `frontend-eng-1` | sonnet | medium | Implementation tickets — frontend-em (GATE-3) catches. |
| `frontend-eng-2` | sonnet | medium | Implementation tickets. |
| `qa-eng` | sonnet | medium | Test authoring, eval runs, regression checks; qa-lead (GATE-4) gate. **Rollback-first.** |
| `security-eng` | sonnet | medium | Red-team execution, scans (lead reviews on opus). **Rollback-first.** |
| `sre-eng` | sonnet | medium | Runbooks, deploy mechanics, monitoring wiring; sre-lead (GATE-5). **Rollback-first.** |
| `design-lead` | sonnet | medium | Design direction, review of design artifacts. |
| `product-designer` | sonnet | medium | Mockups, components, design tokens — visually checked. |
| `ux-researcher` | sonnet | medium | Research notes, UX test synthesis — needs reasoning. |
| `product-analyst` | sonnet | medium | Metrics, KPI/goal-drift reports (GATE-6 responsible) — numeric errors insidious; floor at `medium`. **Rollback-first.** |
| `legal-analyst` | sonnet | medium | Risk-ethics review drafting; escalates novel calls via ticket. **Rollback-first.** |
| `finance-analyst` | sonnet | medium | Token/infra budget checks, burn reports — numeric, insidious; floor at `medium`. **Rollback-first.** |

### Tier S (low-ambiguity coordination) — `sonnet`, effort `low`

| Role | Model | Effort | Task-based rationale |
|---|---|---|---|
| `content-lead` | sonnet | low | Marketing content drafting/editing — iterative, cheaply reviewed, low blast radius. |
| `growth-marketer` | sonnet | low | Campaigns, growth experiments — cheaply reviewed. |
| `cdo` | sonnet | low | Dept coordination docs — checklist-driven. |
| `cmo` | sonnet | low | Dept coordination docs — checklist-driven. |
| `coo` | sonnet | low | GATE-6 accountable but checklist-driven cadence work — raise to `medium` first if GATE-6 pass-rate dips. |
| `board-member` | sonnet | low | Charter-guided reviews and votes — templated. |

### Tier H — `haiku` (effort unsupported): high-frequency, low-ambiguity

| Role | Model | Effort | Task-based rationale |
|---|---|---|---|
| `seo-specialist` | haiku |  | Meta/keyword/structured routine output — `effort` unsupported (400), line omitted. |
| `support-lead` | haiku |  | Triage, SLA tracking, templated responses — `effort` unsupported, omitted. |
| `tech-writer` | haiku |  | Changelog/doc-sync/templated-copy generation — mechanical, high-frequency, wrong output caught by the reviewing manager's gate (ADR 0007 §1 re-tier-eligible class; W3). `effort` unsupported, omitted. |

**Totals:** opus ×10 (all `high`) · sonnet ×19 (13 `medium` + 6 `low`) · haiku ×3
(no effort). = 32. Fable 5 is retired/disabled — there is no native fable split.

**Rollback-first set (T7 > T4, ADR 0013):** `qa-eng`, `security-eng`, `sre-eng`,
`product-analyst`, `finance-analyst`, `legal-analyst` → `medium → high` before any
other band moves, plus `coo` (`low → medium`) if GATE-6 quality dips. If the fixed
eval/gate suite regresses, this set returns to `high` first; effort is never
lowered past the point evals hold ("faster" yields to "correct").

> **Opus floor unchanged (ADR 0007 §2 / ADR 0013 §3).** Every AADL gate owner, all
> architecture/ADR authorship+ratification, and `cto` + `security-lead` stay
> **opus**. Effort changes the token budget, not the capability tier — a cheaper
> *tier* still never reviews a security/gate item; that guarantee is the opus
> model, independent of this effort cut.

> **W3 re-tier (ADR 0007, 2026-06-19).** `tech-writer` moved sonnet → haiku:
> its standing work (changelog upkeep, doc-sync, templated prose) is the
> mechanical/high-frequency, low-ambiguity, downstream-gated class that ADR 0007
> §1 marks re-tier-eligible. The **opus floor is unchanged** — every AADL gate
> owner, all architecture/ADR authorship+ratification, and `cto` + `security-lead`
> stay opus per ADR 0007 §2 (LAW 3). This is the conservative, single named move
> (ADR 0007 §3: data-driven, default no-down-tier); broader re-tiering waits on the
> W8/W19 routing-mix meter. T4 (haiku share) rises but yields to T7 if any eval/gate
> regression appears (DAS-1371) — rollback, not waiver.
>
> **CTO ruling — `security-eng` stays sonnet (RACI 3.6, 2026-06-19).** Backend EM
> flagged that ADR 0007 §2 read "`security-eng` stays opus **always**," conflicting
> with this baseline table (sonnet: "Red-team execution, scans — lead reviews on
> opus"). This operator-committed baseline is canon. **Ruling:** `security-eng`
> stays **sonnet**; the opus control on security work is the **security-lead review
> gate** (the gate signer is opus), not the IC execution tier. ADR 0007 §2's wording
> was over-broad and is corrected to match in the same merge (PR for DAS-1366). No
> up-tier — an opus IC was never the baseline guarantee, and W3 carried no
> deliberate reason to introduce one.

## 2 — Dispatch enforcement (binding)

- `/daslab-cycle` passes `model` **and `effort` explicitly on every Agent call**
  (values = the role's `model:` / `effort:` frontmatter). Frontmatter alone is
  not trusted at runtime — known Claude Code issue
  [#44385](https://github.com/anthropics/claude-code/issues/44385) (subagents
  may silently inherit the parent model). The generator is the source of truth.
- **No wave-mix cap (removed 2026-06-14):** dispatch as many opus roles as the
  wave needs. Re-introduce a per-wave opus cap only if Max-plan limit pressure
  actually appears (watch the 5-hour window); until then it was pure throttle.
- **Correctness guard (binding, keep):** never dispatch two tickets touching
  the same repo area / file set in one wave — parallel edits to the same files
  cause merge conflicts and rework, which lowers throughput.
- Orchestrator sessions: run `/daslab-cycle` on **sonnet** (triage is
  mechanical); run `/daslab-plan` on **opus** (decomposition is judgment).
  Orchestrator/human sessions use **opus** for hard design/debug work —
  Fable is retired/disabled, so there is no fable allowance to spend.
- An agent never upgrades its own model. Too hard for your tier → log
  escalation, reassign to your manager per `board/ROUTING.md`.

## 3 — Change process

1. Edit the table above (PR + chairman approval — this is board policy).
2. Re-run `python3 scripts/gen_subagents.py` (fails loudly if any role lacks a
   row; regenerates all 32 agent files + ROUTING.md with `model:` + `effort:`).
3. Note the change in the weekly board minutes.
