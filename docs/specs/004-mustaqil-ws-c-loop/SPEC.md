# SPEC 004 — MUSTAQIL WS-C LOOP (durable graph loop + per-task sandbox)

- **Goal:** mustaqil-ws-c-loop
- **Owner:** backend-em
- **Status:** reviewed

> WHAT/WHY only. The HOW (the LangGraph state-channel mapping, `interrupt()` /
> conditional-edge mechanics, the E2B/OpenHands sandbox provisioning, the checkpointer
> wiring) lives in ADR-0035 and the AADL Stage-2 design ticket, not here. Binds to
> ADR-0035 (LG-1…LG-5, under DGO-X ADR-0010 C1–C6), the master prompt v3.0 row C
> (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`), and Founder discovery
> answers Q2 (Docker-based E2B/OpenHands on the tenant VM) and Q4 (supervised until the
> first proof lands, then shadow before drive).

## User Scenarios

> Given / When / Then, ordered by priority (P1 first). Behavioural, not technical.

- **P1 —** Given a ticket routed through the DGO-X P2/P3 substrate, when a worker node executes, then the loop runs a durable plan-act-observe-replan cycle whose state can be checkpointed and resumed after an interruption without losing or double-applying committed work — and the board stays canonical throughout.
- **P1 —** Given the substrate holds a graph state that diverges from `board/tickets/`, when the divergence is detected, then the board wins and the graph state reconciles to it — the graph state is never the top-level source of truth.
- **P1 —** Given a ticket sitting behind an open AADL / security / budget / never-auto-approve gate, when the loop reaches it, then it halts at an interrupt point and waits for the Founder — a worker node is never routed past an open gate.
- **P1 —** Given a worker node needs to run untrusted code or shell commands, when it executes them, then they run inside an isolated per-task sandbox so the execution cannot reach the host, the repo, another task, or any credential it was not explicitly scoped.
- **P1 —** Given the loop feature flag is OFF (default), when a wave runs, then dispatch behaves exactly as today, `/daslab-cycle` remains the fallback, and the substrate simply does not drive.
- **P2 —** Given a worker node, when it edits state, then it writes only its own ticket body/log and its work artifacts — never a routing field (assignee / reviewer / routing_reason / confidence), which stay supervisor-only.
- **P2 —** Given the loop checkpoints its progress, when a checkpoint is written, then it reconciles with the run-model and the wave attestation ledger rather than forking a second durable truth, so flag-on dispatch stays equivalent to flag-off.

## Functional Requirements

> One testable requirement per line. `FR-NNN` ids, unique. Child tickets bind to these
> via their `implements:` frontmatter list.

- **FR-001** — The system MUST provide a durable plan-act-observe-replan loop as the DGO-X Phase-2/Phase-3 execution substrate, with checkpoint and resume, consuming LangGraph as a governed substrate that is never the top-level source of truth (ADR-0035 LG-1, ADR-0010 C1).
- **FR-002** — The substrate's graph state MUST be a projection / mirror of `board/tickets/`; any divergence MUST resolve to the board, which stays canonical (ADR-0035 LG-1, C2).
- **FR-003** — Each AADL predecessor gate, and every security / budget / never-auto-approve category, MUST be an interrupt or conditional-edge point that halts and waits for the Founder; a ticket behind an open gate MUST NOT be routed to a worker node (ADR-0035 LG-2, C4).
- **FR-004** — A worker node MUST edit only its own ticket body/log and work artifacts; it MUST NOT write any routing field (assignee / reviewer / routing_reason / confidence), which remain supervisor-only (ADR-0035 LG-3, C3).
- **FR-005** — Checkpoints MUST reconcile with the ADR-0023 run-model and the ADR-0031/0032 attestation + wave-ledger and MUST NOT fork a second durable source of truth, so that flag-on dispatch is equivalent to flag-off (ADR-0035 LG-4, ADR-0025).
- **FR-006** — Each worker node's code / command execution MUST run inside an isolated, in-tenant per-task sandbox (E2B / OpenHands, Docker-based per Q2) such that untrusted execution cannot reach the host, the repo, another task, or an unscoped credential.
- **FR-007** — The substrate MUST be gated by the `ws_c_langgraph_loop` feature flag, DEFAULT OFF, shadow-before-drive; adding it MUST change no dispatch behaviour on merge, and `/daslab-cycle` MUST remain the fallback until the board approves autonomous drive (ADR-0035 LG-5, C5, ADR-0019).

## Success Criteria

> Measurable. `SC-NNN` ids, unique.

- **SC-001** — A checkpoint/resume test proves the loop resumes after a mid-run interruption without losing progress and without double-applying a committed side effect (idempotent resume, DAS-1447).
- **SC-002** — A negative test proves a ticket behind an open gate is not routed to a worker node, and that an injected graph-state divergence resolves back to the board.
- **SC-003** — A test proves a worker node's attempt to write a routing field is rejected / structurally impossible.
- **SC-004** — With the loop flag OFF, a wave's dispatch behaviour is byte-identical to pre-merge; flipping it ON runs the loop only in shadow until the board approves drive.
- **SC-005** — `diagnostics.py` 100/100, `board_lint` / `check_spec_consistency` / `check_dependency_graph` / validators green, green CI on every WS-C PR, no `project:` field on any WS-C ticket (board_lint R9), and a committed wave attestation (ADR-0031/0032).
</content>
</invoke>
