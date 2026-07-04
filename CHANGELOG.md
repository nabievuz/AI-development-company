# Changelog

All notable changes to DasLab are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and DasLab adheres to
[Semantic Versioning](https://semver.org/) (see [ADR 0022](docs/adr/0022-semantic-versioning-policy.md)).

## [2.0.0] — 2026-07-04

DasLab **v2.0 "ORGANISM"** — the file-native org gains a durable, observable,
self-evaluating substrate. This release ships the complete substrate and closes the
audit-remediation program; the code, gates, and evals are all green.

> **Honest scope of "2.0".** The autonomous-tempo loop ships **OFF / shadow** by
> design. The §5 live-tempo KPI rows (T1 busy_fraction, T3 concurrency, T4 model-mix)
> are measured from real operation, so they accumulate once the Founder resolves the
> go-live decision — a ≥3-day window of counted waves then flipping
> `heartbeat_enabled: true` (QONUN-5, evidence-gated by
> `scripts/check_heartbeat_readiness.py`; see [`docs/runbooks/heartbeat-go-live.md`]).
> No KPI number in this release is fabricated: unmeasured is reported as unmeasured.

### Fixed — audit remediation (2026-07-04)

- **R-1 / audit F-1** — the QONUN-3 Founder-approval marker is load-bearing again:
  `APPROVED` counts only in the canonical colon form `APPROVED:`, so a queue's own
  `APPROVED-GOAL-QUEUE` filename/title can no longer self-authorize.
- **R-1b / audit F-1b** — `founder_approved` is accepted only as an anchored
  `founder_approved:` field, not as a machine-writable per-goal table status value.
- **R-2 / audit F-2** — committed KPI evidence `model_mix` now tallies from the
  `run_end` completion (where the model lives), not `run_start`; the 7 stale evidence
  snapshots were reconciled.

### Added / Hardened

- **R-5** — golden-eval coverage raised from 6/32 to **32/32 roles** (each ≥3
  deterministic tasks, ≥0.80 at its assigned tier), via authoring + adversarial
  GATE-4 review + rework + a 32-row `docs/AGENT-ROSTER.md` accuracy×cost scorecard.
- **DAS-1536** — an anti-gaming **prompt-leak detector** in `agent_eval --check-gaming`
  (a `task.md` example that scores through its own verifier fails), a guild-wide cleanup
  of 17 leaking tasks, and a strict **zero-overlap** bar.
- **R-6 (DAS-1537)** — dedicated blocking CI steps for `check_import_ban`,
  `agent_eval --check-gaming`, and `validate_commflows`.
- **R-4 prep (DAS-1538)** — an evidence-gated HEARTBEAT go-live readiness reporter
  (`scripts/check_heartbeat_readiness.py`) + the Founder go-live runbook.

## [1.0.0] — 2026-06-29

First public release of DasLab — a reproducible operating system for a 32-agent
AI software organization. A fresh `git clone` boots the entire org.

### Added

- **The 32-agent organization** — a four-level hierarchy (Board → CEO → C-suite →
  leads → ICs) across six departments, generated into `.claude/agents/` from the
  org tree and the model-allocation policy (opus ×10 / sonnet ×19 / haiku ×3).
- **The file-based board** — one ticket = one `board/tickets/DAS-*.md` file, with
  the `backlog → todo → in_progress → blocked → in_review → done` lifecycle. No
  timer, no server, no API.
- **Orchestration skills** — `/daslab-plan`, `/daslab-cycle`, and `/daslab-run`,
  with worktree-per-ticket concurrency and explicit per-dispatch model selection.
- **The AI-Agent Development Lifecycle (AADL)** — six gated stages
  (Planning → Design → Development → Testing → Deployment → Maintenance).
- **The quality engine** — the weighted 7-dimension 100/100 release gate
  (`scripts/diagnostics.py`) and the CI-enforced validator suite, including the
  fail-closed lint gate ([ADR 0021](docs/adr/0021-fail-closed-ruff-gate.md)).
- **The DGO-X control plane** — graph-orchestrated and gate-driven, running in
  shadow mode ([ADRs 0010–0012](docs/adr/)).
- **The ArcRift persistent-memory loop** — an optional MCP server for
  recall-at-start / store-at-end, scoped strictly per project.
- **The documentation set** — README, [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
  (with diagrams), [`docs/USAGE.md`](docs/USAGE.md), the ADR set
  ([`docs/adr/`](docs/adr/)), and CONTRIBUTING / SECURITY / CODE_OF_CONDUCT.

[1.0.0]: https://github.com/nabievuz/daslab/releases/tag/v1.0.0
