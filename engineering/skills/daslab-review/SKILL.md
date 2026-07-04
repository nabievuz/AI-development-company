---
name: daslab-review
description: >
  DasLab autonomous pre-landing code review for engineering agents (CTO, EMs,
  QA Lead, Backend/Frontend/Security/SRE Engineers, Developer). Runs a two-pass
  CRITICAL/INFORMATIONAL checklist plus a parallel "Review Army" of specialist
  sub-agents over a PR diff, then applies the Fix-First rule autonomously. ALWAYS
  use this skill when reviewing a pull request or `git diff` before it lands,
  when a ticket is in `in_review`, when asked to "review this PR / check my diff",
  or before moving code work to `done`. Emits the DasLab finding format and ends
  with a STATUS line per the orchestrator contract (§5.5/§6). Runs without
  interactive gates as an autonomous pre-landing review in each work wave.
---

# DasLab Review — autonomous pre-landing code review

You are an engineering agent reviewing code **before it lands on `origin/main`**. Your
job: find real problems, fix the mechanical ones yourself, and route the judgment calls
to the right owner — all without a human in the loop. This skill is the engineering
quality gate run before code lands.

## 0 — When this applies
A ticket you own (or were asked to review) has a branch + PR, or a `git diff origin/main`
to inspect. If there is no diff, exit. Never review code on `main` directly.

## 1 — Scope detection (sets which specialists fire)
Read the diff once and set scope flags from the changed paths:
- `SCOPE_AUTH` — auth/session/permission/login files touched
- `SCOPE_BACKEND` — server/API/model/db code
- `SCOPE_FRONTEND` — UI/component/view code
- `SCOPE_MIGRATIONS` — schema/migration files
- `SCOPE_API` — public API surface / response shapes / contracts
- `DIFF_LINES` — total changed lines

## 2 — Pass 1: CRITICAL checklist (you, the main agent)
Read `git diff origin/main`. Flag only real problems; cite `file:line` + a one-line fix.

- **SQL & Data Safety** — string interpolation in SQL (even `.to_i`); TOCTOU check-then-set
  that should be atomic; bypassing model validation for raw writes; N+1 (missing eager load).
- **Race Conditions & Concurrency** — read-check-write without a uniqueness constraint;
  find-or-create without a unique index; non-atomic status transitions; unsafe HTML render
  (`html_safe`/`dangerouslySetInnerHTML`/`v-html`) on user data (XSS).
- **LLM Output Trust Boundary** — LLM-generated values (emails/URLs/names) persisted without
  format validation; tool output used without shape checks; LLM URLs fetched without an
  allowlist (SSRF); LLM output stored in a vector DB without sanitization (stored injection).
- **Shell Injection** — `subprocess(..., shell=True)` with interpolation; `os.system()` with
  variables; `eval`/`exec` on LLM-generated code.
- **Enum & Value Completeness** — when the diff adds an enum/status/tier/type constant,
  **READ** (don't just grep) every consumer: switch/filter/display, allowlist arrays,
  `case`/`if-elsif` chains. Common miss: added to the frontend dropdown but not persisted
  by the backend. This requires reading code OUTSIDE the diff.

## 3 — Pass 2: INFORMATIONAL checklist (you, the main agent)
Async/sync mixing in `async def` (blocking the loop); ORM column-name safety vs schema;
LLM prompt issues (0-indexed lists, stale tool lists);
completeness gaps (<30 min to finish properly); time-window safety (24h "today" key);
type coercion at JSON boundaries (`8` vs `"8"` digests); view perf (inline `<style>`,
O(n·m) lookups, Ruby-side filtering that should be a `WHERE`); CI/CD pipeline correctness.

## 4 — Review Army: parallel specialist dispatch
For each in-scope specialist, launch an **independent sub-agent** (the Agent
tool) with fresh context. They run in parallel and return
findings as one JSON object per line. Scope gates:

| Specialist | Fires when |
|---|---|
| Maintainability | always |
| Testing | always |
| Security | `SCOPE_AUTH` OR (`SCOPE_BACKEND` AND DIFF_LINES > 100) |
| Performance | `SCOPE_BACKEND` OR `SCOPE_FRONTEND` |
| API Contract | `SCOPE_API` |
| Data Migration | `SCOPE_MIGRATIONS` |
| Red Team | DIFF_LINES > 200 OR any CRITICAL found — runs **after** the others, sees their findings |

Each sub-agent prompt: "You are a {specialist} code reviewer. Read `git diff origin/main`.
Return findings as JSON lines `{severity, confidence, path, line, category, summary, fix}`,
severity ∈ {CRITICAL, P1, INFORMATIONAL}. Output `NO FINDINGS` if clean. Be specific, no preamble."

A specialist that errors does not block the rest — collect partial results. If a finding
is reported by two specialists, tag it **MULTI-SPECIALIST CONFIRMED** (boost confidence).

**Degradation:** if the runtime can't spawn sub-agents, skip the army and run
the Pass 1/2 checklist only. Say so.

## 5 — Fix-First rule (the autonomous decision)
Classify every finding, then act — no human gate:

- **AUTO-FIX (apply directly to the branch, commit):** dead code / unused vars; N+1
  (add eager load); stale comments; magic numbers → named constants; missing LLM-output
  validation; version/path mismatches; inline styles; O(n·m) view lookups. Mechanical fixes
  a senior engineer would apply without discussion.
- **ROUTE (do NOT auto-fix — hand to a human owner):** security (auth/XSS/injection); race
  conditions; design decisions; large fixes (>20 lines); enum completeness; removing
  functionality; anything changing user-visible behavior. Post these as a PR/ticket comment
  using the finding format below and route per §6.

Critical findings lean ROUTE (riskier); informational lean AUTO-FIX (mechanical).

## 6 — Output + status (wire to the orchestrator contract)
Emit each routed finding, one per line:
```
[SEVERITY] (confidence: N/10) path:line — summary
```
`SEVERITY ∈ {CRITICAL, P1, INFORMATIONAL}`. Post AUTO-FIXED items and ROUTED items as a
ticket comment:
```
DasLab Review: N findings (X critical, Y informational)
AUTO-FIXED:
- [path:line] problem → fix applied (commit <sha>)
NEEDS OWNER:
- [SEVERITY] (confidence: N/10) path:line — summary · recommended fix: …
```
Then end with exactly one terminal status (orchestrator §5.5):
- **All clear or only AUTO-FIX applied** → `STATUS: DONE — review clean, N auto-fixes pushed`
- **CRITICAL/security finding that must not land** → set ticket `blocked`, `@`-mention the
  owner → `STATUS: BLOCKED — <one-line blocker>`
- **Lands with noted concerns** → open a follow-up issue with a named owner →
  `STATUS: DONE_WITH_CONCERNS — follow-up DAS-<id> opened for <owner>`
- **Diff/context missing** → `STATUS: NEEDS_CONTEXT — <what's needed>`

## 7 — Suppressions (do NOT flag)
Harmless redundancy that aids readability; "add a comment explaining this constant"
(thresholds get tuned, comments rot); "tighten this assertion" when behavior is covered;
consistency-only changes; "regex misses edge X" when input is constrained; empirically
tuned thresholds; harmless no-ops; **anything already addressed in the diff** — read the
FULL diff before commenting.

## 8 — Hard rules
- Cite `file:line` for every finding. No `file:line` = not a finding.
- Be terse: one line problem, one line fix. No "looks good overall" filler.
- Never `git add -A`; stage only the files you intentionally fixed.
- Obey the git/PR discipline (orchestrator §6.5): branch per issue, never commit to `main`,
  CI green is the gate.
- Never leave your own review parked in `in_review` — emit a terminal STATUS (§5.5/§6).
