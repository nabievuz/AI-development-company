# APPROVED-GOAL-QUEUE — MUSTAQIL v3.0 (org-engine program)

- **Program:** MUSTAQIL v3.0 — evolve DasLab into a self-hosted, enterprise-INTERNAL, end-to-end autonomous software *finisher* (0→100 on a scoped goal, all code/IP in-tenant).
- **Type:** Platform / org-engine program (NOT a `projects/<slug>/` project). Queue lives at repo root because the work is on DasLab itself; the one PROOF project (WS-G) will live under `projects/<name>/`.
- **Board target:** org `board/tickets/` (no `project:` field) for every capability workstream. The WS-G proof project's own tickets live on that project's board.
- **Author:** `/daslab-plan` (CEO decomposition role) · **Date:** 2026-07-23 · **Research snapshot:** 2026-07-23
- **Status:** ✅ **FOUNDER-APPROVED 2026-07-23** (`APPROVED`). **All 10 items now decomposed to `board/tickets/`** (2026-07-24): prep + WS-A + WS-B/C/D/E/G/H/A2A/F — 10 epics, 81 MUSTAQIL tickets, 10 SPECs (`docs/specs/002…010`). Execution proceeds in dependency order (A→B→C/D→E→G→H→A2A→F); genuinely infra-dependent steps (live sandbox DAS-1566, VM deploys DAS-1586/1595, HEARTBEAT flip DAS-1622) are `blocked` on external dependencies, not faked.
- **Supersedes:** ORGANISM v2 program (fully closed; board 99/99 done). Keeps all v2.1 hardening.

---

## 1 — Founder discovery answers (intake record — the gate is SATISFIED)

Full record: [`docs/research/2026-07-23-daslab-mustaqil-discovery-answers.md`](docs/research/2026-07-23-daslab-mustaqil-discovery-answers.md) (answered by the Founder, 2026-07-23). Summary of the twelve locks:

| # | Question | Answer |
|---|----------|--------|
| 1 | Proof project (G) | **WS-H dashboard slice** (dogfood — building it proves the finisher) |
| 2 | Tenant infra | **One Linux VM** (Docker E2B/OpenHands + self-host Langfuse) |
| 3 | Budget ceiling | **Conservative defaults** — anchored to the subscription monthly credit |
| 4 | Autonomy appetite | **Supervised first** — approve each gate until first proof, then HEARTBEAT shadow→live |
| 5 | Browser / egress | **Deny-all + allow-list**; no unattended browsing until WS-A governance is live |
| 6 | RBAC | **Founder-only approval + team read-only audit** |
| 7 | "Shipped" (proof) | **Merged + green CI + deployed to the tenant VM** |
| 8 | Effort & timeline | **Solo full-time → ~4–6 weeks to first proof** ⚠️ off-default |
| 9 | Model / inference | **Claude subscription** via ADR-0034 Agent SDK runner (account auth; monthly credit = SI-5 ceiling; metered overflow OFF) ⚠️ custom |
| 10 | Scope guardrail | **Internal self-host only** — reject SaaS / SOC 2 / SSO / multi-tenant billing |
| 11 | Retrieval | **Agentic-search-first** — no vector DB unless a metric + the retrieval ADR justify it |
| 12 | Interop (A2A) | **Defer until after proof** — first post-proof reach increment |

## 2 — Research snapshot (2026-07-23) — sources on-branch

Enrichment is already landed as briefs + proposed ADRs; the queue traces each item to them.

- **Direction brief:** [`docs/research/2026-07-22-daslab-devin-langchain-direction.md`](docs/research/2026-07-22-daslab-devin-langchain-direction.md) — gap analysis DasLab-vs-Devin; ~4.5/6 capabilities already built/designed.
- **Master prompt v3.0:** [`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`](docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md) — the runnable program, workstream map A–H, DoD=100, execution discipline.
- **Parity / patterns:** [`2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`](docs/research/2026-07-22-daslab-vs-autonomous-coding-agents-parity.md) · [`2026-07-23-daslab-agentic-design-patterns-audit.md`](docs/research/2026-07-23-daslab-agentic-design-patterns-audit.md) (~15/21 canonical patterns covered; exceeds on governance).
- **Stack mining:** [`2026-07-23-daslab-production-stack-and-toolkits-mining.md`](docs/research/2026-07-23-daslab-production-stack-and-toolkits-mining.md) — in-tenant runtime BOM (LiteLLM · vLLM/SGLang · Presidio · promptfoo).
- **SWOT / stress-test:** [`2026-07-22-daslab-mustaqil-swot.md`](docs/research/2026-07-22-daslab-mustaqil-swot.md) · [`2026-07-22-daslab-master-prompt-stress-test.md`](docs/research/2026-07-22-daslab-master-prompt-stress-test.md).
- **Proposed ADRs on-branch:** 0033 (tool MCP bridge) · 0034 (Agent SDK runner) · 0035 (LangGraph substrate) · 0036 (Langfuse observability) · 0037 (E2E delivery target) · 0038 (self-host hardening) · 0039 (web control plane). **ADR-0040 (A2A) not yet authored.** Plus one retrieval-strategy ADR to author.
- **External primary source (Q9):** [Anthropic Help Center — Claude Agent SDK on your plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) — account auth, headless `claude -p`, monthly-credit model. ⚠️ **[NEEDS VERIFICATION at build time]** — the credit model was announced 2026-06-15 then paused; confirm live plan terms before WS-B goes live.
- **Existing spikes on this branch (fold in, NOT done):** `tools/mcp_bridges/langchain_tool_bridge.py` + `audit_external_tool.py` (WS-A), `tools/control_plane/app.py` (WS-H), runbooks `docs/runbooks/ws-a-tool-bridge.md` + `ws-h-control-plane.md`, tests `tests/test_ws_a_tool_bridge.py` + `test_ws_h_control_plane.py`. These are prototypes ahead of formal tickets — the epics adopt/harden them, they are not a delivery (ADR-0020: an artifact counts only when it passes in CI under a merged ticket).

## 3 — Assumptions

- This is an **AI-agent program on the org-engine itself**; the established repo pattern (ORGANISM DAS-1440+) is **one epic per workstream**, with the six AADL gates applied *inside* each workstream at ticket level — a workstream may not skip its predecessor's AADL gate. Each workstream authors its ADR delta before its code.
- Every workstream ships **feature-flagged OFF, shadow-before-drive, reversible**.
- **C1/C2 binding:** OSS substrate (LangGraph, Agent SDK, MCP, Playwright, E2B/OpenHands, Langfuse, LiteLLM, vLLM/SGLang, Presidio, promptfoo, A2A) stays *under* DGO-X — the board + AADL + RACI remain canonical truth; no external framework or GUI becomes the org brain or control plane.
- All external tools enter **only** through the ADR-0033 governed MCP edge (least-privilege allow-list, PreToolUse audit, ADR-0012 redaction). No bulk toolkit installs.
- **Owner** column = the *accountable* role for the workstream epic (ADR ratification is CTO per RACI 3.1/3.6); listed role owns delivery, with the consulted roles noted.

## 4 — Explicit non-goals (reject if proposed)

- ❌ SaaS shell — SOC 2 certification, SSO, multi-tenant billing (Q10). Internal self-host only.
- ❌ Rebuilding the 32 agents as LangChain `create_agent` agents — the Agent SDK loads the existing `.claude/agents` verbatim.
- ❌ LangGraph / LangSmith / any GUI as the top-level dispatcher or source of truth — substrate only. **Self-host Langfuse, NOT hosted LangSmith.**
- ❌ A vector DB by default (Q11) — agentic-search-first; indexed retrieval only if a metric + the retrieval ADR justify it, and never as source of truth.
- ❌ Metered API billing / usage-credit overflow (Q9) — subscription monthly credit is the hard ceiling; overflow stays OFF.
- ❌ Turning HEARTBEAT autonomy ON before a ≥3-day clean shadow window + explicit Founder act (WS-F is LAST).
- ❌ Self-upgrading a model / self-retiering / self-widening scope.

## 5 — Prioritized goal queue

Sequence (from v3.0): **A → B → C ; D parallel from A ; E overlaps C ; G after B ; A2A after B/with D ; H after B+D+E ; F last (Founder-gated after ≥3-day clean shadow).**

| order | goal_slug | outcome (Definition-of-Done, evidenced) | why_now | research_basis | owner | status | ticket_refs |
|------:|-----------|------------------------------------------|---------|----------------|-------|--------|-------------|
| 0 | `mustaqil-prep-retrieval-adr` | Retrieval-strategy ADR ratified (agentic-search-first; vector-DB escape-hatch criteria; board stays canonical C2). Program bootstrap: `budgets.yaml` conservative caps, feature-flag scaffold, in-tenant precondition check (TN-1). | Unblocks every WS's tool/retrieval decisions; cheap, no external deps. | v3.0 Part 2 (retrieval discipline), Q11 answer | cto | **planned** | DAS-1541 (epic) · DAS-1542 · DAS-1543 |
| 1 | `mustaqil-ws-a-reach` | Browser + tool reach through the **governed MCP edge** (ADR-0033): Playwright-MCP/browser-use admitted via least-privilege allow-list, PreToolUse audit, ADR-0012 redaction; deny-all egress + explicit domain allow-list; folds in the on-branch bridge spike; green CI + attestation. | First *visible* Devin-ness; the tool-reach lever the Founder chose; gates D. | ADR-0033, direction brief §3, ws-a-tool-bridge runbook, Q5, SPEC-002 | backend-em | **planned** | DAS-1544 (epic) · DAS-1545…DAS-1551 |
| 2 | `mustaqil-ws-b-runner` | Headless programmatic dispatch of a ticket/wave via **Claude Agent SDK / `claude -p`** (ADR-0034), account-auth on a Claude subscription, behind the ADR-0009 admission layer; monthly credit = SI-5 hard ceiling, credit-exhaust = sanctioned pause; green CI. **[NEEDS VERIFICATION]** live plan Agent-SDK terms before go-live. | The execution engine that turns designs into a running loop; gates C, G, A2A, H. | ADR-0034, Q9 analysis, Anthropic Help Center | backend-em | **planned** | DAS-1552 (epic) · DAS-1553…1559 |
| 3 | `mustaqil-ws-d-lens` | Self-host **Langfuse** observability via OTLP export of existing OTel spans (ADR-0036, ADR-0024) — NOT LangSmith; **+ governed-tool admission** (promptfoo, AgentShield, Presidio) each through the 0033 edge; redaction on export; green CI. | Parallel from A; gives the "watch it work" pane + admits the eval/guardrail tools E needs. | ADR-0036, ADR-0024, stack-mining §2 | sre-lead | **planned** | DAS-1570 (epic) · DAS-1571…1577 |
| 4 | `mustaqil-ws-c-loop` | Durable graph loop + per-task sandbox: **LangGraph** as DGO-X P2/P3 substrate with `interrupt()`/conditional routing (ADR-0035, under C1) + **E2B/OpenHands** sandbox; `graph_state` a mirror, board canonical; checkpoint/resume; green CI. | The long-horizon self-correcting loop; overlaps E. | ADR-0035, ADR-0010, ADR-0023 | backend-em | **planned** | DAS-1561 (epic) · DAS-1562…1569 |
| 5 | `mustaqil-ws-e-tenant` | Enterprise-internal hardening (ADR-0038: RBAC Founder-only+team-read, audit, in-tenant secrets) **+ in-tenant runtime BOM**: LiteLLM gateway · vLLM/SGLang inference (deferred eject-path) · Presidio+classifier+policy guardrails · promptfoo+golden-set evals; TN-1 precondition enforced; green CI. | The tenant boundary + runtime the proof runs on; overlaps C. | ADR-0038, stack-mining §2, Q2/Q6/Q10 | sre-lead | **planned** | DAS-1579 (epic) · DAS-1580…1587 |
| 6 | `mustaqil-ws-g-proof` | **One project delivered 0→100 autonomously** (ADR-0037): the WS-H dashboard slice (e.g. CP-3b trigger-run), through all six AADL gates on self-host infra; **shipped = merged + green CI + deployed to the tenant VM**; committed evidence trail + attestation. Lives under `projects/<name>/`. | The MUSTAQIL completion contract — the whole point; proves the finisher by dogfooding. | ADR-0037, Q1/Q7, v3.0 DONE=100 | cpo | **planned** | DAS-1588 (epic) · DAS-1589…1596 |
| 7 | `mustaqil-ws-h-control` | Self-hosted **web control plane** (ADR-0039): extend the read-only cockpit (ADR-0028 `cockpit_html`) to governed control (approve gates / trigger runs) with Founder-only RBAC + audit; **offline-installable** (vendored wheels, no-network in-tenant); **NOT-a-daemon** (optional Founder-enabled process, degrade-to-static); folds in the on-branch control-plane spike; green CI. | The one governed control plane; needs B+D+E first. | ADR-0039, ws-h-control-plane runbook, Q6 | backend-em | **planned** | DAS-1597 (epic) · DAS-1598…1605 |
| 8 | `mustaqil-a2a-outbound` | **A2A outbound interop** (ADR-0040, to author): DasLab as a callable governed agent for another agent system, extending ADR-0036; an external caller submits a *goal proposal* (never a gate approval); publishing an endpoint is a Founder act; in-tenant only. | Deferred until after proof (Q12) — first post-proof reach increment. | ADR-0040 (to author), ADR-0036, v3.0 interop extension | backend-em | **planned** | DAS-1606 (epic) · DAS-1607…1614 |
| 9 | `mustaqil-ws-f-tempo` | **HEARTBEAT go-live** (ADR-0027): autonomous self-driving waves, live only after a **≥3-day clean shadow window** + explicit Founder act; all seven safety invariants (SI-1…SI-7) enforced; monthly-credit ceiling honored. | LAST — a governance act, not engineering; the biggest "feels like Devin" lever, turned on only when everything below is proven. | ADR-0027, Q4, v3.0 order | cto | **planned** | DAS-1615 (epic) · DAS-1616…1623 |

**Legend — status:** `candidate` → `founder_approved` (on APPROVED:) → `planned` (tickets created) → `active` → `done` / `blocked` / `rejected`.

## 6 — Next steps (per the Founder-Approved Goal Queue law)

1. **Founder reviews this queue.** Approve as-is, reorder, drop items, or amend scope.
2. On explicit **`APPROVED:` / `TASDIQLANDI:`**, every item flips `candidate` → `founder_approved`.
3. `/daslab-plan` (or `/daslab-run`) then decomposes **only the next `founder_approved` item** into an epic + PR-sized `board/tickets/` (org-engine, no `project:` field), authoring that workstream's ADR delta first, and updates the item to `planned` with `ticket_refs`. Order-0 prep first, then WS-A.
4. `/daslab-run` drains the queue across waves; each workstream closes its AADL gate before the next starts. **No item dispatches while this queue is unapproved.**

---

*Created by `/daslab-plan` on 2026-07-23. Discovery gate satisfied; queue awaiting explicit Founder approval. No board tickets exist for this program yet.*
