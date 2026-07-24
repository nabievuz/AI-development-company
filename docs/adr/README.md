# Architecture Decision Records (ADRs)

Each ADR records one significant, hard-to-reverse decision: its **context**, the
**decision**, and the **consequences** we accept. ADRs are append-only — a
superseded decision gets a new ADR that references the old one, rather than an
edit in place. New ADRs take the next free number.

| # | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-status-handoff-protocol.md) | Completion status protocol + finding format | Accepted | 2026-06-06 |
| [0002](0002-enforcement-as-code.md) | Enforcement-as-code — advisory laws become CI-gating validators | Accepted | 2026-06-18 |
| [0003](0003-self-locating-root.md) | Self-locating repository root (no hardcoded paths) | Accepted | 2026-06-18 |
| [0004](0004-project-agnostic-engine.md) | Project-agnostic engine (one factory, any goal) | Accepted | 2026-06-18 |
| [0005](0005-worktree-per-ticket-dispatch-ownership.md) | Worktree-per-ticket dispatch ownership | Proposed | 2026-06-19 |
| [0006](0006-static-cache-prefix-layout.md) | Static cache-prefix layout + invalidation rule | Proposed | 2026-06-19 |
| [0007](0007-model-retier-cascade-boundary.md) | Model re-tier boundary: haiku-eligible vs. opus floor | Proposed | 2026-06-19 |
| [0008](0008-nonblocking-arcrift-memory-loop.md) | Non-blocking ArcRift memory loop | Proposed | 2026-06-19 |
| [0009](0009-harness-owns-transport-admission-layer.md) | Harness owns the LLM transport — LAW 8 is an admission layer, a proxy only in a future SDK runner | Proposed | 2026-06-19 |
| [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) | Adopt DGO-X — graph-orchestrated, gate-driven control plane; phased + feature-flagged | Accepted | 2026-06-20 |
| [0011](0011-dgox-phase-1-data-contracts.md) | DGO-X Phase-1 data contracts — `graph_state`, append-only event store, board adapter, shadow-mode rule | Accepted | 2026-06-20 |
| [0012](0012-dgox-event-store-content-classification-redaction-policy.md) | DGO-X event store content-classification + redaction policy (the P2/P3 tool-event security contract) | Accepted | 2026-06-22 |
| [0013](0013-effort-tier-boundary.md) | Effort-tier boundary — per-role `effort` under a fixed opus floor | Accepted | 2026-06-26 |
| [0014](0014-native-clarify-gate.md) | Native ticket-altitude Clarify gate — `[NEEDS CLARIFICATION]` marker + Definition-of-Ready | Accepted | 2026-06-26 |
| [0015](0015-spec-driven-epic-layer.md) | Size-gated per-epic `SPEC.md` + `FR-NNN`/`SC-NNN` traceability | Accepted | 2026-06-26 |
| [0016](0016-ticket-dependency-graph.md) | Machine-readable ticket dependency graph (`depends_on` + `zone`) | Accepted | 2026-06-26 |
| [0017](0017-release-scorer-real-quality.md) | Release scorer measures real quality (ruff gate), not just artifact presence | Accepted | 2026-06-27 |
| [0018](0018-role-overlay-contract.md) | Role-overlay contract — Mission / Scope / Definition of Done / Escalation in every overlay | Accepted | 2026-06-27 |
| [0019](0019-latent-machine-feature-flags.md) | Latent-machine feature flags — DGO-X shadow + T4/T7 governors default OFF | Accepted | 2026-06-27 |
| [0020](0020-gate-promotion-no-false-green.md) | Gate promotion — warn→enforce only with data discipline; unmeasured is SKIPPED, not green | Accepted | 2026-06-27 |
| [0021](0021-fail-closed-ruff-gate.md) | The lint gate is fail-closed — an absent `ruff` fails the Code-quality dimension; an unmeasured lint never scores 100 | Accepted | 2026-06-27 |
| [0022](0022-semantic-versioning-policy.md) | Semantic versioning & release policy — `VERSION` + `CHANGELOG.md` + annotated tags / GitHub Releases; the release gate enforces VERSION/CHANGELOG | Accepted | 2026-06-29 |
| [0023](0023-run-model.md) | Run-model — `run_id`=ULID, `board/runs/<run_id>/` (manifest + per-wave delta checkpoints), gitignored except the retained summary; reuses the existing `routing_decision`/`recovery_drill` event contract so replay/recovery score unchanged | Accepted | 2026-07-03 |
| [0024](0024-span-event-schema.md) | Span-event schema — append-only `span` event (`trace_id`=ticket id, `span_id`/`parent_span_id` tree, `kind` ∈ {invoke_agent, chat, execute_tool, wave, run}, agent/model, timing, token+cache accounting, `status`) using OTel GenAI semantic-convention attribute names so a real OTel exporter is a trivial adapter; extends the ADR 0011 event store, reconciles `graph_state.trace_ids` as a derived pointer-mirror | Accepted | 2026-07-03 |
| [0025](0025-events-load-bearing.md) | The event store is LOAD-BEARING (producers + operator-invoked `--resume`/`--fork` recovery reader) — narrows, by reference, ADR 0010 §5 C3 / ADR 0011 §4's "advisory-only shadow record" framing to *normal-wave* dispatch (flag-on == flag-off preserved); determinism/anti-gaming now guaranteed by committed evidence (P13) + immutable T7 + R-9; refines `test_dgox_phase1_shadow.py` from a per-file producer allowlist to a principled reader-vs-router rule | Accepted | 2026-07-03 |
| [0026](0026-communication-flows.md) | Communication-flows format + GATE-1/6 owner reconciliation — `governance/communication-flows.yaml` is a DERIVED directional-edge view: `(sender, receiver)` tuples with `kind` ∈ {delegation, escalation}, `source` provenance, role keys drawn from the SSOTs and diff-checked against them (undeclared route unrepresentable). Fixes the gate-owner reading: AADL RACI §1 = the single Accountable (GATE-1 cpo, GATE-6 coo), schema `gate_owner` = the signer set (GATE-1 {founder, cpo}, GATE-6 {cto}) — complementary, no A↔A. `founder` = external human gate above chairman, NOT one of the 32 fleet nodes (never emitted as sender/receiver). Interprets — never edits — `ai-agent-lifecycle.md` / `schema.daslab.yaml` / `ROUTING.md` | Accepted | 2026-07-03 |
| [0027](0027-scheduler-safety.md) | Scheduler safety model — the ORGANISM tempo substrate (WS4 HEARTBEAT) is a SHADOW-MODE, operator-invoked heartbeat (`loop_controller.py --tick` via an OPTIONAL, Founder-enabled launchd/cron entry), **NOT a daemon**. Seven binding scheduler invariants: SI-1 one-shot `--tick`, at most one wave, no in-process timer; SI-2 `loop.yaml` stays `shadow`+`auto_apply:false` so `check_loop_mode.py` stays exit 0 (calls `loop_controller.evaluate_promotion`, never reimplements it); SI-3 break-glass kill-switch honored; SI-4 quiet hours; SI-5 per-run/per-day budget caps (`budgets.yaml` + cost-ledger) as a hard dispatch ceiling; SI-6 `max_concurrent_waves = 1`; SI-7 never-auto-approve (gates/interrupt-cards ALWAYS wait for the Founder), live only on an explicit Founder flag-flip after a ≥ 3-day clean shadow window (distinct from `loop_controller`'s ≥ 7-day loop-promotion clock). Constrains — never edits — `loop.yaml` / `check_loop_mode.py` / `break_glass.py` / `features.yaml` / `budgets.yaml` | Accepted | 2026-07-03 |
| [0028](0028-cockpit-form-factor.md) | Cockpit form-factor (ORGANISM WS5 COCKPIT, O5-T01) — the operator cockpit is delivered as **zero-infra, local HTML: static-regeneration-first, with an OPTIONAL stdlib `http.server` live mode**, **NOT a daemon**, no external service, no JS build step. Six binding form-factor invariants: D-1 canonical = static regen to a self-contained `file://` HTML snapshot (default shipped state); D-2 auto-refresh via `<meta http-equiv="refresh">` (no JS at all); D-3 optional stdlib `http.server` live mode, loopback-only, operator-invoked/foreground, regenerate-on-request; D-4 EXTENDS `cockpit.py` `render()`/`_render_panel`/`NODATA` — the HTML wrapper (`cockpit_html.py`, DAS-1482) imports the panel data-binding funcs, never a second cockpit; D-5 degrade-to-static is structural (base case, not a bolted-on path) with generated-at timestamp + inherited `NODATA` non-fabrication; D-6 self-contained single artifact (inline CSS, no CDN/font/analytics/`fetch`). Constrains — never edits — `scripts/cockpit.py` / `trends.py` / the event store + cost-ledger sources | Accepted | 2026-07-03 |
| [0029](0029-guild-model.md) | Guild model (ORGANISM WS6 GUILD, O6-T01) — a **guild is per-ROLE craft**, captured as a compilable agent-template `governance/agent-templates/<role>.md`, **grouped by dept**, with **NO new org unit** (resolves §9 Q5 guild=dept-vs-craft by ruling *craft*). Five binding invariants: G-1 one template per role key, grouped by dept, no new node/edge/schema change; G-2 closed craft field set (identity/goal/behavioral-priors, toolkit allowlist, `model`+`effort`, `produces`/`consumes` defaults, allowed comm-flows routes, eval-baseline ref, a `## Learned` sink); G-3 `model`+`effort` **VERBATIM** from `model-allocation.md`, no Tier F / Fable 5 (haiku omits `effort`); G-4 compiles via `gen_subagents.py` → `.claude/agents/` (generate-and-diff clean), guarded by `check_agents_sync.py` (**not** `check_org_drift`); G-5 a template references — never re-decides — any SSOT, `## Learned` grows only via `daslab-learn` distillation of Founder-accepted feedback. Constrains — never edits — `scripts/gen_subagents.py` / `check_agents_sync.py` / `model-allocation.md` / `communication-flows.yaml` | Accepted | 2026-07-03 |
| [0030](0030-project-os-pack.md) | PROJECT-OS-PACK — the canonical, machine-readable **input contract** a Founder hands DasLab to bootstrap an AI-agent project (ORGANISM WS7 GATEWAY, O7-T01; kills G9 "no intake compiler"). A decision doc + companion spec of record (`docs/specs/PROJECT-OS-PACK.md`). One pack, four parts, rooted at `projects/<name>/`. Six binding invariants: D-1 exactly one `projects/<name>/PROJECT-OS.yaml` manifest at the project root; D-2 closed manifest field set (`name`, `mission`, `constraints`, `stack`, `budget`, `success_metrics`); D-3 the **canonical** AADL §2 `docs/01-planning…06-maintenance` six-stage skeleton, **NOT qaqnuz's divergent names**; D-4 the Founder discovery answers (≥10 Q&A or waiver); D-5 the Founder-approved `APPROVED-GOAL-QUEUE.md` (`APPROVED:`/`TASDIQLANDI:` via `check_approved_goal_queue.py`); D-6 Constitution = QONUN laws + project-local constraints, project-local NEVER relaxes org law (precedence: root `AGENTS.md` §2 + AADL scope note; org law wins on conflict). Constrains — never edits — `ai-agent-lifecycle.md` / `check_approved_goal_queue.py` / the board schema / the QONUN laws; O7-T02 `gateway_compile.py` validates a real pack against it | Accepted | 2026-07-03 |
| [0032](0032-harness-forced-attestation.md) | Harness-forced attestation + reconciliation (ORGANISM WS9 HARNESS) — **extends** [ADR 0031](0031-wave-runner-attestation.md), does not replace it. `run_wave` ATOMICALLY co-produces, with each committed `WaveAttestation`, a COMMITTED, append-only, hash-chained entry in a TRACKED `board/wave-ledger.jsonl` (NOT the gitignored `board/.wave-log`): the exact eight-field `{run_id, wave, ticket_ids, attestation_path, attestation_hash, prev_hash, self_hash, created_at}`, whose `prev_hash`/`self_hash` form a second committed chain (self-exclusion hashing, ADR 0023 §2) independent of the attestation's own `attest_chain`. A new `scripts/check_wave_reconciliation.py` gates CI + diagnostics on: **(a) bijection** committed ledger ⇄ committed attestations (matching ticket set + `attestation_hash`, no orphan either way); **(b) per-run wave-sequence chain continuity** (the ledger hash-chain verifies AND each run's `wave` indices are gap-free — a recorded-but-skipped wave FAILS); **(c) board terminality + coverage** — every attested ticket is `done`, and every board ticket that became `done` **after** the committed `board/.attestation-baseline` (HEAD SHA at regime start, grandfathering pre-regime `done` tickets so the existing 62/62-done repo stays green) is covered by a committed ledger entry (the harness-forcing arm). Fail-closed on real data, inert-by-design on an empty regime (ADR 0020). Going forward a wave that commits done-ness through `run_wave` cannot do so without a durable reconciled attestation + ledger, so omission/tampering of any RECORDED wave and any uncovered post-baseline `done` transition is CI-detectable. Residual recorded with total honesty: this HARNESS-forces attestation for any wave that commits ANY work and moves the residual from "silent omission leaves no trace" to "omission breaks a committed chain" — NOT to zero. The irreducible floor is a wave that commits absolutely nothing (which also delivered nothing); an LLM-driven runtime cannot be forced below that floor without removing the LLM. Reuses — never edits — `scripts/wave_runner.py` / `scripts/check_attestation.py` / `scripts/snapshot_evidence.py` / ADR 0023–0025 / ADR 0031 | Accepted | 2026-07-04 |
| [0031](0031-wave-runner-attestation.md) | Wave-runner + attestation (ORGANISM WS8 ATTEST, O8-T01) — the wave LIFECYCLE MECHANICS move from `daslab-cycle` SKILL **prose** into a deterministic `scripts/wave_runner.py` with one entry point `run_wave(plan, results)`; the orchestrator LLM supplies the routing `plan` + collected `results` as **data** and makes **no mechanical decision inside the runner**, so **flag-on == flag-off DISPATCH DECISIONS** (ADR 0025) is preserved at a function boundary (post-decision mechanics, `organism_emit`-gated). `run_wave` REUSES the existing producers — emits `run_start`/`run_end`/`span` (`dispatch_emitter`), writes wave checkpoints + ticket-ledger (`pulse_checkpoint`), runs per-role guardrails (`guardrail_dispatch`), snapshots committed evidence (`snapshot_evidence`) — and writes a COMMITTED, small+redacted, hash-chained `WaveAttestation` to `metrics/attestations/<run_id>.json`. A new `check_attestation` CI validator gates completeness + integrity (fail-closed on counted runs, inert-by-design on an empty board). Gives the previously-perma-inert event gates teeth via (a) an end-to-end test driving a wave THROUGH the deterministic runner and (b) committed attestations checked in CI. Residual recorded honestly: whether the LLM CALLS `run_wave` is still compliance, but the trust surface shrinks from a prose checklist to ONE call and done-ness flows THROUGH it (no attestation → CI fails → non-compliance detectable, not silent). Reuses — never edits — `dispatch_emitter` / `pulse_checkpoint` / `guardrail_dispatch` / `snapshot_evidence` / ADR 0023–0025 | Accepted | 2026-07-04 |
| [0033](0033-ecosystem-tool-mcp-bridge.md) | Ecosystem-tool MCP bridge — external tools (browser/computer-use + the LangChain catalog) enter ONLY as out-of-process MCP sidecars wired in `.mcp.json`, governed at the MCP edge. Five invariants: TB-1 out-of-process sidecar (engine stays server-free); TB-2 least-privilege per-role allow-list (no global grants); TB-3 `PreToolUse` audit/deny + ADR-0012 redaction on every external-tool call; TB-4 browser/computer-use gated (untrusted egress, HEARTBEAT envelope under autonomy, never past an AADL gate); TB-5 feature-flagged OFF, no dispatch change on merge. Builds on ADR 0009 / 0012 / 0010 §5 (C1–C6). | Accepted | 2026-07-24 |
| [0034](0034-agent-sdk-headless-runner.md) | Claude Agent SDK headless runner — the future SDK-based runner ADR 0009/0010 deferred. A thin `daslab_sdk` runner dispatches a ticket/wave programmatically, loading the repo's own `.claude/agents`+skills+hooks+`.mcp.json` via `setting_sources=['project']` (SR-1: NO `create_agent` rebuild); model explicit per dispatch = the ADR-0009 admission gateway under the SDK (SR-2); calls `run_wave`, no mechanical decision, flag-on==flag-off preserved (SR-3, ADR 0025/0031); board canonical + Git law (SR-4); additive, `/daslab-cycle` stays default, flag OFF (SR-5). Upstream of ADR 0035/0036. | Proposed | 2026-07-22 |
| [0035](0035-langgraph-dgox-execution-substrate.md) | LangGraph as the DGO-X P2/P3 execution substrate — adopt LangGraph as the executing engine for the DGO-X supervisor/gate-engine/sandbox phases: graph_state to LangGraph state, AADL gates to conditional edges + `interrupt()`, nodes to Agent SDK dispatch (ADR 0034), checkpoint/resume to the run-model (ADR 0023). Five invariants: LG-1 substrate UNDER DGO-X, never top-level truth (C1), board canonical (C2); LG-2 gate = edge/interrupt, never dispatch past an open gate (C4); LG-3 workers never write routing fields (C3); LG-4 checkpoints reconcile with the ADR 0023 run-model + 0031/0032 attestation, flag-on==flag-off (ADR 0025); LG-5 phased + `dgox_emit`-flagged, shadow before drive. Extends ADR 0010. | Proposed | 2026-07-22 |
| [0036](0036-outbound-interop-surface-langsmith.md) | Outbound interop surface + LangSmith observability — expose DasLab's governed delivery to the ecosystem (adoption/community) and add a live watch-it-work pane. OB-1 DasLab as a LangGraph node/subgraph and/or MCP server (consumed via langchain-mcp-adapters), backed by the ADR-0034 runner, governance rides along (external caller cannot skip a gate); OB-2 LangSmith is an OTLP export target for the ADR-0024 spans (already `gen_ai.*`-named) — a lens, not the audit system-of-record (event store canonical, ADR 0025); OB-3 same admission/redaction (ADR 0009/0012) at the outbound edge; OB-4 optional/flagged, publishing = Founder act. | Proposed | 2026-07-22 |
| [0037](0037-end-to-end-autonomous-delivery-target.md) | End-to-end autonomous delivery target (MUSTAQIL completion contract) — binds what 'finished' (0->100) means and reconciles 'no unplanned stops' with never-auto-approve. ED-1 'finished' = evidence only (all AADL gates + merged-PR+green-CI + committed attestation 0031/0032 + 100/100 diagnostics + anti-gaming evals; no false-green 0020); ED-2 the only legit halt is a Founder/AADL gate (QONUN-5), resume on APPROVED:/TASDIQLANDI:, not a failure; ED-3 no fabrication (ArcRift recall/store, [NEEDS CLARIFICATION] on unknowns, never invent API/result/test); ED-4 beat the reliability cliff (per-wave goal re-anchor + checkpoint 0023 + WIP=1 + sub-goal decomposition); ED-5 honest scope = scoped Founder-approved goals, proven by one project (G6). Umbrella over ADR 0033-0038 + 0027. | Proposed | 2026-07-22 |
| [0038](0038-enterprise-internal-self-host-hardening.md) | Enterprise-internal self-host hardening (MUSTAQIL WS-E TENANT) — enterprise = INTERNAL self-host (company runs DasLab on its own infra to build its own software; code/IP in-tenant), NOT a sellable SaaS shell. TN-1 in-tenant only (self-host sandbox + Langfuse + tools; nothing leaves the tenant, redaction 0012); TN-2 remove single-user/macOS assumptions (self-locating paths 0003, Linux-first); TN-3 RBAC mapped to the 32-role org + Founder gate (never-auto-approve is human-only; an agent can never approve a gate); TN-4 audit export to the tenant SIEM (event store + attestation as redacted OTel/JSON); TN-5 secrets/egress policy (tenant vault; browser = untrusted egress; egress allow-list). Scope boundary BINDING: SOC 2 / SSO / multi-tenant / billing are OUT of scope. | Proposed | 2026-07-22 |
| [0039](0039-self-hosted-web-control-plane.md) | Self-hosted web control plane (MUSTAQIL WS-H CONTROL) — EXTENDS the read-only cockpit (ADR 0028) into a browser control surface a tenant runs on its own Ubuntu/macOS server: submit goals, approve gates, trigger + watch runs. CP-1 extends the ADR-0028 render seam (one cockpit + a controller layer, not a second view); CP-2 networked but RBAC-gated, no anonymous access, in-tenant only (ADR 0038 TN-1/TN-3); CP-3 governed writes only (submit-goal / trigger-run via ADR-0034 runner / approve-deny), each RBAC-authorized + audited (0024/0025) + redacted (0012), and NEVER self-approving — only a Founder-role identity signs a gate (QONUN-5); CP-4 board stays canonical, dashboard is a view+controller not a source of truth (C2); CP-5 NOT-a-daemon reconciled (optional Founder-enabled process, flagged OFF, degrade-to-static, dispatches nothing itself); CP-6 in-tenant/self-host, no external SaaS. Extends ADR 0028. | Proposed | 2026-07-22 |
| [0041](0041-agentic-search-first-retrieval-strategy.md) | Retrieval strategy — agentic-search-first (grep / Read / `07-CONTEXT-PACK` / ArcRift recall are the default; no vector DB by default), ratifying Founder Q11. Five invariants: RT-1 agentic-search-first is the default retrieval path; RT-2 no vector DB by default (engine stays server-free); RT-3 indexed retrieval (e.g. claude-context) is an escape hatch gated by BOTH a large-repo metric AND an approving ADR; RT-4 the index is NEVER canonical — `board/tickets/` + repo files stay the source of truth (C2), file wins on disagreement; RT-5 if built, the index enters as a governed tool through the ADR-0033 MCP edge, never as core runtime. Builds on ADR 0033 / 0010 §5 (C1–C6) / 0008. | Accepted | 2026-07-24 |

## Themes

- **Foundations ([0001](0001-status-handoff-protocol.md)–[0004](0004-project-agnostic-engine.md)).**
  The completion/handoff protocol, enforcement-as-code (laws become CI-gating
  validators with `diagnostics.py` as the 100/100 release gate), a self-locating
  repository root, and the project-agnostic engine principle.
- **Concurrency, cost & memory ([0005](0005-worktree-per-ticket-dispatch-ownership.md)–[0009](0009-harness-owns-transport-admission-layer.md)).**
  Worktree-per-ticket dispatch ownership, a byte-stable static cache prefix,
  the model re-tier boundary under a fixed opus floor, the non-blocking ArcRift
  memory loop, and the honest ceiling that the harness owns the LLM transport
  (LAW 8 is an admission layer, not a transport proxy).
- **DGO-X control plane ([0010](0010-adopt-dgox-graph-orchestrated-control-plane.md)–[0012](0012-dgox-event-store-content-classification-redaction-policy.md)).**
  Adopting the graph-orchestrated, gate-driven control plane (phased and
  feature-flagged, in shadow mode), its Phase-1 data contracts, and the event
  store's content-classification + redaction policy.
- **Planning, quality & release gates ([0013](0013-effort-tier-boundary.md)–[0022](0022-semantic-versioning-policy.md)).**
  Per-role effort tiers, the Clarify gate / Definition-of-Ready, the optional
  size-gated spec layer and ticket dependency graph, a real-quality release
  scorer, the role-overlay contract, latent-machine feature flags,
  data-disciplined gate promotion (no false green), a fail-closed lint gate, and
  the semantic-versioning & release policy.
- **Durable execution — ORGANISM WS1 PULSE ([0023](0023-run-model.md)–).**
  The run-model: a ULID `run_id`, a `board/runs/<run_id>/` artifact tree (wave-plan
  manifest + per-wave delta checkpoints with board-hash, event offset, ledger-hash
  chain and pending interrupts), gitignored runtime state except a retained
  human-readable summary. It extends — never forks — the ADR 0011 event store,
  reusing the `routing_decision` + `recovery_drill` contract and the reserved
  `run_start`/`run_end` types so the replay/recovery scorers keep working unchanged.
- **Observability & tracing — ORGANISM WS3 BRIDGE ([0024](0024-span-event-schema.md)–).**
  The span-event schema: an append-only `span` event that ties the ADR 0011 event
  store into a timed parent/child trace tree (`trace_id` = ticket id,
  `parent_span_id` chain, `kind` ∈ {invoke_agent, chat, execute_tool, wave, run})
  with agent/model identity, start/end/duration, and input/output/cached token
  accounting. It adopts the OpenTelemetry **GenAI semantic-convention attribute
  names** (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`, …) as the persisted
  field names so a real OTel exporter is a field-mapping shim, keeps the same
  append-only / caller-supplied-`created_at` discipline, and reconciles
  `graph_state.trace_ids` as a derived mirror of pointers into the canonical span
  stream (ADR 0011 §1).
- **Event store is load-bearing — ORGANISM supersession ([0025](0025-events-load-bearing.md)–).**
  Canonicalizes what the durable-execution core revealed: `board/.events.jsonl` is
  **load-bearing** as a producer substrate (the emitter/checkpoints light up the
  T-gates) and as the operator-invoked `--resume`/`--fork` recovery reader. It
  **narrows by reference** — never edits in place — ADR 0010 §5 C3 and ADR 0011 §4's
  "advisory-only shadow record" framing so it holds only for *normal-wave* dispatch
  (flag-on == flag-off preserved; producers and the recovery path are the sanctioned
  exceptions). The determinism/anti-gaming the old rule protected is now guaranteed
  differently — committed evidence (P13), the immutable T7 rubric, and R-9
  (`merged_pr` + green `ci_status` + `t7_pass`) — and the `test_dgox_phase1_shadow.py`
  P1 scan is refined from a per-file producer allowlist to a principled
  reader-vs-router rule (flag only a script that both READS the store and ROUTES the
  normal wave, outside the recovery gate).
- **Typed orchestration — ORGANISM WS2 LOOM ([0026](0026-communication-flows.md)–).**
  The communication-flows format: `governance/communication-flows.yaml` is a
  **derived, validatable** view of the org graph — each edge a directional
  `(sender, receiver)` tuple with `kind` ∈ {`delegation` (down the reporting
  chain), `escalation` (up it)} and a `source` provenance, role keys drawn from
  `board/ROUTING.md` and the `schema.daslab.yaml` escalation ladder, so
  `check_comm_flows.py` can diff it against the SSOTs and make an undeclared route
  structurally unrepresentable. It also fixes two long-ambiguous readings **without
  editing any SSOT**: the AADL RACI (`ai-agent-lifecycle.md` §1) is the single
  **Accountable** per gate (GATE-1 `cpo`, GATE-6 `coo`) while
  `schema.daslab.yaml:gate_owner` is the **signer set** (GATE-1 `{founder, cpo}`,
  GATE-6 `{cto}`) — complementary, not an `A↔A` conflict; and `founder` is an
  **external human gate above the chairman**, not one of the 32 fleet routing
  nodes, so it is never emitted as a `sender`/`receiver`.
- **Autonomous tempo — ORGANISM WS4 HEARTBEAT ([0027](0027-scheduler-safety.md)–).**
  The scheduler safety model: the tempo substrate is a **shadow-mode,
  operator-invoked heartbeat** (`scripts/loop_controller.py --tick`, driven by an
  **optional, Founder-enabled** launchd/cron entry) — resolving the "NOT a daemon"
  law against the "autonomous tempo" goal by putting cadence in an external OS entry
  the Founder owns while the process stays a one-shot `--tick`. It fixes seven
  **binding scheduler invariants** (SI-1…SI-7): one wave per tick with no in-process
  timer; `loop.yaml` stays `shadow`+`auto_apply:false` so `check_loop_mode.py` stays
  exit 0 (the heartbeat *calls* `loop_controller.evaluate_promotion`, never
  reimplements the clean-day/GATE-6 rule); break-glass kill-switch honored; quiet
  hours; per-run/per-day budget caps (`budgets.yaml` + cost-ledger) as a hard
  dispatch ceiling; `max_concurrent_waves = 1`; and the never-auto-approve law —
  gates and interrupt-cards **always** wait for the Founder, with live dispatch
  reachable only via an explicit Founder flag-flip after a ≥ 3-day clean shadow
  window (a conservative go-live clock kept distinct from `loop_controller`'s ≥ 7-day
  loop-promotion clock). It **constrains — never edits** — `loop.yaml`,
  `check_loop_mode.py`, `break_glass.py`, `features.yaml`, and `budgets.yaml`; the
  WS4 implementation tickets (O4-T02 flow-router, O4-T03 scheduler, O4-T06
  safety-rail drills) build against this contract.
- **Operable cockpit — ORGANISM WS5 COCKPIT ([0028](0028-cockpit-form-factor.md)–).**
  The cockpit form-factor: the operator cockpit reaches a browser as **zero-infra,
  local HTML that is static-regeneration-first**, with an **optional** stdlib
  `http.server` live mode — resolving the "auto-refreshing, zero-infra" goal against
  the "NOT a daemon / no external service / no JS build step" constraints by making a
  plain self-contained `file://` snapshot the default shipped state and the served
  page a thin, operator-invoked convenience over the *same* pure render. Six
  **binding form-factor invariants** (D-1…D-6): static-regen canonical; auto-refresh
  via `<meta http-equiv="refresh">` (no JavaScript at all); an optional
  loopback-only, foreground `http.server` live mode that regenerates on request and
  holds no daemon lifetime; the HTML target **EXTENDS** `scripts/cockpit.py`'s
  `render()`/`_render_panel`/`NODATA` seam (the wrapper `cockpit_html.py` imports the
  panel data-binding funcs — one cockpit, two skins, never a second cockpit);
  degrade-to-static is **structural** (the base case, not a bolted-on fallback) with
  a generated-at timestamp and inherited `NODATA` non-fabrication; and a
  self-contained single artifact (inline CSS, no CDN / web font / analytics /
  runtime `fetch`). It **constrains — never edits** — `scripts/cockpit.py`,
  `scripts/trends.py`, and the event-store + cost-ledger data sources; the WS5
  implementation tickets (O5-T02 panels, O5-T03 Action Console, O5-T04 HTML wrapper)
  build against this contract.
- **Specialist depth — ORGANISM WS6 GUILD ([0029](0029-guild-model.md)–).**
  The guild model: a **guild is the per-ROLE craft of a role**, not a new
  organizational body — captured as a compilable agent-template
  `governance/agent-templates/<role>.md`, **grouped by department**, with **NO new
  org unit** (resolving §9 Q5's "guild = dept vs craft" fork by ruling *craft* and
  respecting the existing 32-node hierarchy: no new routing node, no new edge, no
  `schema.daslab.yaml` change). Five **binding invariants** (G-1…G-5): one template
  per role key, grouped by dept, with no topology change (G-1); a closed craft field
  set — identity/goal/behavioral-priors, toolkit allowlist, `model`+`effort`,
  `produces`/`consumes` defaults, allowed `communication-flows` routes, an
  eval-baseline reference, and a bounded/deduped/dated `## Learned` sink (G-2);
  `model`+`effort` copied **VERBATIM** from `governance/policies/model-allocation.md`
  with **no Tier F / Fable 5** (retired, no restore path) and haiku omitting `effort`
  (G-3); compilation through the **existing** `scripts/gen_subagents.py` overlay flow
  into `.claude/agents/*` (generate-and-diff clean), guarded by
  `scripts/check_agents_sync.py` — **not** `check_org_drift`, which is the sibling
  org-schema generate-and-diff gate (G-4); and a template that **references, never
  re-decides** any SSOT, with `## Learned` growing only via the `daslab-learn`
  distillation of Founder-accepted feedback (G-5). It **constrains — never edits** —
  `scripts/gen_subagents.py`, `scripts/check_agents_sync.py`,
  `governance/policies/model-allocation.md`, and `governance/communication-flows.yaml`;
  the WS6 implementation tickets (O6-T02 templates, O6-T03 compile, O6-T04/O6-T05
  golden-evals, O6-T06 learned-instructions) build against this contract.
- **Intake gateway — ORGANISM WS7 GATEWAY ([0030](0030-project-os-pack.md)–).**
  The PROJECT-OS-PACK: the canonical, normative, machine-readable **input contract** a
  Founder hands DasLab to bootstrap an AI-agent project — the one gate every new project
  enters through, closing gap G9 ("no intake compiler"). A decision doc plus a companion
  **spec of record** (`docs/specs/PROJECT-OS-PACK.md`) that writes the contract out field
  by field. One pack is **four parts, rooted at `projects/<name>/`** (Project Placement
  Law): a machine-readable `PROJECT-OS.yaml` manifest, the canonical lifecycle skeleton,
  the Founder discovery answers, and the approved goal queue. Six **binding
  pack-format invariants** (D-1…D-6): exactly one `projects/<name>/PROJECT-OS.yaml`
  manifest at the project root (D-1); a **closed** manifest field set — `name`,
  `mission`, `constraints`, `stack`, `budget`, `success_metrics` (D-2); the doc tree is
  the **canonical** AADL §2 `docs/01-planning…06-maintenance` six-stage skeleton, **not
  qaqnuz's divergent names** (`01-intake`/`02-prd`/`03-rfc`/… stay a legacy layout that
  maps via `LIFECYCLE-MAP.md`, never a new pack's shape) (D-3); the pack carries the
  Founder discovery answers — ≥10 Q&A or an explicit waiver (D-4); it carries the
  Founder-approved `APPROVED-GOAL-QUEUE.md`, load-bearing via the `APPROVED:`/
  `TASDIQLANDI:` signal and the existing `check_approved_goal_queue.py`, so no ticket
  compiles from an unapproved queue (D-5); and the project's **Constitution = QONUN laws
  + project-local constraints**, where a project-local constraint may only **tighten**,
  **never relax**, org law — the precedence law (root `AGENTS.md` §2 + the AADL scope
  note), org law winning on conflict and a relaxing pack rejected as invalid (D-6). It
  **constrains — never edits** — `governance/policies/ai-agent-lifecycle.md`,
  `scripts/check_approved_goal_queue.py`, the board ticket schema, and the QONUN laws;
  the WS7 implementation tickets (O7-T02 `gateway_compile.py` intake, O7-T03 stage-gated
  delivery, O7-T04/O7-T05 the E2E + generality sample packs) build against this contract.
- **Provable waves — ORGANISM WS8 ATTEST ([0031](0031-wave-runner-attestation.md)–).**
  The wave-runner + attestation: the wave **lifecycle mechanics** move out of
  `daslab-cycle/SKILL.md` **prose** — which the orchestrator LLM was trusted to execute
  by hand, leaving the event/span/checkpoint/ledger/evidence gates **perma-inert in CI**
  (gitignored runtime state, produced only by a live LLM wave) — into a single
  deterministic `scripts/wave_runner.py` entry point, `run_wave(plan, results)`. The
  orchestrator supplies the routing **`plan`** (which tickets → which roles → which
  models, decided in the unchanged step 2–3 triage off the canonical board files) and
  the collected **`results`** (per-ticket outcome + PR/CI/T7 evidence + timings) as
  **data**, and the runner makes **no mechanical decision**: it never re-selects,
  re-routes, or re-tiers, so the ADR 0025 **flag-on == flag-off DISPATCH DECISIONS**
  guarantee is preserved at a function boundary instead of in prose (post-decision
  mechanics, `organism_emit`-gated, failure-isolated). `run_wave` **reuses — never
  re-implements** the shipped producers: the wave-open/close checkpoints + ticket-ledger
  (`pulse_checkpoint`), the `run_start`/`run_end`/`span` triplet (`dispatch_emitter`),
  the per-role guardrail tripwires (`guardrail_dispatch`), and the committed redacted
  evidence snapshot (`snapshot_evidence`) — and then writes one **committed,
  small+redacted, doubly hash-chained** `WaveAttestation` per wave to
  `metrics/attestations/<run_id>.json` (tracked like `metrics/evidence/`, so a fresh
  clone / CI can see it; `ledger_hashes` binds it to the ADR 0023 checkpoint chain and
  `attest_chain` links it to the prior run's receipt). A new `scripts/check_attestation.py`
  CI validator gates **completeness** (every R-9-counted run must have an attestation
  whose `mechanics` block shows every step fired — reusing `snapshot_evidence.counted_run_ids`)
  and **integrity** (the two hash chains verify, and the receipt cross-checks the
  committed evidence snapshot), **fail-closed on counted runs** and **inert-by-design on
  an empty board** (ADR 0020: unmeasured is SKIPPED, never false-green). This gives the
  previously-perma-inert gates teeth two ways: **(a)** an end-to-end test drives a
  synthetic wave THROUGH the deterministic, clock-injected runner so CI exercises the
  full event/checkpoint/ledger/evidence chain on real fixture data, and **(b)** live
  waves commit attestations that `check_attestation` verifies on merge. The **residual is
  recorded honestly**: whether the LLM actually *calls* `run_wave` is still a compliance
  step (the runtime stays a markdown skill an LLM executes) — but the trust surface
  shrinks from a ~six-paragraph prose checklist to **one call**, and wave done-ness flows
  **through** that call, so an omission leaves no committed attestation and **fails CI**
  (detectable, not silent) rather than passing unnoticed. It **reuses — never edits** —
  `dispatch_emitter.py`, `pulse_checkpoint.py`, `guardrail_dispatch.py`,
  `snapshot_evidence.py`, and ADR 0023–0025; the WS8 implementation tickets build the
  runner, the validator, and the schema-conformance test against this decision.
- **Harness-forced attestation — ORGANISM WS9 HARNESS ([0032](0032-harness-forced-attestation.md)–).**
  The harness-forced attestation regime: WS8 ([ADR 0031](0031-wave-runner-attestation.md))
  shrank wave-mechanics enforcement to **one `run_wave` call** and gave the event gates teeth,
  but recorded its residual honestly — whether the LLM actually *calls* `run_wave` is still a
  compliance step, and the ATTEST re-audit named the irreducible-at-that-layer shape of the gap:
  a **total silent omission** (a wave that commits its work — `done` transitions, merged PRs —
  yet never calls `run_wave`) leaves **no committed attestation and no committed trace of the
  omission**, because `check_attestation` is inert on an empty store and there is no committed
  "a wave happened ⇒ an attestation MUST exist" cross-check. WS9 installs exactly that
  cross-check by **extending — not replacing** the 0031 regime. The same deterministic
  `run_wave` ATOMICALLY co-produces, with each committed `WaveAttestation`, one line in a
  **TRACKED, append-only, hash-chained** `board/wave-ledger.jsonl` (**not** the gitignored
  `board/.wave-log`) — the closed eight-field entry `{run_id, wave, ticket_ids,
  attestation_path, attestation_hash, prev_hash, self_hash, created_at}`, whose `prev_hash`/
  `self_hash` form a **second committed chain** (self-exclusion hashing, ADR 0023 §2) layered on
  top of each attestation's own `attest_chain`. A new `scripts/check_wave_reconciliation.py`,
  wired into `ci.yml` + `diagnostics.py`, enforces a mutually-corroborating triangle — the
  committed ledger, the committed attestations, and the board's `done` transitions: **(a)
  bijection** (committed ledger ⇄ committed attestations, matching ticket set + `attestation_hash`,
  no orphan either way); **(b) per-run wave-sequence chain continuity** (the ledger hash-chain
  verifies end-to-end AND each run's `wave` indices are gap-free — a recorded-but-skipped wave is
  a FAIL); and **(c) board terminality + coverage** (every attested ticket is `done`, and every
  board ticket that became `done` **after** the committed `board/.attestation-baseline` is covered
  by a committed ledger entry — the harness-forcing arm). The committed
  `board/.attestation-baseline` pins the HEAD SHA at regime start, **grandfathering** pre-regime
  `done` tickets so the live repo stays green while every new `done` transition is forced to carry
  reconciled proof. Fail-closed on real data, inert-by-design on an empty regime (ADR 0020). The
  **residual is recorded with total honesty**: this HARNESS-forces attestation for any wave that
  commits *any* work, and makes mid-sequence skips + tampering CI-detectable via a durable broken
  hash-chain — but the **irreducible floor** is a wave that **commits absolutely nothing** (which
  also delivered nothing); an LLM-driven runtime cannot be forced below that floor without removing
  the LLM. It moves the residual from *"silent omission leaves no trace"* to *"omission breaks a
  committed chain"* — **toward, not to, zero**. It **reuses — never edits** — `scripts/wave_runner.py`,
  `scripts/check_attestation.py`, `scripts/snapshot_evidence.py`, and ADR 0023–0025 / ADR 0031; the
  WS9 implementation tickets build the ledger co-write, the reconciliation validator, the committed
  baseline, and the schema-conformance + end-to-end tests against this decision.
- **LangChain-ecosystem interop / Governed-Devin direction ([0033](0033-ecosystem-tool-mcp-bridge.md)–[0039](0039-self-hosted-web-control-plane.md)).** The direction that brings DasLab to autonomous-agent-platform parity while keeping governance as the moat (briefs: `docs/research/2026-07-22-daslab-devin-langchain-direction.md`, `docs/research/2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`). The LangChain ecosystem is adopted strictly as **substrate under DGO-X** (ADR 0010 C1): an inbound MCP tool bridge for browser/computer-use + the integration catalog (0033), a Claude Agent SDK headless runner that realizes ADR 0009's deferred SDK gateway (0034), LangGraph as the DGO-X P2/P3 execution engine with AADL gates as conditional edges/interrupts (0035), and an outbound subgraph/MCP surface plus a non-invasive LangSmith OTLP observability lens (0036). All four are Proposed, feature-flagged OFF, and change no dispatch behaviour on merge. The MUSTAQIL v3.0 prep layer adds an explicit **retrieval-strategy** decision ([0041](0041-agentic-search-first-retrieval-strategy.md), ratifying Founder Q11): agentic-search-first (grep / Read / `07-CONTEXT-PACK` / ArcRift recall) is the default and no vector DB is stood up by default; an indexed-retrieval escape hatch is built only when a large-repo metric *and* a governing ADR both approve it, and if built it enters as a derived, governed tool through the ADR 0033 edge — the index is never canonical, `board/tickets/` stays the source of truth (C2).
