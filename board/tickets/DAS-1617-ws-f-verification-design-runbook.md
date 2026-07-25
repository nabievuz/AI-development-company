---
id: DAS-1617
title: WS-F Design — SI-1..SI-7 verification evidence design and go-live runbook addenda
status: done
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-003, FR-005]
labels: [governance, security]
zone: docs/design
depends_on: [DAS-1616]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-F).** Design what "SI-N is verified"
concretely means, and what (if anything) the existing go-live runbook still needs.
No new scheduler/kill-switch code — this is an evidence-mapping and documentation
design stage.

- **Evidence map (FR-005):** for each of SI-1…SI-7, name the exact existing
  enforcement artifact that proves it — e.g. SI-1 → `loop_controller.py`'s one-shot
  `--tick` contract + its tests; SI-2 → `scripts/check_loop_mode.py` exit-0;
  SI-3 → `scripts/break_glass.py` `is_active()` consult path; SI-4 → the quiet-hours
  config/tests; SI-5 → `config/budgets.yaml` + cost-ledger; SI-6 →
  `max_concurrent_waves = 1` enforcement; SI-7 → `check_heartbeat_readiness.py` +
  the never-auto-approve law. Flag any invariant with no currently-passing artifact
  as a **real gap** and hand it to DAS-1618/1619 — do not paper over one.
- **Runbook addenda (FR-003):** review `docs/runbooks/heartbeat-go-live.md` against
  SPEC-010; confirm it already separates the ≥3-day heartbeat clock from
  `loop_controller`'s ≥7-day loop-promotion clock and names the Founder-only flip.
  If MUSTAQIL's monthly-credit-ceiling precondition (Q9/FR-004) is not yet folded in,
  design the minimal addendum — extend the existing runbook, never fork a second one.
- Security Lead consulted on the never-auto-approve boundary (SI-7); SRE Lead
  accountable (owns the scheduler/runbook surface per DAS-1538 precedent).

## Acceptance criteria
- [x] A design note (folded into this ticket or a short doc under `docs/design/`)
      maps each SI-1..SI-7 invariant to one named, currently-existing enforcement
      artifact — any gap explicitly flagged for DAS-1618/1619.
      → `docs/design/ws-f-tempo-verification.md` §1 (evidence map, `verified how`
      column) + §2 (per-invariant command + exact pass predicate); G1 §3, G2 §4, G3 §5.
- [x] `docs/runbooks/heartbeat-go-live.md` reviewed against SPEC-010 SC-004; confirmed
      compliant or a minimal, scoped addendum designed (credit ceiling / MUSTAQIL
      context) — no fork, no rewrite of the Founder-flip section.
      → addendum applied in place: two-clocks table, credit-ceiling precondition,
      step-3 gate line, step-7 relabel, Related entries. Step 4 (THE FLIP) untouched.
- [x] Security Lead review recorded on the SI-7 never-auto-approve boundary.
      → design §6 (claim, 3 verification mechanisms with verbatim output, verdict);
      one residual (`features.yaml` path-matcher asymmetry) escalated to CTO for
      Security Lead adjudication rather than self-cleared — §6.4.
- [x] `board_lint`/`check_spec_consistency` green.
      → plus `diagnostics.py` 100/100 and `check_links.py` clean (see log).

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Design). Maps SI-1..SI-7 to existing enforcement
artifacts; scopes the runbook addenda to the MUSTAQIL credit-ceiling precondition.

### 2026-07-24 — SRE / DevOps Lead
**GATE-2 (Design) CLOSED for WS-F TEMPO.** Design/documentation stage only — no
scheduler, kill-switch, readiness reporter, credit accountant, or second runbook was
authored; **no flag was flipped** (`heartbeat_enabled` stays `false`, `ws_f_heartbeat`
stays the inert placeholder); DAS-1622 stays `blocked` by design (FR-006) and was not
touched. Exactly three paths written: `docs/design/ws-f-tempo-verification.md` (new),
`docs/runbooks/heartbeat-go-live.md` (extended in place), and this ticket.

**1. Design note — `docs/design/ws-f-tempo-verification.md`.** Builds on DAS-1616's
GATE-1 coverage map (extended, not redone) and adds the operational half:

- **§1 evidence map** — each of SI-1…SI-7 → one named, currently-existing enforcement
  artifact owned by a `done` ticket, plus a **verified-how** column (the command).
- **§2 verification protocol** — the load-bearing handoff to DAS-1620: per invariant,
  the exact command and the exact output that constitutes a pass. Three non-obvious
  rules recorded there rather than left to the drill author's judgement:
  - **SI-1's pass predicate is *termination*, not a string** — a `--tick` that did not
    return would be the daemon SI-1 forbids.
  - **SI-7's readiness pass is honesty, not exit 0.** `check_heartbeat_readiness.py`
    exits **1** today (`0/3` clean days) and that red is the *correct* result. The
    predicate DAS-1619/1620 must assert is verdict ⟺ evidence on disk; a `READY`
    verdict on <3 clean rows is the failure, not the red.
  - **Count discipline** — the drill asserts `exit 0 ∧ 0 failed ∧ collected ≥ baseline`,
    never `== 195`; DAS-1618 will add tests, and an equality assertion would break the
    moment the gap it exists to close gets covered.
- **§2.3** records what a verification pass does **not** establish, so DAS-1619 cannot
  overclaim (no clean window exists; SI-1's OS half unverifiable in-repo; the credit
  ceiling is a data check today, not an enforcement check).

**2. G1 (SI-5 / FR-004) — designed, not fixed here; handed to DAS-1618 (§3).** The
minimal wiring that gives the monthly credit ceiling a `--tick` enforcement point,
**reusing `ws_b_admission` — a second credit accountant is explicitly forbidden**:

- **Call site 1 — `scripts/loop_controller.py`:** a thin `_monthly_credit_exhausted()`
  adapter beside `_per_day_budget_exceeded`, calling `ws_b_admission`'s
  `load_mustaqil_budgets()` + `check_credit_exhaustion()` directly. ≤ ~15 lines, **zero
  arithmetic of its own**; failure-isolated to `False`. Surfaced in `safety_rails` so
  it is observable in **shadow** mode too.
- **The gotcha DAS-1618 must not walk into:** call the two *pure* functions, **never**
  `admit()` (fails closed on the absent per-tick `model`, LAW 3 → every tick REJECTED)
  and **never** `gated_admit()` (gated on `ws_b_agent_sdk_runner`, a *different* flag —
  a safety rail that vanishes when an unrelated flag is OFF is not a safety rail).
- **Call site 2 — `scripts/flow_router.py`:** one `monthly_credit_exhausted` field on
  `TickContext` + one clause in `_dispatch_blocked`, placed after the SI-5 per-day
  clause and before SI-6 (keeps the SI-5 clauses adjacent and the reason string
  deterministic for `TestDeterminism`).
- **Decision semantics on exhaustion:** the action is **`idle`**; `sanctioned_pause` is
  a *reason string*, **never a fourth action**. `flow_router.DECISIONS` must stay
  exactly `{dispatch, validate, idle}` — that closed set *is* SI-7's structural
  enforcement (`decision_alphabet_is_closed()`, `TestDecisionAlphabet`); widening it
  would trade a structural guarantee for a runtime one. Blocks **dispatch only, never
  `validate`** (the quiet-hours precedent). Never an error, never a non-zero exit,
  never a false-green. `metered_overflow` stays OFF and unreachable — no parameter,
  kwarg, flag, or env var may enable it.
- **Call site 3 — `scripts/check_heartbeat_readiness.py`:** resolves the residual that
  §3.3 alone leaves open. `config/budgets.yaml` declares credit *per plan* but never
  which plan is **active**, and `CreditState`'s dataclass default (`max_20x`) must NOT
  be inherited — assuming the most generous plan would under-report exhaustion on Pro.
  With no declared plan the ceiling is correctly **inert** (unknown plan → not
  exhausted). Rather than guess (unsafe) or fail closed in the tick (a false-red that
  freezes the substrate and *prevents* the shadow window from ever accumulating), the
  undeclared plan becomes a **readiness blocker**: `ready = (not flag_on) ∧ window_met ∧
  credit_precondition_met`. Net: the heartbeat can never be declared READY while its
  outer ceiling is unenforceable, and is never frozen by an unconfigured one. DAS-1618
  also adds `mustaqil.monthly_credit_ceiling.active_plan` (a Founder-visible budget
  declaration; the file's open `[NEEDS VERIFICATION at WS-B go-live]` marker is the
  same question and is **not** agent-resolvable). `used_usd` comes from the month-to-date
  window of the ledger the tick already reads — same reader, no new cost accounting.
- **ADR record (CTO's standing call, carried forward unchanged):** ADR-0027 stays
  `Accepted` and **unamended at this stage**; the monthly ceiling is an extension of
  SI-5, not a contradiction. When DAS-1618 lands the wiring the clean record is an
  **ADR-0027 addendum ratified by the CTO** (RACI 3.1 — not an SRE Lead act). Recorded
  as a required DAS-1618 companion item so it is not lost between stages.

**3. G2 (SC-004 / FR-003) — minimal scoped addendum APPLIED to the existing runbook.**
No fork; **step 4 (THE FLIP) is byte-identical** — its text, its QONUN-5 citation, and
its "no agent may make this edit" sentence are untouched. Four edits:

- A **"Two clocks — and one release criterion — do not conflate"** table after *What
  "live" changes*, giving each of the three "≥N" numbers its bar, checker, what it
  gates, and what it does **not**: (1) **≥3 clean days** — SI-7 /
  `check_heartbeat_readiness.py` → gates `heartbeat_enabled`; (2) **≥7 clean days +
  a human-approved GATE-6 record** — SI-2 / `loop_controller.MIN_CLEAN_DAYS = 7` →
  gates `config/loop.yaml` `mode` (never `heartbeat_enabled`; the heartbeat can be live
  while `loop.yaml` stays `shadow` forever); (3) **≥7 rolling waves** → gates the
  `VERSION 2.0.0` bump and is **not a clock at all** — it counts waves, not days, and
  authorizes no autonomy. Rows 2 and 3 both contain the numeral 7 and mean entirely
  different things — that adjacency was the conflation SI-7 forbids.
- A **monthly-credit-ceiling precondition** in the *Precondition* section with its
  check command, the `sanctioned_pause`/`metered_overflow: OFF` semantics, and the
  open `[NEEDS VERIFICATION at WS-B go-live]` marker.
- One command line added to **step 3**'s Founder-verified gate list.
- **Step 7** relabelled explicitly as the *release criterion*, cross-referring the table.

**4. G3 — no action, as instructed.** SI-1's OS-scheduler half is covered-by-construction
(`board/schedule.yaml` `installed: false`; nothing in-repo installs launchd/cron). §5
records it and **forbids DAS-1620 from authoring a scheduler inspector/installer/mock** —
inventing one would put a scheduler-installing artifact in a repo whose contract is that
it never installs one.

**5. Security review — SI-7 never-auto-approve boundary (§6). Consulting, not
self-certifying.** Claim verified: *no agent, on any WS-F ticket, has a reachable path
that sets `heartbeat_enabled: true`, signs a gate, or answers an interrupt-card; and no
never-auto-approve-category ticket can carry `approval: auto*`.* Three independent
mechanisms, all green on observed output:

1. **Structural** — `flow_router.DECISIONS` is the closed frozenset
   `{dispatch, validate, idle}`; there is no `approve`/`answer` action to invoke.
2. **Event-log scanner** — drill rail `SI-7=ok`, `zero gate/approval violations`, with a
   scanner-has-teeth negative test so a clean result is not a blind scanner.
3. **Board CI blocker**, verbatim:
   `OK: 182 tickets checked, no never-auto-approve violations.` (exit 0)

DAS-1622's real frontmatter (`stage: GATE-5`, `labels: [governance, security]`, **no
`approval:` field**) was evaluated through the live
`check_never_auto_approve.matches_category` and resolves to **two** never-auto-approve
categories (`gate5_deployment`, `security_sensitive`) — were it ever to carry
`approval: auto*`, CI would fail it twice. **VERDICT: boundary VERIFIED.**

**ESCALATION → CTO (for Security Lead adjudication) — one residual I do not hold the
authority to resolve.** `config/risk_taxonomy.yaml`'s `governance_or_policy` matcher
lists `**/loop.yaml` (SI-2's SSOT) among its paths but **not** `**/features.yaml`
(SI-7's flip point). Probed against the live matcher:

| synthetic frontmatter | categories matched |
|---|---|
| `approval: auto` + `paths: ["config/loop.yaml"]` | `governance_or_policy` |
| `approval: auto` + `paths: ["config/features.yaml"]` | **none** |
| `approval: auto` + `stage: GATE-5` | `gate5_deployment` |
| `approval: auto` + `labels: [security]` | `security_sensitive` |

**Latent, not live.** The flip is structurally unreachable, and every WS-F ticket
(DAS-1622 included) carries `stage: GATE-5` and/or `labels: [security]`, so today's
boundary holds through two independent matchers. The exposure is a *future* ticket that
edits `config/features.yaml` while declaring neither the GATE-5 stage nor a
security/governance label. **Not fixed here** because the fix edits
`config/risk_taxonomy.yaml` — itself a `governance_or_policy` never-auto-approve path,
outside this ticket's `zone: docs/design`, and a Security Lead consult / CTO
ratification call. Asserting a taxonomy change from this seat would be precisely the
self-issued clearance this review exists to avoid. **Non-blocking for GATE-2.**

**6. Gates re-run by me (observed output, not claimed):**
- `python3 scripts/board_lint.py` → `OK — 181 ticket(s) checked, 0 violations.` (exit 0;
  the single pre-existing non-fatal DAS-1507 body-status WARN is unrelated to WS-F).
- `python3 scripts/check_spec_consistency.py` → `OK: 10 SPEC.md file(s) checked,
  structure + ticket refs consistent.` (exit 0).
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (Governance, Portability 15/15,
  Security 10/10, Git-hygiene 5/5 all PASS).
- `python3 scripts/check_links.py` → `check_links: OK — no broken relative links in
  tracked Markdown.` (exit 0). That scanner reads `git ls-files`, so the **new, untracked**
  design note would not have been covered — I additionally ran its own `broken_links()`
  against both files directly: `docs/design/ws-f-tempo-verification.md` → no broken links
  (3 relative targets resolve); `docs/runbooks/heartbeat-go-live.md` → no broken links.

**7. Evidence re-run for the map (observed, all local/read-only):**
- 8 suites → **195 passed** (`test_no_daemon` 43 · `test_check_loop_mode` 9 ·
  `test_break_glass` 13 · `test_scheduler` 42 · `test_flow_router` 37 ·
  `test_kill_switch_drill` 24 · `test_check_heartbeat_readiness` 9 ·
  `test_loop_controller` 18).
- `kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok
  SI-7=ok SI-2=ok` … `OK — every safety rail held on every pass (zero gate/approval
  violations, loop off).` (exit 0).
- `check_loop_mode.py` → `OK: loop off — mode 'shadow', auto_apply false (levers only,
  no controller).` (exit 0).
- `loop_controller.py --tick --trigger cron_tick` → `[SHADOW-OBSERVE] tick: cron_tick ->
  IDLE`, all three rails `False`, promotion blockers `0/7 clean day(s)` + no GATE-6
  record, exit 0 (the process **returned** — SI-1's one-shot contract).
- `ws_b_admission.py` → `mustaqil budgets loaded: True`; `monthly_credit_ceiling:
  {'plan_credit_usd': {'pro': 20, 'max_5x': 100, 'max_20x': 200}, 'on_exhaustion':
  'sanctioned_pause', 'metered_overflow': False}`.
- `check_heartbeat_readiness.py` → **`VERDICT: NOT READY`**, `0/3 consecutive clean
  day(s) (from 0 history row(s))`, exit 1 — recorded verbatim in the design note §2.2.
  This is the honest, expected baseline and is unchanged from GATE-1; nothing was
  massaged and **no readiness claim is made**.

**Decision.** GATE-2 CLOSED. SI-1…SI-7 each have a named enforcement artifact plus a
reproducible pass predicate; G1 has a concrete design bound to `ws_b_admission` with the
forbiddances written down; G2 is applied to the one runbook; G3 is recorded as
covered-by-construction with an explicit "do not invent an artifact" instruction; the
SI-7 boundary is verified with one residual escalated rather than self-cleared.
`status: done` — this unblocks exactly **DAS-1618** (sre-eng, Development).
