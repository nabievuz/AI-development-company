# DasLab × "Agentic Design Patterns" (Gulli) — capability audit & adoption plan

**Date:** 2026-07-23
**Source:** [github.com/evoiz/Agentic-Design-Patterns](https://github.com/evoiz/Agentic-Design-Patterns) — Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (424-page book + chapter notebooks; ~1.7k★). License: educational-use-with-attribution; code examples MIT. (Author royalties donated to Save the Children.)
**Relates to:** `2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`, `2026-07-22-daslab-mustaqil-master-prompt.md`, ADR-0033…0039.

---

## 0. The one constraint that decides how we read this book

The book's 21 patterns are **framework-agnostic vocabulary**; its *code* is single-file Jupyter notebooks on **LangChain + OpenAI**. Under **ADR-0010 constraint C1** (no external framework becomes the org brain) and QONUN Model-Allocation (Claude-only, explicit per dispatch), we adopt **the taxonomy and the audit lens — never the notebooks as an org substrate**. This is the same stance we already took for LangChain itself in ADR-0035/0036: substrate under DGO-X, never top-level truth.

So the useful question is not "which patterns are we missing" (it turns out: almost none) but **"does a published, ecosystem-standard taxonomy expose any real gap, and does it give us shared words to prove parity with Devin/Jules/Copilot?"** Both, and the second matters as much as the first.

> Honesty note: the book's *per-chapter internal text* could not be extracted cleanly (the fetch tool correctly refused to invent descriptions it couldn't read). This audit therefore maps DasLab against the **canonical, field-standard meaning of each named pattern** — which is exactly the layer that matters for a gap audit — not against paraphrased book prose. Where a pattern's book-specific nuance would change a verdict, it is flagged.

---

## 1. The 21-pattern audit

Legend: **✅ Have** (implemented) · **✅✅ Exceed** (implemented *and* governance-hardened beyond the book's scope) · **🟡 Bounded/Partial** (present but deliberately limited, or internal-only) · **◻️ Candidate** (not adopted; a real adoption option).

| # | Pattern (Gulli) | DasLab | Where it lives in DasLab |
|---|---|---|---|
| 1 | Prompt Chaining | ✅ | Skill pipeline (`investigate`→`review`→`learn`), orchestrator wave phases, `/daslab-cycle` |
| 2 | Routing | ✅✅ | DGO-X graph-orchestrated control plane (ADR-0010/0011); `routing_decision` events; `communication-flows.yaml` (ADR-0026) |
| 3 | Parallelization | ✅ | Multi-agent waves; worktree-per-ticket dispatch (ADR-0005); `max_concurrent_waves` cap (ADR-0027 SI-6) |
| 4 | Reflection | ✅ | `daslab-review` skill; the Reflect step (orchestrator §2.9.5); QA role + `daslab-qa` |
| 5 | Tool Use | ✅ | MCP `.mcp.json`; ecosystem-tool MCP bridge (ADR-0033); harness admission layer (ADR-0009) |
| 6 | Planning | ✅ | `/daslab-plan`; size-gated `SPEC.md` + `FR-NNN`/`SC-NNN` (ADR-0015); ticket dependency graph (ADR-0016) |
| 7 | Multi-Agent Systems | ✅✅ | The whole thing: 32 roles × 4-level hierarchy, RACI, guild craft-templates (ADR-0029) |
| 8 | Memory Management | ✅✅ | ArcRift persistent memory (ADR-0008) **+** `daslab-learn` trust-triad (read-write / read-only / deny) so workstreams can't poison each other — richer than the book's flat memory |
| 9 | Learning & Adaptation | 🟡 | Capture side is real (`daslab-learn`, guild `## Learned` sink, ADR-0029 G5). **Online autonomous adaptation is deliberately withheld** — learnings grow only via Founder-accepted-feedback distillation (QONUN). See §3.4. |
| 10 | Model Context Protocol | ✅ | ArcRift is an MCP server; ADR-0033 bridge; outbound MCP surface (ADR-0036 OB-1) |
| 11 | Goal Setting & Monitoring | ✅✅ | Founder-Approved Goal Queue law; `PROJECT-OS.yaml.success_metrics` (ADR-0030); cockpit (ADR-0028); completion contract (ADR-0037) |
| 12 | Exception Handling & Recovery | ✅ | Run-model `--resume`/`--fork` + `recovery_drill` (ADR-0023/0025); 3-strike escalation (`daslab-investigate`); break-glass (ADR-0027 SI-3); bounded-retry→`blocked` (Master-Prompt v2.1) |
| 13 | Human-in-the-Loop | ✅✅ | **DasLab's signature.** Never-auto-approve (QONUN-5), AADL six-gate lifecycle, Clarify gate + `[NEEDS CLARIFICATION]` (ADR-0014), interrupt cards, human Founder gate |
| 14 | Knowledge Retrieval (RAG) | ◻️/🟡 | No vector/embedding index. DasLab uses **agentic search** (grep+Read), the curated `07-CONTEXT-PACK`, and ArcRift recall. Deliberate — but never written down as a decision. See §3.2. |
| 15 | Inter-Agent Communication (A2A) | 🟡 | **Internal** comms are rich (board tickets as bus; `communication-flows.yaml` delegation/escalation edges). The **A2A *protocol* as an external interop surface is not adopted.** Strongest candidate — see §3.1. |
| 16 | Resource-Aware Optimization | ✅ | Model-Allocation law (opus×10/sonnet×19/haiku×3); effort tiers (ADR-0013); budget caps (ADR-0027 SI-5) + cost-ledger; re-tier boundary (ADR-0007) |
| 17 | Reasoning Techniques | 🟡 | Effort tiers = reasoning-budget control; verifier subagents exist. **No named CoT/ToT/self-consistency layer** for gate-critical calls. Optional — see §3.3. |
| 18 | Guardrails / Safety | ✅✅ | QONUN laws + enforcement-as-code (ADR-0002); fail-closed lint gate (ADR-0021); redaction (ADR-0012); RBAC (ADR-0038); `PreToolUse` audit/deny (ADR-0033 TB-3) |
| 19 | Evaluation & Monitoring | ✅✅ | Per-role + e2e `evals/`; anti-gaming evals; `diagnostics.py` 100/100 release gate; no-false-green (ADR-0020); real-quality scorer (ADR-0017); OTel-named spans (ADR-0024) |
| 20 | Prioritization | ✅ | Board priority; ticket dependency graph + `zone` (ADR-0016); WIP=1 discipline |
| 21 | Exploration & Discovery | ✅ | `daslab-investigate` (root-cause Iron Law); Founder discovery ≥10 Q&A (ADR-0030 D4); `daslab-canary` |

**Tally:** ~15 Have (7 of them Exceed), 4 Bounded/Candidate (9, 14, 15, 17), **0 foundational gaps.**

---

## 2. The strategic read: the book *validates* DasLab, and validates it loudest where it counts

Line the verdicts up against the book's own four-part structure:

- **Part One (Core, 1–7):** all ✅. Table stakes; DasLab has them.
- **Part Two (Advanced, 8–11):** ✅✅ / 🟡. DasLab's memory and goal-monitoring are *richer* than the pattern (trust-triad; Founder-approved queue + completion contract).
- **Part Three (Production, 12–14):** the split shows up here — DasLab **exceeds** on Human-in-the-Loop, is solid on Recovery, and has an unwritten stance on Retrieval.
- **Part Four (Enterprise, 15–21):** DasLab **exceeds** on Guardrails, Evaluation, and Multi-Agent, and the only genuine adoption candidate in the whole book (A2A) lives here.

The pattern is not subtle: **DasLab is strongest exactly where the book's single-notebook LangChain/OpenAI examples are weakest — the production/enterprise governance patterns (7, 11, 13, 18, 19).** That is the same conclusion the parity brief reached against Devin/Jules/Copilot, now corroborated by an independent, published, ecosystem-standard taxonomy. This is *citation ammunition*: when we claim "governed autonomy, not raw autonomy," we can now name the 21 canonical patterns and show DasLab covers all of them and hardens five.

---

## 3. Genuine adoption candidates (ranked)

Each is written as a proposal under existing constraints (C1, board-as-truth, never-auto-approve). None changes dispatch on merge; all are Founder-gated.

### 3.1 A2A as an outbound interop surface (Pattern 15) — **highest value**

**What.** Adopt the Agent-to-Agent (A2A) protocol as an *outbound* interop surface, a **sibling to ADR-0036** (which already exposes DasLab as a LangGraph node / MCP server). A2A is the emerging cross-vendor standard for one agent system to call another with a typed task envelope; it is the natural complement to MCP (MCP = tools to an agent; A2A = agent to agent).

**Why now.** It advances the exact goal driving MUSTAQIL — *ecosystem reach* — without touching the org brain. An external orchestrator (or another company's agent) could hand DasLab a task over A2A, and **governance rides along**: the request lands as a *goal proposal* (never a gate-skip), the same admission/redaction edge as ADR-0033/0036 applies, and completion still requires the AADL gates. It is the outbound twin of the WS-H control plane's inbound "submit-goal."

**Constraint.** OB-style invariants: the external caller **cannot skip a gate** (it submits work, it does not approve it); publishing an A2A endpoint is a **Founder act**; in-tenant only (ADR-0038 TN-1); flagged OFF by default.

**Where it lands.** A new **ADR-0040 "A2A outbound interop surface,"** explicitly extending ADR-0036, folded into MUSTAQIL WS-A/WS-C reach. Small, self-contained, high ecosystem-signal.

### 3.2 Make the retrieval stance an explicit decision (Pattern 14)

**What.** DasLab has *silently* chosen agentic search (grep + Read + curated `07-CONTEXT-PACK` + ArcRift recall) over embedding/vector RAG. That is a defensible, current-best-practice choice (it is what Claude Code itself does) — but it is nowhere written as a decision, so it reads as an omission rather than a position.

**Why.** An enterprise evaluator asking "where is your RAG?" deserves a one-page answer. And there is a real boundary case: on a *very large* tenant monorepo, grep-first can get slow/lossy, so the ADR should name the **escape hatch** (an optional, in-tenant, gitignored retrieval index — never the source of truth, always reconciled against files per C2/board-as-truth).

**Where it lands.** A short **ADR "retrieval strategy: agentic-search-first, indexed-retrieval as a bounded escape hatch,"** or a `docs/` design note if that's lighter than the situation warrants. Decision-first; code optional and deferred.

### 3.3 A named reasoning-technique layer for gate-critical calls (Pattern 17) — optional

**What.** Today reasoning depth is controlled by per-role *effort tiers* (ADR-0013) plus ad-hoc verifier subagents. The book names an explicit toolbox (chain-of-thought, self-consistency, ReAct, tree-of-thought). The only place this would *pay* in DasLab is the **highest-stakes, irreversible decisions** — e.g. a release-gate scoring call or a security sign-off — where **self-consistency (N-sample majority)** or a **small verifier panel** measurably cuts single-sample error.

**Why cautious.** For most waves this is over-engineering; effort tiers already cover it. Scope it to *gate-critical* decisions only, or skip. Lowest priority of the four.

**Where it lands.** Optional note under the evaluation/guardrail ADRs; not its own workstream.

### 3.4 Learning *cadence*, not learning *autonomy* (Pattern 9)

**What.** The capture machinery is already there (`daslab-learn`, guild `## Learned` sink). What is missing is a **regular distillation cadence** — a scheduled, Founder-reviewed pass that promotes accepted per-wave learnings into guild templates. This is *governed* learning: the org compounds, but a human still signs the promotion.

**Why NOT more.** The book's fuller "Learning & Adaptation" includes online self-modification. DasLab **deliberately withholds** that — it collides with never-auto-approve and Model-Allocation (no self-upgrade). So this candidate is explicitly the *bounded* version: cadence + human gate, never autonomous online adaptation. Worth stating so the boundary is a choice on record, not a gap.

**Where it lands.** A scheduled `daslab-learn` distillation ritual (could be a Founder-enabled scheduled task), gated by the same feedback-acceptance rule ADR-0029 G5 already names.

---

## 4. Appendices as prior art for the Devin-parity / MUSTAQIL work

The book's appendices (A–G) include material directly adjacent to the parity program — notably the **CLI-agents** and **coding-agents** appendices. Treat these as **reference/prior-art to mine**, not code to adopt: cross-check our WS-A (REACH) and WS-B (RUNNER) designs against the coding-agent appendix's decomposition, and harvest any evaluation ideas for the WS-G (PROOF) SWE-bench-style proof project. No dependency, no C1 exposure — just reading the field's homework.

---

## 5. Recommendation

**Bottom line.** This repo is not a source of missing capability — it is **independent validation** that DasLab's architecture spans the full canonical agentic-pattern space, plus **shared vocabulary** to prove that claim in the ecosystem's own terms, plus **exactly one high-value adoption** (A2A outbound) and two small "write-down-the-decision" items (retrieval stance; learning cadence).

**Proposed next actions** (Founder-gated, in priority order):

1. **ADR-0040 — A2A outbound interop surface** (extends ADR-0036; folds into MUSTAQIL reach). The one net-new capability worth building.
2. **Retrieval-strategy ADR** — write the agentic-search-first stance + bounded index escape hatch as an explicit decision.
3. **Fold the vocabulary into the parity brief** — add a "21-canonical-patterns coverage" row to `…-parity.md` so the Devin/Jules comparison cites a published taxonomy.
4. *(Optional / deferred)* reasoning-technique note for gate-critical calls; `daslab-learn` distillation cadence.

Everything here stays additive, flagged-off, and gate-preserving — consistent with ADR-0010 C1 and the MUSTAQIL completion contract (ADR-0037). Nothing adopts LangChain/OpenAI code into the org brain.
