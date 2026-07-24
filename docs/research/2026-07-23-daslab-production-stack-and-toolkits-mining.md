# DasLab upgrade mining — four evoiz repos (production-ai-stack, ECC, awesome-claude-code-toolkit, ai-engineering-hub)

**Date:** 2026-07-23
**Sources:**
- [evoiz/production-ai-stack](https://github.com/evoiz/production-ai-stack) — fork of `h9-tec/production-ai-stack`. A single-README, opinionated **production LLM-systems reference** (layered BOM + 7 principles + 3 reference architectures). MIT.
- [evoiz/ECC](https://github.com/evoiz/ECC) — actually maintained by `affaan-m`. An **agent-harness mega-config**: 67 agents / 271 skills / hooks / rules / MCP configs + AgentShield security scanner; cross-harness (Claude Code, Cursor, Codex, OpenCode…). MIT.
- [evoiz/awesome-claude-code-toolkit](https://github.com/evoiz/awesome-claude-code-toolkit) — fork of `rohitg00/...`. An **awesome-list index** of the Claude Code ecosystem (135 agents, 176+ plugins, hooks, MCP configs, GUIs). Apache-2.0.
- [evoiz/ai-engineering-hub](https://github.com/evoiz/ai-engineering-hub) — fork of `patchy631/...`. An **education library**: 93+ RAG/agent/MCP/fine-tuning tutorial projects. MIT.

**Relates to:** `2026-07-22-daslab-mustaqil-master-prompt.md` (WS-A…H), `2026-07-23-daslab-agentic-design-patterns-audit.md`, ADR-0033/0036/0037/0038; the earlier "Claude-the-model is proprietary → in-tenant options" thread.

---

## 0. How to read four repos none of which is a framework

Three are **curation/education** (a BOM guide, an awesome-index, a tutorial library) and one (**ECC**) is a **less-governed parallel system** to DasLab. So "what can we take" is deliberately *not* "adopt a framework" — under **ADR-0010 C1** nothing here becomes the org brain, and under QONUN (Model-Allocation, Founder-Approved Goal Queue) + board-as-truth + never-auto-approve, most of the *bulk* on offer (67 ungoverned agents, 271 ungoverned skills, install-everything one-liners, ungoverned GUI control planes) would actively **violate** DasLab law if adopted. DasLab already has the *governed* version of almost all of it.

The job is therefore **mining**: pull specific ideas, a concrete runtime BOM, and a few individually-governable tools — and be equally explicit about what to leave. The single highest-value repo is **production-ai-stack**, because it is a battle-tested bill-of-materials for exactly the in-tenant self-host runtime the current program (MUSTAQIL WS-E TENANT, ADR-0038) is about to need — and it independently validates DasLab's principles.

> Provenance honesty: evoiz is the **curator/forker** for three of these, not the original author; ECC is a third party's (affaan-m). Nothing below depends on authorship — only on the ideas.

---

## 1. Per-repo verdict

| Repo | What it really is | Value to DasLab | Take / Leave |
|---|---|---|---|
| **production-ai-stack** | Opinionated production LLM-runtime BOM + principles + reference archs | **High — direct** | **TAKE** as the reference BOM for WS-E self-host runtime (§2). Also validates DasLab principles (§4). |
| **ECC** | A less-governed agent-harness mega-config (competes with DasLab's category) | **Low-medium** | Mostly **LEAVE** (bulk agents/skills/cross-harness = ungoverned, violates QONUN/AADL). **TAKE** one idea: AgentShield as a *governed security-scanner tool* (§3.1). |
| **awesome-claude-code-toolkit** | An index/catalog of the CC ecosystem | **Medium — as a sourcing list** | **TAKE** 2–3 specific tools to evaluate through the ADR-0033 governance edge (§3.2/3.4). **LEAVE** the catalog itself + GUI control planes. |
| **ai-engineering-hub** | 93+ tutorial projects | **Medium — reference only** | **TAKE** specific projects as prior-art for named workstreams (§3.3). **LEAVE** as code. |

---

## 2. The one that matters: production-ai-stack → the WS-E TENANT runtime BOM

ADR-0038 (enterprise-internal self-host) names *what* must be true (in-tenant, Linux-first, RBAC, audit, egress policy) but not the concrete runtime *bill of materials*. This repo supplies exactly that, layer by layer, and most of it lines up with decisions DasLab has already made — which is the point.

| Stack layer (production-ai-stack default) | DasLab today | Verdict |
|---|---|---|
| **Inference — vLLM / SGLang** (open-weight) or OpenAI-compatible providers | Anthropic API (Claude, proprietary) | **NEW / answers an open question** — this is the concrete "how" for the in-tenant-inference mitigation path we flagged when confirming Claude-the-model is the one proprietary dependency. See §2.1. |
| **Gateway — LiteLLM** (pinned), model routing | ADR-0009 harness admission layer + Model-Allocation law | **Adopt-candidate** — LiteLLM is a natural in-tenant realization of the admission gateway that also routes Anthropic-API ↔ Bedrock/Vertex ↔ on-prem without changing agents. |
| **Observability — Langfuse (self-host default)**; LangSmith = managed alt | WS-D LENS chose **self-host Langfuse**; ADR-0036 names LangSmith as an OTLP export target | **Validates** — independent BOM lands on the exact same default. |
| **Evals — promptfoo + hand-labeled golden set** (before LLM-judge) | `evals/` per-role + e2e baselines; diagnostics 100/100; no-false-green (ADR-0020) | **Validates + a tool** — promptfoo is a concrete CI harness worth evaluating for `evals/`; "golden set before LLM-judge" is already DasLab discipline. |
| **Guardrails — layered: Presidio + classifier + policy** | ADR-0012 redaction + guardrail_dispatch + QONUN enforcement-as-code | **Adopt-candidate** — Presidio (PII detection) is a concrete in-tenant component for the TN-5 redaction/egress layer. |
| **Durable execution — Temporal** | Run-model + event store + attestation (ADR-0023/0025/0031/0032) already give replay/resume | **Already have (own version)** — Temporal stays *optional*, as previously noted; DasLab's durability is native. |
| **Agentic backend ref-arch — MCP tools + E2B sandbox + gated approval for writes** | ADR-0033 MCP bridge + sandbox + **never-auto-approve** | **Validates precisely** — their headline reference architecture *is* DasLab's pattern. |
| **Cost — prefix/KV caching + model routing** (largest savings) | Static cache-prefix (ADR-0006) + Model-Allocation + budgets (ADR-0027 SI-5) + cost-ledger | **Validates** — their `$52K→<$5K` anecdote is our thesis with a number on it. |

### 2.1 It concretely answers the "Claude is proprietary" question

Earlier we established the one non-OSS dependency is the Claude model, with three in-tenant mitigations (direct Anthropic API / Bedrock-Vertex in-tenant-cloud / full open-weight on-prem). production-ai-stack is the **operational recipe** for paths 2–3: a **LiteLLM gateway** in front of the model so agents are provider-agnostic, with **vLLM/SGLang** serving open-weight models entirely in-tenant when a tenant's policy forbids any external model call. This doesn't change DasLab's default (Claude via API for quality) — it makes the *fallback* a wiring decision, not a rewrite, and gives ADR-0038 a real answer to "what if nothing may leave the tenant, including the model call?"

**Where it lands:** a **research appendix / runbook feeding ADR-0038 WS-E** — "in-tenant runtime BOM" (inference, gateway, guardrails, evals) — not a new law. Everything stays additive and Founder-gated.

---

## 3. Individually-governable items worth pulling

### 3.1 AgentShield (from ECC) — a governed security-scanner tool
ECC ships **AgentShield** (1,282 tests / 102 rules) that scans an agent harness for unsafe configs, injection surfaces, and secret leakage. DasLab has `daslab-security-audit` + a security-lead, but a dedicated *harness-security scanner* is a real addition. **Take it the DasLab way:** evaluate it as an out-of-process tool behind the ADR-0033 governance edge (least-privilege, `PreToolUse` audit), owned by the security-lead — never as a bulk import of ECC. Verify its rules against ADR-0012/0038 before trusting it.

### 3.2 claude-context / semantic search (from the awesome-list) — only if the retrieval ADR says so
The catalog features **claude-context** (semantic code search via Milvus, ~40% token reduction). This is the concrete candidate for the **indexed-retrieval escape hatch** proposed in the agentic-patterns brief (§3.2). **But note the tension:** production-ai-stack explicitly cautions *against* a dedicated vector DB as an opening move ("prove retrieval metrics warrant migration first"). So this stays gated behind the **retrieval-strategy ADR** — agentic-search-first, index only when a large-monorepo metric justifies it. Document both, decide with data.

### 3.3 ai-engineering-hub — prior art pointers for named workstreams
Not code to adopt — reference projects to point specific leads at:
- **`agent2agent-demo`** → concrete A2A prior art for the proposed **ADR-0040 A2A outbound surface**.
- **`eval-and-observability`, `trustworthy-rag`, `corrective-rag`, `context-engineering-workflow`** → technique reference for WS-D LENS and the retrieval decision.
- **`Multi-Agent-deep-researcher-mcp`, `web-browsing-agent`** → reference for WS-A REACH (browser/tool reach, ADR-0033).

### 3.4 Bouncer's "second-model audit gate" idea (from the awesome-list)
**Bouncer** uses a *second model* to audit an agent's output before it passes. That's the adversarial-verification / no-false-green idea as a gate primitive. Worth considering as an **optional hardening of the release gate** (a cross-model verifier on high-stakes gate decisions) — overlaps the reasoning-techniques candidate (agentic-patterns brief §3.3). Optional, gate-critical only.

---

## 4. Validation wins (worth citing internally)

production-ai-stack's **7 principles** read like an external restatement of DasLab law:

- *"Every layer needs an eject path"* ⇄ portability / no-lock-in (ADR-0038 TN-2).
- *"Systems must be fully replayable"* ⇄ event store + run-model + hash-chained attestation (ADR-0023/0025/0032).
- *"Evaluations precede dashboards"* ⇄ evals-first, diagnostics gate, no-false-green (ADR-0017/0020).
- *"Agent autonomy requires observable, bounded, rollback-capable systems"* ⇄ HEARTBEAT invariants + never-auto-approve (ADR-0027, QONUN-5).
- *"Models are ~20% of the system; orchestration/retrieval matter more"* ⇄ DGO-X + board-as-truth (ADR-0010).

An independent, production-grounded guide reaching DasLab's conclusions is citation ammunition for the same "governed, not raw, autonomy" case the parity brief makes.

---

## 5. What to explicitly NOT take (governance reasons)

- **ECC's 67 agents / 271 skills in bulk, cross-harness parity, ungoverned memory/continuous-learning** — DasLab already has governed equivalents (32-role org, ArcRift, `daslab-learn` with the trust-triad). Bulk import breaks Model-Allocation (Claude-only, explicit per dispatch), AADL gates, and board-as-truth. Cross-harness (Cursor/Codex/…) is *deliberately* out of scope.
- **GUI session managers (opcode, ccmanager, vibe-kanban)** — ungoverned control planes that bypass RBAC/audit; DasLab is building the *governed* WS-H control plane instead (ADR-0039). These validate the direction; do not adopt them.
- **The "install everything" one-liner / whole awesome-list** — antithesis of least-privilege (ADR-0033 TB-2). Mine individual items through the edge; never bulk-install.
- **Fine-tuning / vector-DB-first / multi-agent-swarm** — production-ai-stack itself says skip these until data warrants; so does DasLab discipline.

---

## 6. Recommendation & next actions

**Bottom line.** No new brain, no framework. The real upgrade is **one concrete BOM** (production-ai-stack → the in-tenant self-host runtime for WS-E, including the operational answer to the proprietary-model question) plus **a small shortlist of individually-governable tools** (AgentShield; promptfoo; Presidio; claude-context *iff* the retrieval ADR opens that door) and **prior-art pointers** for A2A / evals / reach. Everything else is validation or a deliberate leave.

Proposed next actions (Founder-gated, priority order):

1. **WS-E runtime BOM appendix** feeding ADR-0038 — inference (vLLM/SGLang) + gateway (LiteLLM) + guardrails (Presidio+classifier+policy) + evals (promptfoo+golden set), with the in-tenant-inference recipe as the explicit answer to the proprietary-model constraint.
2. **Fold AgentShield + promptfoo + Presidio** into the WS-D/WS-E tool shortlist, each to be admitted through the ADR-0033 governance edge (security-lead owns AgentShield).
3. **Point WS-A / WS-D / ADR-0040 leads** at the named ai-engineering-hub projects as prior art (A2A demo especially).
4. *(Gated)* the retrieval-strategy ADR decides whether claude-context's indexed search is ever built; production-ai-stack's "no vector-DB-first" caution is part of that record.

All additive, flagged-off, gate-preserving, in-tenant — consistent with ADR-0010 C1, ADR-0038, and the ADR-0037 completion contract. Nothing adopts an external harness or framework as the DasLab brain.
