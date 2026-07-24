# WS-B headless Agent SDK runner design — daslab_sdk call-shape, admission gateway, run_wave boundary, subscription auth + credit ceiling

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted)
- **Date:** 2026-07-24
- **Ticket:** DAS-1554 (WS-B Design); epic DAS-1552 (MUSTAQIL WS-B RUNNER)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — subscription auth, admission gateway, host-state isolation)
- **Binds to:** ADR-0034 (SR-1…SR-5, Accepted 2026-07-24), `docs/specs/003-mustaqil-ws-b-runner/SPEC.md` (FR-001…FR-008, SC-001…SC-005, reviewed), ADR-0009 (harness-owns-transport / admission-layer ceiling), ADR-0025/0031 (dispatch-equivalence + `run_wave` attestation), ADR-0027 SI-5 (per-dispatch budget ceiling), ADR-0019 (feature flags), ADR-0005 (Git law / worktree), Founder discovery answer Q9 (Claude subscription, account auth, monthly credit = the hard budget ceiling)
- **Downstream:** DAS-1555 (`daslab_sdk` core runner), DAS-1556 (admission + auth + budget wiring), DAS-1557 (negative tests — this doc hands it §7), DAS-1558 (deploy runbook + flag flip), DAS-1559 (maintenance / health-eval)

> **Scope of this doc.** WHAT the headless runner contract is and HOW its pieces
> interlock — the SDK call shape, the admission-gateway contract, the exact
> `run_wave` function boundary, the subscription-auth + budget/credit integration,
> the board/Git-law boundary, the feature-flag posture, the `env`/`cwd` isolation,
> and the negative-path spec the Testing ticket implements. It ships **no runtime
> code**: the `daslab_sdk/` module, the auth/budget wiring, the flag consumer, and
> the tests are built by DAS-1555/1556/1557 against this design. Interface
> signatures below are contracts, not implementations. This ticket touches only
> `docs/design/` + the ticket file.

## 0. The dispatch path (one picture)

`/daslab-cycle` (interactive) and `daslab_sdk` (headless) are **two producers of
the same decision data**, funnelled through **one** post-decision seam. The
runner adds a headless front-door; it does not add a second decision-maker.

```
                       ws_b_agent_sdk_runner OFF (default)  ─────────────────────┐
                                                                                 │
  ticket/wave (data)                                                    /daslab-cycle
        │                                                              (interactive,
        ▼   ws_b_agent_sdk_runner ON                                    unchanged — the
  daslab_sdk.dispatch_ticket / dispatch_wave                            default & fallback)
        │                                                                        │
        ▼  [A] SR-1 load-shape                                                    │
  Claude Agent SDK query(prompt, options)                                        │
    options: cwd=REPO_ROOT, setting_sources=["project"],                         │
             model=<explicit, LAW 3>, env=<isolated>, permission_mode            │
        │  loads .claude/agents (32 shims) + skills + CLAUDE.md                   │
        │  + hooks + .mcp.json (ArcRift) — NEVER a create_agent port             │
        ▼  [B] SR-2 admission gateway (ADR-0009)                                  │
  admit(dispatch): explicit model? within SI-5 budget? credit left?             │
        │  auth = Claude-account/OAuth profile (NOT a metered API key)           │
        ▼  [C] collect outcomes                                                   │
   plan: WavePlan   results: WaveResults    (orchestrator-supplied DATA)          │
        │                                                                        │
        └──────────────►  [D] SR-3 the ONE seam  ◄───────────────────────────────┘
                    scripts/wave_runner.py:run_wave(plan, results)
                    checkpoint · run_start/run_end/span · guardrails ·
                    ledgers · evidence · attestation · wave-ledger
                          (ADR-0025/0031/0032 — no second producer)
```

- **[A] SR-1 / FR-001 (§1)** — the runner loads the repo's OWN agents via
  `setting_sources=["project"]`; porting the 32 roles to another abstraction is
  forbidden.
- **[B] SR-2 / FR-002 + FR-006 (§2, §4)** — every dispatch carries an explicit
  `model`, routed through the ADR-0009 admission gateway; auth is a swappable
  Claude-account path, and the SI-5 per-dispatch budget + monthly credit ceiling
  are enforced here.
- **[C]→[D] SR-3 / FR-003 (§3)** — the runner makes no routing/selection/re-tier
  decision; it hands orchestrator-supplied `(plan, results)` to
  `run_wave`, so ADR-0025/0031 flag-on == flag-off holds at a function boundary.
- **SR-4 / FR-004 (§5)** — the board stays canonical; a code-touching ticket
  still gets a worktree/branch/PR; the runner never merges its own PR.
- **SR-5 / FR-005 (§6)** — all of the above sits behind `ws_b_agent_sdk_runner`
  (default OFF); absent SDK ⇒ the runner is simply unavailable and dispatch is
  unchanged.

`daslab_sdk` throughout means the thin platform module under `daslab_sdk/` (or
`scripts/`, per ADR-0034 §Enforcement) that wraps the **Claude Agent SDK**
(`claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk`) — the packaged Claude
Code harness whose `query(prompt, options)` loads a repo's project settings. It
is **not** the Anthropic Messages-API SDK and not a `create_agent` reimpl.

---

## 1. Call-shape — load the repo's own agents (SR-1 / FR-001)

**Requirement (FR-001 / SR-1):** for every dispatch the runner sets `cwd` to the
repo root and loads the repo's own agents, skills, `CLAUDE.md`, hooks, and MCP
configuration; porting the 32 guild roles to a different agent abstraction is
**FORBIDDEN** — the generated `.claude/agents/*` shims stay canonical
(ADR-0018/0029 compile path, C1).

### 1.1 The `query()` invocation and its options

The runner's core is one call into the Agent SDK's `query(prompt, options)`, with
options fixed by this design (interface contract, not implementation):

```python
# daslab_sdk — contract shape (HOW-detail; no runtime code shipped by this ticket)
def dispatch_ticket(
    *,
    ticket_id: str,          # DAS-NNNN — the unit to dispatch
    role: str,               # role key = .claude/agents/<role>.md (from ROUTING/plan)
    model: str,              # EXPLICIT, resolved per §2.1 (LAW 3) — never inferred here
    prompt: str,             # the role dispatch envelope /daslab-cycle would send
    env: Mapping[str, str],  # the isolated env of §6 — never os.environ passthrough
) -> TicketDispatchResult: ...
```

The `ClaudeAgentOptions` the runner passes into `query()` are pinned to these
load-bearing values:

| Option | Value | Why (invariant) |
|---|---|---|
| `cwd` | repo root (absolute) | SR-1: settings/agents/skills/`.mcp.json` resolve relative to the repo, not the caller's CWD. |
| `setting_sources` | `["project"]` | SR-1: loads the repo's `.claude/` project settings — the 32 shims, `CLAUDE.md`, hooks, `.mcp.json` (ArcRift included) — **without a rebuild**. |
| `model` | the explicit `model` arg (§2.1) | SR-2 / LAW 3: the model is always passed, never inferred from frontmatter alone. |
| `env` | the isolated map of §6 | ADR-0034 accepted-risk mitigation: no host-level state leaks across concurrent headless dispatches. |
| `permission_mode` | the non-interactive, hook-governed mode | SR-4 / WS-A: the same `.claude/settings.json` `PreToolUse` admission the CLI honors is honored headlessly (ADR-0033 §2.1). |

**Structural invariant (SR-1).** The runner has **no** code path that constructs
a role from anything other than the loaded `.claude/agents/<role>.md` shim. There
is no `create_agent(...)`, no LangChain/other-abstraction role builder, no
inline system-prompt assembly — a role that is not a generated shim is
**unreachable by construction**. This is the tool-analogue of ADR-0033's
structural-unreachability rule, applied to agent identity: the generated shims
are the only role definitions the runner can load, so a "ported" role has no
place in the runner's definition.

### 1.2 Why the load-shape preserves dispatch decisions

Because `setting_sources=["project"]` loads the *same* files `/daslab-cycle` reads
in-session, the role's system prompt, allowed tools, hooks, and MCP servers are
byte-identical between the two entrypoints. The runner therefore changes *where
the dispatch is launched from* (a headless process vs. an interactive session),
never *what a role is*. Combined with §2's explicit model and §3's `run_wave`
seam, this is what makes SC-001's dispatch-equivalence achievable: same agents +
same model + same post-decision seam ⇒ same board/event/attestation outcome.

**Trace:** `cwd`=repo root + `setting_sources=["project"]` load of the canonical
shims, no `create_agent` port — closes **FR-001 / SR-1**.

---

## 2. Explicit-model + admission gateway (SR-2 / FR-002 + FR-006 + ADR-0009)

**Requirement (FR-002 / SR-2):** every dispatch passes an explicit model sourced
from `governance/policies/model-allocation.md`; the ticket frontmatter's own
model hint is **not** trusted as the sole source. Under the SDK the runner
finally **is** the in-orchestrator admission gateway ADR-0009 described — it
governs *what dispatches, with which model, under which per-dispatch budget*
(ADR-0027 SI-5), honoring the LAW 8 ceiling rather than re-opening it.

### 2.1 The explicit-model rule (LAW 3)

`model` is a **required** argument on every `daslab_sdk` dispatch entry point
(§1.1). It is resolved by the orchestrator/planner from
`governance/policies/model-allocation.md` — the task-complexity → tier table —
and threaded through `WavePlan.tickets[].model` exactly as `run_wave` already
consumes it (`TicketPlan.model`, `wave_runner.py`). The runner:

- **never** reads the ticket file to infer a model, and **never** defaults a
  missing model to a tier;
- **rejects** a dispatch whose `model` is absent/empty **before** the `query()`
  call is made — the model call is not reached (SC-002). This is a fail-closed
  precondition, mirroring `run_wave`'s own "validate inputs up front, before ANY
  side effect" discipline (`_build_records`).

The frontmatter `model:` field remains an authoring convenience the *planner*
may read; it is never the runner's trusted source (claude-code#44385 — the
frontmatter alone is not trusted on dispatch). The resolved, explicit value is
what reaches `query(options.model=...)` and what `run_wave` attests.

### 2.2 The runner IS the ADR-0009 admission gateway

ADR-0009 recorded the honest ceiling: under the Claude Code *harness*, DasLab does
not own the LLM transport, so LAW 8 is an **admission** layer (governs *what is
dispatched and when*), and the literal "no un-proxied call" transport-proxy form
is reachable "**only under a future SDK-based runner**." **This runner is that
SDK runner.** The admission gateway is a single function every dispatch passes
through before `query()` is called:

```python
# daslab_sdk — admission contract (fail-closed; no dispatch bypasses it)
def admit(*, ticket_id: str, role: str, model: str) -> AdmissionDecision:
    """Return ADMIT or a sanctioned HOLD. Governs which model dispatches, under
    which per-dispatch SI-5 budget, using the swappable Claude-account auth path.
    Makes NO routing/selection/re-tier decision (that stays SR-3 / run_wave-adjacent)."""
```

What the gateway **governs** (the ADR-0009 admission surface, now real under the SDK):

- **explicit-model admission** — a dispatch with no explicit model is refused
  here (§2.1, SC-002);
- **per-dispatch budget** — the ADR-0027 SI-5 ceiling: a dispatch that would
  breach the `mustaqil:` per-run/per-day cap (`config/budgets.yaml`, DAS-1543) is
  held, not dispatched (§4, SC-004);
- **auth admission** — the dispatch authenticates through the Claude-account
  path (§4.1), keeping the auth mechanism swappable behind this one seam.

What the gateway **does NOT** do (kept out, per SR-3): it makes no routing,
selection, or re-tier decision — it does not pick the model, does not pick the
role, does not reorder the wave. Those are the orchestrator's decisions, carried
in `plan` as data (§3). The gateway is a *yes/hold on an already-made decision*,
not a decision-maker. This is the exact ADR-0009 split — "admission and
concurrency, not the raw transport / not the routing" — now enforceable because
the runtime (the SDK) is one DasLab owns end-to-end.

**Ceiling honored, not re-opened.** ADR-0009's LAW 8 restatement said "no agent
is dispatched outside the admission layer." The runner satisfies the *stronger*
SDK-runner form by construction: `query()` is only ever called from inside
`admit(...) == ADMIT`, so there is no dispatch path that skips admission — the
grep/CI proof ADR-0009 deferred to "the SDK-runner milestone" is now assertable
(SC-002 asserts the missing-model refusal arm of it).

**Trace:** explicit `model` from the allocation policy + the single fail-closed
`admit()` gateway (model + SI-5 budget + swappable auth), no routing decision —
closes **FR-002 / SR-2** and the FR-006 admission-routing half.

---

## 3. The `run_wave` boundary — no mechanical decision, one producer (SR-3 / FR-003)

**Requirement (FR-003 / SR-3):** the runner makes no routing/selection/re-tier
decision of its own; it **calls** `scripts/wave_runner.py:run_wave(plan, results)`
with the plan/results the orchestrator supplied as data, so the ADR-0025
dispatch-equivalence guarantee holds at a function boundary; and it emits the
same `run_start`/`run_end`/`span`/checkpoint/attestation stream (ADR-0023/0024/
0031/0032) — never a second, divergent producer.

### 3.1 The exact function boundary

`run_wave` is already the deterministic post-decision seam (`wave_runner.py`,
DAS-1499/ADR-0031). Its public API is unchanged by WS-B; the headless runner is
simply a **new caller** of it:

```python
# scripts/wave_runner.py — the SEAM (unchanged; daslab_sdk is a new caller of it)
run_wave(
    plan: WavePlan,        # the routing DECISION (immutable) — TicketPlan{ticket_id, role, model, ...}
    results: WaveResults,  # the collected OUTCOMES (immutable) — TicketResult{outcome, merged_pr, ci_status, ...}
    *, created_at: str,    # caller-supplied ISO-8601 Z — run_wave reads NO clock
    organism_emit: bool = True,  # the ADR-0025 gate: False ⇒ no-op, returns None
    ...
) -> WaveAttestation | None
```

The headless runner's responsibility ends at **assembling `(plan, results)` from
the same data `/daslab-cycle` would assemble** and calling `run_wave`:

- `plan` — a `WavePlan` whose `TicketPlan`s carry the orchestrator's already-made
  `{role, model}` routing (the model is the explicit §2 value). The runner does
  **not** compute this; it is handed the decision.
- `results` — a `WaveResults` built from the outcomes the runner *observed* by
  dispatching through `query()` (each `TicketResult.outcome/merged_pr/ci_status/
  final_status/output`), plus the caller-supplied timestamps.

`run_wave` then performs the identical mechanics for both entrypoints:
checkpoint → `run_start`/`run_end`/`span` per dispatch → guardrail tripwires →
ledgers + completions + close-checkpoint → committed evidence → the doubly
hash-chained `WaveAttestation` → the atomic `board/wave-ledger.jsonl` entry
(ADR-0032). Because `run_wave` "reads no clock and makes no routing decision"
and does "the SAME mechanical steps every time" given `(plan, results)`, an
identical decision dispatched through either entrypoint produces an identical
attestation (SC-001).

### 3.2 One producer, not two — the SR-3 property

The runner **must not** fork the event/attestation producers. It never calls
`dispatch_emitter` / `pulse_checkpoint` / `snapshot_evidence` / the ledger
appenders directly, and never writes to `board/.events.jsonl`,
`metrics/attestations/`, or `board/wave-ledger.jsonl` itself. Its *only* write
into that surface is **through `run_wave`**. This is the load-bearing SR-3
invariant: `run_wave` is already a single-producer seam
(`organism_emit`-gated, "REUSE, never re-implement"); a second producer would
break the ADR-0032 reconciliation bijection (`verify_wave_ledger` — no orphan
attestations, no gap in the chain). The headless runner is a *client of the
decision seam*, exactly as the interactive dispatcher is.

### 3.3 Flag-on == flag-off dispatch decisions

The dispatch *decisions* (which tickets, to which roles, on which models, in what
order) are the orchestrator's and live in `plan`. Neither entrypoint alters them.
With `ws_b_agent_sdk_runner` OFF the headless path does not run at all
(`/daslab-cycle` dispatches byte-identically, §6); with it ON, the same `(plan,
results)` flows to the same `run_wave`. The runner has no `organism_emit`-style
second toggle of its own — it inherits the one on `run_wave`. Therefore flag-on
== flag-off holds at the ADR-0025 §(d) reader-vs-router boundary: the runner
reads its inputs from its arguments and writes exclusively via the append-only
producer `run_wave` drives.

**Trace:** `run_wave(plan, results)` called with orchestrator-supplied data, no
direct producer writes, one attestation stream — closes **FR-003 / SR-3** and
preserves ADR-0025/0031.

---

## 4. Subscription auth + budget/credit ceiling (FR-006 / FR-007 / FR-008 + ADR-0027 SI-5 + Q9)

**Requirement (FR-006/007/008):** the runner authenticates to the model using a
**Claude-subscription account**, not a metered API key, routed through the
admission layer so the auth path stays swappable (FR-006). A wave that would
breach the per-run/per-day cap or the monthly subscription credit MUST evaluate
to **idle + alert**, never a partial dispatch or a false success; metered
overflow stays disabled by default (FR-007). Exhaustion of the monthly credit is
a **sanctioned pause** that resumes on refresh — never a crash, silent stop, or
failed run (FR-008). This is Founder discovery answer Q9.

### 4.1 Auth — Claude-account / OAuth, not a metered API key

The Agent SDK resolves credentials the same way the `ant` CLI and Claude Code do
(first match wins): `ANTHROPIC_API_KEY` → `ANTHROPIC_AUTH_TOKEN` → the active
OAuth profile stored by `ant auth login` under `~/.config/anthropic/`. The
subscription path is the **OAuth profile** — a Claude-account login that draws
against the plan's monthly credit — **not** a metered `ANTHROPIC_API_KEY`.

Design controls (built by DAS-1556, wired here):

- The runner's isolated `env` (§6) **must not** carry `ANTHROPIC_API_KEY` (and
  not an empty `ANTHROPIC_API_KEY=""`, which still wins its precedence slot). Its
  presence would shadow the subscription profile and route spend onto a metered
  key — the exact "subscription-only, no metered $" intent violated. The isolation
  design therefore *drops* the API-key vars from the child env and lets the SDK
  resolve the account OAuth profile.
- Auth is admitted through the single §2.2 gateway, so the *mechanism* is
  swappable behind one seam: the day the plan's headless-auth terms change, only
  the gateway's auth resolution changes — no dispatch path is rewritten.

### 4.2 Budget — the SI-5 hard dispatch ceiling

`config/budgets.yaml` `mustaqil:` (DAS-1543) is the SSOT. Two nested ceilings, both
enforced at admission (§2.2), never as a post-hoc excuse:

1. **`mustaqil.caps.per_run` / `per_day`** — the conservative self-imposed
   dispatch ceiling (ADR-0027 SI-5). A wave (`--tick`) whose *estimated* usage
   would breach either cap evaluates to **idle + alert** (`on_breach:
   idle_and_alert`, wired via `scripts/alerting.py`) — it dispatches **nothing**,
   never a partial/degraded wave, never a false-green. The estimate is
   pre-dispatch (token estimate + post-hoc accounting, the ADR-0009 harness-era
   granularity), so the breach is caught *before* `query()` is called for the
   wave's tickets.
2. **`mustaqil.monthly_credit_ceiling`** — the OUTER ceiling (Q9): the
   subscription's monthly credit (`plan_credit_usd` per active plan). When the
   monthly credit depletes, further Agent-SDK requests stop.

`metered_overflow: false` is honored as a hard invariant: the runner never falls
back to usage-credit / API-rate overflow to exceed the subscription. Flipping it
ON is a Founder-only budget decision (out of the runner's authority).

### 4.3 Credit exhaustion — a sanctioned pause, not a failure

When the monthly credit is exhausted (`on_exhaustion: sanctioned_pause`), the
runner treats the halt like an expected gate — an idle wait for the credit
refresh — **not** a crash, a silent stop, or a failed run:

- the wave evaluates to **idle + alert** (same shape as a budget breach: no
  dispatch, an alert emitted);
- the run's status is a *sanctioned pause*, distinguishable in the runner's
  return contract from an error outcome, so no false-green and no false-red is
  produced;
- on credit refresh the runner resumes normally (idempotent re-entry — a paused
  `--tick` that later runs again is safe; guard-before-act, DAS-1447).

The distinction the design must preserve for SC-004: **budget-breach** and
**credit-exhaustion** both resolve to *idle + alert / sanctioned pause*, which is
neither a completed dispatch (false-green) nor an unhandled exception (crash /
false-red). "Size waves to fit the monthly credit; do not assume overflow
exists" (`config/budgets.yaml`).

### 4.4 Flip-time precondition (bound on DAS-1558)

`config/budgets.yaml` carries a standing `[NEEDS VERIFICATION at WS-B go-live]`
marker: the credit-based subscription model was announced 2026-06-15 then paused,
so the live plan's Agent-SDK terms, per-plan monthly credit, and headless-use
policy must be re-verified against Anthropic's live docs **before the flag is
flipped ON**. Per the DAS-1553 closure, this is a **flip-time / Deployment
precondition, NOT a build-time blocker** — the runner builds and tests behind
`ws_b_agent_sdk_runner` OFF regardless of live terms (Q9 already fixes the model
stance). This design records the precondition and **binds it as an explicit
Deployment precondition on DAS-1558**: DAS-1558 must re-verify current plan terms
before ever setting the flag ON. The numbers in `config/budgets.yaml`
(`pro: 20`, `max_5x: 100`, `max_20x: 200`) are placeholders keyed to the active
plan and are re-confirmed at that gate.

**Trace:** OAuth-profile subscription auth (no metered key) through the swappable
gateway (FR-006); SI-5 per-run/per-day + monthly-credit ceilings → idle+alert,
metered-overflow OFF (FR-007); credit-exhaustion → sanctioned pause, resume on
refresh (FR-008); DAS-1558 flip precondition — closes **FR-006/007/008 + Q9**.

---

## 5. Board / Git-law boundary (SR-4 / FR-004)

**Requirement (FR-004 / SR-4):** the runner reads and writes the board exactly
as `/daslab-cycle` does (C2 — board stays canonical); a code-touching ticket MUST
still get its own worktree, branch, and pull request (ADR-0005); and the runner
MUST NOT merge its own pull request.

- **Board is canonical, read/written the same way (C2).** The runner's view of
  ticket state is `board/tickets/*.md` — the same files `/daslab-cycle` reads. It
  mutates a ticket's frontmatter/log only through the same edit discipline
  (status transition + `## Log` entry, never a silent edit; board README rules).
  The one board write `run_wave` performs on the runner's behalf — the
  idempotent `run_id:` frontmatter stamp (`_stamp_wave_run_ids`) — is the
  existing audit-trail marker, not a new routing-field write.
- **No routing-field writes by the runner (C3).** The runner does not write
  `assignee`, dispatch order, or reviewer fields. Routing is the orchestrator's;
  the runner carries it as `plan` data (§3) and never mutates it back onto the
  board. A dispatched role agent edits only its own ticket file plus its work
  artifacts (board README concurrency rule) — the headless runner does not widen
  that.
- **Worktree / branch / PR still required for code (ADR-0005).** A code-touching
  ticket dispatched headlessly gets the same one-issue-one-branch-one-worktree
  treatment; `in_review` still requires a pushed branch/PR; `done` still requires
  a **merged PR with green CI**. The runner produces the work; it does not shortcut
  the Git law because it ran without a human in the session.
- **The runner never merges its own PR (C4 / SR-4).** Headless dispatch advances
  a ticket to `in_review` and routes it to the reviewer per `board/ROUTING.md`;
  the merge is a separate, reviewer-gated action. There is no runner code path
  that self-merges — the merge authority is not in the runner's surface at all,
  the same way `/daslab-cycle` never self-merges. AADL gate order (`depends_on` /
  open-gate skips) is unchanged by the runner's existence.

**Trace:** board canonical + read/written identically, no routing-field writes,
worktree/branch/PR preserved, no self-merge — closes **FR-004 / SR-4**.

---

## 6. Feature-flag / additive + host-state isolation (SR-5 / FR-005 + ADR-0034 accepted risk)

**Requirement (FR-005 / SR-5):** the runner is OFF by default behind a feature
flag; `/daslab-cycle` remains the default, behaviour-defining path; merging the
runner changes no interactive-wave behaviour. Plus the ADR-0034 accepted risk:
the SDK reads host-level config regardless of `setting_sources`, so the runner
must set explicit `env`/`cwd` isolation.

### 6.1 The flag — `ws_b_agent_sdk_runner`, default OFF

The flag `ws_b_agent_sdk_runner` already exists in `config/features.yaml`
(default `false`), read via `scripts/feature_flags.py:enabled(...)`. Its consumer
is the subscription-Claude dispatch path (this runner). Posture:

- **OFF (default) ⇒ inert.** The `daslab_sdk` dispatch path does not run.
  `/daslab-cycle` is the only entrypoint and a wave run through it is
  **byte-identical to pre-merge** (SC-003). The runner adds a *capability*, not a
  behaviour change to interactive waves — merging it flips nothing.
- **Absent SDK ⇒ unavailable, not broken.** If the Claude Agent SDK is not
  installed, the runner is simply unavailable (a clean "runner unavailable"
  result), and dispatch is unchanged. The SDK is an *optional* dependency of the
  headless path, never a hard dependency of the engine — `/daslab-cycle` has no
  SDK dependency at all.
- **ON is a Founder-only flip** once the flip precondition holds (§4.4 /
  DAS-1558): the runner authenticates via the Claude account/OAuth path and the
  ADR-0009 admission layer wraps it (`config/features.yaml` comment). Flipping is
  never the runner's own act.

### 6.2 Explicit `env`/`cwd` isolation (ADR-0034 accepted risk)

ADR-0034 accepts, and this design mitigates, that the SDK reads host-level config
regardless of `setting_sources`. So a headless dispatch could otherwise inherit or
leak host-level state across concurrent runs. The runner sets, per dispatch:

- **`cwd` = repo root (absolute).** Pins project-settings resolution to the repo
  and keeps relative paths deterministic; a dispatch never resolves settings
  from the caller's arbitrary CWD.
- **An explicit, constructed `env` — not an `os.environ` passthrough.** The child
  process env is *built*, not inherited: it carries only what a dispatch needs
  (repo-scoped vars) and **omits** host-level credentials and state — in
  particular `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` are dropped so the
  subscription OAuth profile resolves (§4.1) and no metered key leaks in. Any
  host-level `ANTHROPIC_*`, cloud-provider, or session var not on the runner's
  allow-set is excluded.
- **Per-dispatch isolation for concurrency.** Because there is no parallel cap
  (Model Allocation Law), concurrent headless dispatches must not share mutable
  host state. Each `query()` gets its own constructed `env` and its own worktree
  (§5) — the two isolation surfaces (process env + filesystem worktree) together
  ensure one dispatch cannot observe or corrupt another's host-level state.

This isolation is the same posture WS-A takes for the sidecar ("no mounted
secrets unless explicitly scoped", ADR-0012 §3) applied to the runner's process
boundary: least host-state by default, allow-set only.

**Trace:** `ws_b_agent_sdk_runner` OFF ⇒ inert + byte-identical interactive
waves; absent SDK ⇒ unavailable; explicit constructed `env` + `cwd`=repo-root +
per-dispatch worktree isolation — closes **FR-005 / SR-5** and the ADR-0034
accepted-risk mitigation.

---

## 7. Negative-path spec for DAS-1557 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1557, `zone: tests`, `implements:
[SC-001, SC-002, SC-003, SC-004]`, `depends_on: [DAS-1555, DAS-1556]`) must
assert. Each is written so it can be implemented directly against the `daslab_sdk`
surface (`admit`, `dispatch_ticket`/`dispatch_wave`, the flag consumer, the budget
evaluator) plus the existing `run_wave` seam, and folded into
`tests/test_ws_b_agent_sdk_runner.py`.

### SC-001 — dispatch-equivalence (flag-on == flag-off DECISIONS) (SR-1/SR-3)

- **SC-001a — same board/event/attestation outcome.** Given one fixed
  `(plan, results)` decision, assert that the attestation `run_wave` produces when
  called by the headless runner is **equal** (same `tickets`, `wave`,
  `counts`, `event_digest`, `ledger_digest`, and a verifying `attest_chain`) to
  the one produced by an interactive dispatch of the same decision. The seam is
  deterministic given `(plan, results)` and a caller-supplied `created_at`, so
  fix `created_at` and assert equality of the committed payload (modulo the
  `attest_chain.prev` tip, which is store-position, not decision).
- **SC-001b — one producer, not two.** Assert the runner writes into
  `board/.events.jsonl` / `metrics/attestations/` / `board/wave-ledger.jsonl`
  **only** through `run_wave` — e.g. with `organism_emit=False` the runner
  produces **zero** post-decision writes (parity with a flag-off wave), and with
  it ON the wave-ledger still reconciles (`verify_wave_ledger([]) == []`; no
  orphan attestation, no chain gap). A second, direct producer write is a test
  failure.

### SC-002 — missing-explicit-model rejection (SR-2 / LAW 3)

- **SC-002a — explicit model required, rejected before the model call.** Assert a
  dispatch with an absent/empty `model` is **rejected by `admit()`** and that
  **no `query()` / model call is reached** (e.g. a spy on the SDK call records
  zero invocations). The rejection is a fail-closed precondition, evaluated
  before any side effect.
- **SC-002b — frontmatter is not the trusted source.** Assert that a ticket whose
  frontmatter carries a `model:` hint but whose dispatch is invoked without the
  explicit resolved `model` argument still **rejects** — the runner does not fall
  back to the frontmatter hint (claude-code#44385). The explicit argument is the
  only trusted source.

### SC-003 — flag-off no-op / byte-identical interactive wave (SR-5)

- **SC-003a — inert with the flag OFF.** With `ws_b_agent_sdk_runner` OFF
  (default), assert the `daslab_sdk` dispatch path does not run and a wave driven
  through `/daslab-cycle`'s existing path is **byte-identical to pre-merge** (no
  new events, no new attestation attributable to the runner). Merging the runner
  changes no interactive-wave behaviour.
- **SC-003b — absent SDK ⇒ unavailable, not error.** Assert that with the SDK
  import unavailable, invoking the runner yields a clean "runner unavailable"
  result (not a crash, not a dispatch), and `/daslab-cycle` is unaffected.

### SC-004 — budget-breach and credit-exhaustion → idle+alert / sanctioned pause (FR-007/008)

- **SC-004a — budget breach → idle + alert.** Given a `mustaqil.caps.per_run` (or
  `per_day`) cap that the wave's estimate would breach, assert the wave evaluates
  to **idle + alert**: **zero** dispatches occur, an alert is emitted (via the
  `scripts/alerting.py` seam), and the result is **neither a completed dispatch
  (false-green) nor an unhandled exception (crash/false-red)**. Assert
  `metered_overflow` stays OFF — the runner does not dispatch by spilling past the
  subscription.
- **SC-004b — credit exhaustion → sanctioned pause.** Given the monthly credit is
  depleted (`on_exhaustion: sanctioned_pause`), assert the wave evaluates to a
  **sanctioned pause**: idle + alert, a status distinguishable from an error
  outcome, no false-green and no crash, and that a subsequent run after the
  credit "refreshes" resumes normally (idempotent re-entry — no double-apply of
  any side effect, DAS-1447).
- **SC-004c — the two are the same evaluation, distinct from success/crash.**
  Assert both breach and exhaustion resolve to the idle+alert / sanctioned-pause
  family and are never scored as a satisfied wave or an exception.

**Hand-off:** SC-001 → §1 (load-shape) + §3 (`run_wave` seam); SC-002 → §2
(explicit model + admission); SC-003 → §6 (flag + availability); SC-004 → §4
(budget/credit). All assertions are expressible against the `daslab_sdk` surface
DAS-1555/1556 build plus the existing `run_wave` / `verify_wave_ledger` primitives.

---

## 8. Traceability matrix

| SPEC FR | ADR-0034 SR | This design | DAS-1557 SC |
|---|---|---|---|
| FR-001 — load repo's own agents; no port | SR-1 | §1 (`cwd`+`setting_sources=["project"]`, structural no-`create_agent`) | SC-001a |
| FR-002 — explicit model from allocation policy; frontmatter not trusted | SR-2 | §2.1 (required arg, fail-closed) + §2.2 (admission gateway) | SC-002a, SC-002b |
| FR-003 — no mechanical decision; call `run_wave`; one event stream | SR-3 | §3 (`run_wave(plan, results)` seam, single producer, flag-on==flag-off) | SC-001a, SC-001b |
| FR-004 — board canonical; worktree/branch/PR; no self-merge | SR-4 | §5 (C2/C3/C4, ADR-0005 Git law) | SC-001b (board parity), covered structurally |
| FR-005 — OFF by default; interactive unchanged; merge is inert | SR-5 | §6.1 (flag) | SC-003a, SC-003b |
| FR-006 — Claude-subscription auth (not metered key); routed through admission; swappable | SR-2 (admission) + Q9 | §4.1 (OAuth profile) + §2.2 (gateway) | SC-002 (admission), SC-004a (metered-overflow OFF) |
| FR-007 — cap/credit breach → idle+alert, no false-green; metered overflow OFF | ADR-0027 SI-5 + Q9 | §4.2 (SI-5 ceilings), §4.3 (idle+alert) | SC-004a, SC-004c |
| FR-008 — credit exhaustion → sanctioned pause, resume on refresh; never crash/silent-stop | ADR-0027 SI-5 + Q9 | §4.3 (sanctioned pause, idempotent re-entry) | SC-004b, SC-004c |
| ADR-0034 accepted risk — SDK reads host config regardless of `setting_sources` | SR-5 (bounded by flag) | §6.2 (explicit constructed `env` + `cwd` + per-dispatch worktree isolation) | SC-003 (flag-gated), isolation covered structurally |

## 9. Open items handed downstream (not decided here)

- **DAS-1555** builds the `daslab_sdk/` core runner: the `query()` call-shape (§1),
  the `dispatch_ticket`/`dispatch_wave` entry points, and the `(plan, results)`
  assembly that calls `run_wave` (§3) — all behind `ws_b_agent_sdk_runner` OFF.
- **DAS-1556** wires the admission gateway (§2.2), the Claude-account/OAuth auth
  resolution + API-key-drop env construction (§4.1, §6.2), and the SI-5
  budget/credit evaluator against `config/budgets.yaml` `mustaqil:` (§4.2–4.3).
- **DAS-1557** implements §7's negative-path spec (SC-001…SC-004) in
  `tests/test_ws_b_agent_sdk_runner.py`.
- **DAS-1558 (Deployment)** carries the **flip-time precondition** (§4.4): before
  the flag is ever set ON, re-verify the live plan's Agent-SDK terms, per-plan
  monthly credit, and headless-use policy against Anthropic's live docs; the flip
  itself is a Founder-only act.
- **Security Lead (consulted)** reviews §4.1 subscription-auth / no-metered-key
  posture and §6.2 host-state isolation; **CTO (accountable)** ratifies GATE-2
  closure.
- The concrete `daslab_sdk` module path (`daslab_sdk/` vs `scripts/`) is an
  ADR-0034-sanctioned implementation choice left to DAS-1555, not decided here.
