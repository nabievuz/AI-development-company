# ADR 0037 — End-to-end autonomous delivery target (the MUSTAQIL completion contract)

- **Status:** Proposed (Backend EM authors; **CTO ratifies — RACI 3.1/3.6**; CEO + Founder consulted — this fixes the org's completion contract)
- **Date:** 2026-07-22
- **Scope:** Platform / org-engine — the binding definition of "end-to-end autonomous delivery" and of "finished"
- **Deciders:** Backend EM (author), **CTO (accountable)**; CEO consulted (program owner); Founder consulted (the gate authority the contract preserves)
- **Relates:** umbrella over the MUSTAQIL workstreams — [0033](0033-ecosystem-tool-mcp-bridge.md), [0034](0034-agent-sdk-headless-runner.md), [0035](0035-langgraph-dgox-execution-substrate.md), [0036](0036-outbound-interop-surface-langsmith.md), [0038](0038-enterprise-internal-self-host-hardening.md), and [0027](0027-scheduler-safety.md); enforces [0020](0020-gate-promotion-no-false-green.md) (no false-green), [0031](0031-wave-runner-attestation.md)/[0032](0032-harness-forced-attestation.md) (attestation), [0014](0014-native-clarify-gate.md) (clarify); program `docs/research/2026-07-22-daslab-mustaqil-master-prompt.md`
- **Supersedes / Amends:** nothing — names the target and the completion contract fresh; changes no dispatch behaviour.

> The Founder's north star is DasLab as an **end-to-end autonomous software finisher** — hand it a goal, it delivers 0→100. This ADR fixes *what that means as a binding contract*, so "autonomous" cannot drift into "ungoverned" and "finished" cannot be claimed without evidence. It is the umbrella the MUSTAQIL workstreams (ADR 0033–0038) close their gates against.

## Context

"Complete the whole project autonomously" is the industry frontier and the source of the reliability cliff (success rates fall on long-horizon tasks; agents mark work done without verifying it). DasLab is already architected for it — a durable goal (Founder-approved queue), checkpoint/resume (ADR 0023), memory (ArcRift), definition-of-done (AADL gates + the 100/100 release gate), and per-ticket fresh context that resists dilution. What is missing is not the machinery but a **written contract** that (a) defines "finished" only by evidence, (b) reconciles "0→100, no unplanned stops" with the never-auto-approve law, and (c) binds "no hallucination" to enforcement rather than assertion. Without this contract, an autonomous run can false-green, run past a human gate, or fabricate a result.

## Decision

**Adopt "end-to-end autonomous delivery" as a named platform target governed by a binding completion contract.** Invariants:

### ED-1 — "Finished" (0→100) is defined ONLY by evidence
A goal is complete **only** when: every AADL gate is closed; every code ticket has a merged PR + green CI; every wave has a committed hash-chained attestation (ADR 0031/0032); `scripts/diagnostics.py` = 100/100 on a clean tree; and golden evals pass with the anti-gaming probe. No prose "done", no self-report, and no unmeasured dimension counts (ADR 0020 — unmeasured is SKIPPED, never green). If it cannot be evidenced, it is not finished.

### ED-2 — The only legitimate halt is a Founder/AADL gate
"Autonomous, 0→100, no unplanned stops" means: the org advances to a sanctioned gate, presents evidence, and **waits** for the Founder, then resumes immediately on `APPROVED:`/`TASDIQLANDI:`. Gates and interrupt-cards **always** wait for the Founder (never-auto-approve, QONUN-5); a gate halt is a designed checkpoint, **not** a failure and **not** a licence to run past it. "No unplanned stops" forbids silent blockers and abandonment — a blocked unit opens a `blocked` ticket with the exact reason and escalates (ROUTING.md); it never loops or guesses past the block.

### ED-3 — No fabrication
Recall from ArcRift at the start of a unit of work and store the decision at the end; cite real files/commits/spans. An unknown fact is marked `[NEEDS CLARIFICATION]` (ADR 0014) and escalated — never resolved by inventing an API, a result, or a passing test. A claim without a real artifact is treated as false.

### ED-4 — Beat the reliability cliff structurally
Re-anchor the top-level goal from ArcRift at the **start of every wave** (not just at program start); checkpoint every wave (ADR 0023); keep WIP = 1 per role and one repo-zone per wave; and decompose the program into Founder-approved sub-goals rather than one unbounded run. Context dilution and goal drift are defeated by the org structure, not by a longer prompt.

### ED-5 — Honest scope of "end-to-end"
The target is **scoped, well-specified** goals from the Founder-approved queue. An ambiguous or unbounded-greenfield goal must first pass the Clarify gate (ADR 0014). The binding honest bound: reliable completion of *arbitrary* long-horizon projects is unsolved industry-wide; DasLab's claim is scoped-project completion, **proven by one delivered project** (the MUSTAQIL PROOF workstream / G6), not asserted omnicompetence.

## Consequences

**Positive:** The org gains a single, measurable, enforceable completion contract; "autonomous finisher" becomes something CI can check rather than something a prompt asserts. ED-2 removes the contradiction between "no stops" and the never-auto-approve law. ED-3/ED-4 convert the anti-hallucination and anti-cliff intentions into mechanisms already present in the repo.

**Negative / accepted:** The contract makes "done" *harder* to reach (evidence-gated), which is the point — it trades speed-of-claiming-done for truth-of-done. The residual is recorded honestly: an LLM runtime cannot be *guaranteed* never to hallucinate or stall; ED-1/ED-3 reduce this from "silent" to "detectable" (a lapse breaks a committed chain and fails CI), not to zero.

**Law check:** **AADL** (ED-1 gates). **Never-auto-approve / QONUN-5** (ED-2). **No false-green / ADR 0020** (ED-1). **Attestation / ADR 0031/0032** (ED-1). **Clarify / ADR 0014** (ED-3/ED-5). **Persistent Memory** (ED-3/ED-4 ArcRift). **Model allocation & project placement** unchanged.

## Enforcement / acceptance

- Ratified by the **CTO**; CEO + Founder consulted. `Proposed` until sign-off.
- The ED-1 completion contract **is** the release gate for the MUSTAQIL program: each workstream (ADR 0033–0038) closes its AADL gate against it; the program is 100% only when ED-1 holds and the PROOF project (G6) is delivered 0→100.
- Any future "is this actually finished / can it run past the Founder / did it verify this?" question resolves here.
