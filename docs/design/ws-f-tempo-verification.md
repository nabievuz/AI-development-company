# WS-F TEMPO verification design — one named enforcement artifact per SI-1…SI-7, a reproducible per-invariant verification protocol, and the minimal wiring that gives FR-004's monthly credit ceiling a `--tick` enforcement point

- **Status:** Design (AADL Stage 2 — GATE-2) — SRE / DevOps Lead accountable (owns the scheduler/runbook surface, DAS-1538 precedent); CTO consulted (ADR-0027 ratifier, GATE-1 carry-in); Security Lead consulted — SI-7 never-auto-approve boundary (§6; one residual routed, §6.4)
- **Date:** 2026-07-24
- **Ticket:** DAS-1617 (WS-F Design); epic DAS-1615 (MUSTAQIL WS-F TEMPO)
- **Author:** SRE / DevOps Lead (responsible + accountable stage owner)
- **Binds to:** [ADR-0027](../adr/0027-scheduler-safety.md) (SI-1…SI-7, **Accepted** 2026-07-03, CTO ratified — **unamended by this doc**), [SPEC-010](../specs/010-mustaqil-ws-f-tempo/SPEC.md) (FR-001…FR-006 / SC-001…SC-004, reviewed at GATE-1), the DAS-1616 GATE-1 coverage map (this doc's carry-in — it is extended, not redone), `config/budgets.yaml` `mustaqil:` block (DAS-1543 — the budget SSOT), `config/risk_taxonomy.yaml` + `scripts/check_never_auto_approve.py` (QONUN-5), and [`docs/runbooks/heartbeat-go-live.md`](../runbooks/heartbeat-go-live.md) (the single go-live runbook — **extended in place**, never forked).
- **Reuses, never re-implements:** `scripts/ws_b_admission.py` (`load_mustaqil_budgets` / `check_credit_exhaustion` — the **sole** credit accountant, ADR-0034 SR-2), `scripts/loop_controller.py` (`tick`, `day_is_clean`, `clean_live_days`), `scripts/flow_router.py` (the closed decision alphabet), `scripts/break_glass.py`, `scripts/kill_switch_drill.py`, `scripts/check_heartbeat_readiness.py`, `scripts/cost/cost_ledger.py`.
- **Downstream:** **DAS-1618** (Development — implements §3's wiring and §2's residuals; `zone: scripts`), **DAS-1619** (the go/no-go readiness artifact — consumes §2's protocol + §3.5's new precondition), **DAS-1620** (Testing — the SI-1…SI-7 drill; §2 IS its spec), DAS-1621 (kill-switch drill), DAS-1622 (Deployment — **`blocked` by design**, FR-006; untouched by this doc).

> **Scope of this doc.** WHAT "SI-N is verified" means operationally and HOW a
> verifier reproduces it — the exact command, the exact output that constitutes a
> pass, and the artifact of record behind each of the seven invariants — plus the
> minimal design for the one substantive coverage gap (G1, the monthly credit
> ceiling) and the runbook addendum that closes the one wording gap (G2). It ships
> **no runtime code**: the credit-ceiling wiring is built by DAS-1618 against §3,
> and the drill is built by DAS-1620 against §2. This ticket touched exactly three
> paths: this file, `docs/runbooks/heartbeat-go-live.md` (§4), and its own ticket
> file. **No flag was flipped**; `heartbeat_enabled` stays `false` and its flip
> remains a Founder-only QONUN-5 act (ADR-0027 SI-7 / FR-006).

## 0. The verification model (one picture)

WS-F is a **governance-verification act, not an engineering build** (SPEC-010). So
the design surface here is not a system — it is a *proof obligation per invariant*.
Each of the seven invariants must resolve to one artifact that already exists, one
command a verifier can run today, and one output that is unambiguously a pass:

```
  ADR-0027 invariant  ──▶  named enforcement artifact  ──▶  verification command  ──▶  PASS predicate
        SI-N                (code/config in-repo,           (deterministic, local,     (exact string +
                             owned by a `done` ticket)       read-only, no network)     exit code)
                                     │                              │                        │
                                     ▼                              ▼                        ▼
                       §1 evidence map (the WHAT)      §2 verification protocol      §2 pass predicates
                                     │                   (the HOW — DAS-1620's spec) │
                                     │                                                │
                                     └──────────────▶ §3 G1: the one invariant whose artifact
                                                          does NOT reach the --tick path
                                                          (monthly credit ceiling — designed here,
                                                           built by DAS-1618)
```

Three rules govern the whole doc, and they are the reason it is short:

1. **Verify, do not rebuild (FR-001).** Every row in §1 names an artifact that
   exists today and is owned by a `done` ticket. Nothing in WS-F authors a second
   scheduler, kill-switch, readiness reporter, credit accountant, or runbook.
2. **A gap is designed, never asserted away (FR-005).** The two real gaps the CTO
   routed here (G1, G2) get concrete resolutions — G1 a wiring design handed to
   DAS-1618 (§3), G2 an addendum applied in this ticket (§4). G3 is
   covered-by-construction and gets **no** invented artifact (§5).
3. **An honest red is a pass.** `check_heartbeat_readiness.py` exits **1** today
   (`0/3 clean days`). That exit-1 is the *correct* observed state and the
   *expected* result of its verification (§2, SI-7). A verifier that treats
   "exit 0" as the SI-7 pass predicate would be asserting a readiness that does not
   exist — the precise failure mode SC-001 forbids.

---

## 1. Evidence map — one named, currently-existing enforcement artifact per invariant

Carried in from DAS-1616's GATE-1 map and extended with the **verified-how** column
(the command a verifier runs; §2 gives each one its exact pass predicate).

| SI | Invariant (ADR-0027) | Named enforcement artifact of record | Verified how (command) | Verdict |
|---|---|---|---|---|
| **SI-1** | Operator-invoked, NOT a daemon | `tests/test_no_daemon.py` (AST scan over the declared `SCHEDULER_FILES` set for `while True` / `threading.Timer\|Thread` / `sched` / asyncio `run_forever` / `time.sleep`-in-loop, plus `TestScannerCanary` proving the scanner has teeth); the one-shot `tick()` in `scripts/loop_controller.py` (holds no process, loop, or self-rescheduling timer) | `pytest tests/test_no_daemon.py` **+** `loop_controller.py --tick` returns to the shell | **PRESENT** — in-repo half fully covered; OS-scheduler half is covered-by-construction (**G3**, §5) |
| **SI-2** | `loop.yaml` stays `shadow` + `auto_apply: false` | `config/loop.yaml` (the SSOT); `scripts/check_loop_mode.py` (the tripwire, a `diagnostics.py` dimension); `kill_switch_drill.py` rail `SI-2 check_loop_mode` (which also asserts the drill never edits `loop.yaml`); `tests/test_check_loop_mode.py`, `tests/test_scheduler.py::TestCheckLoopModeStaysGreen`, `tests/test_loop_controller.py::test_cli_does_not_mutate_loop_config` | `scripts/check_loop_mode.py` (exit 0) | **PRESENT** |
| **SI-3** | Break-glass kill-switch honored | `scripts/break_glass.py::is_active` (60-min auto-expiring, audit-logged); `loop_controller.tick` SI-3 branch; `flow_router._dispatch_blocked` `break_glass_active` clause; `kill_switch_drill.py` rail `SI-3 break_glass_kill_switch` (engage → IDLE, auto-expiry → dispatch restored); `tests/test_break_glass.py`, `tests/test_scheduler.py::TestTickSafetyRails` | `kill_switch_drill.py --smoke` (`SI-3=ok`) **+** `pytest tests/test_break_glass.py` | **PRESENT** |
| **SI-4** | Quiet hours | `board/schedule.yaml` `quiet_hours: {start: "22:00", end: "06:00", timezone: UTC}`; `loop_controller._in_quiet_hours` (midnight-wrapping, failure-isolated to `False`); `flow_router` `in_quiet_hours` clause; `kill_switch_drill.py` rail `SI-4 quiet_hours`; `tests/test_scheduler.py::TestInQuietHours` (incl. "quiet hours block dispatch, never validate") | `kill_switch_drill.py --smoke` (`SI-4=ok`) **+** `pytest tests/test_scheduler.py` | **PRESENT** |
| **SI-5** | Per-run and per-day budget caps (cost-ledger enforced) | `config/budgets.yaml` `caps.per_run`/`caps.per_day` **and** the stricter `mustaqil.caps.*` + `on_breach: idle_and_alert`; `loop_controller._per_day_budget_exceeded` (consults `scripts/cost/cost_ledger.py::aggregate_spans` — activate, don't duplicate); `flow_router` `per_day_budget_exceeded` clause; `scripts/check_cost.py`, `scripts/alerting.py::budget_governor`; `kill_switch_drill.py` rail `SI-5 budget_caps`; `tests/test_scheduler.py::TestPerDayBudget` | `kill_switch_drill.py --smoke` (`SI-5=ok`) **+** `pytest tests/test_scheduler.py` | **PRESENT for per-run/per-day.** The **monthly credit ceiling** (FR-004) has data but **no `--tick` enforcement point** → **G1**, designed in §3 |
| **SI-6** | Max-concurrent-waves cap | `board/schedule.yaml` `max_concurrent_waves: 1`; `flow_router._runs_in_flight` / `_wave_in_flight` (a `run_start` with no `run_end` → a would-be dispatch degrades to IDLE citing SI-6); `loop_controller._DEFAULT_MAX_CONCURRENT_WAVES = 1`; `kill_switch_drill.py` rail `SI-6 max_concurrent_waves`; `tests/test_flow_router.py::TestInFlightDetection`, `::TestDispatchSafetyGates` | `kill_switch_drill.py --smoke` (`SI-6=ok`) **+** `pytest tests/test_flow_router.py` | **PRESENT** |
| **SI-7** | Never-auto-approve; live only on a Founder flag-flip after a ≥3-day clean shadow window | **Structural:** `flow_router.DECISIONS = frozenset({dispatch, validate, idle})` — no `approve`/`answer` action exists to call. **Config:** `config/features.yaml` `heartbeat_enabled: false` + `scripts/feature_flags.py` `DEFAULTS`; `board/schedule.yaml` `never_auto_approve: true`. **Scanners:** `kill_switch_drill.py` rail `SI-7 never_auto_approve` (auto-approval event scanner + a scanner-has-teeth negative test + `decision_alphabet_is_closed()`); `scripts/check_never_auto_approve.py` (QONUN-5 CI blocker). **Clock:** `scripts/check_heartbeat_readiness.py` (the ≥3-day bar; `MIN_CLEAN_DAYS_HEARTBEAT = 3`). **Procedure:** `docs/runbooks/heartbeat-go-live.md` step 4 (Founder-only flip) | `kill_switch_drill.py --smoke` (`SI-7=ok`) **+** `check_never_auto_approve.py` (exit 0) **+** `check_heartbeat_readiness.py` (honest verdict) **+** `pytest tests/test_scheduler.py::TestTickNeverAutoApprove tests/test_flow_router.py::TestDecisionAlphabet` | **PRESENT** — boundary reviewed in §6. Runbook two-clock wording was **partial** → **G2**, closed in §4 |

**Provenance.** Every artifact above is owned by a `done` ticket (DAS-1472…DAS-1478,
DAS-1538, DAS-1543). WS-F verifies them; it rebuilds none of them (FR-001).

---

## 2. What "SI-N is verified" means operationally — the verification protocol

This section is the **load-bearing handoff to DAS-1620**. For each invariant: the
exact command, and the exact output that constitutes a pass. Everything is local,
read-only, deterministic, and network-free. All outputs below were **observed on
2026-07-24** during this ticket, not claimed.

### 2.0 The composite pre-check (run once, before the per-SI passes)

```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py -q
```

**PASS predicate:** `195 passed`, exit 0. Per-file split (asserted individually so a
regression localizes): `test_no_daemon` 43 · `test_check_loop_mode` 9 ·
`test_break_glass` 13 · `test_scheduler` 42 · `test_flow_router` 37 ·
`test_kill_switch_drill` 24 · `test_check_heartbeat_readiness` 9 ·
`test_loop_controller` 18.

> **Count discipline for DAS-1620.** The numbers above are the 2026-07-24 baseline,
> not a frozen contract — DAS-1618 will *add* tests. The pass predicate is
> `exit 0 ∧ 0 failed ∧ 0 errors ∧ collected ≥ baseline`, never an equality on a
> hard-coded total. A drill that asserts `== 195` fails the moment the gap it was
> written to close gets its test, which is exactly backwards.

### 2.1 Per-invariant pass predicates

| SI | Command | PASS predicate (exact) |
|---|---|---|
| **SI-1** | `python3 -m pytest tests/test_no_daemon.py -q` | `43 passed`, exit 0 — no daemon pattern in any declared `SCHEDULER_FILES` entry, and the canary proves the scanner would catch one |
| **SI-1** | `python3 scripts/loop_controller.py --tick --trigger cron_tick` | **The process returns** (exit 0) having printed exactly one decision. The one-shot contract is verified by *termination*, not by a string: a `--tick` that did not return would be the daemon SI-1 forbids. Observed: `[SHADOW-OBSERVE] tick: cron_tick -> IDLE`, exit 0 |
| **SI-2** | `python3 scripts/check_loop_mode.py` | Verbatim `OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).`, exit 0 |
| **SI-3** | `python3 scripts/kill_switch_drill.py --smoke` | The pass line contains `SI-3=ok` |
| **SI-4** | `python3 scripts/kill_switch_drill.py --smoke` | The pass line contains `SI-4=ok` |
| **SI-5** | `python3 scripts/kill_switch_drill.py --smoke` | The pass line contains `SI-5=ok` (per-day breach → IDLE; per-run ceiling present in the real SSOT) |
| **SI-5** | `python3 scripts/ws_b_admission.py` | `mustaqil budgets loaded: True` **and** the printed `monthly_credit_ceiling` shows `on_exhaustion: sanctioned_pause` + `metered_overflow: False` (a **data** check today; §3 makes it an enforcement check) |
| **SI-6** | `python3 scripts/kill_switch_drill.py --smoke` | The pass line contains `SI-6=ok` |
| **SI-7** | `python3 scripts/kill_switch_drill.py --smoke` | The pass line contains `SI-7=ok`, **and** the closing line is `kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).`, exit 0 |
| **SI-7** | `python3 scripts/check_never_auto_approve.py --board board --config config/risk_taxonomy.yaml` | `OK: N tickets checked, no never-auto-approve violations.`, exit 0 (observed 2026-07-24: `N = 182`) |
| **SI-7** | `python3 scripts/check_heartbeat_readiness.py` | See **2.2** — the pass predicate is *honesty*, not exit 0 |

Observed drill line, 2026-07-24, verbatim:

```
kill-switch-drill: running 1 pass(es) of the 6 safety rails...
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```

### 2.2 The SI-7 readiness predicate — why exit 1 is the pass today

`check_heartbeat_readiness.py` exits **0 only when READY** and **1 when NOT READY**.
Today the shadow window is `0/3` from `0` history rows, so the correct observed
result is **exit 1**. Verbatim, 2026-07-24:

```
HEARTBEAT go-live readiness (ADR-0027 SI-7 / §5 WS4) — evidence-gated report
==========================================================================
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  Founder-verified gates (this tool cannot check — confirm before flipping):
    - kill-switch drill passes: python3 scripts/kill_switch_drill.py --smoke
    - zero gate/approval violations in the event log (check_never_auto_approve + interrupts answered)
--------------------------------------------------------------------------
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
  Next: keep the scheduler in shadow (heartbeat_enabled: false) collecting
  counted waves; feed daily rows with metrics_history_feeder.py; re-run this check.
```

**PASS predicate (binding on DAS-1619 and DAS-1620):** the reporter's verdict
**matches the evidence on disk** — i.e. `clean_days` equals the streak actually
present in `board/.metrics-history.jsonl`, `heartbeat_enabled` echoes the real flag,
and `ready` is `false` whenever `clean_days < 3`. A **`READY` verdict with fewer
than 3 clean rows is the failure**, not the red. DAS-1620's drill therefore asserts
the *relationship* (verdict ⟺ evidence), seeding a synthetic history to exercise
both arms, and never asserts a bare exit code against the live repo.

### 2.3 What a verification pass does NOT establish

Recorded so the go/no-go artifact (DAS-1619) cannot overclaim:

- It does not establish that a clean shadow window exists — that is `0/3` and only
  counted waves move it (the runbook's stated precondition).
- It does not verify the **OS-scheduler half of SI-1** — nothing in-repo installs
  or inspects a launchd/cron entry (§5).
- It does not, **today**, verify that the monthly credit ceiling constrains dispatch
  — only that the ceiling *data* is present and correctly shaped (§3 is why).

---

## 3. G1 — giving FR-004's monthly credit ceiling a `--tick` enforcement point (design; built by DAS-1618)

### 3.1 The gap, precisely

`config/budgets.yaml` carries `mustaqil.monthly_credit_ceiling`
(`plan_credit_usd: {pro: 20, max_5x: 100, max_20x: 200}`,
`on_exhaustion: sanctioned_pause`, `metered_overflow: false`), and it **is** enforced
on the WS-B admission path (`scripts/ws_b_admission.py::check_credit_exhaustion`,
guarded against drift by `scripts/ws_b_health_check.py`). But
`scripts/loop_controller.py`, `scripts/flow_router.py`, and
`scripts/check_heartbeat_readiness.py` contain **zero** references to it. SPEC-010
FR-004 requires the ceiling to be "an additional hard dispatch ceiling **the
heartbeat honors**" — and the heartbeat's dispatch path never reads it. SI-5 in the
`--tick` path is per-run + per-day only.

### 3.2 The binding constraint: reuse `ws_b_admission`, author no second accountant

`ws_b_admission.check_credit_exhaustion(credit_state, mustaqil)` is the **sole**
implementation of "is the monthly credit exhausted". It already encodes the exact
semantics FR-004 needs (returns an exhaustion dict carrying `on_exhaustion`, or
`None`; an unknown plan is fail-safe-**inert**, never a fabricated exhaustion). The
`--tick` path must call it. It must not re-derive it.

**The non-obvious gotcha DAS-1618 must not walk into.** The tick must call the two
*pure* functions — `load_mustaqil_budgets()` and `check_credit_exhaustion()` —
**directly**. It must **not** route through `admit()` or `gated_admit()`:

- `admit()` fails closed on an absent `model` (LAW 3) and would return `REJECTED`
  for every tick — the heartbeat has no per-ticket model at tick time.
- `gated_admit()` is gated on the **`ws_b_agent_sdk_runner`** flag, a *different*
  flag from `heartbeat_enabled`. Routing the heartbeat's SI-5 ceiling through it
  would make the ceiling silently inert whenever WS-B is OFF — a safety rail that
  disappears when an unrelated flag is off is not a safety rail.

### 3.3 Call site 1 — `scripts/loop_controller.py`: a thin adapter, no arithmetic

A single helper beside the existing `_per_day_budget_exceeded`, following that
function's established shape exactly (lazy import inside the function, total failure
isolation, a plain `bool` out):

- `_monthly_credit_exhausted(budgets_path, credit_state=None) -> bool` — loads the
  `mustaqil:` block via `ws_b_admission.load_mustaqil_budgets(budgets_path)`, calls
  `ws_b_admission.check_credit_exhaustion(...)`, returns `exhaustion is not None`.
- **No arithmetic of its own** — target ≤ ~15 lines, zero comparisons against
  `plan_credit_usd`. If DAS-1618 finds itself writing `used >= limit`, the design has
  been violated.
- **Failure-isolated to `False`** (mirroring `_per_day_budget_exceeded`): a missing
  file, absent `yaml`, or an import error must never fabricate a pause. A fabricated
  pause would freeze the tick at `idle` forever and *prevent* the shadow window from
  ever accumulating — a false-red that blocks go-live is as damaging as a false-green.
- `tick()` computes it alongside the other rails and surfaces it in the returned
  `safety_rails` dict as `monthly_credit_exhausted`, and in `_print_tick`'s rail
  block. It is therefore visible in **shadow** mode too — which is the point: the
  ceiling must be observable in the shadow window before it can be trusted live.

### 3.4 Call site 2 — `scripts/flow_router.py`: one clause, and the decision alphabet does **not** move

- `TickContext` gains `monthly_credit_exhausted: bool = False` (defaulted, so every
  existing caller and test is unaffected).
- `_dispatch_blocked` gains exactly one clause, positioned **after** the SI-5
  per-day clause and **before** the SI-6 in-flight clause, so the two SI-5 clauses
  stay adjacent and the reason string stays deterministic (`TestDeterminism` asserts
  fixed reason strings):

  ```
  if ctx.monthly_credit_exhausted:
      return True, "monthly subscription credit exhausted — sanctioned pause (SI-5/FR-004)"
  ```

- `route_from_store` gains the matching keyword argument; the CLI gains
  `--credit-exhausted`, mirroring the existing `--budget-exceeded`.

**Decision semantics on exhaustion — `sanctioned_pause` is a REASON, never a fourth
action.** The outcome is `idle`. `flow_router.DECISIONS` stays exactly
`{dispatch, validate, idle}`. This is not a stylistic preference: the closed alphabet
*is* SI-7's structural enforcement, checked by
`kill_switch_drill.decision_alphabet_is_closed()` and
`tests/test_flow_router.py::TestDecisionAlphabet`. Adding a `paused` action would
widen the set that structurally cannot contain `approve`, and would trade a
structural guarantee for a runtime one. **Forbidden.**

Three further semantics, each traceable to `config/budgets.yaml`'s own wording:

- **Blocks dispatch only — never `validate`.** Credit exhaustion follows the
  quiet-hours precedent already asserted in `tests/test_scheduler.py`
  ("quiet hours block dispatch, never validate"). Validation is read-only and free;
  halting it would blind the org exactly when its budget is stressed.
- **Never an error.** Exhaustion must not raise, must not exit non-zero, and must
  not be logged as a failure. `--tick` still exits 0. It is "an expected idle,
  like a gate" (budgets.yaml, verbatim) — and equally never a false-green: the
  tick must say plainly *why* it idled.
- **`metered_overflow` stays OFF, unreachable.** No parameter, kwarg, CLI flag, or
  env var added by DAS-1618 may enable overflow. Flipping it is a Founder-only
  `config/budgets.yaml` edit, exactly as `ws_b_admission` already states.

### 3.5 Call site 3 — `scripts/check_heartbeat_readiness.py`: the ceiling becomes a go-live precondition

This is the call site that makes FR-004 real rather than decorative, and it resolves
a residual §3.3 alone would leave open.

**The residual.** `CreditState` needs a `plan` and a `used_usd`.
`config/budgets.yaml` today declares the credit *per plan* but never which plan is
**active** — there is no `active_plan` key. `CreditState`'s dataclass default is
`plan="max_20x"`, and the tick adapter must **not** inherit that default: silently
assuming the most generous plan would under-report exhaustion on a Pro account.
With no declared plan, `check_credit_exhaustion` correctly returns `None`
(unknown plan → never exhausted) and the ceiling is **inert**.

**The resolution — inert in the tick, blocking at the gate.** Rather than guess a
plan (unsafe) or fail closed in the tick (a false-red that freezes the substrate),
the undeclared plan becomes a **readiness blocker**:

- `assess()` gains a credit precondition. `ready` becomes
  `(not flag_on) and window_met and credit_precondition_met`.
- Two distinct blocker strings, because they are different conditions:
  `"monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared"`
  and `"monthly subscription credit exhausted — sanctioned pause in effect"`.
- Rendered as its own line beside the clean-window line, so the Founder-facing
  artifact shows the ceiling's status without reading YAML.

Net effect: the heartbeat can never be declared READY while its outer ceiling is
unenforceable, and it is never frozen by an unconfigured one. DAS-1618 must also add
`mustaqil.monthly_credit_ceiling.active_plan` to `config/budgets.yaml` (a
Founder-visible budget declaration; the file already carries an open
`[NEEDS VERIFICATION at WS-B go-live]` marker on the live plan's Agent-SDK terms —
the same open question, and it is **not** resolvable by any agent).

**`used_usd` source.** The tick already consults
`cost.cost_ledger.aggregate_spans(events).raw_estimated_cost_usd` for the per-day
cap. The month-to-date aggregate over the same ledger is the analogous number and
is the seam DAS-1618 uses — same reader, different window. No new cost accounting.

### 3.6 Explicit forbiddances for DAS-1618

1. **No second credit accountant.** `ws_b_admission.check_credit_exhaustion` stays
   the only implementation; `loop_controller` holds an adapter with no arithmetic.
2. **No new decision action** and no widening of `flow_router.DECISIONS`.
3. **No `metered_overflow` enablement path** of any kind.
4. **No edit to `config/features.yaml` or `config/loop.yaml`** — no flag moves; the
   `heartbeat_enabled` flip stays a Founder act (FR-006), and `ws_f_heartbeat`
   remains an inert placeholder that is never the flip point.
5. **No fabricated pause and no fabricated readiness** — every failure path is
   inert-and-honest, and every blocker names its own condition.
6. **No fork of the runbook** — §4 is the addendum; there is one go-live runbook.

### 3.7 ADR record (CTO's standing call, carried forward unchanged)

ADR-0027 SI-5's text names only `caps.per_run` / `caps.per_day`. The monthly ceiling
is a later DAS-1543 addition asserted by SPEC-010 FR-004 — an **extension, not a
contradiction**. ADR-0027 therefore stays `Accepted` and **unamended at this stage**;
this design edits no ADR. When DAS-1618 lands the wiring, the clean record is an
**ADR-0027 addendum (or a small amending ADR) ratified by the CTO** at that point —
the CTO is the ADR ratifier (RACI 3.1), and it is not an SRE Lead act. Recorded here
as a required DAS-1618 companion item so it cannot be lost between stages.

---

## 4. G2 — the runbook addendum (applied in this ticket)

`docs/runbooks/heartbeat-go-live.md` was reviewed against SPEC-010 SC-004. It already
names the Founder-only flip (step 4), already shows no agent-reachable path to
perform it, and already calls the LADDER "a **separate** gate". Two defects remained:

1. It never stated the loop-promotion clock's **≥7 clean day** figure beside the
   **≥3-day** heartbeat clock — so "separate gate" was asserted without the number
   that makes it checkable; and step 7's release criterion ("≥7 **rolling waves**")
   sat unlabeled next to that same numeral, inviting exactly the conflation SI-7
   forbids.
2. It carried no monthly-credit-ceiling precondition (FR-003 / FR-004).

**Applied — minimal and scoped, extending the existing file, no fork:**

- A new **"Two clocks — and one release criterion — do not conflate"** section after
  *What "live" changes*: a three-row table separating (a) the ≥3-day heartbeat
  go-live clock (SI-7 · `check_heartbeat_readiness.py` · gates `heartbeat_enabled`),
  (b) the ≥7-clean-day loop-promotion clock (SI-2 · `loop_controller.MIN_CLEAN_DAYS`
  = 7 **plus** a human-approved GATE-6 record · gates `config/loop.yaml` `mode`), and
  (c) the ≥7-rolling-wave `VERSION 2.0.0` release criterion — **neither clock**; it
  gates a version bump, not autonomy. Each row names what it gates and what it does
  **not**.
- A **monthly-credit-ceiling precondition** added to the *Precondition* section,
  with its check command, and one line added to step 3's Founder-verified gate list.
- Step 7 labelled explicitly as the release criterion, cross-referring the table.

**Not touched:** step 4 (THE FLIP) — its text and semantics are byte-identical. The
Founder-only act, the QONUN-5 citation, and the "no agent may make this edit"
sentence are unchanged.

---

## 5. G3 — SI-1's OS-scheduler half is covered-by-construction (no artifact, by design)

`tests/test_no_daemon.py` proves the *in-repo* scheduler files contain no daemon
pattern. The cadence itself lives in a **Founder-owned launchd/cron entry** that
this repo documents (`board/schedule.yaml`, `installed: false`) and deliberately
never installs — that is SI-1's whole design ("the tempo lives in the OS entry,
never inside the process"). **No repo-side enforcement artifact is possible, and
none is to be invented.** DAS-1620 must record SI-1's external half as
covered-by-construction with the two in-repo checks of §2.1 as its evidence, and
must **not** author a launchd/cron inspector, installer, or mock. Inventing one
would put a scheduler-installing artifact in a repo whose contract is that it never
installs one.

---

## 6. Security review — the SI-7 never-auto-approve boundary

Conducted by the SRE / DevOps Lead as the accountable stage owner, against the real
validators. This is a **recorded verification with its evidence**, not a
self-issued clearance: §6.4 records the one residual that exceeds this role's
authority and routes it.

### 6.1 The boundary claim, stated precisely

> **No agent, on any WS-F ticket, has a reachable path that (a) sets
> `heartbeat_enabled: true`, (b) signs a gate, or (c) answers an interrupt-card;
> and no ticket in a never-auto-approve category can carry `approval: auto*`.**

### 6.2 Verification — three independent mechanisms, all currently green

1. **Structural (the strongest).** `flow_router.DECISIONS` is the closed frozenset
   `{dispatch, validate, idle}`. There is no `approve` or `answer` action to
   invoke — (b) and (c) are unreachable by construction, not by a runtime check
   that could be bypassed. Asserted by
   `tests/test_flow_router.py::TestDecisionAlphabet` and by
   `kill_switch_drill.decision_alphabet_is_closed()`; the whole path is a pure
   evaluator (`tick()` "never mutates anything", exit 0 always).
2. **Event-log scanner.** `kill_switch_drill.py` rail `SI-7 never_auto_approve`
   scans for auto-approved gate/interrupt events and ships a scanner-has-teeth
   negative test, so a clean result cannot be a scanner that sees nothing.
   Observed: `SI-7=ok`, `zero gate/approval violations`.
3. **Board-level CI blocker.** `scripts/check_never_auto_approve.py` against
   `config/risk_taxonomy.yaml`. Observed verbatim, 2026-07-24:

   ```
   OK: 182 tickets checked, no never-auto-approve violations.
   ```
   (exit 0.)

**The Deployment ticket's own classification, verified against the live matcher.**
DAS-1622 (the flip) carries `stage: GATE-5` and `labels: [governance, security]` and
declares **no `approval:` field**. Evaluating its real frontmatter through
`check_never_auto_approve.matches_category` resolves it to two never-auto-approve
categories — `gate5_deployment` and `security_sensitive` — so were it ever to carry
`approval: auto*`, CI would fail it twice over. Its status is `blocked` by design
(FR-006) and was not touched.

### 6.3 Verdict

**The SI-7 boundary claim as stated in §6.1 is VERIFIED** against the artifacts of
record, with all three mechanisms green on observed output. `heartbeat_enabled`
remains `false`; `ws_f_heartbeat` remains an inert placeholder that is never the
flip point.

### 6.4 One residual — a path-matcher asymmetry — routed, not resolved here

While verifying §6.2's third mechanism, a genuine ambiguity surfaced that this role
should not adjudicate alone. `config/risk_taxonomy.yaml`'s `governance_or_policy`
matcher lists `**/loop.yaml` (SI-2's SSOT) among its paths but **not**
`**/features.yaml` (SI-7's flip point). Probing the live matcher with synthetic
frontmatter:

| Synthetic ticket frontmatter | Categories matched |
|---|---|
| `approval: auto` + `paths: ["config/loop.yaml"]` | `governance_or_policy` ✅ |
| `approval: auto` + `paths: ["config/features.yaml"]` | **none** ⚠️ |
| `approval: auto` + `stage: GATE-5` | `gate5_deployment` ✅ |
| `approval: auto` + `labels: [security]` | `security_sensitive` ✅ |

**Assessment (deliberately not overstated).** This is a **latent** asymmetry, not a
live hole. Today the flip is unreachable structurally (§6.2.1), and every WS-F
ticket — DAS-1622 included — carries `stage: GATE-5` and/or `labels: [security]`,
so the live boundary holds through two independent matchers. The exposure is a
*future* ticket that edits `config/features.yaml` while declaring neither the
GATE-5 stage nor a security/governance label and self-declaring `approval: auto`.

**Why it is not fixed here.** The fix is an edit to `config/risk_taxonomy.yaml` —
which is itself a `governance_or_policy` never-auto-approve path, is outside this
ticket's `zone: docs/design`, and is a Security Lead consult / CTO ratification
call, not an SRE Lead one. Asserting a taxonomy change from this seat would be
exactly the self-issued clearance this review is meant to avoid.

**Routed:** escalated to the **CTO** (this role's declared escalation route) with
the recommendation to route it onward to the **Security Lead**, who owns the
never-auto-approve boundary, for a decision on whether `**/features.yaml` (or a
narrower `config/features.yaml`) belongs in the `governance_or_policy` path list.
**Non-blocking for GATE-2** — the boundary of §6.1 is verified without it. Logged
on DAS-1617; not silently carried.

---

## 7. Handoff

- **DAS-1618 (Development, sre-eng, `zone: scripts`)** — implement §3.3/§3.4/§3.5
  under §3.6's forbiddances; add `active_plan` to `config/budgets.yaml`; add tests
  for the new rail (both arms: exhausted → idle-with-reason, and inert-when-unknown
  → dispatch unaffected); pair the change with the CTO-ratified ADR-0027 addendum of
  §3.7. **Do not flip any flag.**
- **DAS-1619 (go/no-go artifact)** — consume §2's protocol verbatim; report the
  readiness verdict per §2.2's predicate (honesty, not exit 0); state the one
  remaining Founder act and never recommend performing it.
- **DAS-1620 (Testing, qa-eng, `zone: tests`)** — §2 is the drill's specification:
  one enforcement point per invariant, the pass predicate of §2.1, the
  verdict-⟺-evidence assertion of §2.2, the count discipline of §2.0, and SI-1's
  external half recorded as covered-by-construction per §5 (no scheduler inspector).
- **DAS-1622 (Deployment)** — stays `blocked` by design (FR-006). Its closure
  condition is the Founder act, not an agent's.
