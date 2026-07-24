# DasLab vs. the autonomous agent platforms — capability parity analysis & path

- **Type:** Competitive / research brief (companion to `2026-07-22-daslab-devin-langchain-direction.md`)
- **Date:** 2026-07-22
- **Status:** Draft for Founder review
- **Goal (Founder):** Bring DasLab to the level of the autonomous agent platforms — Jules, GitHub Copilot coding agent, Augment Code, Factory.ai, Devin (software-engineering agents), plus Perplexity Computer and Manus (general autonomous agents).
- **Scope:** Platform strategy — capability matrix, honest gap analysis, and a parity path that reuses the "Governed Devin" program (phases A–E, ADRs 0033–0036).

---

## 0 — The one thing to get right first

**DasLab is not the same *kind* of product as these five.** Four of them (Jules, Copilot, Devin, and to a degree Augment) are **single-agent or small-fleet coding *engineers*** that take a scoped task on an existing repo and return a PR, sold as funded SaaS with an enterprise shell. Factory is the closest cousin — a **Droid fleet** — but still without a gated lifecycle. DasLab is a **governed, multi-role software *organization*** that plans, builds, ships, and operates whole products through a six-gate lifecycle. Perplexity Computer and Manus sit even further out — *general* autonomous agents with a browser and a cloud "computer," not software engineers at all (see §3b).

So "bring DasLab to their level" is really **two different targets**, and conflating them is the trap:

- **Capability parity** — make DasLab *operate* as autonomously as they do (async cloud execution, a browser, a ticket→PR front door, live observability). **Buildable** by a small effort; it reuses the Governed-Devin program almost entirely.
- **Market parity** — match them as *businesses* (SOC 2 + SSO + VPC packaging, a public benchmark number, distribution, community). That is **a funded company, not a coding task** — Cognition alone is valued around $10B, and Google/Microsoft stand behind Jules/Copilot.

The matrix below shows DasLab already **beats all five** on the axes that are hardest to copy (multi-role org, gated lifecycle, governance depth, unbounded parallelism) and **trails** them on a small, specific, mostly-cheap set of executional gaps. The winning move is not to become a sixth Devin — it is to graft their autonomous *feel* onto DasLab's governance moat and own the empty square on the board: **the governed autonomous software org.**

## 1 — The field, in one line each (mid-2026, verified)

**Software-engineering agents:**

- **Jules (Google)** — fire-and-forget async agent; clones your GitHub repo into an isolated Google Cloud VM, plans, edits, tests, opens a PR. Gemini 3.1 Pro; up to 60 concurrent tasks (Ultra). GitHub-only; MCP client with a curated allow-list; consumer-bundled ($19.99–$199.99/mo). No published SWE-bench; documented prompt-injection/exfiltration findings.
- **GitHub Copilot coding agent ("cloud agent")** — assign a GitHub issue, it works in an ephemeral **GitHub Actions** environment and opens a PR; choice of **Claude or Codex** models; Mission Control fleet orchestration; MCP support; governance reuses GitHub's policy/audit/branch-protection. Token-metered "AI Credits" since June 2026. Framed for low-to-medium-complexity tasks.
- **Augment Code** — enterprise platform built on a proprietary **Context Engine** (structural/semantic index over 400K+-file monorepos), relaunched June 2026 as **Cosmos**, an orchestrator of specialist "Experts." Multi-model (Prism router); exposes its Context Engine **as an MCP server**; SOC 2 Type II + ISO 42001 + VPC/self-host. ~51.8% SWE-bench Pro.
- **Factory.ai** — "agent-native" **Droid** fleet (Code / Knowledge / Reliability / Product / Review); terminal-first (`droid`), model-agnostic, persistent "Droid Computers." Jira/Linear/PagerDuty first-class. Claims #1 Terminal-Bench (58.75%). SOC 2 **Type I** (note: lower bar), VPC/on-prem/air-gapped.
- **Devin (Cognition)** — "the AI software engineer"; own cloud workspace with **shell + editor + browser**, DeepWiki repo indexing, Knowledge + Playbooks; up to 10 parallel sessions + "Managed Devins" (coordinator → worktree-isolated children). Absorbed Windsurf → Devin Desktop IDE. SOC 2 Type II, VPC. SWE-bench numbers contested; absent from mid-2026 public leaderboards.

**General autonomous agents (browser/computer — a different category, included per the Founder's list):**

- **Perplexity Computer** — a cloud multi-agent system (Firecracker microVMs) that drives the **Comet** browser and ~400+ connectors to complete general web tasks asynchronously; ~19-model orchestration with no own frontier model; SOC 2 Type II. A general web/task agent, **not** a real software engineer (reviewers report black-box builds and cost overruns); documented Comet prompt-injection/exfiltration flaws.
- **Manus** — an autonomous general agent that operates its own cloud VM (*"Manus's Computer"*: browser + terminal + filesystem) via a planner + dynamic sub-agents; builds/deploys simple apps, sites, and docs, with a "Wide Research" 100+ sub-agent fan-out. Generalist, not IDE-grade; reliability falls off past ~20 steps, "session amnesia," contested certs; its ~$2–3B Meta acquisition was blocked by Chinese regulators (Apr 2026).

## 2 — Capability matrix

Legend: ⭐ leads the field · ✅ strong · 🟡 partial · ❌ absent. "DasLab→" = DasLab at the end of the Governed-Devin program.

| # | Capability | Jules | Copilot | Augment | Factory | Devin | **DasLab now** | **DasLab→** |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | Async cloud execution (isolated env per task) | ✅ | ✅ | ✅ | ✅ | ⭐ | ❌ | ✅ |
| 2 | Ticket/issue → PR front door (GitHub/Jira/Linear) | ✅ | ⭐ | ✅ | ⭐ | ✅ | 🟡 | ✅ |
| 3 | Parallel task fan-out (fleet) | ✅ | ✅ | ✅ | ✅ | 🟡 | ⭐ | ⭐ |
| 4 | Multi-agent role specialization | 🟡 | ❌ | ✅ | ✅ | 🟡 | ⭐ | ⭐ |
| 5 | Whole-lifecycle **gated** delivery (plan→…→maintain) | ❌ | ❌ | 🟡 | 🟡 | ❌ | ⭐ | ⭐ |
| 6 | Repo-wide indexing of **existing** large codebases | 🟡 | 🟡 | ⭐ | ✅ | ✅ | ❌ | 🟡 |
| 7 | Browser / computer use | 🟡 | ❌ | 🟡 | 🟡 | ⭐ | ❌ | ✅ |
| 8 | Persistent memory / learned conventions | 🟡 | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | Model-agnostic (multi-model) | ❌ | ✅ | ✅ | ✅ | 🟡 | ❌* | 🟡 |
| 10 | Integration breadth (Slack/IDE/CI/trackers) | 🟡 | ⭐ | ✅ | ✅ | ✅ | ❌ | 🟡 |
| 11 | MCP interop (consume **and** expose) | 🟡 | ✅ | ⭐ | ✅ | ✅ | 🟡 | ✅ |
| 12 | Governance depth (gates, RACI, audit, attestation) | ❌ | 🟡 | 🟡 | 🟡 | 🟡 | ⭐ | ⭐ |
| 13 | Enterprise shell (SOC 2, SSO, VPC, multi-user) | 🟡 | ⭐ | ⭐ | ✅ | ✅ | ❌ | ❌† |
| 14 | External proof (public benchmark / adoption) | 🟡 | 🟡 | ✅ | ✅ | 🟡 | ❌ | 🟡 |

\* Claude-only **by design** (Model-Allocation Law: opus/sonnet/haiku). A deliberate identity choice, not an oversight.
† Enterprise packaging is the **strategic fork** of §5 — a company-building decision, not on the default engineering path.

> The two **general** autonomous agents (Perplexity Computer, Manus) are compared separately in §3b — they are browser/computer agents, not software-engineering agents, so most SWE rows above don't apply to them.

## 3 — Where DasLab already wins, ties, and trails

**Leads (⭐) — and no competitor is close:**
- **Multi-role org + gated lifecycle (rows 4, 5).** A 32-role, four-level company running an AADL six-gate lifecycle (Planning→…→Maintenance) with RACI and board approvals. Factory's Droids and Augment's Experts are *specialist fleets*, but none enforces a gated lifecycle where **a deployment is machine-blocked while GATE-5 is open**. This is genuinely unique.
- **Governance depth (row 12).** Append-only event store, hash-chained wave attestations (ADR-0031/0032), never-auto-approve (QONUN-5), a 100/100 release gate. The five treat governance as admin settings (permissions, audit log); DasLab treats it as the substrate.
- **Unbounded parallelism (row 3).** Worktree-per-ticket with no parallel cap already matches or exceeds Jules' 60 and Devin's 10.

**Ties (✅):** Persistent memory (row 8) — ArcRift recall/store + guild `## Learned` templates hold their own against Devin's Knowledge/Playbooks and Augment's shared context.

**Trails — the real work, seven gaps:**

| Gap | What's missing | Cheap? | Maps to |
|---|---|---|---|
| **G1** | Async **cloud execution** + isolated sandbox per ticket (they all run headless in the cloud; DasLab runs interactively, locally, one operator) | Medium | Governed-Devin **Phase B** (Agent SDK headless runner) + DGO-X **P3** sandbox + **Phase D** HEARTBEAT tempo |
| **G2** | **Browser / computer use** (Devin's signature; the visible "wow") | **Cheap** | **Phase A** MCP tool bridge — *your chosen lever* |
| **G3** | **External front door** — assign a GitHub Issue / Jira / Linear ticket and get a PR | **Cheap–Medium** | New MCP bridges mapping trackers ⇄ `board/tickets` (inbound) + DasLab-as-MCP (outbound) |
| **G4** | **Indexing of existing large codebases** (Augment Context Engine, Devin DeepWiki) | Medium | Optional — **consume** an index via MCP rather than rebuild; only matters if DasLab targets *existing-repo* work vs. greenfield |
| **G5** | **Live "watch it work" pane** | **Cheap** | **Phase A′** LangSmith (spans already OTel-shaped, ADR-0024) |
| **G6** | **External proof point** (a public benchmark or a shipped public project) | Medium | Run SWE-bench via the headless runner, or ship one project 0→100 through AADL in public |
| **G7** | **Enterprise shell** (SOC 2 cert, SSO, VPC, multi-user SaaS) | Expensive | The **strategic fork** (§5) — a business, not a feature |

Notice the cluster: **four of the seven gaps (G2, G3, G5, and the visible half of G1) are exactly the Governed-Devin program you already chose.** Closing them is not new scope — it is finishing the plan.

## 3b — The general autonomous agents (Perplexity Computer, Manus)

The Founder's list also names two agents that are **not** software engineers: **Perplexity Computer** (a cloud multi-agent system in Firecracker microVMs driving the **Comet** browser across 400+ connectors) and **Manus** (an autonomous general agent operating its own cloud VM, *"Manus's Computer,"* via a planner + dynamic sub-agents). They matter here for one reason: they set the bar on exactly the two capabilities DasLab most visibly lacks — an **async cloud computer** (G1) and a **browser/computer-use** surface (G2). On everything DasLab is built for, they are far behind.

| Dimension | Perplexity Computer | Manus | **DasLab now** | **DasLab→** |
|---|:--:|:--:|:--:|:--:|
| Async cloud computer (VM per task) | ✅ | ⭐ | ❌ | ✅ |
| Browser / computer-use | ⭐ | ⭐ | ❌ | ✅ |
| General (non-code) task breadth | ⭐ | ⭐ | ❌* | ❌* |
| Software-engineering depth | ❌ | 🟡 | ✅ | ✅ |
| Multi-agent role specialization | 🟡 | 🟡 | ⭐ | ⭐ |
| Gated lifecycle + governance depth | ❌ | ❌ | ⭐ | ⭐ |
| Persistent memory | 🟡 | ❌ | ✅ | ✅ |
| Enterprise shell | ✅ | 🟡 | ❌ | ❌† |

\* DasLab is deliberately a *software* org, not a general task agent — general breadth is out of scope by design.

Read: both are **generalists with a computer** — strong on reach and autonomy, weak on engineering depth (Perplexity's coding is a "black box" with cost overruns; Manus's reliability falls off sharply past ~20 steps) and effectively **ungoverned** (no gated lifecycle; Manus's very certifications are contested, and both carry documented prompt-injection/exfiltration exposure). So the governed-org wedge holds *even harder* against them than against the coding agents. The concrete lesson for DasLab is narrow and already in the roadmap: **their "wow" is the browser + the cloud computer (G1 + G2) — Phase A + Phase B, not a new direction.** Manus also carries real platform-risk noise (its ~$2–3B Meta acquisition was blocked by Chinese regulators in April 2026) — a reminder that an impressive demo and a durable platform are different things.

## 4 — Positioning against each (the wedge)

- **vs. Devin** — Devin has the highest raw autonomy and a real browser, but reliability on ambiguous work is openly contested and there is **no gated lifecycle**. DasLab's wedge: *"a Devin whose every action is an attested event and that physically cannot ship past a gate no human approved."*
- **vs. Copilot coding agent** — Deeply GitHub-native and model-flexible, but GitHub-locked and framed for low-to-medium complexity. DasLab's wedge: *platform-neutral, whole-org delivery with governance Copilot's admin settings don't reach.*
- **vs. Augment** — Best-in-class **Context Engine** for giant existing monorepos. Don't rebuild it — **consume it via MCP** (Augment exposes it as an MCP server). DasLab's wedge: *the org and the lifecycle around the context, not the context itself.*
- **vs. Factory** — The closest cousin (agent-native Droid fleet, enterprise). But Factory is SOC 2 **Type I** and its fleet has no AADL-style gates or charter/RACI. DasLab's wedge: *the governed version of Factory's fleet idea.*
- **vs. Jules** — Fire-and-forget and Gemini-native, but single-vendor, GitHub-only, consumer-bundled. DasLab's wedge: *multi-role, governed, not locked to one model vendor.*

The pattern: **every competitor is ❌/🟡 on rows 5 and 12.** That empty square — *governed, whole-lifecycle autonomy* — is the category DasLab can own instead of losing a feature race to five funded teams.

## 5 — The strategic fork (decide this explicitly)

"Their level" forces one honest choice:

- **Path 1 — Capability parity on the governance wedge (recommended).** Close G1, G2, G3, G5 (all in the Governed-Devin program), get one proof point (G6), and consume — not rebuild — codebase indexing (G4) via MCP. Outcome: DasLab *operates* as autonomously as the five for the work it does, and is the only one that is governed. Tractable for a solo/small effort.
- **Path 2 — Market parity (a company).** Add G7: SOC 2, SSO, VPC, multi-user SaaS, a sales motion, and community/adoption to fight the VS analysis's real weakness (community 1/10, adoption 2/10). This is a funding-and-team decision, not an architecture one, and competing head-on with Cognition/Google/GitHub on packaging is the losing frame.

**Recommendation:** commit to **Path 1** and treat Path 2 as an optional, later, deliberately-funded step. Win the category the matrix says is empty; do not out-feature five funded companies on their own turf.

## 6 — Concretely, what to build (reusing the program)

1. **Phase A — browser + tool reach (G2).** FastMCP sidecar exposing a computer-use/Playwright browser tool + one search/retriever, wired in `.mcp.json`, governed by allow-list + `PreToolUse` hook. Days. The visible "Devin-like" win.
2. **Phase A′ — LangSmith pane (G5).** OTLP export of the ADR-0024 spans. Days. "Watch it work."
3. **Phase B — headless runner (G1a).** `daslab_sdk` over the Claude Agent SDK (loads `.claude/agents` via `setting_sources=["project"]`). Unlocks cloud execution, benchmarking, and the front door. → **ADR-0034.**
4. **Front-door bridge (G3).** MCP adapters mapping GitHub Issues / Jira / Linear into `board/tickets` (inbound) and DasLab-as-a-node/MCP (outbound). → extends **ADR-0033/0036.**
5. **DGO-X P3 sandbox + Phase D HEARTBEAT (G1b, tempo).** Per-ticket isolated cloud workspace; autonomy switched on under ADR-0027's SI-1…SI-7, Founder-gated. → **ADR-0035.**
6. **One proof point (G6).** Point the headless runner at **SWE-bench Verified/Pro** for a public number, *or* ship one real project 0→100 through AADL in the open. This attacks adoption/community directly.
7. **Codebase index (G4), only if needed.** If DasLab takes on existing-repo tasks, consume Augment's MCP Context Engine or build a DeepWiki-style index — don't make it a prerequisite for greenfield delivery.

---

## Sources

**Platforms (mid-2026):**
- Jules — https://jules.google/ · https://jules.google/docs/usage-limits/ · https://developers.googleblog.com/jules-gemini-3/ · https://techcrunch.com/2025/08/06/googles-ai-coding-agent-jules-is-now-out-of-beta/
- GitHub Copilot coding agent — https://github.com/features/copilot/agents · https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents · https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/
- Augment Code — https://www.augmentcode.com/ · https://www.augmentcode.com/context-engine · https://www.augmentcode.com/blog/auggie-tops-swe-bench-pro · https://siliconangle.com/2026/06/05/augment-code-launches-cosmos-bring-agentic-ai-software-development-teams/
- Factory.ai — https://factory.ai/ · https://factory.ai/enterprise · https://factory.ai/news/terminal-bench · https://docs.factory.ai/cli/user-guides/choosing-your-model
- Devin — https://devin.ai/ · https://docs.devin.ai/work-with-devin/deepwiki · https://cognition.ai/blog/swe-bench-technical-report · https://devin.ai/blog/windsurfs-next-chapter/
- Perplexity Computer / Comet — https://www.perplexity.ai/comet · https://www.perplexity.ai/hub/blog/introducing-perplexity-computer · https://brave.com/blog/comet-prompt-injection/ · https://www.builder.io/blog/perplexity-computer
- Manus — https://manus.im · https://manus.im/security · https://en.wikipedia.org/wiki/Manus_(AI_agent) · https://techcrunch.com/2026/04/27/china-vetoes-metas-2b-manus-deal-after-months-long-probe/

**DasLab / interop (companion brief):** ADR-0010 DGO-X · ADR-0023 run-model · ADR-0024 span-events · ADR-0027 scheduler-safety · Claude Agent SDK https://code.claude.com/docs/en/agent-sdk/claude-code-features · langchain-mcp-adapters https://github.com/langchain-ai/langchain-mcp-adapters · LangSmith OTel https://docs.langchain.com/langsmith/trace-with-opentelemetry
