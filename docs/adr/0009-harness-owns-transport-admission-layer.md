# ADR 0009 — The harness owns the LLM transport: LAW 8 is an admission layer in the harness runtime, a transparent proxy only in a future SDK runner

- **Status:** Proposed (authored by Backend EM; **CTO ratifies — GATE-2 / RACI 3.1 A**)
- **Date:** 2026-06-19
- **Scope:** Platform / orchestration + resource governance
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted)
- **Relates:** ADR 0005, 0006, 0007, 0008

> This is the **honest-ceiling ADR**. It records a constraint that shapes both the current
> harness runtime and any future SDK-based runner, so implementations are designed against
> the real architecture instead of a wished-for one. The spec mandates writing the ceiling
> down (P6, IMPROVISATION CLAUSE).

## Context

**ENTERPRISE INVARIANT LAW 8** (spec): *"EVERY LLM call routes through the Resource Manager.
No agent makes a raw, unmetered Claude call. No bypass."* The Resource Manager's `DO` says:
*"Build a **transparent proxy in front of every Claude endpoint** (LAW 8 — no bypass)"* with
rate accounting, AIMD, priority queue, circuit breaker, zombie reaping, token budgets, and the
same-zone guard at admission. Its acceptance demands: *"zero raw/un-proxied Claude calls
remain (grep + CI check)."*

**Verified DRY_RUN finding (the load-bearing one).** DasLab today runs as **Claude Code
subagents** dispatched by `/daslab-cycle` / `/daslab-run` at the repo root (current-state
§2). In that runtime, **the Claude Code harness owns the LLM transport end to end.** When
the orchestrator spawns a subagent (the `Agent` tool), the harness — not any DasLab code —
opens the model connection, sends the request, applies the model, and streams the result.
**There is no seam in the dispatch path where DasLab code can interpose a proxy on the
actual HTTP transport.** A DasLab-authored "transparent proxy in front of every Claude
endpoint" presumes DasLab controls the transport; under the Claude Code harness it does not.

Therefore the literal Resource Manager design — a transport-level proxy that every call
physically traverses, proven by "zero un-proxied calls (grep + CI)" — is **not achievable
while the runtime is the Claude Code harness.** Writing it as if it were achievable would ship a
false guarantee (a "no bypass" claim that the architecture cannot enforce), which violates
the honesty principle (P6) and would be a hollow gate (LAW 2).

## Decision

**Split LAW 8 enforcement by runtime, and say so plainly:**

1. **Claude Code harness runtime → LAW 8 is an in-orchestrator
   ADMISSION layer, NOT a transport proxy.** The Resource Manager governs **what the
   orchestrator is allowed to dispatch and when** — before the harness makes the call:
   - **admission control** (global concurrency gate C_max — how many subagents the
     orchestrator spawns per wave);
   - **priority queue over a dependency DAG** (p0 > high > normal > low; shortest-token-cost
     tiebreak) deciding dispatch order;
   - **the LAW 6 same-zone guard enforced at admission** (no two tickets in one repo zone
     per dispatch unit — this part **is** fully enforceable here and is the immediate
     win);
   - **rate-limit backpressure** driven by **observed** signals (the harness surfaces
     rate-limit/`retry-after` behaviour as errors/latency the orchestrator can read and
     react to with AIMD on **admission rate**), not by parsing every response header inside
     a proxy DasLab owns;
   - **per-run token/$ budgets** accounted at the **dispatch-decision** granularity (per
     ticket/per wave) using token estimates and post-hoc accounting — **not** a
     per-call inline meter on a transport DasLab does not own;
   - **circuit breaker + zombie reaping** at the dispatch/worktree layer (reclaim a slot
     from a stuck subagent — ties to ADR 0005's reap pass).

   The honest LAW 8 restatement:
   > *Every **dispatch** is admitted, prioritized, zone-checked, and budget-accounted by the
   > Resource Manager. The Manager governs admission and concurrency; it does not — and on
   > the Claude Code harness **cannot** — sit on the raw HTTP transport. "No bypass" means
   > "no agent is dispatched outside the admission layer," not "every byte traverses a
   > DasLab proxy."*

2. **A future SDK-based runner → LAW 8 becomes a true transparent proxy.** If DasLab moves
   dispatch onto the **Claude Agent SDK** (or a direct Anthropic API client DasLab owns),
   the runtime *does* own the transport, and the literal transparent proxy — every call
   physically traversing a DasLab-owned client with per-call header parsing, RPM/TPM
   accounting, and a grep/CI proof of "zero un-proxied calls" — becomes achievable. That is
   the architecture under which "transparent proxy / no raw call" is enforceable. It is
   **explicitly future work**, gated by its own ADR (cost, behaviour-parity, model-identity
   per LAW 3).

3. **Acceptance criteria are rewritten to match reality.** The literal "zero un-proxied Claude
   calls (grep + CI)" is **re-scoped** for the harness runtime to: *"zero dispatches outside
   the admission layer (the orchestrator is the single dispatch chokepoint; a grep/CI check
   asserts every spawn path goes through the admission API)."* The transport-level grep
   proof is **deferred** to the SDK-runner milestone and labelled as such — we do not claim
   to have proven something the architecture cannot prove.

## Consequences

**Positive (honesty + real wins):** the same-zone guard, concurrency cap, priority
ordering, AIMD-on-admission, circuit-breaker, and zombie reaping are **all enforceable
today** at the dispatch layer and deliver the safety spine that makes high concurrency safe
(T8 spirit) — without pretending to a transport proxy that doesn't exist. The kill-switch
(halt all dispatch) and the cost-throttle (drop to cheap tier on budget breach) are
admission-layer actions and remain fully real. The admission Resource Manager is the next
step; the transport proxy is correctly filed as SDK-runner future work.

**Negative / accepted (the honest ceiling):**
- **Per-call inline metering and header-level rate parsing are not available** on the
  harness runtime — token/$ accounting is per-dispatch-estimate and post-hoc, not a
  hard real-time inline ceiling. A true real-time per-call hard budget needs the SDK runner.
- The "no raw call / no bypass" guarantee is **weaker than the literal LAW 8 text** on the
  harness: it is "no dispatch outside admission," not "no byte outside a proxy." This is
  **recorded, not hidden** — that is the entire purpose of this ADR.
- The Resource Manager's strongest, transport-level form is **blocked on a runtime change**
  (Claude Code harness → SDK runner), which is a larger architectural decision.

**Law check:** LAW 2 (no hollow gate — we refuse to ship a "no bypass" claim the
architecture can't back; we state the real boundary); LAW 8 (honored in its **enforceable**
form — admission-layer governance of every dispatch — with the transport-proxy ideal
correctly deferred and labelled); LAW 3 (a future multi-endpoint/SDK path must serve the
**same model identity** the allocation policy assigns — restated here so the SDK-runner work
inherits it); LAW 10 (kill-switch + concurrency cap are admission-layer, fully real today).

## Enforcement / acceptance

- Immediately: the **same-zone admission guard** and **concurrency cap** are the
  orchestrator's, with a grep/CI check that every dispatch path goes through the admission
  API.
- The Resource Manager acceptance is **re-scoped** per §Decision.3 to the admission-layer
  proof; the transport-proxy "zero un-proxied calls" proof is filed as the **SDK-runner
  milestone**, gated by its own ADR.
- This ADR is the citation any future "why isn't LAW 8 a real proxy yet?" question resolves
  to.
