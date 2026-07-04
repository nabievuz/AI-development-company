# RFC-0001: Engineering finish guard — block status=done without a verified commit

- Author: CTO (DasLab)
- Status: Accepted
- Date: 2026-06-01
- Related: DAS-381, DAS-384, parent DAS-382, tracking DAS-385

## Summary

Add a runtime guard that refuses to let an engineering agent transition a
ticket to `done` (or `in_review`) without a verified `git` commit produced
during the current board runtime run. The guard ships as a DasLab-owned CLI
(`daslab-finish-guard`, in `@daslab/orchestrator`) backed by a pure decision
core, mandated by the engineering role overlay as the finishing call. Behavior
gates behind feature flag `DASLAB_FINISH_GUARD=1`.

## Motivation

Engineering agents have flipped a ticket to `done` with green tests but no
commit and no comment — the work was never actually written. The prose-only
fix (494c840) did not prevent recurrence: the role overlay already said "never
done without a commit + comment" and the agent ignored it. Prose is not
enforcement. We need an unbypassable runtime check before the next
product-impacting task runs.

## Proposal

### Placement decision

We considered two placement points:

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Inside the agent's CLI/runtime adapter** | Closest to the action | Requires forking the upstream agent runtime; not feasible inside our delivery budget; couples DasLab to upstream releases | **Rejected** |
| **B. DasLab-owned finish-guard CLI** (`daslab-finish-guard`) | Lives in this repo; ships now; mandated via the engineering role overlay and a CI-style preflight; works for any DasLab engineering agent | Bypassable in principle if an agent ignores its role overlay — but the failure mode is observable (no commit, no status write, ticket stays `in_progress`, supervisor picks it up) | **Selected — this RFC** |

We ship **B now**. It is the necessary and sufficient fix because the guard
itself owns the status write — an agent that runs the guard cannot mark itself
`done` without a commit; an agent that skips the guard fails to write the
finish at all and gets caught by supervisor stalled-work detection.

### Component shape

1. `packages/orchestrator/src/finish-guard.ts` — pure decision function
   `evaluateFinishGuard(input) → {allow, enforcedStatus?, reason, marker}`.
   No I/O, no clock, no env.
2. `packages/orchestrator/src/scripts/finish-guard.ts` — CLI:
   - `daslab-finish-guard start --issue <id> --run <runId> [--cwd .]` —
     writes HEAD-at-start to a per-run state file under
     `$XDG_STATE_HOME/daslab-finish-guard/<runId>.json` (fallback
     `/tmp/daslab-finish-guard/<runId>.json`).
   - `daslab-finish-guard finish --issue <id> --run <runId> --status <status>
     [--comment <text>] [--read-only-claim <text>]` — reads HEAD-at-start,
     runs `git rev-parse HEAD` in `cwd`, evaluates the decision, then writes
     the result to the board ticket:
     - **allow** → set `status` + the supplied comment, prefixed with the
       structured guard marker.
     - **block** → set `status=blocked`, write a comment carrying the marker
       `runtime-guard:no-commit`, and reassign to CTO (per `board/ROUTING.md`).
3. Feature flag `DASLAB_FINISH_GUARD`. Unset/0 → CLI prints a one-line warning
   and passes through (transparent write); 1 → enforces. Default off for one
   release cycle so we can measure compliance before tightening.
4. The engineering role overlay updated: the finishing sequence MUST call
   `daslab-finish-guard finish ...`; a bare status write to `done`/`in_review`
   is forbidden.

### Decision rule (encoded)

The guard `allow`s the transition iff one of these holds:

- Status is not `done` and not `in_review` — guard inactive (marker
  `runtime-guard:n/a`).
- The agent supplied a non-empty `--read-only-claim` (≥ 8 chars). The claim is
  echoed verbatim into the comment so it is auditable (marker
  `runtime-guard:read-only-claim`). This intentionally trusts the agent because
  read-only tasks legitimately have no commit; abuse is caught at audit time,
  not at the guard.
- `headAtStart !== headNow` — a commit landed during this run (marker
  `runtime-guard:commit-verified`).

Otherwise the guard **blocks** (`enforcedStatus: 'blocked'`): with marker
`runtime-guard:no-commit` when HEAD is unchanged, or `runtime-guard:missing-state`
when the start snapshot is absent (fail closed).

## Non-scope

- This RFC does not enforce diff sizes, lint, or test-pass — those live in the
  existing per-package CI script and the engineer's checklist.
- No changes to the agent runtime; we do not fork any upstream CLI.

## Alternatives

- **Tighten the agent's prose brief further** — already proven insufficient
  (494c840 → DAS-384). Rejected.

## Risks & Open Questions

- **R1.** Agent skips the guard CLI and writes the ticket directly. Mitigation:
  the role overlay mandates the CLI; the absence of a guard marker on a
  `done`/`in_review` comment is an audit signal; supervisor stalled-work
  detection catches no-write runs.
- **R2.** False-positive blocks for legitimate read-only tasks. Mitigation:
  `--read-only-claim` escape hatch; audited via the comment trail.
- **R3.** State file lost between `start` and `finish` (e.g. tmp wipe mid-run).
  Mitigation: on missing state at `finish`, treat as HEAD-unchanged (fail
  closed, marker `runtime-guard:missing-state`) — the agent must restart with a
  fresh `start`.

## Threat Model

This RFC introduces no network surfaces and no new data flows. The guard reads
local git HEAD, writes a per-run state JSON in a user-owned directory, and
writes the ticket file in the board runtime; it does not transmit or log
secrets/PII.

### Data Flows

| Flow | Source | Destination | Sensitive? | Encrypted? |
|------|--------|-------------|------------|------------|
| HEAD-at-start capture | local `git rev-parse` | local JSON file (`$XDG_STATE_HOME/daslab-finish-guard/<runId>.json`) | no (commit sha) | n/a (local disk) |
| Finish write | finish-guard CLI | board ticket (status + comment) | low (ticket state + comment) | n/a (local file in `git`) |

### Trust Boundaries

- Agent process → local git: trusted (same OS user).
- Agent process → board runtime: local ticket-file writes under the same OS
  user. No network or new auth surface.

### Abuse Scenarios

| Scenario | Attack | Mitigation |
|----------|--------|------------|
| 1. Agent forges `--read-only-claim` to skip the commit check on a write task | Agent supplies a bogus claim, the write succeeds | Claim is echoed verbatim into the audit comment with marker `runtime-guard:read-only-claim`. CTO audits weekly. |
| 2. Agent edits its own state file to fake `headAtStart` | Local file tampering | Same OS-user trust boundary applies to all local files; not a new threat. |
| 3. Agent bypasses the CLI and writes the ticket directly | Protocol bypass | The role overlay mandates the CLI; absence of a guard marker on a `done`/`in_review` comment is an audit signal; supervisor catches the no-marker failure mode. |

### Security Controls Checklist

- [x] Authentication required on all new endpoints (A01) — N/A; no endpoints, the CLI writes local files only.
- [x] Authorisation / ownership check prevents IDOR (A01) — the guard writes only the ticket id passed by the agent; the board's reviewer routing enforces assignee.
- [x] No secrets or PII logged or returned in error responses (A02) — guard logs commit shas + reason strings only.
- [x] All database queries parameterised; no raw SQL concatenation (A03) — N/A; no SQL.
- [x] Rate limiting applied on new public/auth endpoints (A04) — N/A; no endpoints.
- [x] HTTP security headers present on new responses (A05) — N/A; CLI only.
- [x] Input validated with Zod at the API boundary (A08) — CLI args validated; the status/comment payload is a fixed shape.
- [ ] Webhook payloads validated with HMAC if applicable (A08) — N/A.
- [x] Security events emitted for auth/admin/privilege actions (A09) — every guard decision writes a structured comment with a marker; that IS the audit log for this control.
- [ ] User-supplied URLs go through `safeFetch` from `@daslab/ssrf-guard` (A10) — N/A; no URL fetching from user input.

## Acceptance

- Implementation in `@daslab/orchestrator`, behind flag.
- Unit tests: positive (HEAD changed) + negative (HEAD unchanged → blocked,
  marker present) + read-only-claim path + missing-state path.
- The engineering role overlay updated to mandate the CLI.
