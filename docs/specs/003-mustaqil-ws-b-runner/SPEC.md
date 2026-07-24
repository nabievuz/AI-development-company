# SPEC 003 — MUSTAQIL WS-B RUNNER (headless Agent SDK dispatch)

- **Goal:** mustaqil-ws-b-runner
- **Owner:** backend-em
- **Status:** draft

> WHAT/WHY only. The HOW (`daslab_sdk` module layout, `query()` call shape,
> `setting_sources` wiring, the `run_wave` call boundary) lives in ADR-0034 and
> the AADL Stage-2 design ticket, not here. Binds to ADR-0034 (SR-1…SR-5), the
> master prompt (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`
> Part 1 row B + Part 2), and Founder discovery answer Q9 (Claude subscription,
> account auth, monthly credit = the hard budget ceiling).

## User Scenarios

- **P1 —** Given a ticket ready for programmatic dispatch, when the runner is invoked headlessly, then it loads the repo's own existing agents, skills, `CLAUDE.md`, hooks, and `.mcp.json` and dispatches with an explicit per-dispatch model — producing the same board and event outcome as an equivalent interactive wave.
- **P1 —** Given the WS-B feature flag is OFF (default), when a wave runs, then `/daslab-cycle` stays the only entrypoint and dispatch behaviour is unchanged.
- **P1 —** Given a code-touching ticket dispatched through the headless runner, when the work completes, then a worktree/branch/PR is still required and the runner does not merge its own PR.
- **P2 —** Given the monthly Claude-subscription credit is at or near exhaustion, when a wave would breach the budget ceiling, then the wave evaluates to idle plus alert, and the pause is treated as sanctioned rather than a failure.
- **P2 —** Given the runner needs model access, when it dispatches, then the call routes through the admission layer using Claude-account authentication rather than a metered API key, keeping the auth path swappable.

## Functional Requirements

- **FR-001** — The runner MUST set `cwd` to the repo root and load the repo's own agents, skills, `CLAUDE.md`, hooks, and MCP configuration for every dispatch; porting the guild roles to a different agent abstraction is FORBIDDEN — the generated shims stay canonical.
- **FR-002** — Every dispatch MUST pass an explicit model sourced from the model-allocation policy; the ticket frontmatter's own model hint MUST NOT be trusted as the sole source.
- **FR-003** — The runner MUST make no routing, selection, or re-tier decision of its own; it MUST call the existing wave-execution function with the plan and results the orchestrator supplied, and MUST emit the same run-start/run-end/span/checkpoint/attestation event stream a wave already emits — never a second, divergent producer.
- **FR-004** — The runner MUST read and write the board exactly as the interactive entrypoint does; a ticket that touches code MUST still get its own worktree, branch, and pull request, and the runner MUST NOT merge its own pull request.
- **FR-005** — The runner MUST be off by default behind a feature flag; the interactive entrypoint MUST remain the default, behaviour-defining path, and merging the runner MUST change no interactive-wave behaviour.
- **FR-006** — The runner MUST authenticate to the model using a Claude-subscription account rather than a metered API key, and MUST route that access through the existing admission layer so the auth path stays swappable and per-dispatch budget enforcement holds.
- **FR-007** — A wave that would breach its configured per-run or per-day cap, or the monthly subscription credit, MUST evaluate to idle plus alert rather than proceeding or reporting a false success; metered overflow beyond the subscription credit MUST stay disabled by default.
- **FR-008** — Exhaustion of the monthly subscription credit MUST be handled as a sanctioned pause that resumes on credit refresh, never surfaced as a crash, a silent stop, or a failed run.

## Success Criteria

- **SC-001** — A headless dispatch of a ticket (and, via the wave entrypoint, a full wave) produces the same board state, event stream, and attestation a comparable interactive dispatch would produce — a dispatch-equivalence test passes.
- **SC-002** — A test proves every headless dispatch carries an explicit model argument; a dispatch attempted without one is rejected before it reaches the model call.
- **SC-003** — With the feature flag OFF, the runner is inert and a wave run through the interactive entrypoint is byte-identical to pre-merge; flipping the flag ON changes no interactive-wave behaviour.
- **SC-004** — A budget-breach and a credit-exhaustion scenario are each proven, by test, to evaluate to idle plus alert / sanctioned pause rather than a false-green or an unhandled crash.
- **SC-005** — `diagnostics.py` scores 100/100, `board_lint`/`check_spec_consistency`/`check_dependency_graph` all pass, green CI on every WS-B pull request, and no ticket in this workstream carries a `project:` field.
