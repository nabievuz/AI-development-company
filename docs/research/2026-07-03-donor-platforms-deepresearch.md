# Donor Platforms Deep-Research — DasLab v2.0 "ORGANISM" Foundation

> Date: 2026-07-03 · Baseline reviewed: DasLab v1.0.0 (repo root, 67 scripts, 33 agent roles) ·
> Donors analyzed: LangGraph, Microsoft Agent Framework, CrewAI, Agency Swarm, SuperAGI ·
> Method: 3 parallel web-research passes (2025–2026 primary sources, licenses verified from
> LICENSE files) + 1 full repo inventory pass. Companion artifact:
> [`MASTER-PROMPT-ORGANISM.md`](MASTER-PROMPT-ORGANISM.md).

---

## 0 — Xulosa (O'zbekcha qisqa hulosa)

Beshala donor ham tekshirildi va litsenziyalari tasdiqlandi — **beshovi ham MIT**. Bu degani:
ularning **pattern'larini (g'oya, arxitektura, mexanizm) nol majburiyat bilan** o'zimiznikidek
qilib, noldan qayta yozish mumkin — g'oya mualliflik huquqi bilan himoyalanmaydi. Faqat bitta
qat'iy shart: **birorta faylni so'zma-so'z ko'chirmaymiz** (verbatim copy MIT notice talab qiladi);
hamma narsa clean-room usulida, DasLab'ning o'z fayl-native uslubida qayta ishlanadi. Natija —
100% original kod, hech qanday attribution shart emas.

Asosiy topilmalar: (1) **SuperAGI o'lgan** (oxirgi reliz 2024-yanvar, kompaniya SDR-SaaS'ga
pivot qilgan) — undan faqat APM-cockpit va scheduler pattern'lari olinadi, kod emas.
(2) **LangGraph'ning yagona chuqur ustunligi** — durable execution (checkpoint + resume +
time-travel); bu DasLab'ning eng katta bo'shlig'i. (3) **MAF'ning Magentic dual-ledger**
(task ledger + progress ledger + stall detection) — DasLab'da yo'q bo'lgan "jonli planner"ning
tayyor retsepti. (4) **CrewAI'ning role anatomy + test/train** — 32 agentni "kuchli mutaxassis"ga
aylantirish retsepti. (5) **Agency Swarm'ning schema-enforced routing** — agentlararo aloqani
governance darajasida qotirish usuli. DasLab hozir governance bo'yicha hammadan kuchli (10/10),
lekin tempo (busy 0.11), evals (yo'q) va durable resume (yo'q) bo'yicha eng zaif. 22 pattern →
7 workstream'ga jamlandi; master-prompt shu asosda yozildi.

---

## 1 — Method

Three independent research passes (LangGraph; MAF + Agency Swarm; CrewAI + SuperAGI +
2026 landscape), each grounded in official docs, GitHub repos (stars/releases/LICENSE
verified live), and 2025–2026 engineering analyses. One repo-inventory pass over this
repository (scripts, skills, board, metrics, docs, projects). All source URLs in §9.
Capability scores in §5 are the author's assessment, not benchmarks.

## 2 — DasLab v1.0.0 baseline

**What exists (strong):** file-based governance-first engine — QONUN laws, AADL 6-stage
gated lifecycle, T1–T7 metric contract registry with anti-gaming rule (units count only
with merged PR + green CI + T7 pass), 35 `check_*.py` validators + 3 generators, 33 agent
roles with substantive overlays, 6 skills (`daslab-canary/investigate/learn/qa/review/
security-audit`) + 3 orchestration commands (`/daslab-plan`, `/daslab-cycle`, `/daslab-run`),
DGO-X event store (`board/.events.jsonl`), ArcRift persistent memory law, prompt-cache
prefix invariant, model-allocation law (opus×10 / sonnet×19 / haiku×3), org schema
(`org/schema.daslab.yaml` → gen_org/gen_subagents/gen_codeowners), loop-mode scaffolding
(`loop_controller.py`, `check_loop_mode.py`, `feature_flags.py` — present but not activated),
`cockpit.py`/`wave_kpi.py`/`trends.py`/`alerting.py` telemetry seeds, `replay_qa.py`,
projects `qaqnuz` (full AADL doc pack) and `wolter-invest`.

**Functional gaps (the 2.0 targets):**

| # | Gap | Evidence |
|---|-----|----------|
| G1 | No durable wave execution — no checkpoint/resume/replay of a run; T5 target 0.99 exists as a drill, not a mechanism | `metrics/registry.yaml` T5; no `board/.checkpoints/` |
| G2 | Tempo is human-cranked — busy_fraction baseline 0.11 (target 0.60), idle_wave_rate 0.70 (target 0.15); loop mode exists but disabled | T1/T2 baselines; `loop_controller.py` inactive |
| G3 | No dynamic planner — `/daslab-plan` is static decomposition; no per-wave progress ledger, no stall detection/replan | skill flow |
| G4 | No typed inter-agent contracts — tickets carry prose, not `produces:`/`consumes:` schemas; routing not schema-enforced | `board_lint.py` scope |
| G5 | Telemetry is untyped — events exist but no span model (trace/span ids, token usage, duration); KPI gates evidence-thin (`.events.jsonl`/`.wave-log` gitignored, uncommitted) | `.gitignore` |
| G6 | No cost/token metering per ticket/agent/model | no ledger script |
| G7 | Cockpit is static — no live run feed, per-agent success, per-tool usage, budget view | `cockpit.py` |
| G8 | No per-agent eval harness — model allocation is judgment-based; no golden tasks, no accuracy×cost data | no `evals/` |
| G9 | No Project-OS intake compiler — docs pack → APPROVED-GOAL-QUEUE → stage-gated story tickets is manual | `docs/03-PROJECTS.md` flow |

## 3 — Donor dossiers

### 3.1 LangGraph (langchain-ai/langgraph) — the durability donor

**Status:** 1.0 GA 2025-10-22; latest 1.2.7 (2026-06-30); ~36.4k★; **MIT (verified)**.
OSS = full runtime; the paid layer (LangGraph Platform → "LangSmith Deployment", $39/seat +
usage) sells hosted persistence, cron, Studio UI — i.e., **they monetize exactly the ops
layer DasLab builds natively for free.**

**Mechanisms that matter (deep enough to re-derive):**
- **Pregel/BSP super-steps.** Plan → parallel execute → apply-writes barrier. Parallel
  node writes stay invisible until the step commits. A DasLab *wave* is already a
  super-step — the pattern legitimizes wave-boundary checkpointing.
- **Checkpointer + pending writes.** Snapshot at every super-step keyed by `thread_id`
  + `checkpoint_id`, **plus per-task durable writes as each node finishes** — so a failed
  sibling re-runs alone, finished work is never repeated.
- **Time travel.** History list → replay from any checkpoint (prior nodes not re-executed)
  → fork via state-edit into a branch, original audit trail intact.
- **`interrupt()`/`Command(resume=…)`.** Typed suspension with JSON payload; graph waits
  indefinitely; resume injects the human's value where the node paused. Caveat: the
  interrupted node re-runs from its start — pre-interrupt side effects must be idempotent.
- **Channels/reducers.** Per-key merge policies (`last-value`, append, aggregate) make
  concurrent same-key writes conflict-free. DeltaChannel (1.2) stores per-step deltas to
  stop checkpoint bloat.
- **Send + defer.** Runtime fan-out to N dynamic tasks with private state; `defer=True`
  holds the reduce node until all branches land.
- **CachePolicy.** Node-level cache by input-hash + TTL; hits flagged `cached: true`.
- **deepagents (25.6k★)** — LangChain productized todo-planning, virtual filesystem,
  subagents, context offloading: **exactly what DasLab already does natively**; validates
  the architecture, adds nothing DasLab lacks.

**Weaknesses:** abstraction/complexity tax, debugging opaque without paid LangSmith,
checkpoint bloat on long threads, overkill for linear flows. **Threat check:** the SWOT
threat (type-safe vendor runtimes shrink its role) is *partially* true — simple-agent
segment moved to Pydantic-AI/OpenAI SDK; LangGraph narrowed to the durable/stateful niche
but deepened there.

### 3.2 Microsoft Agent Framework (microsoft/agent-framework) — the orchestration donor

**Status:** 1.0 GA 2026-04-03 (AutoGen + Semantic Kernel merged successor); Python 1.8.1,
.NET 1.11.1; ~11.8k★; **MIT (verified)**. Azure AI Foundry is the commercial control plane.

**Mechanisms that matter:**
- **Typed workflow graph.** Executors declare handled message types; edges (direct /
  conditional / switch / fan-out / fan-in) are **validated at build time** — type
  mismatches, unreachable executors, duplicate edges fail before anything runs.
- **BSP supersteps + checkpointing.** Checkpoint at each superstep barrier: executor
  states, in-flight messages, pending request/responses, shared state; resume by
  `checkpoint_id` across process restarts.
- **Magentic dual-ledger orchestrator** (the crown jewel):
  - *Task ledger* (outer loop): facts — given / known / to-look-up / educated guesses —
    plus the plan, regenerated on replan.
  - *Progress ledger* (inner loop): each round the manager emits JSON —
    `is_request_satisfied`, `is_in_loop`, `is_progress_being_made`, `next_speaker`,
    `instruction_or_question` — then routes that instruction to the chosen agent.
  - *Stall rule:* `in_loop || !progress → stall_count++ else max(0, stall_count-1)`;
    `stall_count > 3 → ResetAndReplan` (facts-update + plan-update against history,
    `REPLANNED` event), bounded by `max_round_count` / `max_reset_count`. Optional human
    plan sign-off and pause-on-stall.
- **HITL via request/response executors** — workflow idles until a response arrives,
  composable with checkpoints.
- **OTel GenAI semconv v1.37 natively:** spans `invoke_agent` / `chat` / `execute_tool`
  with `gen_ai.*` attributes (agent id/name, usage tokens), histograms
  `gen_ai.client.operation.duration` + `gen_ai.client.token.usage`. **DevUI** local
  debug/run UI.

**Weaknesses:** Azure/Foundry gravity (durable execution beyond checkpoints requires
Azure Durable Task Scheduler), 21/24 Python packages still beta at GA, migration churn,
smaller OSS community. Checkpointing alone criticized as "a storage operation, not a
reliability guarantee" — DasLab must pair checkpoints with resume drills (T5).

### 3.3 CrewAI (crewAIInc/crewAI) — the specialist-depth donor

**Status:** 1.14.6 stable (2026-05-28), pushed today; 54.8k★; **MIT (verified)**; $18M
funded; enterprise = AMP suite (deploy/tracing/governance). Claims: 100k+ certified devs.

**Mechanisms that matter:**
- **Role anatomy.** Agent = role + goal + backstory — three compiled prompt functions:
  identity/competence frame, per-decision optimization target, behavioral priors. Tasks
  carry `description` + `expected_output` (explicit output contract per unit of work).
- **Flows.** Deterministic event layer: `@start` / `@listen` / `@router` (+ `and_`/`or_`
  combinators) over **typed pydantic state** with `@persist` (SQLite) checkpoints —
  "autonomy in the boxes, determinism in the arrows." Crews run *inside* flow steps.
- **Unified memory scoring.** Recall ranks by **semantic similarity + recency +
  importance** (tunable half-life), LLM-assigned scope/importance at save time,
  self-organizing scope tree, `forget(scope=…)`.
- **Guardrails.** `output_pydantic` schemas + guardrail fns returning (pass, feedback) →
  bounded retry-with-feedback per task.
- **`crewai test` / `train`.** N-iteration runs, LLM-judged 1–10 score table per
  task/agent/run; train persists human-feedback adjustments consumed on later runs.

**Weaknesses:** natural-language agent coordination (paraphrase chatter, ~18% token
overhead vs LangGraph in one 2026 bench), opaque debugging, hidden prompt templates,
loops/conditionals inside crews awkward. Common pattern: "prototype CrewAI, productionize
LangGraph" — i.e., its *ergonomics* are the asset, not its runtime.

### 3.4 Agency Swarm (VRSEN/agency-swarm) — the typed-routing donor

**Status:** v1.10.1 (2026-06-11); 4.4k★; **MIT (verified)**; VRSEN AI (dogfooded agency
business); v1.x rebuilt on OpenAI Agents SDK + Responses API; 92% test coverage.

**Mechanisms that matter:**
- **`communication_flows` = directional (sender, receiver) tuples.** Enforcement is
  structural: each declared flow registers the receiver into the sender's `SendMessage`
  tool schema — **an undeclared route is unrepresentable**, not merely discouraged.
  Routing constraints live in the tool schema, not in prompt hopes.
- **SendMessage mechanics:** synchronous request-response, control returns to caller
  (orchestrator-worker); parallel delegation via separate threads; `Handoff` variant
  transfers control + full history permanently.
- **Guardrail tripwires.** Input guardrails screen user *and* inter-agent messages;
  output guardrails return `(tripwire, feedback)` — tripped → feedback injected as
  system message → retry ≤ `validation_attempts` → escalate.
- **Manifesto + MasterContext.** Shared instructions prepended to every agent; run-scoped
  KV blackboard so tools share data without burning message tokens; full thread
  persistence via load/save callbacks.

**Weaknesses:** OpenAI lock-in, small community, no graph control flow / workflow
checkpointing / time-travel — conversation persistence only.

### 3.5 SuperAGI (TransformerOptimus/SuperAGI) — the ops-console donor (post-mortem)

**Status: effectively dead.** Last release v0.0.14 (2024-01); last commit 2025-01-22;
company pivoted to an AI-SDR SaaS; unpatched vulns; docs partially 404. 17.6k★ frozen.
**MIT (verified — some 2026 articles wrongly say Apache-2.0).** The SWOT threat
("if community pace drops, long-term reliance is risky") **fully materialized** —
vindicating DasLab's pattern-extraction-not-dependency strategy.

**Patterns worth harvesting (it pioneered the "agent ops platform" shape):** GUI ops
console (agent list, live run feed, logs) + Action Console (mid-run human input);
versioned agent templates + provisioning; task queue + resource manager (per-run file
workspaces); toolkit marketplace; **scheduler** (at-time / recurring / after-N-runs);
**APM** — per-agent/model/tool token & run dashboards with budget controls.

## 4 — 2026 landscape (adjacent, not donors)

- **OpenAI Agents SDK** — minimal primitives (handoffs, guardrails, sessions, tracing);
  Temporal integration GA 2026-03 gives it durable workflows. Confirms: durability +
  typed guardrails are the industry bar now.
- **Claude Code ecosystems** — Claude Flow renamed **Ruflo** (2026-01), v3.16, ~31k★,
  hive-mind topology, 87 MCP tools (self-reported benchmarks — treat skeptically);
  awesome-claude-code ~37k★; VoltAgent 100+ role packs. DasLab is already
  state-of-the-art on role-frontmatter subagents/hooks/memory-files; the ecosystem's
  only real lead is autonomous tempo.
- **Spec-driven development** — GitHub **Spec Kit** (`/constitution → /specify → /plan →
  /tasks → /implement`; constitution = non-negotiable principles; tasks are
  dependency-aware), **BMAD-METHOD** (persona agents; planning agents emit PRD +
  architecture; a scrum-master agent shreds them into **self-contained story files**
  carrying full context), **Agent OS** (Standards / Product / Specs three-layer docs;
  v3 defers execution to Claude Code Plan Mode). Together: the industry converged on
  exactly DasLab's "Project OS docs pack → build" thesis — but none has DasLab's
  governance gates. G9 closes with a fusion of all three.
- **Agent evals** — SWE-bench Verified saturating (~87.6%); frontier moved to SWE-bench
  Pro (~59–69%) and **Terminal-Bench 2.0** (89 tasks, 5 attempts, fractional credit);
  **HAL** (Princeton) standardizes **accuracy × cost** evaluation. Copy the *harness
  shape* (task dir + verifier script + k attempts + cost per solve), not the datasets.

## 5 — Capability matrix (author's assessment, 0–10)

| Capability | LangGraph | MAF | CrewAI | Agency Swarm | SuperAGI† | **DasLab 1.0** | **DasLab 2.0 target** |
|---|---|---|---|---|---|---|---|
| Durable execution (checkpoint/resume/replay) | **10** | 8 | 6 | 4 | 4 | 4 | **10** |
| Dynamic planning + stall detection | 6 | **9** | 6 | 5 | 3 | 4 | **10** |
| Typed contracts + routing enforcement | 7 | **9** | 7 | **9** | 3 | 4 | **10** |
| Guardrails / bounded retry loops | 5 | 7 | **8** | **9** | 3 | 5 | **9** |
| Autonomous tempo / scheduling | 5 | 6 | 7 | 4 | **8** | 2 | **9** |
| Observability (spans, tokens, cost) | 6* | **10** | 7 | 5 | 8 | 4 | **10** |
| Ops cockpit | 5* | 7 | 6* | 4 | **9** | 4 | **9** |
| Specialist role depth | 4 | 5 | **9** | 7 | 6 | 7 | **10** |
| Per-agent evals / training loop | 6* | 6 | **8** | 4 | 5 | 2 | **9** |
| Long-term memory governance | 7 | 6 | **8** | 5 | 5 | 8 | **9** |
| Governance / compliance / gates | 3 | 6 | 4 | 5 | 3 | **10** | **10** |
| Spec→build pipeline (docs pack → tickets) | 3 | 3 | 4 | 3 | 2 | 5 | **10** |

\* = strong only via paid platform (LangSmith / AMP). † = historical (unmaintained).
**Read:** DasLab already owns the governance moat no donor has; every other row is
closable by pattern reimplementation. No donor is strong on >4 rows; DasLab 2.0 targets
≥9 on all 12.

## 6 — Extraction map: 22 patterns → 7 workstreams

| WS | Codename | Patterns (donor → mechanism) | Kills gap |
|----|----------|------------------------------|-----------|
| WS1 | **PULSE** — durable execution core | P1 super-step wave checkpoints + per-ticket pending writes (LangGraph); P2 run_id resume cursor + time-travel fork (LangGraph); P3 typed interrupt/resume Founder-gate objects (LangGraph); P4 per-zone merge policies/reducers (LangGraph); P5 Send+defer dynamic fan-out/fan-in tickets (LangGraph); P6 input-hash node cache (LangGraph) | G1 |
| WS2 | **LOOM** — typed orchestration | P7 dual-ledger planner + stall counter + bounded replan (MAF); P8 produces/consumes schemas + build-time plan validation (MAF); P9 schema-enforced communication flows (Agency Swarm); P10 guardrail tripwires with bounded retry-with-feedback (Agency Swarm + CrewAI) | G3, G4 |
| WS3 | **BRIDGE** — observability | P11 OTel GenAI-semconv span JSONL in the event store (MAF); P12 cost/token ledger per ticket/agent/model + budgets (SuperAGI APM); P13 committed KPI evidence snapshots (audit finding) | G5, G6 |
| WS4 | **HEARTBEAT** — autonomous tempo | P14 event-driven flow router — @start/@listen/@router equivalents over `.events.jsonl`, pure-Python routing (CrewAI Flows); P15 scheduler: cron/launchd + `board/schedule.yaml` + after-N-runs triggers + budget governor (SuperAGI); P16 per-run workspaces `runs/<id>/` (SuperAGI) | G2 |
| WS5 | **COCKPIT** — ops console | P17 live cockpit from event store: run feed, per-agent success/tokens, per-tool usage, budget view, Action Console for pending interrupts (SuperAGI + MAF DevUI) | G7 |
| WS6 | **GUILD** — specialist depth | P18 role templates: role/goal/backstory-grade overlays + toolkit + eval baseline + escalation, compiled by `gen_subagents.py` (CrewAI + SuperAGI); P19 per-agent eval harness — `evals/<agent>/<task>/` + `verify.py`, k attempts, accuracy×cost, haiku-judge (HAL + Terminal-Bench + `crewai test`); P20 `## Learned` training loop from Founder feedback (CrewAI train); P21 ArcRift recall ranking = similarity+recency+importance half-life (CrewAI memory) | G8 |
| WS7 | **GATEWAY** — Project-OS compiler | P22 spec compiler fusion: constitution=QONUN (Spec Kit) + three-layer docs (Agent OS) + self-contained story tickets (BMAD) → `spec_compile.py`: docs pack → queue check → stage-gated story tickets with embedded context/acceptance/gate tags | G9 |

## 7 — IP & Clean-Room Donor Protocol (binding for the build)

All five donors are MIT-licensed (verified). Legal position, plainly:

1. **Patterns, algorithms, architectures, and ideas are not copyrightable.** Native
   reimplementation from this document (mechanism descriptions, not source) creates
   **100% DasLab-original code with zero attribution obligation** — nothing to disclose,
   in code comments or anywhere else, because nothing is copied.
2. **Verbatim or near-verbatim code copying is forbidden in this program.** MIT requires
   preserving the copyright + permission notice on copies; stripping it would be a
   license violation. The clean rule that satisfies both law and the "everything is
   ours" goal: *never copy code — re-derive from the mechanism*. If a future exception
   is ever made, the notice goes in `legal/THIRD-PARTY-NOTICES.md` — non-negotiable.
3. **No donor imports.** None of the five libraries enters `requirements*.txt`.
4. **Naming hygiene.** DasLab names its own concepts (wave-checkpoint, progress-ledger,
   flow-router…); no donor trademarks in code, docs, or marketing claims.
5. **Engineering memory only:** donor provenance of each pattern lives in ArcRift +
   this report (internal), so future sessions can re-verify mechanisms — a due-diligence
   ledger, not a public attribution.

## 8 — Win conditions (beating each donor on home turf)

- **vs LangGraph (durability):** kill-mid-wave drill → resume with zero lost/duplicated
  tickets, T5 ≥ 0.99, time-travel fork of a past wave — file-native, no Postgres, no
  paid platform.
- **vs MAF (orchestration+observability):** dual-ledger planner live in `/daslab-cycle`
  with stall→replan events + 100% dispatches emitting GenAI-semconv spans — without
  Azure.
- **vs CrewAI (specialists):** all 32 agents pass ≥80% of their golden evals at their
  assigned model tier, with a working test→learn loop — and typed coordination instead
  of NL chatter.
- **vs Agency Swarm (typed routing):** undeclared agent→agent route is structurally
  unrepresentable AND validator-enforced — plus durability it lacks entirely.
- **vs SuperAGI (ops):** live cockpit + scheduler + APM that is *maintained* — and a
  governance layer it never had.
- **Unique moat kept:** QONUN laws, AADL gates, anti-gaming metric contract, ArcRift
  memory law, Founder goal queue — no donor has an equivalent.

## 9 — Sources

**LangGraph:** github.com/langchain-ai/langgraph (+ /blob/main/LICENSE) · langchain.com/blog/langchain-langgraph-1dot0 · docs.langchain.com/oss/python/langgraph/{persistence, checkpointers, durable-execution, interrupts, use-time-travel, pregel, graph-api, use-graph-api, streaming, stores} · github.com/langchain-ai/deepagents · langchain.com/pricing · zenml.io/blog/langgraph-pricing · uvik.net/blog/langchain-vs-langgraph · open-techstack.com/blog/langgraph-vs-openai-agents-sdk-vs-pydanticai-2026 · speakeasy.com/blog/ai-agent-framework-comparison
**MAF:** github.com/microsoft/agent-framework · pypi.org/project/agent-framework · devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0 · learn.microsoft.com/en-us/agent-framework/{workflows/workflows, workflows/edges, workflows/checkpoints, workflows/orchestrations/magentic, agents/observability, overview} · learn.microsoft.com/python/api/agent-framework-core/agent_framework.standardmagenticmanager · microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks · diagrid.io/blog/still-not-durable-how-microsoft-agent-framework-and-strands-agents-repeat-the-same-mistake · joshuaberkowitz.us (MAF risk assessment) · datarekha.com/blog/microsoft-agent-framework-production
**CrewAI:** github.com/crewAIInc/crewAI (+ LICENSE, releases) · docs.crewai.com/en/concepts/{agents, flows, memory, tasks, testing, knowledge} · docs.crewai.com/en/observability/overview · crewai.com/enterprise · pulse2.com/crewai-multi-agent-platform-raises-18-million-series-a · redwerk.com/blog/langgraph-vs-crewai · markaicode.com/vs/langgraph-vs-crewai-multi-agent-production
**Agency Swarm:** github.com/VRSEN/agency-swarm (+ LICENSE, releases, src/agency_swarm/tools/send_message.py) · agency-swarm.ai/{core-framework/agencies/communication-flows, additional-features/guardrails/output-guardrails, additional-features/agency-context, references/api, migration/guide}
**SuperAGI:** github.com/TransformerOptimus/SuperAGI (+ LICENSE, releases, issue #1460) · datacamp.com/blog/superagi (Feb 2026 status) · superagi.com/docs (APM)
**Landscape:** openai.github.io/openai-agents-python · temporal.io/blog/announcing-openai-agents-sdk-integration · github.com/ruvnet/ruflo · github.com/hesreallyhim/awesome-claude-code · github.com/VoltAgent/awesome-claude-code-subagents · github.com/github/spec-kit · developer.microsoft.com/blog/spec-driven-development-spec-kit · github.com/bmad-code-org/BMAD-METHOD · github.com/buildermethods/agent-os · morphllm.com/swe-bench-pro · hal.cs.princeton.edu · arxiv.org/pdf/2601.11868 (Terminal-Bench 2.0)
