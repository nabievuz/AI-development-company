---
id: DAS-1629
title: Declare the active subscription plan in the budgets config so the credit ceiling is enforceable
status: done
assignee: cto
author: sre-eng
verified_by: cto
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: config
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-25
---

## Description

**BLOCKED — requires Founder input. Surfaced by DAS-1618 (WS-F GATE-3 part 1).**

`config/budgets.yaml` declares `mustaqil.monthly_credit_ceiling.plan_credit_usd`
per plan (`pro` 20 / `max_5x` 100 / `max_20x` 200) but **never declares which plan
is active**. Without it the SI-5 / FR-004 outer credit ceiling cannot be evaluated:
there is no ceiling value to compare spend against.

**Why an agent cannot resolve this.** Which Claude subscription plan DasLab runs on
is a fact about the Founder's account, not about the repository. Inferring it would
mean inventing a spend ceiling — and `CreditState`'s `max_20x` default is the most
permissive of the three, so a wrong guess silently grants the largest budget. That
is precisely the failure the ceiling exists to prevent, which is why DAS-1617's
design forbids inheriting the default.

**Current behavior with the plan undeclared (correct, by design — do not "fix"):**
- The `--tick` path stays **inert**. Failing closed there would be a false red that
  freezes the substrate and prevents the ≥3-day shadow window from ever
  accumulating — the gate would block the very evidence it is waiting for.
- `check_heartbeat_readiness.py` instead reports a **readiness blocker**
  (`active_plan is undeclared`), landed by DAS-1618.

**Consequence the Founder should be aware of:** HEARTBEAT can never report READY
while its outer ceiling is unenforceable. This is a deliberate property, not a bug —
but it does mean **the go-live path is gated on this decision.**

**Unblock condition:** the Founder states the active plan. Then declare it in
`config/budgets.yaml` (an `active_plan` key naming one of the three), verify
`check_heartbeat_readiness.py` drops that specific blocker, and confirm the tick
path now evaluates the ceiling rather than staying inert.

⛔ Do NOT guess the plan. Do NOT flip any flag. Do NOT remove the readiness blocker
without a declared plan behind it.

## Acceptance criteria
- [x] Founder has stated the active plan (recorded verbatim in this ticket's log with the date).
- [x] `active_plan` declared in `config/budgets.yaml` matching that statement exactly.
- [x] `check_heartbeat_readiness.py` no longer reports the `active_plan is undeclared` blocker — verified by observed before/after output, not asserted.
- [x] The `--tick` path evaluates the ceiling instead of staying inert; covered by a test.
- [x] `diagnostics.py` 100/100; `board_lint`/validators green; no flag flipped; no `project:` field (R9).

## Log
### 2026-07-24 — SRE Engineer
Raised during DAS-1618's GATE-3 work; recorded by the orchestrator in the same run.
Not resolved there: `config/` was outside that ticket's zone lock, and the value is
a Founder fact rather than an engineering one. Carried as `blocked` with this precise
reason rather than defaulted — per FR-004 / ADR-0020, an unenforceable cap is never
reported as enforced.

### 2026-07-25 — Founder decision (orchestrator-recorded)
The Founder stated verbatim: **"active_plan is max_20x"** (2026-07-25, in-session,
direct answer to this ticket's unblock condition). This authorizes declaring
`active_plan: max_20x` in `config/budgets.yaml`'s `monthly_credit_ceiling` block —
credit ceiling **$200/month** (`plan_credit_usd.max_20x`). Unblock condition met;
status `blocked → in_progress`. Safe to arm now: the DAS-1618 monthly-ceiling window
fix (reviewed twice) means declaring the plan evaluates a correctly-windowed ceiling,
not a latching lifetime total — the round-1 hold on this ticket was explicitly lifted.

### 2026-07-25 — SRE / DevOps Lead
Executed the Founder decision. Declared `active_plan: max_20x` in
`config/budgets.yaml :: mustaqil.monthly_credit_ceiling` — the exact selector the
code reads (`check_heartbeat_readiness._active_plan` and
`loop_controller._monthly_credit_exhausted` both read
`mustaqil.monthly_credit_ceiling.active_plan`; `ws_b_admission.check_credit_exhaustion`
keys `plan_credit_usd[active_plan]`). Resolved ceiling = **$200/mo**. This is the ONLY
change to budgets.yaml — `git diff config/budgets.yaml` shows only the added
`active_plan: max_20x` line (+ its comment); `on_exhaustion: sanctioned_pause` and
`metered_overflow: false` untouched; no cap value changed. No flag flipped
(`heartbeat_enabled` still `false`); no `project:` field; `board/.events.jsonl` /
`board/.metrics-history.jsonl` still absent.

**Readiness blocker DROPS — verbatim before/after (`check_heartbeat_readiness.py`):**

BEFORE (VERDICT: NOT READY, exit 1) — two blockers:
```
  XX monthly credit ceiling .. plan=undeclared  exhausted=False  (FR-004)
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
```
AFTER (VERDICT: NOT READY, exit 1) — the active_plan blocker is GONE, only the window remains:
```
  OK monthly credit ceiling .. plan=max_20x  exhausted=False  (FR-004)
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
```
The persistent 0/3 red (0 history rows) is CORRECT and remains — not a failure to fix.

**Tick path now EVALUATES the ceiling (was inert) — observed on a scratch ledger only
(real `board/.events.jsonl` never written), real budgets:**
```
[$0 month-to-date, absent ledger]     _monthly_credit_exhausted = False   (under $200 — evaluated, not inert)
[$250 month-to-date, scratch ledger]  _monthly_credit_exhausted = True    (over $200)
[$175 month-to-date, scratch ledger]  _monthly_credit_exhausted = False   (under $200 — ceiling is exactly $200)
[real board/.events.jsonl present?]   False
```

**Test pinning the resolution (`tests/test_loop_controller.py`, DAS-1629 block):**
`test_real_budgets_declares_a_resolvable_active_plan` +
`test_real_active_plan_resolves_to_its_authoritative_ceiling_in_tick` assert the REAL
config's declared plan resolves to `plan_credit_usd[active_plan]` (authoritative key,
boundary-proven at ceiling±$0.01), so a future plan change or a value-moved-to-wrong-key
mis-declaration is caught — not a bare `== 200`.

**Gate deltas — `heartbeat_go_no_go.py --skip-drill --skip-daemon-scan` (still NO-GO, exit 1):**
The `monthly credit ceiling enforceable (FR-004)` gate FLIPPED **FAIL → PASS**
(`active_plan=max_20x`); the sibling `credit exhaustion resolves to a sanctioned pause`
gate PASS. `clean shadow window >= 3 days` stays **FAIL** (0/7) and `event log`
stays **UNKNOWN** (absent) — overall verdict unchanged NO-GO, now held by the window
alone, exactly as designed.

**Full verification (observed):**
- `kill_switch_drill.py --smoke` — OK, 6 rails held (SI-2..SI-7), exit 0.
- `diagnostics.py` — SCORE = 100/100.
- Full repo suite — `2614 passed, 25 skipped`. Two prior real-repo honesty tests that
  PINNED the old undeclared state were updated to the declared reality (in-zone, tests/):
  `test_check_heartbeat_readiness.test_cli_exit_codes` (clean window now READY→exit 0) and
  `test_heartbeat_go_no_go.test_the_real_repo_is_honestly_no_go_today` (credit gate FAIL→PASS,
  verdict still NO-GO on the window).
- `board_lint.py` — OK, 200 tickets, 0 violations. `ruff check scripts tests` — All checks passed.

**Second-order effect (confirmed safe, not re-litigated).** Declaring `active_plan`
ARMS the FR-004 monthly credit ceiling in the tick path for the first time. The DAS-1618
window fix means `_monthly_credit_exhausted` evaluates a correctly-windowed **month-to-date**
figure (`aggregate_spans(since=_window_start(now, unit="month"))`), not a latching lifetime
total — so the ceiling resets at the billing-month boundary and cannot freeze the substrate
at idle once crossed. At $0 month-to-date spend it evaluates `False` (not exhausted), and
all failure paths (missing file/yaml/import) are failure-isolated to `False` (never a
fabricated pause). No path found where arming the ceiling could freeze the substrate.

Status `in_progress → in_review`; assignee `sre-lead → cto` (author is `sre-eng`; routing
review to CTO keeps author ≠ reviewer per ROUTING).

### 2026-07-25 — CTO (review — ACCEPT)
Reviewed the execution of the Founder decision. This one-line config edit is the change
that ARMS the FR-004 monthly credit ceiling in the tick path for the first time, so it got
a full re-verification, not a rubber stamp. Separating **re-verified-by-me** from **accepted**:

**RE-VERIFIED (ran/observed myself, verbatim):**
1. `git diff config/budgets.yaml` — the ONLY change is `+ active_plan: max_20x` (+ its 6-line
   comment) inside `mustaqil.monthly_credit_ceiling`. `on_exhaustion: sanctioned_pause`,
   `metered_overflow: false`, and every cap value byte-identical. No cap widened.
2. Value = `max_20x` — matches the Founder's verbatim statement ("active_plan is max_20x")
   exactly; not `pro`, not `max_5x`. Keys into `plan_credit_usd.max_20x` = **$200/mo**.
3. Key nesting is what the code READS: `loop_controller._monthly_credit_exhausted` and
   `check_heartbeat_readiness._active_plan` both read `mustaqil.monthly_credit_ceiling.active_plan`;
   `ws_b_admission.check_credit_exhaustion` keys `plan_credit_usd[active_plan]`. Traced all three
   readers to source — the value sits at the exact level they resolve, not a decorative level.
4. `check_heartbeat_readiness.py` — `OK ... plan=max_20x exhausted=False (FR-004)`; the
   `active_plan is undeclared` blocker is GONE; VERDICT **NOT READY exit 1** held by the sole
   remaining `0/3 clean shadow window` blocker. Readiness did NOT flip to READY.
5. Arming is safe — independent scratch-ledger boundary proof (injected `CreditState`, real
   budgets, absent real ledger): used $0 / $175 / $199.99 → False; $200 / $200.01 / $250 → True.
   `_window_start(unit="month")` → 2026-07-01, so the figure is **month-to-date** (resets at the
   billing boundary, does not latch). Real path with absent `board/.events.jsonl` → False
   (failure-isolated, never a fabricated pause). No path found where arming freezes the substrate.
6. `heartbeat_go_no_go.py` — FR-004 `monthly credit ceiling enforceable` gate flipped **FAIL→PASS**
   (`active_plan=max_20x`); sibling `credit exhaustion resolves to a sanctioned pause` PASS;
   `clean shadow window >= 3 days` still **FAIL**; `event log` still **UNKNOWN** (absent); overall
   verdict **NO-GO exit 1**, now held by the window alone. Which changed / which held: as designed.
7. Pin test is authoritative-key-based, not `== 200` on a spend result:
   `test_real_active_plan_resolves_to_its_authoritative_ceiling_in_tick` proves the boundary at
   `plan_credit_usd[active_plan] ± $0.01`; `test_real_budgets_declares_a_resolvable_active_plan`
   asserts `active_plan in plan_credit_usd` and pins the value at the authoritative key
   (`plan_credit_usd[active_plan] == 200`) — so relocating $200 to the wrong plan fails loudly.
8. `kill_switch_drill.py --smoke` — 6 rails held, exit 0. WS-F cluster (readiness + go/no-go +
   loop_controller + ws_b_admission) — 136 passed. Full repo suite — **2614 passed, 25 skipped**.
   `diagnostics.py` — **100/100**. `board_lint.py` — 0 violations, 200 tickets (lone WARN is
   DAS-1507, unrelated). `ruff check scripts tests` — All checks passed. `heartbeat_enabled` still
   `false`; both jsonl stores absent.

**ACCEPTED (Founder facts / decisions I did not re-litigate):**
- The active plan IS `max_20x` — a fact about the Founder's Claude account, recorded verbatim
  2026-07-25; I confirm it is correctly declared and now enforceable, not that it is the right plan.
- The DAS-1618 month-window fix is reviewed-accepted upstream; I confirmed it is doing its job
  here (non-latching ceiling), I did not re-review that fix.

**Verdict:** (a) the Founder-stated plan is correctly declared and the FR-004 outer ceiling is now
enforceable ($200/mo, month-to-date, non-latching); (b) the SOLE remaining go-live blocker is the
`0/3` clean shadow window, which requires counted waves (merged PR + green CI + T7) — that is a
push/CI decision, NOT an engineering one. Merged-PR/green-CI is outstanding by orchestrator
directive and not a bounce reason. Status `in_review → done`, `verified_by: cto`.
