# SPEC 010 — MUSTAQIL WS-F TEMPO (HEARTBEAT go-live — LAST, Founder-gated)

- **Goal:** mustaqil-ws-f-tempo
- **Owner:** cto
- **Status:** reviewed

> WHAT/WHY only. The HOW (scheduler internals, clean-day math, kill-switch mechanics)
> already lives in ADR-0027 (SI-1…SI-7), `scripts/loop_controller.py`,
> `scripts/break_glass.py`, `scripts/check_heartbeat_readiness.py`, and
> `docs/runbooks/heartbeat-go-live.md` — all shipped, all flag-OFF. WS-F is a
> **governance-verification act, not an engineering build**: it confirms SI-1…SI-7
> coverage, closes any real gaps in the shadow/evidence tooling, and produces one
> Founder-facing go/no-go artifact. The actual `heartbeat_enabled` flip stays a
> Founder-only QONUN-5 act, out of any agent's authority. Binds to ADR-0027,
> the direction brief (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`
> row F + "F last, Founder-gated after a ≥3-day clean shadow window"), and the
> MUSTAQIL BUDGET precondition (monthly Claude-subscription credit ceiling).

## User Scenarios

- **P1 —** Given the shadow-mode heartbeat (`heartbeat_enabled: false`), when WS-F
  runs its verification pass, then every one of SI-1…SI-7 has a named, currently-green
  enforcement point (script, test, or drill) on record — no invariant is asserted
  without evidence.
- **P1 —** Given the Founder wants to know whether HEARTBEAT can go live, when they
  read the WS-F go/no-go artifact, then it states plainly READY or NOT READY, the
  exact clean-day count against the ≥3-day bar, and the one remaining Founder act —
  never a recommendation to flip anything itself.
- **P1 —** Given no agent role, when any WS-F ticket is worked, then `heartbeat_enabled`
  is never flipped to `true` and no gate/interrupt-card is auto-approved — the
  Deployment child stays `blocked` until the Founder acts.
- **P2 —** Given the Claude-subscription monthly credit is the outer ceiling (MUSTAQIL
  BUDGET precondition), when the go-live evidence is assembled, then the credit
  ceiling is confirmed alongside the existing SI-5 per-run/per-day caps, not instead
  of them.
- **P2 —** Given the shadow window is currently 0/3 clean days (no counted waves yet),
  when WS-F Development work runs, then it closes real tooling gaps that block the
  window from accumulating (e.g. a counted-wave/CI path feeding
  `board/.metrics-history.jsonl`) — it does not fabricate or shortcut the count.

## Functional Requirements

- **FR-001** — WS-F MUST verify, not rebuild: it confirms ADR-0027 (Accepted,
  2026-07-03) and its SI-1…SI-7 invariants are the binding contract, and that the
  existing enforcement points (`scripts/loop_controller.py`, `scripts/break_glass.py`,
  `scripts/check_loop_mode.py`, `scripts/check_heartbeat_readiness.py`,
  `docs/runbooks/heartbeat-go-live.md`) are the artifacts of record — no duplicate
  scheduler, kill-switch, or readiness reporter is authored.
- **FR-002** — WS-F MUST confirm, with a fresh run of `scripts/check_heartbeat_readiness.py`
  (or a documented successor), the exact consecutive clean-day count
  (T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7 holds) against the **≥ 3-day** SI-7 go-live bar before
  any go-live claim is made — a stale or fabricated readiness claim is forbidden.
- **FR-003** — A go-live runbook MUST document the Founder-only flag-flip act
  (`heartbeat_enabled: true`) as distinct from `loop_controller`'s separate ≥7-day
  loop-promotion clock (SI-7's "two distinct clocks, do not conflate"); WS-F folds any
  MUSTAQIL-specific addenda (the monthly credit ceiling, in-tenant precondition) into
  the existing runbook rather than forking a second one.
- **FR-004** — The Claude-subscription **monthly credit ceiling** MUST be confirmed as
  an additional hard dispatch ceiling the heartbeat honors, alongside — never in place
  of — the SI-5 per-run/per-day caps in `config/budgets.yaml`; credit exhaustion is a
  sanctioned pause (idle + alert), never a false-green or a failure.
- **FR-005** — Each of SI-1…SI-7 MUST have a verifiable, currently-passing evidence
  artifact (an existing test, drill, or reporter) named and re-run before the
  Deployment child ticket can be considered for closure; a gap discovered here is a
  Development-stage fix, never asserted-away at Deployment.
- **FR-006** — The `heartbeat_enabled` flip MUST NOT be performed by any agent under
  any WS-F ticket — it is a Founder-only QONUN-5 never-auto-approve act, gated on the
  ≥3-day clean shadow window (SI-7). The WS-F Deployment ticket MUST carry
  `status: blocked` with this as its recorded reason until the Founder acts; closing
  it any other way is a spec violation.

## Success Criteria

- **SC-001** — `scripts/check_heartbeat_readiness.py` (or its documented successor) is
  re-run and its verdict (READY/NOT READY, exact clean-day count vs. the 3-day bar)
  is recorded verbatim in the WS-F evidence trail — no fabricated readiness.
- **SC-002** — A kill-switch / safety-rail drill (SI-3 break-glass honored, SI-6
  max-concurrent-waves=1) is run with **zero gate/approval violations** recorded in
  the event log, reusing the existing drill machinery (e.g. `DAS-1478`'s tests)
  rather than a new one.
- **SC-003** — `diagnostics.py` 100/100; `board_lint` / `check_spec_consistency` /
  `check_dependency_graph` all green; no `project:` field on any WS-F ticket
  (board_lint R9); a committed wave attestation where a PR exists.
- **SC-004** — The go-live runbook explicitly separates the **≥3-day** heartbeat-live
  clock (SI-7) from the `loop_controller` **≥7-day** loop-promotion clock, names the
  Founder-only flip step, and shows no agent-reachable path to perform it — verified
  by re-reading `docs/runbooks/heartbeat-go-live.md` against this SPEC at WS-F
  Planning/Design closure.
