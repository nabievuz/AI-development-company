# Top-10 Open-Source Alternatives to DasLab 2.0 — Deep Research, Capability Matrix & SWOT

> Date: 2026-07-03 · Companion to [`2026-07-03-donor-platforms-deepresearch.md`](2026-07-03-donor-platforms-deepresearch.md)
> (the 5 donors — LangGraph, MAF, CrewAI, Agency Swarm, SuperAGI — are NOT repeated here).
> Method: 3 parallel research passes; stars/licenses/releases verified LIVE from GitHub
> (API + LICENSE files) on 2026-07-03. Visual: [`2026-07-03-daslab-alternatives-swot.html`](2026-07-03-daslab-alternatives-swot.html).
> Scores are the author's assessment (0–10), not benchmarks.

---

## 0 — Xulosa (O'zbekcha)

DasLab 2.0'ga to'liq muqobil bo'la oladigan **birorta ham** open-source loyiha topilmadi — 10
nomzodning hech biri DasLab'ning to'rt ustunini (gated governance + typed kontraktlar +
per-agent evals + spec→build kompilyator) birlashtirmaydi: R11 (governance) bo'yicha eng
yuqori begona ball — BMAD 7, R12 (spec→build) bo'yicha — MetaGPT/BMAD 8, lekin ikkalasida ham
runtime/durability/telemetriya yo'q. Umumiy reyting: **OpenHands (67/120)** va **AgentScope
(67/120)** yetakchi — birinchisi eng kuchli ijro dvigateli + eval madaniyati, ikkinchisi eng
kuchli infra (OTel, sandbox, interrupt-service). **DasLab 1.0 hozirning o'zida 59/120** —
o'ninchi emas, uchinchi-to'rtinchi o'rin atrofida; ORGANISM (v2.0) bajarilsa 115/120 bo'ladi.
Muhim ogohlantirishlar: (1) **Ruflo** (62.7k★!) — audit bilan isbotlangan fabrikatsiya tarixi
(soxta SWE-bench, `Math.random()` metrikalar) — yulduzga aldanmang; (2) **AutoGPT Platform**
aslida to'liq OSS emas (Polyform Shield); (3) sektor patterni: org-qatlam qiymati yopiq
mahsulotga aylanadi (MetaGPT→Atoms, GPT-Engineer→Lovable $12B, CAMEL→Eigent) — bu DasLab
tezisini tasdiqlaydi va soatni tezlashtiradi. Eng qimmatli import-pattern'lar: Letta'ning
git-backed MemFS'i (ArcRift uchun), OpenHands'ning regression-eval intizomi, AgentScope'ning
interrupt-service'i, BMAD'ning step-file token arxitekturasi, CAMEL'ning
FailureHandlingConfig semantikasi.

---

## 1 — Rubric (12 rows, anchors)

R1 durable execution (checkpoint/resume/replay) · R2 dynamic planning + stall detection ·
R3 typed contracts + enforced routing · R4 guardrails / bounded retries · R5 autonomous
tempo/scheduling · R6 observability (spans/tokens/cost) · R7 ops cockpit (OSS) · R8
specialist role depth · R9 per-agent evals/training · R10 long-term memory governance ·
R11 governance/compliance/human gates · R12 spec→build pipeline (docs pack → software).
Anchors: 0 absent · 3 ad-hoc/DIY · 5 partial/manual/paid-only · 7 solid built-in ·
9–10 best-in-class with evidence.

## 2 — Identity table (verified 2026-07-03)

| # | Project | Repo | ★ | License (verified) | Latest release | Backing | Maintenance |
|---|---------|------|---|--------------------|----------------|---------|-------------|
| 1 | OpenHands (ex-OpenDevin) | OpenHands/OpenHands | 79.2k | MIT (+ `enterprise/` commercial carve-out) | cloud-1.40.0, weekly; V1 SDK line | OpenHands Inc., $18.8M Series A (Madrona, 2025-11) | Very active (same-day push) |
| 2 | AgentScope 2.x | agentscope-ai/agentscope | 27.4k | Apache-2.0 | v2.0.1 (2026-06-05) + Java 2.0 | Alibaba Tongyi Lab | Very active; churn 0.x→2.x |
| 3 | CAMEL (+Workforce/OWL/Eigent) | camel-ai/camel | 17.3k | Apache-2.0 (⚠ OWL repo: NO license file) | v0.2.90 (2026-03-22; alphas since) | Eigent AI Ltd (UK) | Slowing; energy → Eigent product (v1.0.0 2026-06-16) |
| 4 | Letta (ex-MemGPT) | letta-ai/letta | 23.6k | Apache-2.0 | 0.16.8 (2026-05-14); letta-code v0.27.18 active | Letta Inc., $10M seed (Felicis) | Server slowing; pivot to Letta Code |
| 5 | ChatDev 2.0 "DevAll" | OpenBMB/ChatDev | 33.4k | Apache-2.0 | v2.2.0 (2026-03-23) | OpenBMB / Tsinghua NLP (academic) | Active, research-cadence |
| 6 | AutoGPT Platform | Significant-Gravitas/AutoGPT | 185.3k | ⚠ Polyform Shield (platform) + MIT (classic only) | v0.6.65 (2026-06-25) | Significant Gravitas, $12M (Redpoint) | Very active; cloud-first |
| 7 | BMAD-METHOD v6 | bmad-code-org/BMAD-METHOD | 50.0k | MIT (+ BMad™ trademark notice) | v6.9.0 (2026-06-22) | BMad Code LLC, ~150 contributors | Healthy; v7 signposted |
| 8 | MetaGPT (→ Atoms) | FoundationAgents/MetaGPT | 68.4k | MIT | v0.8.1 (2024-04!) — frozen | DeepWisdom (>$50M; Atoms product) | OSS dormant; company alive |
| 9 | Ruflo (ex-Claude-Flow) | ruvnet/ruflo | 62.7k | MIT | v3.16.3 (2026-07-01), 1553 releases | Solo dev (ruvnet) + consultancy | Hyperactive; credibility debt |
| 10 | Agent Zero | agent0ai/agent-zero | 18.3k | MIT (© Agent Zero s.r.o.) | v2.2 (2026-07-02) | Agent Zero s.r.o. (CZ) | Very active |

## 3 — Capability matrix (author's assessment, 0–10)

| Row | OpenHands | AgentScope | CAMEL | Letta | ChatDev | AutoGPT | BMAD | MetaGPT | Ruflo | AgentZero | **DasLab 1.0** | **DasLab 2.0 tgt** |
|-----|-----------|------------|-------|-------|---------|---------|------|---------|-------|-----------|----------------|--------------------|
| R1 durable execution | 7 | 7 | 4 | **8** | 3 | 6 | 4 | 4 | 5 | 5 | 4 | 10 |
| R2 planning + stall | 6 | 6 | **7** | 3 | 6 | 3 | 4 | 4 | 4 | 3 | 4 | 10 |
| R3 typed contracts | 5 | 6 | 5 | 5 | 6 | **7** | 4 | 6 | 2 | 1 | 4 | 10 |
| R4 guardrails/retries | **7** | **7** | **7** | 4 | 4 | 5 | 5 | 5 | 3 | 4 | 5 | 9 |
| R5 autonomous tempo | 6 | 3 | 3 | 6 | 2 | **8** | 2 | 2 | 4 | 5 | 2 | 9 |
| R6 observability | 6 | **8** | 4 | 6 | 5 | 6 | 1 | 4 | 3 | 2 | 4 | 10 |
| R7 ops cockpit (OSS) | **7** | **7** | 6 | 6 | 6 | 6 | 2 | 1 | 5 | 6 | 4 | 9 |
| R8 role depth | 4 | 4 | 6 | 2 | 5 | 2 | **8** | 6 | 6 | 3 | 7 | 10 |
| R9 per-agent evals | **7** | **7** | 4 | 2 | 2 | 2 | 1 | 3 | 2 | 1 | 2 | 9 |
| R10 memory governance | 4 | 6 | 5 | **9** | 4 | 2 | 4 | 3 | 6 | 6 | 8 | 9 |
| R11 governance/gates | 4 | 4 | 3 | 2 | 4 | 3 | **7** | 3 | 1 | 2 | **10** | 10 |
| R12 spec→build | 4 | 2 | 2 | 3 | 6 | 2 | **8** | **8** | 5 | 2 | 5 | 10 |
| **TOTAL /120** | **67** | **67** | 56 | 56 | 53 | 52 | 50 | 49 | 46 | 40 | **59** | **115** |

**Read:** (1) DasLab 1.0 at 59 already ranks #3 of 12 — and #1 by a wide margin on the two
rows that define the category it actually plays in (R11 governance, R10+R11 combined).
(2) The leaders win on *infrastructure* rows (R1/R6/R7/R9), exactly the ORGANISM
workstreams — after v2.0 no alternative is within 45 points. (3) Nobody combines pillars:
top R11 elsewhere = 7 (BMAD, no runtime); top R12 = 8 (MetaGPT frozen / BMAD human-paced).

## 4 — Dossiers + SWOT (founder view vs DasLab)

### 4.1 OpenHands — 67/120 · the strongest execution engine

Open platform for autonomous software agents (event-stream architecture as single source
of truth; sandboxed Docker runtimes; CodeAct agent; delegation + repo-level microagents;
V1 rebuilt on the MIT software-agent-sdk). Claims 77.6% SWE-bench Verified, #1 and only
OSS agent in the top-10 (early 2026). 20+ integrated benchmarks; regression evals gate
releases. GUI cockpit OSS; fleet ops/RBAC/audit = paid cloud.

- **S:** best verified execution + eval discipline in OSS; durable event log; funded ($18.8M), ships weekly; embeddable SDK.
- **W:** one generalist engineer, not an org — no roles/gates/metric contracts/spec pipeline; governance features paywalled; V0→V1 churn.
- **O (adopt):** use software-agent-sdk sandboxes as DasLab's risky-ticket execution substrate; copy regression-eval gating into golden evals; event-log-as-truth hardening for wave checkpoints; stuck-detector heuristics.
- **T:** the most serious commercial threat — "open standard for autonomous software development" + enterprise sales; every DasLab pitch gets benchmarked against it.

### 4.2 AgentScope — 67/120 · the strongest infrastructure

Alibaba's engineering-serious framework+runtime+studio: async agents with realtime
steering and a distributed interrupt service (state persistence/recovery hooks), plan
module, short/long-term + agentic memory (Mem0, multi-tenant RAG), Docker/E2B sandboxes,
fine-grained permission system, OTel-native Studio (traces, tokens, evals), K8s/serverless
deploy, eval + finetuning modules. Apache-2.0, Py/TS/Java.

- **S:** Alibaba-scale infra DasLab could never build alone; OTel spans + real eval module; sandbox + permission system.
- **W:** framework, not organization — no board/gates/goal queue/metric contracts; 3 breaking major versions in ~14 months; Alibaba-cloud gravity.
- **O (adopt):** interrupt-service design → wave checkpoint/resume; OTel span conventions; E2B/Docker sandbox backends; Studio run-replay UX for the cockpit; eval module shape for `agent_eval.py`.
- **T:** if Alibaba ships an opinionated "agent org" layer (Agent Team is the seed), DasLab's infra layer gets commoditized at price zero.

### 4.3 CAMEL / Workforce / OWL / Eigent — 56/120 · the closest conceptual cousin

Role-playing research pioneer grown into Workforce: task-decomposer → coordinator →
parallel workers with dependency passing, **dynamic worker spawn on repeated failure**,
and the most explicit failure semantics in OSS (`FailureHandlingConfig`: max_retries,
recovery-strategy allowlist, halt_on_max_retries). OWL topped GAIA OSS (58.18→69.09).
Eigent (14.2k★, Apache-2.0, v1.0.0) wraps it as a desktop "AI workforce" — explicitly
marketed against Claude Cowork. ⚠ OWL repo has no LICENSE file; framework releases
slowing (alphas only since March).

- **S:** best OSS coordinator/planner/worker with codified failure recovery; GAIA credibility; unique synthetic-data/self-improvement stack.
- **W:** no durable execution, weak telemetry, no governance; framework decaying as the 14-person company bets on Eigent; OWL unlicensed.
- **O (adopt):** FailureHandlingConfig semantics → DasLab bounded-retry rules; dynamic-worker-spawn as escalation valve; lifecycle callbacks as metrics seam; data-gen loops to mint eval sets.
- **T:** Eigent is the closest *product* competitor to the "AI workforce" story — open-source, desktop, revenue-claiming.

### 4.4 Letta — 56/120 · the memory monopolist

Stateful-agent platform (agents as DB-persisted services; self-editing core memory
blocks; shared blocks across agents; sleep-time consolidation agents; ADE context
inspector). 2026 pivot: Letta Code (git-backed **MemFS** — memory as versioned markdown
repo with defrag skill, worktree-concurrent "dream" subagents; 42.5% Terminal-Bench,
real leaderboard). Tool rules (constrained tool sequencing) deprecated. OSS server
slowing; cloud Constellation is the bet.

- **S:** deepest memory science (published research); durable-by-construction runtime; credible benchmarks; Apache-2.0.
- **W:** not a delivery org (no roles/gates/board); OSS server → maintenance mode; deprecation whiplash.
- **O (adopt):** git-backed MemFS pattern for ArcRift (versioned memory commits, defrag, worktree concurrency); sleep-time consolidation as DasLab idle-tempo job (direct hit on idle_wave_rate 0.70); shared memory blocks for cross-agent context.
- **T:** owns the "stateful agents" category; org-orchestration on top of its memory moat would attack DasLab from below.

### 4.5 ChatDev 2.0 "DevAll" — 53/120 · the research goldmine

Tsinghua's virtual software company (chat-chain of instructor↔assistant phase dialogues,
communicative dehallucination) relaunched 2026-01 as a YAML-DAG multi-agent platform with
typed node kinds, an OSS web console (canvas + live WebSocket monitor + human nodes), and
research spine: MacNet (1,000+-agent DAG scaling law) and Puppeteer (RL-trained dynamic
orchestrator, NeurIPS 2025) integrated.

- **S:** best academic corpus on agent-team communication; real OSS cockpit; only empirical team-size scaling law; Apache-2.0.
- **W:** grad-student bus factor; abandoned SDLC depth right when pivoting; no durability/evals/cost governance.
- **O (adopt):** communicative dehallucination as mandatory ticket-clarification before dispatch; Puppeteer-style learned wake-up for the planner; MacNet law to size waves; Human-node UX to sanity-check Founder gates.
- **T:** low commercial threat; narrative risk only ("DevAll" as default orchestration mental model).

### 4.6 AutoGPT Platform — 52/120 · the automation gorilla (⚠ not fully OSS)

Visual block-graph builder + server-side executor (FastAPI/Supabase/Redis/RabbitMQ),
first-class cron + webhook triggers, marketplace with per-block credit metering. 185k★.
**License caveat: the actively developed `autogpt_platform/` is Polyform Shield
(source-available, non-compete) — only the legacy classic code is MIT.**

- **S:** massive distribution; production trigger/scheduler infra; typed block pins; marketplace flywheel.
- **W:** not OSS where it matters; blocks ≠ roles; no lifecycle, evals, spec→build; automation ceiling.
- **O (adopt):** per-block credit metering → budget governor; webhook/cron trigger design; marketplace trust signals (run counts/ratings) for skills reuse.
- **T:** owns the prosumer "hire agents" narrative; a code-delivery vertical would squeeze DasLab's low end.

### 4.7 BMAD-METHOD v6 — 50/120 · the process twin (no engine)

Methodology-as-software: persona agents (Analyst/PM/Architect/Dev/UX/TW as
`.agent.yaml` + skills), 34+ step-file workflows, two-phase planning→dev cycle emitting
**self-contained story files** + `sprint-status.yaml` — file-native markdown like DasLab.
Scale-adaptive routing (bug-fix path vs enterprise path), party-mode adversarial review
crews with persistent memory, marketplace modules; harness-agnostic. Human-paced by
design; no telemetry/evals/scheduler.

- **S:** category-defining brand for AI-agile; deepest persona/workflow content; 150 contributors + marketplace; runs on any harness.
- **W:** no execution engine — no waves, telemetry, budgets, evals, autonomy; quality depends on the driving human; trademark-guarded.
- **O (adopt):** step-file token architecture for long workflows; **scale-adaptive lifecycle routing** (DasLab's fixed 6-stage flow regardless of task size is a real gap); party-mode review crews; module/marketplace packaging for Project-OS packs.
- **T:** "BMAD + any harness" is the default answer to "AI software team" — DasLab must position as *autonomous governed org* vs *facilitated methodology*, or read as a BMAD clone.

### 4.8 MetaGPT → Atoms — 49/120 · the frozen pioneer

The canonical "AI software company" (SOP-as-prompt role pipeline: PRD→design→tasks→code;
typed pydantic artifacts; pub-sub message pool; DataInterpreter; CostManager budget caps;
AFlow workflow-search research). OSS frozen at v0.8.1 (Apr 2024, last push 2026-01);
energy moved to closed **Atoms** (ex-MGX; claimed $1M ARR month one; "Race Mode" runs
competing parallel teams and auto-evaluates variants).

- **S:** peer-reviewed spec→build pipeline; elegant typed pub-sub; huge mindshare.
- **W:** OSS dormant 26 months; no durability/scheduler/cockpit/evals/gates; demo-scale output ceiling.
- **O (adopt):** artifact schemas (PRD/design/tasks) to harden GATEWAY; pub-sub subscription routing for tickets; AFlow-style search to auto-tune pipelines; **Race-Mode competing waves** as an eval idea.
- **T:** Atoms is DasLab's thesis productized with >$50M — if it ships an enterprise/API tier, "docs-pack → deployed business" becomes purchasable.

### 4.9 Ruflo (ex-Claude-Flow) — 46/120 · scale without trust

Claude Code swarm meta-harness (queen/worker hive-mind, 5 topologies, SPARC methodology,
hooks automation, genuinely solid HNSW/SQLite memory, Ed25519-signed releases). 62.7k★,
1,553 releases in 13 months, #2 contributor is "claude". **Credibility debt is
documented, not rumored:** independent + self-commissioned audits found ~290 of ~300 MCP
tools are stubs, the famous "84.8% SWE-bench" came from a `simulate_benchmarks.py` using
`random.uniform()` (never on the official leaderboard; removed after the May 2026
AlphaSignal audit), "Flash Attention 7×" fabricated with `Math.random()`, token-saving
stats hardcoded, and a CLI bug silently inverted negative training feedback. Consensus
"consensus" is a single-process EventEmitter; agents spawn with
`--dangerously-skip-permissions`.

- **S:** unmatched distribution (62.7k★, 700k npm installs); real memory layer; daily shipping; signed-artifact verification is genuinely mature.
- **W:** fabrication culture destroys enterprise trust; ~97% stub tools per audits; zero human gates (autonomy-first, permissions skipped); solo-maintainer churn.
- **O (adopt):** Ed25519-signed wave/release manifests; hooks packaging as a Claude Code plugin; hosted live-agents dashboard as a marketing surface; ReasoningBank-style pattern retrieval into ArcRift.
- **T:** owns "Claude swarm" mindshare/SEO; if the v3 cleanup succeeds, velocity could out-feature DasLab; its inflated claims also poison category credibility for everyone — differentiate with *committed evidence* (T1–T7 anti-gaming).

### 4.10 Agent Zero — 40/120 · the runtime UX benchmark

General-purpose autonomous agent in one Docker container (Kali-root Linux + XFCE desktop
in the browser). Hierarchical superior/subordinate spawning with role profiles;
everything defined in editable prompt files; memory with AI-filtered recall +
consolidation; instruments; SKILL.md-standard skills; Time-Travel snapshots with
diff/rollback; MCP + A2A; Plugin Hub (100+ plugins with AI security scans — including a
BMAD plugin).

- **S:** best OSS runtime UX (desktop-in-browser, launcher, 1-command install); local-model-first economics; active company + weekly releases.
- **W:** single agent tree — no board/contracts/telemetry/lifecycle; root autonomy is an enterprise nonstarter; prompt-file flexibility trades away governance.
- **O (adopt):** Time-Travel snapshot/rollback semantics for wave checkpoints; AI security-scanning of skills/plugins pre-install; launcher-grade packaging so non-founders can run DasLab.
- **T:** its Plugin Hub absorbing BMAD proves runtimes commoditize methodologies — DasLab's moat must be the governance *engine*, not the docs pack.

## 5 — Cross-cutting findings

1. **The enclosure pattern is universal.** MetaGPT→Atoms, GPT-Engineer→Lovable (archived
   OSS; ~$400M ARR, $6.6B→talks at $12B), CAMEL→Eigent, OpenHands enterprise carve-out,
   AutoGPT→Polyform, Letta→Constellation, Suna→Kortix. Org-layer value gets closed. Twin
   consequence for DasLab: the thesis is validated, and the OSS window is a clock.
2. **Nobody combines the four pillars.** Governance gates (best foreign score 7),
   spec→build compiler (8, but engineless/frozen), enforced typed contracts (7, blocks
   not agents), per-agent evals (7, engine-level not role-level) never co-occur. DasLab
   2.0's 115/120 profile has no OSS competitor within 45 points.
3. **Stars ≠ substance.** Ruflo (62.7k★) scores 46/120 with documented fabrication;
   Agent Zero (18.3k★) beats none of the leaders. Verified evidence — DasLab's committed
   KPI snapshots — is a differentiator worth marketing.
4. **The infra rows are buyable-free.** AgentScope/OpenHands prove R1/R6/R7/R9 patterns
   are commodity engineering now — exactly what ORGANISM reimplements natively; no reason
   to adopt their runtimes and inherit their churn.
5. **Watch-list (quarterly re-check):** OpenHands Cloud gating features, Alibaba "Agent
   Team", Atoms enterprise tier, Eigent growth, BMAD v7, Archon (22.7k★, MIT — YAML
   "harness builder", nearest neighbor to the Project-OS compiler).

## 6 — Honorable mentions (excluded from top-10, with reasons)

**Dify** 147k★ (app/workflow builder, custom Apache+conditions license — not an org
engine) · **n8n** 195k★ (fair-code Sustainable Use License — NOT open source; $2.5B→$5.2B
valuation — automation adjacent) · **Goose** 50k★ Apache-2.0, now Linux Foundation
(healthy single desktop agent, no org layer) · **Suna/Kortix** 19.9k★ (license changed to
custom; SaaS-first pivot) · **Archon** 22.7k★ MIT (harness-builder, watch closely) ·
**Aider** 47k★ Apache-2.0 (coasting since 2025-08; pair-programmer, not a platform) ·
**Swarms** 6.7k★ (documented credibility concerns + crypto token — not a serious
benchmark) · **GPT-Engineer** (archived; see Lovable).

## 7 — Sources

**OpenHands:** github.com/OpenHands/OpenHands (+LICENSE) · openhands.dev/blog/weve-just-raised-18-8m… · github.com/OpenHands/software-agent-sdk (arXiv 2511.03690) · openhands.dev/blog/openhands-cloud-self-hosted… · tekai.dev/references/2026-04-03-openhands…
**AgentScope:** github.com/agentscope-ai/agentscope (+releases v2.0.1) · arXiv 2508.16279 · github.com/agentscope-ai/agentscope-studio · github.com/agentscope-ai/agentscope-runtime · alibabacloud.com/blog/agentscope-java-2-0…
**CAMEL/OWL/Eigent:** github.com/camel-ai/camel (+LICENSE) · docs.camel-ai.org/key_modules/workforce · github.com/camel-ai/owl · camel-ai.org/blogs/…owl-crab-and-mcp… · github.com/eigent-ai/eigent · eigent.ai/about
**Letta:** github.com/letta-ai/letta · github.com/letta-ai/letta-code · letta.com/blog/our-next-phase · letta.com/blog/sleep-time-compute · letta.com/blog/context-repositories · docs.letta.com/guides/core-concepts/stateful-agents
**ChatDev:** github.com/OpenBMB/ChatDev (+LICENSE, releases v2.0.0/v2.2.0) · deepwiki.com/OpenBMB/ChatDev/1.1-what-is-chatdev-2.0 · arXiv 2406.07155 (MacNet) · x-cmd.com/blog/260110 · ibm.com/think/topics/chatdev
**AutoGPT:** github.com/Significant-Gravitas/AutoGPT (+root LICENSE: Polyform/MIT split) · releases autogpt-platform-beta-v0.6.65 · agpt.co/pricing · pitchbook.com/profiles/company/539951-77
**BMAD:** github.com/bmad-code-org/BMAD-METHOD (+LICENSE) · newreleases.io …/v6.9.0 · docs.bmad-method.org/reference/agents · vibesparking.com …bmad-v630-changelog
**MetaGPT/Atoms:** github.com/FoundationAgents/MetaGPT (+LICENSE, releases) · atoms.dev/metagpt · kr-asia.com/from-metagpt-to-atoms… · thestar.com.my …deepwisdom…
**Ruflo:** github.com/ruvnet/ruflo (+releases v3.16.3) · issues #653/#1425/#1514/#1896 · gist.github.com/roman-rr/ed603b676af019b8740423d2bb8e4bf6 · docs/reviews/intelligence-system-audit-2026-05-29.md · sublimecoding.com/blog/ruflo-claude-flow-multi-agent-deep-dive
**Agent Zero:** github.com/agent0ai/agent-zero (+LICENSE, v2.0/v2.2 releases) · agent-zero.ai · docs/architecture.md
**Mentions:** github.com/langgenius/dify · github.com/n8n-io/n8n (+ blog.n8n.io/series-c) · github.com/block/goose · github.com/kortix-ai/suna · github.com/coleam00/Archon · github.com/Aider-AI/aider · github.com/AntonOsika/gpt-engineer (archived) · forbes.com …lovable-12-billion… (2026-06-05)
