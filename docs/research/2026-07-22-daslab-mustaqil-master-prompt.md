# MUSTAQIL — Master Prompt: DasLab as a self-hosted, enterprise-internal, end-to-end autonomous finisher

- **Type:** Program plan + Master Prompt (v1 → analysis → upgraded v2). Companion to `2026-07-22-daslab-devin-langchain-direction.md` and `2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`.
- **Date:** 2026-07-22
- **Status:** Draft for Founder review — the v2 prompt is the one to run through `/daslab-plan`
- **Codename:** **MUSTAQIL** ("independent / autonomous") — the org-engine program that switches on the end-to-end finisher DasLab already designed, for **enterprise-internal self-hosted** use.
- **Chosen path (Founder):** enterprise-**internal** use — a company runs DasLab on its own infra to build its own software; self-host + RBAC + audit; OSS stack, no vendor lock-in, code/IP stays in-tenant. (NOT enterprise-SaaS packaging — that is a separate, later, funded program.)

---

## Part 1 — The program (concrete plan)

### 1.1 Goal (one sentence)

Evolve DasLab into a **self-hosted, enterprise-internal, end-to-end autonomous software finisher**: a governed AI org a company runs entirely on its own infrastructure to take a scoped, well-specified software goal from **0 → 100** (planned → built → tested → shipped → verified) with minimal human input, keeping all code and IP in-tenant. It **installs on an Ubuntu server (Linux-first) or macOS** and is operated from a **browser via a self-hosted web dashboard (WS-H / ADR-0039)** as well as the CLI.

### 1.2 The workstreams

Named in DasLab's WS idiom (PULSE/LOOM/BRIDGE…). Each is shippable, feature-flagged OFF, and reversible.

| WS | Name | Goal | OSS (under C1) | ADR | Done-when (DoD) |
|---|---|---|---|---|---|
| **A** | **REACH** | Browser + tool reach through the governed MCP edge | Playwright-MCP, browser-use | 0033 | Browser tool in `.mcp.json`; per-role allow-list + `PreToolUse` audit + ADR-0012 redaction; a role opens a live page and verifies rendered behaviour |
| **B** | **RUNNER** | Headless programmatic dispatch of a ticket/wave | Claude Agent SDK | 0034 | `daslab_sdk` dispatches with explicit model, loads `.claude/agents` via `setting_sources`; identical board/event outcome to an interactive wave |
| **C** | **LOOP** | Durable graph loop + per-task sandbox | LangGraph, E2B / OpenHands | 0035 | `graph_state`→LangGraph state, gates→`interrupt()`, node→SDK dispatch; per-ticket sandbox; checkpoint/resume; green in shadow |
| **D** | **LENS** | Self-host observability (no external SaaS) | **Langfuse** (OTel) | 0036 | ADR-0024 spans export via OTLP to in-tenant Langfuse; redacted; nothing leaves the tenant |
| **E** | **TENANT** | Enterprise-internal hardening | self-host stack | **0038 (new)** | single-user/macOS assumptions removed; RBAC + audit export; secrets/VPC policy; whole stack runs in-tenant |
| **F** | **TEMPO** | Autonomous tempo (self-driving waves) | DasLab HEARTBEAT | 0027 | ≥3-day clean shadow window; SI-1…SI-7 safety drills green; Founder flag-flip |
| **G** | **PROOF** | One project delivered 0→100 autonomously | SWE-bench + one real project | **0037 (new)** | one scoped project through all six AADL gates 0→100, on self-host infra, with a committed evidence trail |
| **H** | **CONTROL** | Self-hosted **web control dashboard** — submit goals, approve gates, trigger + watch runs from a browser | FastAPI/Flask + `cockpit_html` (ADR-0028) | **0039 (new)** | networked but RBAC-gated dashboard on the tenant server; read (board/status/spans) + governed write (goal/run/approve — audited, never-auto-approve, Founder-only gate approval); degrade-to-static; flagged OFF |

### 1.3 Sequence, dependencies, timeline

Order (dependencies, not just letters): **A → B → C**, with **D (LENS)** running in parallel from A, **E (TENANT)** overlapping C, **G (PROOF)** starting once B lands, **H (CONTROL)** once B + D + E are in (it needs the runner, live observability, and RBAC), and **F (TEMPO)** strictly **last** and Founder-gated (per ADR-0027 C5: no autonomous scheduler before the substrate is reliable).

Rough estimate (solo builder; ~2–3× faster with help):

- A + D: ~1 week · B: ~1–2 weeks · C: ~3–5 weeks · G (first proof): ~1–2 weeks · E: ~4–8 weeks · F: gated (code exists).
- **Capability core (A–D):** ~6–9 weeks. **First end-to-end autonomous proof (through G):** ~2–3 months solo / ~4–6 weeks full-time. **Enterprise-internal-ready (through E) + TEMPO live:** ~3–4 months.

### 1.4 Definition of "finished" (0 → 100) — the anti-false-green anchor

The program is 100% **only** when all hold, each **evidenced** (no exceptions, no vibes):

1. Every WS meets its written DoD (table above).
2. Every code-touching ticket: **merged PR + green CI**; every wave: **committed hash-chained attestation** (ADR-0031/0032); **no false-green** (ADR-0020).
3. `scripts/diagnostics.py` = **100/100** on a clean tree; golden evals pass **with the anti-gaming probe**; `board_lint`, `check_links`, and all validators green.
4. **PROOF (G):** one scoped project delivered **0→100** through the six AADL gates on self-host infra, with a committed evidence trail.
5. **Self-host:** sandbox, observability, and tools all run **in-tenant**; no external SaaS dependency; no code/IP leaves the tenant.

### 1.5 OSS substrate (self-host, permissive, no lock-in)

LangGraph (MIT) · Claude Agent SDK (MIT) · langchain-mcp-adapters + MCP Python SDK/FastMCP (MIT/Apache) · Playwright-MCP (Apache-2.0) / browser-use (MIT) · E2B (Apache-2.0) / OpenHands (MIT) · **Langfuse (MIT — not LangSmith)** · Temporal (MIT, optional) · SWE-bench (MIT). All Apache-2.0-compatible; all self-hostable.

### 1.6 Guardrails (binding)

ADR-0010 **C1–C6** apply verbatim: the OSS above are **substrate under DGO-X**, never the org brain; the board + AADL + RACI stay canonical. All QONUN laws hold (Project Placement, AADL, Model Allocation, Persistent Memory, Founder-Approved Goal Queue). Every new capability ships **feature-flagged OFF**, shadow-before-drive.

---

## Part 2 — Master Prompt v1 (first draft)

```text
GOAL: Turn DasLab into an end-to-end autonomous software finisher that a company
can run on its own infrastructure to build its own software from 0 to 100 with
minimal human input, keeping code and IP private.

Build the browser/tool reach, a headless runner, a durable execution loop with a
sandbox, self-hosted observability, enterprise-internal hardening (RBAC, audit),
autonomous tempo, and prove it by finishing one real project end to end.

Use open-source only: LangGraph, Claude Agent SDK, Playwright-MCP, E2B/OpenHands,
Langfuse, Temporal, SWE-bench.

Finish everything 0→100 without stopping and without hallucinating. Do not leave
anything half-done. Report when complete.
```

---

## Part 3 — Analysis of v1 (why it is not safe to run as-is)

v1 reads well but would misfire inside DasLab. Concrete defects:

1. **"Without stopping" contradicts the never-auto-approve law (QONUN-5).** DasLab *must* halt at Founder/AADL approval gates. v1 either pushes the org to run past gates (a law violation) or is internally contradictory. → v2 defines the **only** legitimate stops and makes clear a Founder gate is not a failure.
2. **"Without hallucinating" is asserted, not enforced.** Saying it changes nothing. → v2 **binds** the claim to DasLab's real mechanisms: evidence-backed gates, attestation, ArcRift recall/store, and `[NEEDS CLARIFICATION]` instead of invention.
3. **Definition-of-done is vague** ("finish everything", "don't leave half-done"). Unmeasurable → the org can't know when it's done and may gold-plate or false-green. → v2 uses the §1.4 concrete criteria + per-WS DoD.
4. **Scope is unbounded** — "enterprise" could drift into SOC 2 / SSO / multi-tenant SaaS (months of the wrong work). → v2 fixes the boundary: enterprise = **internal self-host**, not a SaaS shell.
5. **OSS adoption is unconstrained by C1** — v1 could let LangGraph/OpenHands become the top-level brain, breaking DasLab's moat. → v2 states **consume, don't rebuild; substrate under DGO-X; board stays canonical.**
6. **No intake path.** A platform program cannot just "start"; it must pass the Founder-Approved Goal Queue and `/daslab-plan`. → v2 routes it explicitly.
7. **No sequencing / dependencies** — parallel work on shared zones causes conflicts; TEMPO could go live before the substrate is safe (violates ADR-0027 C5). → v2 fixes order + predecessor gates + TEMPO-last.
8. **Ignores the reliability cliff.** A months-long program suffers context dilution and goal drift. → v2 mandates per-wave ArcRift re-anchoring, checkpoints, and decomposition into approved sub-goals.
9. **"Report when complete" invites a single silent long run.** → v2 requires per-wave evidence and no silent blockers (open a `blocked` ticket + escalate).

---

## Part 4 — Master Prompt v2 (upgraded — run THIS)

```text
PROGRAM: MUSTAQIL — evolve DasLab into a self-hosted, enterprise-INTERNAL,
end-to-end autonomous software finisher.

GOAL (single, binding): a governed AI org a company runs entirely on its own
infrastructure to take a scoped, well-specified software goal from 0 to 100
(planned → built → tested → shipped → verified) with minimal human input, keeping
all code and IP in-tenant. Deliver this as an org-engine program plus ONE proof
project. "Enterprise" here means INTERNAL self-hosted use (RBAC, audit, in-tenant)
— NOT a sellable SaaS shell (no SOC 2 cert / SSO / multi-tenant billing in scope).

DONE = 100 (all must hold, each EVIDENCED — no vibes):
- All eight workstreams reach their written Definition-of-Done.
- Every code ticket: merged PR + green CI. Every wave: committed hash-chained
  attestation (ADR-0031/0032). No false-green (ADR-0020).
- scripts/diagnostics.py = 100/100 clean; golden evals pass with the anti-gaming
  probe; board_lint / check_links / all validators green.
- PROOF: one scoped project delivered 0→100 through the six AADL gates on
  self-host infra, with a committed evidence trail.
- Self-host: sandbox + observability + tools run in-tenant; nothing leaves it.

WORKSTREAMS & ORDER (each feature-flagged OFF, shadow-before-drive):
  A REACH (ADR-0033: Playwright-MCP browser + catalog, governed MCP edge)
  B RUNNER (ADR-0034: Claude Agent SDK headless runner)
  C LOOP (ADR-0035: LangGraph + E2B/OpenHands sandbox under DGO-X)
  D LENS (ADR-0036: self-host Langfuse via OTLP — NOT LangSmith)  [parallel from A]
  E TENANT (ADR-0038: remove single-user/macOS assumptions; RBAC + audit; in-tenant)
  F TEMPO (ADR-0027: HEARTBEAT go-live) — LAST, Founder-gated, after ≥3-day clean shadow
  G PROOF (ADR-0037: one project 0→100)  [starts once B lands]
  H CONTROL (ADR-0039: self-hosted web control dashboard) [after B+D+E]
  Order: A → B → C ; D parallel ; E overlaps C ; G after B ; H after B+D+E ; F last.
  A workstream may not skip its predecessor's AADL gate.

OSS SUBSTRATE — adopt UNDER ADR-0010 C1 (patterns in their lane, NEVER the org
brain; board + AADL + RACI stay canonical; CONSUME, do not rebuild):
  LangGraph · Claude Agent SDK · langchain-mcp-adapters/FastMCP · Playwright-MCP /
  browser-use · E2B / OpenHands · Langfuse (self-host) · Temporal (optional) ·
  SWE-bench. All permissive (Apache-2.0-compatible), all self-hostable.

EXECUTION DISCIPLINE — "0→100, no UNPLANNED stops, no hallucination":
- The ONLY legitimate pauses are the sanctioned Founder / AADL approval gates
  (never-auto-approve, QONUN-5): present evidence, WAIT, and resume immediately on
  APPROVED:/TASDIQLANDI:. A Founder gate is NOT a failure-stop.
- No silent blockers: if blocked, open a `blocked` ticket with the exact reason and
  escalate to the manager (ROUTING.md). Never abandon, never loop, never guess past it.
- Evidence over vibes: every "done" is backed by a REAL artifact (merged PR, green
  CI, committed span/attestation, passing eval). If you cannot evidence it, it is
  NOT done — do not claim it (ADR-0020 no-false-green; ADR-0032 forced attestation).
- No fabrication: recall via ArcRift at task start, store the decision at end; cite
  real files/commits. If a fact is unknown, mark [NEEDS CLARIFICATION] (ADR-0014) and
  escalate — NEVER invent an API, a result, or a passing test.
- Beat the reliability cliff: re-anchor the top-level GOAL from ArcRift at the start
  of every wave; checkpoint each wave (ADR-0023); keep tickets small (one issue = one
  branch = one PR = one worktree); no two tickets touch the same repo zone in a wave.
- Respect all QONUN laws (Project Placement, AADL, Model Allocation, Persistent
  Memory, Founder-Approved Goal Queue). Capability = org-engine tickets in
  board/tickets/; the PROOF project lives under projects/<name>/.

INTAKE: run through /daslab-plan → Founder Discovery Gate (≥10 questions) → current
research → projects/… or program APPROVED-GOAL-QUEUE.md → explicit Founder approval →
/daslab-run drains it across waves. Author one ADR delta per workstream before its code.
```

---

## Part 5 — How to run it in DasLab

1. Hand **Part 4 (v2)** to `/daslab-plan` as the program goal. It triggers the **Founder Discovery Gate** (≥10 questions) — answer them, or waive explicitly.
2. `/daslab-plan` enriches with research and writes the **`APPROVED-GOAL-QUEUE.md`**; nothing dispatches until you sign `APPROVED:` / `TASDIQLANDI:`.
3. `/daslab-run` drains the queue across waves; each workstream authors its ADR (0033–0038), ships behind a feature flag, and closes its AADL gate before the next starts.
4. **TEMPO (F)** stays OFF until you flip the HEARTBEAT flag after a ≥3-day clean shadow window — that is the moment DasLab starts *self-driving* to done.
5. The whole program is **org-engine** work (board/tickets/), except **PROOF (G)**, which is a real project under `projects/<name>/` delivered 0→100 as the living proof that the finisher works.

> Honest note: no LLM-driven system can be *guaranteed* never to hallucinate or stall. What v2 does is bind "0→100, no unplanned stops, no fabrication" to DasLab's **enforcement** — attestation, no-false-green, evidence-gated T-gates, `[NEEDS CLARIFICATION]`, and escalation — so a lapse **breaks a committed chain and fails CI** rather than passing silently. That is the strongest form of the promise that is actually true.
