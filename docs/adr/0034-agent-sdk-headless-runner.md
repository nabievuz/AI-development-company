# ADR 0034 — Claude Agent SDK headless runner: the future SDK runner ADR 0009/0010 deferred

- **Status:** Proposed (Backend EM authors; **CTO ratifies — RACI 3.1/3.6**; Security Lead consulted — secrets, admission)
- **Date:** 2026-07-22
- **Scope:** Platform / org-engine — a programmatic (headless) dispatch entrypoint
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted)
- **Relates:** direction + parity briefs (`docs/research/2026-07-22-*`); is the "future SDK-based runner" named by [0009](0009-harness-owns-transport-admission-layer.md) and [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) §2; upstream of [0035](0035-langgraph-dgox-execution-substrate.md) and [0036](0036-outbound-interop-surface-langsmith.md); preserves [0025](0025-events-load-bearing.md)/[0031](0031-wave-runner-attestation.md) flag-on==flag-off
- **Supersedes / Amends:** nothing — establishes the runner fresh; additive; `/daslab-cycle` stays the default.

> DasLab runs only inside an interactive Claude Code session (a human runs `/daslab-cycle`). Parity gap G1 (async cloud execution), the G6 benchmark proof point, autonomous tempo (ADR 0027), and the outbound surface (ADR 0036) all require one thing DasLab lacks: a way to run a ticket/wave **programmatically**. This ADR adopts that runner and fixes the boundary ADR 0009 left open.

## Context

ADR 0009 wrote down a load-bearing ceiling: under the Claude Code **harness**, DasLab does not own the LLM transport, so the model gateway is an *admission* layer, not a proxy — and the literal "no un-proxied call" form is reachable "**only under a future SDK-based runner**." ADR 0010 inherited that ceiling verbatim. The Claude **Agent SDK** is now that runner: its `query()` loads the repo's own `.claude/agents`, skills, `CLAUDE.md`, hooks, and `.mcp.json` via `setting_sources=["project"]` — the exact 32 charters, no rebuild. That makes a headless DasLab tractable without touching the org model.

## Decision

**Adopt a thin `daslab_sdk` runner over the Claude Agent SDK that dispatches a ticket (and, via `run_wave`, a wave) programmatically against the same repo, additive to `/daslab-cycle`.** Binding invariants:

### SR-1 — Load the repo's own agents; never rebuild them
The runner sets `cwd` = repo root and `setting_sources=["project"]`, loading the existing agents/skills/`CLAUDE.md`/hooks/`.mcp.json` (ArcRift included). Porting the 32 roles to LangChain `create_agent` or any other agent abstraction is **forbidden** — the generated `.claude/agents/*` shims stay canonical (ADR 0018/0029).

### SR-2 — Model is explicit per dispatch; the runner IS the ADR 0009 gateway
Every dispatch passes `model` explicitly from `governance/policies/model-allocation.md` (frontmatter untrusted, LAW 3). Under the SDK the runner finally is the in-orchestrator admission gateway ADR 0009 described — it governs *what dispatches with which model, under which per-dispatch budget* (ADR 0027 SI-5), honoring the LAW 8 ceiling rather than re-opening it.

### SR-3 — No mechanical decision in the runner; flag-on == flag-off
The runner makes no routing/selection/re-tier decision of its own: it **calls** `scripts/wave_runner.py:run_wave(plan, results)` (ADR 0031) with the plan/results the orchestrator supplied as data, so the ADR 0025 dispatch-equivalence guarantee holds at a function boundary. It emits the same `run_start`/`run_end`/`span`/checkpoint/attestation stream (ADR 0023/0024/0031/0032) — it does not fork a second producer.

### SR-4 — Board stays canonical; Git law holds
The runner reads/writes `board/tickets/*.md` exactly as `/daslab-cycle` does (C2); a code-touching ticket still gets a worktree/branch/PR (ADR 0005), and `done` still requires a merged PR with green CI. The runner does not merge its own PRs.

### SR-5 — Additive and feature-flagged
`/daslab-cycle` remains the default, behaviour-defining entrypoint and the fallback. The runner is opt-in, flag-gated (ADR 0019, default OFF); nothing about interactive waves changes on merge.

## Consequences

**Positive:** Unlocks headless CI runs, the G6 public-benchmark proof point, cloud execution + per-ticket sandbox (DGO-X P3), autonomous tempo (ADR 0027), and the outbound subgraph/MCP surface (ADR 0036) — from **one** small, well-bounded call path. It converts ADR 0009's deferred "no un-proxied call" from an aspiration into a scoped, gated deliverable.

**Negative / accepted:** A second runtime surface to maintain and secure alongside the interactive harness; multi-tenant isolation caveats apply (the SDK reads host-level config regardless of `setting_sources` — the runner must set explicit `env`/`cwd` isolation). Accepted and bounded by SR-5's flag.

**Law check:** **LAW 8 / ADR 0009** (the SDK runner is the sanctioned place the admission layer becomes a real gateway; ceiling honored, not re-opened). **Model allocation** (SR-2 explicit `model`). **ADR 0025/0031** (SR-3 preserves flag-on==flag-off + reuses `run_wave`). **AADL** (gates enforced through DGO-X/`run_wave`, not bypassed). **Git law** (SR-4). **Project placement** (the runner is platform code under `scripts/`/`daslab_sdk/`, hosts no project content — C6).

## Enforcement / acceptance

- Ratified by the **CTO**; Security Lead consulted on secrets/isolation. `Proposed` until sign-off.
- Acceptance tests: a dispatch passes an explicit `model` (SR-2); the runner routes through `run_wave` and emits the standard attestation (SR-3, checked by `check_attestation`/`check_wave_reconciliation`); a headless wave produces the same board/event outcome as an interactive one (SR-4).
- Feature key in `config/features.yaml` `DEFAULTS` **OFF**; runner code under `daslab_sdk/` (or `scripts/`).
- Any future "how does DasLab run without a human in the loop / where is the SDK gateway?" question resolves here.
