# ADR 0027 — Scheduler safety model (tempo substrate = shadow-mode, operator-invoked heartbeat; NOT a daemon)

- **Status:** Accepted (**CTO — decider; RACI 3.1 A (ADR ratifier); AADL GATE-1 Planning artifact — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / org-engine — the safety envelope for the ORGANISM tempo substrate (WS4 HEARTBEAT). A **decision doc only**: it fixes the invariants the WS4 implementation tickets must satisfy and ships **no runtime tempo code**. It does not modify `config/loop.yaml`, `scripts/check_loop_mode.py`, `scripts/break_glass.py`, or `config/features.yaml`; it names them as the invariants' enforcement points.
- **Deciders:** **CTO (accountable)** — ADR/architecture authority (RACI 3.1; IC authors, MGR reviews, CTO ratifies). CEO consulted (WS4 planning owner, ticket author); COO consulted (GATE-6 Maintenance Accountable — the tempo substrate is a maintenance-surface capability). The live flag-flip in §5 is a **Founder** human gate.
- **Relates:** ORGANISM WS4 HEARTBEAT (`docs/research/ORGANISM-PROGRAM-PLAN.md` §9 Q3 — the approved default #3; §WS4 tickets O4-T01…O4-T07). Cites — but does **not** edit — `config/loop.yaml` (the loop-mode SSOT), `scripts/check_loop_mode.py` (the loop-off tripwire), `scripts/loop_controller.py` (the promotion **evaluator**), `scripts/break_glass.py` (the kill-switch), `config/budgets.yaml` (the cost-cap SSOT), `scripts/cost/cost_ledger.py` + `scripts/check_cost.py` (cost accounting), `config/features.yaml` (feature-flag SSOT), and `config/risk_taxonomy.yaml` (`loop.yaml` ∈ `governance_or_policy` never-auto-approve paths). Builds on ADR 0019 (latent-machine feature flags, default OFF) and ADR 0023–0025 (the durable-execution run-model and load-bearing event store the heartbeat reads).
- **Supersedes / Amends:** nothing. This ADR **interprets and constrains** existing brakes by reference; it mutates none of them.

> **Numbering note.** The WS4 plan text (§WS4 O4-T01, §Appendix ADR ledger) names this artifact "ADR-0026" and the cockpit form-factor decision "ADR-0027". The append-only ADR numbering rule (README) already assigned **0026** to *communication-flows* (Accepted 2026-07-03), so scheduler-safety takes the next free number, **0027**, and the cockpit form-factor decision (WS5 O5-T01) will take **0028**. Plan-text numbers are indicative; the README ledger is authoritative.

> WS4 HEARTBEAT is the load-bearing autonomy mechanism — the thing that lets the
> org advance work without a human pressing "go" each wave. Before any tempo code
> lands we need a merged, referenceable decision that fixes the safety envelope, so
> the implementation tickets (O4-T02 flow-router, O4-T03 scheduler, O4-T06
> safety-rail drills) build **against a contract**, not against an agent's judgement
> of the day. This ADR closes GATE-1 (Planning) for WS4 by making the "NOT a daemon,
> shadow-first, human-in-the-loop" stance the architectural contract. **No dispatch
> behaviour changes on merge.**

## Context

The `--tick` question is a genuine fork the ORGANISM audit surfaced (§9 Q3): the
platform's **"NOT a daemon" law** (an agent is operator-invoked, never a
background timer) sits in tension with the WS4 goal of **autonomous tempo** (the
org advancing waves on its own cadence). Ruling this wrong in either direction is
expensive:

- **Too autonomous** — a real background daemon that dispatches waves on a wall
  clock — violates the "NOT a daemon" law, can burn tokens unattended, and could
  auto-advance work past a gate no human approved.
- **Too manual** — no tempo substrate at all — leaves WS4's whole reason for
  existing unbuilt.

The platform already ships the brakes this decision leans on; none of them are
invented here:

- **`config/loop.yaml`** — the loop-mode SSOT: `mode: shadow`, `auto_apply: false`,
  the `ladder: [shadow, measured, limited_live, full]`. Editing it is
  governance/policy → never-auto-approve (QONUN-5; `config/risk_taxonomy.yaml`
  lists `**/loop.yaml`).
- **`scripts/check_loop_mode.py`** — the loop-off tripwire (a `diagnostics.py`
  dimension). It FAILS (exit 1) if `mode ∈ {limited_live, full}` or if
  `auto_apply` is anything but `false`. Exit 0 today.
- **`scripts/loop_controller.py`** — the promotion **evaluator** (`--tick`,
  `--propose`). It NEVER mutates: it reports eligibility to climb the loop ladder
  one rung, and that requires ≥ 7 clean live T1–T7 days **and** a human-approved
  GATE-6 `capability_promotion` record (`max_quality_drop 0`). With no live data it
  reports "not eligible" and fabricates nothing.
- **`scripts/break_glass.py`** — the 60-minute, single-rollback-scope, audit-logged
  emergency override, `is_active(now)` auto-expiring.
- **`config/budgets.yaml`** — per-run and per-day cost caps (`caps.per_run`,
  `caps.per_day`), enforced/accounted by `scripts/cost/cost_ledger.py`,
  `scripts/check_cost.py`, and alerted by `scripts/alerting.py`.
- **`config/features.yaml`** — latent-machine feature flags (ADR 0019), default OFF
  until a real consumer is live.
- **The never-auto-approve law** (QONUN-5) — gates and interrupt-cards ALWAYS wait
  for the Founder; `new_goal`, `governance_or_policy`, `gate5_deployment`, and the
  other never-auto-approve categories can never carry `approval: auto*`.

The question is not "build new safety" — it is "which **existing** brakes bind the
tempo substrate, and in what shape". This ADR answers that as a closed set of
invariants.

**AADL stage.** GATE-1 Planning. A decision doc; it ships no runtime tempo change.

**Extend-vs-new posture (binding).** CONSTRAIN, do not mutate. This is a NEW ADR
file (highest existing is 0026 → this is 0027). It edits none of the brakes above;
it records the envelope they jointly form and that the WS4 code (O4-T02…O4-T06)
must live inside. WS4 is "**activate, don't duplicate**": the heartbeat *calls* the
existing evaluators/brakes, it never reimplements the 7-clean-day/GATE-6 rule or a
private budget check.

## Decision

The ORGANISM tempo substrate is a **SHADOW-MODE, operator-invoked heartbeat**
(§9 default #3): `scripts/loop_controller.py --tick`, driven by an **optional**
launchd/cron entry **the Founder chooses to enable**. It is **not a daemon** and it
never runs the org past a human gate. The following are the **binding scheduler
invariants** — the contract every WS4 implementation ticket must satisfy, and the
citation any future "can the heartbeat do X?" question resolves to.

### SI-1 — Operator-invoked, NOT a daemon

The heartbeat is a **one-shot `--tick`**: one invocation evaluates the trigger
state (`.events.jsonl` — `ticket_created` / `wave_completed` / `interrupt_answered`
/ after-N-runs / cron) and dispatches **at most one wave**, then exits. It holds no
long-lived process, no internal wall-clock loop, no self-rescheduling timer.

- Cadence, if any, is supplied **externally** by an OS scheduler (launchd/cron) that
  the **Founder** opts into — the same way a human would re-run `/daslab-cycle`,
  only on a timer the Founder owns and can remove. The tempo lives in the OS entry,
  never inside the process.
- This preserves the "**one operator invocation = one wave, no background timer**"
  contract (plan §WS4). An absent or disabled launchd/cron entry means the heartbeat
  simply does not fire — the default, shipped state.
- The launchd/cron entry is **optional and off by default**. Nothing in this repo
  installs it; enabling it is a deliberate Founder act (see SI-7).

### SI-2 — `loop.yaml` stays `shadow` + `auto_apply: false` (check_loop_mode stays exit 0)

The heartbeat **never** edits `config/loop.yaml`. Under this ADR the loop stays
`mode: shadow`, `auto_apply: false`, permanently, so
`scripts/check_loop_mode.py` **continues to exit 0** and the `diagnostics.py`
loop-off dimension stays green.

- The heartbeat may **READ** metrics and **dispatch** waves; it may **never** flip
  `loop.yaml` to `measured` / `limited_live` / `full`, nor set `auto_apply: true`.
  Doing so is a governance/policy edit → **QONUN-5 human-only**, forbidden to
  automate.
- Promoting the *self-optimizing loop* up its ladder (`shadow → measured → …`) is a
  **separate, stricter** governance path, unchanged by this ADR: it needs
  `loop_controller.evaluate_promotion` to report eligible (≥ 7 clean live T1–T7
  days) **plus** a human-approved GATE-6 record, and a human then edits `loop.yaml`.
  That path is orthogonal to — and must not be conflated with — the heartbeat going
  live (SI-7). **The heartbeat going live does not touch `loop.yaml`.**
- Where the heartbeat needs the promotion verdict, it **calls
  `loop_controller.evaluate_promotion`** as the gate — it never reimplements the
  clean-day/GATE-6 rule (WS4 "activate, don't duplicate").

### SI-3 — Break-glass kill-switch is honored

Before dispatching a wave a `--tick` MUST consult `scripts/break_glass.py`
`is_active(now)`. The kill-switch is a hard stop for the tempo substrate:

- The Founder (or on-call) can halt all autonomous dispatch by activating
  break-glass (`break_glass.py activate`); while any override is live the heartbeat
  **dispatches nothing**. Break-glass auto-expires after 60 minutes, so this is a
  bounded, audited stop — never a silent permanent disable.
- Consulting break-glass is read-only and appends nothing; the heartbeat never
  activates or clears break-glass itself (that is a human/operator act, audit-logged
  to `board/.events.jsonl`).

### SI-4 — Quiet hours

The heartbeat honors a **configured quiet-hours window** during which it dispatches
no waves. A `--tick` that fires inside the quiet window evaluates to **idle** (logs
the skip; dispatches nothing).

- Quiet hours are declared in the scheduler config (the future `board/schedule.yaml`
  the O4-T03 scheduler ticket introduces), not hard-coded. An unset/empty quiet-hours
  config means "no quiet window" — but the invariant is that the mechanism exists and
  the heartbeat obeys it.
- Rationale: bounded blast radius during the hours a human is least able to watch —
  the substrate defaults to *quiet*, and autonomy is the exception a human widens.

### SI-5 — Per-run and per-day budget caps (cost-ledger enforced)

Every `--tick` is a cost event bounded by `config/budgets.yaml`:

- **Per-run caps** (`caps.per_run`) — a single wave a `--tick` dispatches must not
  exceed the per-run input/output-token and cost caps.
- **Per-day caps** (`caps.per_day`) — the heartbeat MUST consult the cost-ledger
  (`scripts/cost/cost_ledger.py` / `scripts/check_cost.py`) for spend already
  accrued in the calendar day; a `--tick` that would breach the per-day cap
  evaluates to **idle** and dispatches nothing (breach → `scripts/alerting.py`).
- Caps are read from `budgets.yaml` (currently informational until the C1 cost-gate
  is promoted per ADR 0020's data discipline); the heartbeat treats them as its
  **hard dispatch ceiling** regardless of the org-wide gate promotion state — a
  self-imposed autonomy budget stricter than the shared gate.

### SI-6 — Max-concurrent-waves cap

The heartbeat runs **at most one wave at a time**. A `--tick` that fires while a
prior heartbeat-dispatched wave is still in flight evaluates to **idle** (it does not
start an overlapping wave).

- Concretely `max_concurrent_waves = 1` for the autonomous substrate. This is the
  tempo-substrate analogue of the "one invocation = one wave" contract and is
  **narrower** than the operator-invoked `/daslab-cycle`, where the Model-Allocation
  Law removed the parallel cap: a *human* running a wave is watching it; an
  *unattended timer* must not stack waves.
- The in-wave zone-collision correctness rule (no two same-`zone` tickets in one
  wave) is unchanged and still applies within the single wave a `--tick` dispatches.

### SI-7 — Never-auto-approve; live only on an explicit Founder flag-flip after a ≥ 3-day clean shadow window

The never-auto-approve law is absolute for the tempo substrate:

- **Gates and interrupt-cards ALWAYS wait for the Founder.** The heartbeat may
  advance work up to a gate/interrupt and then **stops**; it never signs a gate,
  never answers an interrupt-card, never authorizes a new goal (QONUN-3), never sets
  `approval: auto*` on a never-auto-approve-category ticket, and — per SI-2 — never
  flips a governance flag. A GATE-5-open deployment stays blocked (machine-enforced).
- **Shadow-first.** The heartbeat ships behind a `config/features.yaml` flag
  (a new heartbeat key added to the feature-flag `DEFAULTS`, **default OFF**, per
  ADR 0019 — distinct from the already-live `organism_emit` channel). In its default
  shipped state it **observes and records** (what it *would* dispatch) without
  dispatching.
- **Live only on an explicit Founder flag-flip after a ≥ 3-day clean shadow window.**
  Moving from shadow-observe to live-dispatch requires (a) a **≥ 3-day** window of
  clean shadow readings (rolling `T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7 holds`, per O4-T07) and
  (b) the **Founder** explicitly flipping the feature flag ON (and, to run
  unattended, opting into the launchd/cron entry of SI-1). No agent may perform this
  flip; it is a QONUN-5 human-only act.
- **Two distinct clocks, do not conflate.** This ≥ 3-day heartbeat-go-live window is
  a conservative gate on *the substrate dispatching real waves*; it is **not** the
  loop-mode promotion gate (`loop_controller`'s ≥ 7 clean days + GATE-6), which
  governs `loop.yaml`'s mode and stays untouched (SI-2). The heartbeat can be live
  while `loop.yaml` remains `shadow` forever.

## Consequences

**Positive.**
- WS4 O4-T02 (flow-router), O4-T03 (scheduler), O4-T04 (metrics feeder), O4-T05
  (run-workspaces) and O4-T06 (kill-switch/safety-rail drills) build against a
  **fixed, closed set of seven invariants** instead of re-deriving safety per
  ticket; O4-T06's acceptance ("zero gate/approval violations in the event log")
  becomes a direct test of SI-3…SI-7.
- The "NOT a daemon" law and "autonomous tempo" goal are reconciled without editing
  either: tempo lives in an **optional, Founder-owned OS scheduler entry**, while the
  process stays a one-shot `--tick`. The org can advance on a cadence without a
  background daemon existing in-repo.
- Every brake is **activated, not duplicated**: the heartbeat calls
  `loop_controller.evaluate_promotion`, `break_glass.is_active`, and the cost-ledger,
  so there is exactly one implementation of each rule and `check_loop_mode.py` stays
  green by construction.

**Negative / accepted.**
- The heartbeat is deliberately **less capable than a real daemon**: single wave at a
  time, quiet hours, a self-imposed budget ceiling, and a human gate to go live. This
  caps throughput. **Accepted** — bounded blast radius is the whole point of a
  load-bearing autonomy mechanism; speed is recovered later, by a Founder widening the
  envelope, never by an agent.
- Quiet hours and `max_concurrent_waves` need a home in the scheduler config
  (`board/schedule.yaml`, introduced by O4-T03); until that lands the invariants are a
  written contract, not yet executable code. **Accepted** — GATE-1 Planning fixes the
  contract; the enforcing code is downstream WS4 work whose acceptance hooks cite this
  ADR.
- Two clean-window clocks now coexist (≥ 3-day heartbeat-go-live vs.
  `loop_controller`'s ≥ 7-day loop-promotion). **Accepted** — SI-7 writes down the
  distinction explicitly so they are never conflated; they gate different things
  (dispatching real waves vs. editing `loop.yaml`).

**Law check.**
- **Charter / RACI** — the CTO is the ADR ratifier (RACI 3.1 A: IC authors, MGR
  reviews, CTO ratifies); this ADR is decided by the CTO, with COO consulted as the
  GATE-6 Maintenance Accountable. It amends no policy — it constrains existing brakes
  by reference.
- **AADL** — a GATE-1 Planning artifact for ORGANISM WS4; no gate skipped; ships no
  runtime tempo change. It reaffirms the never-auto-approve law for gates/interrupts
  and keeps GATE-5-open deployments blocked.
- **Board audit / governance-as-policy** — no SSOT edited in place (`loop.yaml`,
  `check_loop_mode.py`, `break_glass.py`, `features.yaml`, `budgets.yaml` all
  untouched); the envelope is recorded here by reference so the append-only audit
  trail holds. No never-auto-approve category is triggered (a decision doc, not a
  policy/flag mutation) — indeed SI-2/SI-7 *reinforce* QONUN-5: `loop.yaml` and any
  live flag-flip stay human-only.
- **Project placement** — a platform-level ADR under `docs/adr/`; no project artifact
  written; the `board/tickets/` ticket carries no `project:` field.
- **Model allocation** — unchanged; CTO on opus per the table.

## Enforcement / acceptance

- This ADR is decided by the **CTO** (RACI 3.1, GATE-1 Planning) and is `Accepted` on
  merge. It adds a row to `docs/adr/README.md` and extends the WS4 theme.
- SI-1…SI-7 are the contract the WS4 implementation tickets satisfy and their
  acceptance hooks test:
  - **SI-2** — `scripts/check_loop_mode.py` **exit 0** (O4-T01, O4-T03 acceptance:
    "`check_loop_mode` stays green").
  - **SI-3…SI-7** — O4-T06's "**zero gate/approval violations in the event log**"
    kill-switch/safety-rail drills (budget/day caps, quiet hours, gates never
    auto-approved).
  - **SI-7 go-live** — O4-T07: a **≥ 3-day** clean shadow run
    (`T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7` on a rolling window), then a **Founder** flag-flip.
- The heartbeat MUST **call** `loop_controller.evaluate_promotion`,
  `break_glass.is_active`, and the cost-ledger — never reimplement their rules — and
  add its feature key to `config/features.yaml` `DEFAULTS` **default OFF** (ADR 0019).
- Any future "can the heartbeat run past a gate / dispatch overlapping waves / flip
  `loop.yaml` / go live without the Founder?" question resolves to **no** by
  SI-2/SI-6/SI-7. An undeclared autonomy is not in the envelope — so it is not
  permitted.
