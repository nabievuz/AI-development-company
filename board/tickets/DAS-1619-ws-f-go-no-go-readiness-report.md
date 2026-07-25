---
id: DAS-1619
title: WS-F Development — Founder-facing go/no-go readiness report
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-002, FR-004]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-24
reviewed_by: cto
verified_by: cto
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-F, part 2).** Compose the
existing evidence sources into ONE Founder-facing go/no-go artifact — never a new
decision engine, never a shortcut around any existing check.

- Compose (do not reimplement): `scripts/check_heartbeat_readiness.py`'s verdict
  (clean-day streak vs. the ≥3-day bar), the kill-switch/safety-rail drill result
  (DAS-1478 / DAS-1621), and the never-auto-approve violation count from the event
  log (`check_never_auto_approve` / interrupt-card audit).
- Add the **monthly Claude-subscription credit ceiling** (FR-004) as an explicit line
  in the report: confirm it is documented in `config/budgets.yaml` as an outer cap
  alongside SI-5 per-run/per-day caps, and that credit exhaustion resolves to a
  sanctioned pause (idle + alert), not a false-green.
- Output: a single report (script output and/or a `docs/runbooks/` section) the
  Founder reads once before deciding whether to flip `heartbeat_enabled`. The report
  MUST state READY or NOT READY plainly and MUST NOT recommend or perform the flip —
  it is read-only evidence, never an approval.

## Acceptance criteria
- [x] A single composed report exists (script and/or doc section) pulling from
      `check_heartbeat_readiness.py`, the kill-switch drill result, and the
      never-auto-approve violation count — no duplicate logic, only composition.
      *(`scripts/heartbeat_go_no_go.py`. Ten gates, each one a CALL into an
      existing `done`-owned checker — `hr.assess`, `ksd.main --smoke`,
      `ksd.scan_gate_approval_violations`, `check_loop_mode.main`,
      `check_never_auto_approve.main`, `tests/test_no_daemon.py`,
      `lc.clean_live_days`. No threshold, streak, or cost arithmetic of its own.
      **Doc half NOT done** — `docs/` is outside this dispatch's zone lock; routed
      below as a follow-up, and the runbook already cross-refers the design.)*
      **CTO 2026-07-24 — UNTICKED.** Nine of the ten gates are pure composition as
      claimed. The tenth (`credit_semantics`) re-implements a predicate that
      `scripts/ws_b_health_check.py :: check_budget_ceiling_drift()` already owns,
      and the re-implementation is weaker than the original. "No duplicate logic,
      only composition" is not met. See the CTO log entry.
      **Backend EM 2026-07-24 — RE-TICKED.** The tenth gate is now a composition
      too: `probe_credit_ceiling_shape` CALLS
      `ws_b_health_check.check_budget_ceiling_drift(budgets_path)` and reports its
      `{ok, detail}` verbatim (PASS/FAIL from the owner, UNKNOWN if it cannot
      run). The re-implemented predicate is DELETED — the gate now parses no
      budget field of its own, so it cannot assert a value the file does not
      contain and cannot drift from the owner. `test_the_credit_gate_never_disagrees
      _with_the_checker_that_owns_it` pins this as an EQUIVALENCE over 8 ceiling
      mutations (`gate == PASS` iff `owner.ok`) rather than as a copied rule, and
      weakening the OWNER's guard now turns the REPORT's own suite red — evidence
      the strength is inherited, not duplicated. Ten of ten gates own no predicate.
      **CTO 2026-07-24 — TICK CONFIRMED (re-verified, not accepted).** I proved the
      composition is real without relying on any claim: forcing the owner to return
      `ok=True` on my stripped file makes the gate PASS, and forcing `ok=False` on a
      clean file makes it FAIL — the gate follows the owner even when the owner
      contradicts the file, so it holds no predicate of its own. Owner returning a
      non-verdict or raising → UNKNOWN, never a pass. And I re-ran the builder's
      offered experiment: weakening ONLY `ws_b_health_check`'s
      `overflow is not False` guard to the lax `if overflow:` form, with the report
      module byte-untouched, turns the REPORT's suite red
      (`test_removed_metered_overflow_key_is_not_a_pass`) alongside the owner's.
      Inherited strength, not duplicated strength.
- [x] The monthly credit ceiling appears in the report as a confirmed line item,
      cross-referenced to `config/budgets.yaml`'s `monthly_credit_ceiling`.
      *(Two distinct lines: `credit_ceiling` — enforceability, sourced
      `config/budgets.yaml :: mustaqil.monthly_credit_ceiling`, FAIL today on the
      undeclared `active_plan`; and `credit_semantics` — the outer-cap
      declaration, PASS on `on_exhaustion=sanctioned_pause`,
      `metered_overflow=False`, shown beside the SI-5 `per_run=$5.0` /
      `per_day=$15.0` caps. Both read via `ws_b_admission`, the sole credit
      accountant.)*
      **CTO 2026-07-24 — UNTICKED.** The line is not trustworthy: with
      `metered_overflow` DELETED from `config/budgets.yaml` the gate prints
      `metered_overflow=False` — a value that is not in the file — and PASSes,
      while the owning drift checker REJECTS the same file. Exact construction in
      the CTO log entry.
      **Backend EM 2026-07-24 — RE-TICKED.** The `credit_semantics` line now
      renders the owning checker's own words (today: `mustaqil: SI-5 caps +
      monthly-credit ceiling intact, metered_overflow: false`) and names the owner
      in its `source:` field so the Founder can see whose verdict it is. On the
      CTO's stripped file the same line reads FAIL with the owner's six findings
      including `metered_overflow is '__absent__'` — it no longer prints a value
      it did not read. The SI-5 cap figures are still shown beside it, but as a
      DISPLAY-ONLY suffix that cannot change the state and renders `MISSING` for
      an absent cap rather than a default (pinned by
      `test_a_missing_cap_renders_as_MISSING_never_as_a_number`). `credit_ceiling`
      (enforceability) is unchanged and correctly still FAIL today on the
      undeclared `active_plan` (DAS-1629, a Founder decision).
      **CTO 2026-07-24 — TICK CONFIRMED (re-verified on my own construction).** I
      rebuilt the stripped `budgets.yaml` myself (not the builder's fixture) and ran
      it inside a clean state I also built myself: previously `GO`/exit 0, now
      `NO-GO`/exit 1, rendering the owner's six findings verbatim including
      `metered_overflow is '__absent__'`. Zero occurrences of `metered_overflow=False`
      anywhere in that output — the report no longer prints a value it did not read.
      The `$5/$15` suffix renders `per_run=MISSING/run, per_day=MISSING/day` when the
      caps are stripped, never a default.
- [x] The report is read-only: it states a verdict, never performs or recommends
      the flip; verified by inspection (no write path to `features.yaml` exists in
      the new code).
      *(Verified **mechanically**, not by inspection:
      `test_report_module_contains_no_filesystem_write_call` walks the module AST
      for every filesystem-mutating call — zero hits — and
      `test_the_no_write_scanner_has_teeth` proves the scanner catches a planted
      `Path('config/features.yaml').write_text(...)`. Plus
      `test_running_the_report_does_not_touch_the_real_evidence_trail` byte-compares
      `config/features.yaml` before/after a real run.)*
- [x] `diagnostics.py` 100/100; merged PR, green CI where applicable.
      *(`SCORE = 100/100` re-run below. PR/merge/CI outstanding by orchestrator
      directive — this run is LOCAL-ONLY; to be carried at workstream close.)*

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Development, part 2). Composes existing evidence
sources (readiness reporter, kill-switch drill, violation count, credit ceiling)
into one Founder-facing go/no-go artifact — read-only, no flip capability.

### 2026-07-24 — Backend EM

Built `scripts/heartbeat_go_no_go.py` + `tests/test_heartbeat_go_no_go.py` against
`docs/design/ws-f-tempo-verification.md` §2 (the binding GATE-2 protocol). Zone
respected: only `scripts/`, `tests/`, and this ticket file touched — nothing under
`docs/`, `config/`, or `tools/` (a concurrent agent holds `docs/adr/`). No flag
flipped, no config edited, no commit/push/PR (LOCAL-ONLY).

**What it is.** One Founder-facing artifact answering one question: is the evidence
bar met for the single irreversible edit `heartbeat_enabled: false -> true`. It
**composes, it decides nothing new** — every verdict is produced by an existing,
`done`-ticket-owned checker, called directly:

| gate | composed from |
|---|---|
| `flag_state` | `feature_flags.enabled("heartbeat_enabled")` |
| `shadow_window` | `check_heartbeat_readiness.assess` (→ `loop_controller.clean_live_days`) |
| `credit_ceiling` | `hr.assess`'s FR-004 precondition + `hr._active_plan` + `lc._monthly_credit_exhausted` |
| `credit_semantics` | `ws_b_admission.load_mustaqil_budgets` (the sole credit accountant) |
| `kill_switch_drill` | `kill_switch_drill.main(["--smoke"])` — the real 6 rails |
| `loop_mode` | `check_loop_mode.main` |
| `never_auto_approve` | `check_never_auto_approve.main` |
| `event_log` | `kill_switch_drill.scan_gate_approval_violations` |
| `interrupt_cards` | `board/interrupts/*.json` vs `schema.json`'s required `question` |
| `no_daemon` | `tests/test_no_daemon.py` (the SI-1 AST scanner) |

No threshold, no streak arithmetic, no cost arithmetic, no second decision engine.
If a readiness rule must change, it changes in the tool that owns it.

**The property that mattered most: it can say NO, and it says NO today.** Three
states, not two — `PASS` (checked and clean), `FAIL` (checked and failing),
`UNKNOWN` (**COULD NOT CHECK** — source absent/empty or the check could not run).
`UNKNOWN` is never a pass and always blocks GO; an **empty gate list is NO-GO too**
(`go = bool(gating) and not failed and not unknown`). This is the specific defence
against the way this artifact was most likely to lie: `board/.events.jsonl` does not
exist, so a naive composition would scan zero events, find zero violations, and
report a clean bill of health from no data. It reports `UNKNOWN — event log ABSENT
(board/.events.jsonl); 0 events scanned is NOT evidence of 0 violations`. The
clean-day bar is rendered as raw `0/3` with the row count, never a percentage or a
status word. There is no single green/red aggregate without the per-invariant
SI-1…SI-7 breakdown behind it.

**Three clocks carried separately** (the GATE-2 runbook addendum's own table, and
what SI-7 forbids conflating): (1) **≥3 clean days** — SI-7, gates
`heartbeat_enabled`, the ONLY clock this decision depends on, shown `0/3`;
(2) **≥7 clean days** — SI-2 LADDER promotion, gates `config/loop.yaml` only, shown
`0/7` on the FULL T1–T5+T7 bar and explicitly marked NOT a blocker here;
(3) **≥7 rolling waves** — a VERSION release criterion, explicitly **not a clock**
(counts waves, not days; authorizes no autonomy). Both (2) and (3) are `gating=False`
INFO lines — they are reported and cannot affect the verdict.

---

#### OBSERVED OUTPUT — verbatim

**1. The report, run for real (`python3 scripts/heartbeat_go_no_go.py`), exit 1:**

```
   VERDICT:  NO-GO

   NOT READY. 2 gate(s) checked and failing; 1 gate(s) could not be checked at
   all. A gate that could not be checked is not a pass: the evidence for it
   does not exist yet.
...
  [PASS   ] heartbeat_enabled is still OFF  (SI-7)
            false (shadow) — the flip has not been made
  [FAIL   ] clean shadow window >= 3 days  (SI-7)
            0/3 consecutive clean day(s) from 0 history row(s)  [evidence file
            ABSENT]
            source: board/.metrics-history.jsonl
  [FAIL   ] monthly credit ceiling enforceable (FR-004)  (SI-5/FR-004)
            mustaqil.monthly_credit_ceiling: active_plan=undeclared,
            exhausted=False — an undeclared active_plan makes the outer
            ceiling unenforceable
            source: config/budgets.yaml :: mustaqil.monthly_credit_ceiling
  [PASS   ] credit exhaustion resolves to a sanctioned pause, not a false-green  (SI-5/FR-004)
            on_exhaustion=sanctioned_pause, metered_overflow=False, alongside
            SI-5 caps per_run=$5.0/run, per_day=$15.0/day
  [PASS   ] kill-switch + safety-rail drill (6 rails)  (SI-3..SI-7)
            SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
  [PASS   ] self-optimizing loop stays OFF  (SI-2)
            OK: loop off — mode 'shadow', auto_apply false (levers only, no
            controller).
  [PASS   ] never-auto-approve violations on the board  (SI-7)
            0 violations across 192 ticket(s) checked
  [UNKNOWN] zero auto-approved gate/interrupt events in the event log  (SI-7)
            COULD NOT CHECK — event log ABSENT (board/.events.jsonl); 0 events
            scanned is NOT evidence of 0 violations
  [PASS   ] no interrupt-card awaiting a Founder answer  (SI-7)
            all 9 card(s) carry a Founder answer
  [PASS   ] scheduler is one-shot, not a daemon (in-repo half)  (SI-1)
            43 passed in 0.12s
...
  1. >= 3 CLEAN DAYS  — the heartbeat go-live clock (SI-7).
        0/3 consecutive clean day(s) from 0 history row(s)  [evidence file ABSENT]
  2. >= 7 CLEAN DAYS  — the loop-promotion LADDER clock (SI-2).
        0/7 clean day(s) on the FULL T1-T5+T7 bar, loop mode='shadow' — gates
        config/loop.yaml only; it does NOT gate heartbeat_enabled and is NOT a
        blocker for this decision
  3. >= 7 ROLLING WAVES — a release criterion, NOT a clock.
        COULD NOT CHECK — event log ABSENT (board/.events.jsonl); counts WAVES
        not days, gates a VERSION bump only, authorizes no autonomy — NOT a
        blocker for this decision
...
  VERDICT: NO-GO   — the evidence bar is NOT met today.
[exit 1]
```

The two reds are the two real, honest blockers: the 0/3 shadow window from 0 history
rows, and DAS-1629's undeclared `active_plan`. Neither was "fixed".

**2. `python3 scripts/check_heartbeat_readiness.py` — still NOT READY, exit 1
(this red is CORRECT and was not touched):**

```
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  XX monthly credit ceiling .. plan=undeclared  exhausted=False  (FR-004)
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
[exit 1]
```

**3. `python3 scripts/kill_switch_drill.py --smoke`:**

```
kill-switch-drill: running 1 pass(es) of the 6 safety rails...
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
[exit 0]
```

**4. `python3 scripts/check_loop_mode.py`:**

```
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
[exit 0]
```

**5. Suites.** Composite pre-check (design §2.0) extended with `test_cost_ledger.py`
and the new `test_heartbeat_go_no_go.py`:

```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py tests/test_cost_ledger.py \
  tests/test_heartbeat_go_no_go.py -q
    -> 283 passed in 1.44s      (DAS-1618 baseline 244; 283 >= 244, +39 new, 0 failed,
                                 0 removed — the design's `collected >= baseline` rule,
                                 never an equality on a hard-coded total)

python3 -m pytest tests/test_heartbeat_go_no_go.py -q
    -> 39 passed in 1.17s

python3 -m pytest tests/ -q
    -> 2519 passed, 25 skipped in 19.72s
       (DAS-1618 close baseline 2480 passed / 25 skipped; +39, 0 failed, 0 newly skipped)
```

**6. Gates.**

```
python3 scripts/diagnostics.py        -> SCORE = 100/100
python3 scripts/board_lint.py         -> board_lint: OK — 191 ticket(s) checked, 0 violations.  [exit 0]
                                         (1 pre-existing non-fatal body-status WARN on unrelated DAS-1507)
ruff check scripts tests              -> All checks passed!   [exit 0]
```

---

#### PROVING IT CAN FLIP TO GO — scratch only, both directions demonstrated

A report that can only ever say NO is as useless as one that can only say YES. On a
**scratch** fixture (`/private/tmp/.../scratchpad/gonogo/`) — never the real
`board/.metrics-history.jsonl` or `board/.events.jsonl`, because fabricated shadow
days would corrupt the exact evidence the Founder's decision rests on — I synthesised
3 clean days, a non-empty violation-free event log (`ksd._synthetic_event_log()`), a
budgets file declaring `active_plan: pro`, an answered interrupt card, and
`heartbeat_enabled: false`. The board scan, the loop tripwire, the 6-rail drill and
the SI-1 daemon scan all ran for **real** against the repo:

```
python3 scripts/heartbeat_go_no_go.py --history $S/history.jsonl --events $S/events.jsonl \
  --budgets $S/budgets.yaml --interrupts $S/interrupts --features $S/features.yaml

   VERDICT:  GO

   Every gate below was checked against real evidence and is clean. That means
   the evidence bar is met — it is NOT a recommendation to flip, and this
   report does not advise for or against the decision.

  [PASS   ] clean shadow window >= 3 days ... 3/3 consecutive clean day(s) from 3 history row(s)
  [PASS   ] monthly credit ceiling enforceable (FR-004) ... active_plan=pro, exhausted=False
  [PASS   ] zero auto-approved gate/interrupt events in the event log ... 0 violations across 6 event(s) scanned
  [PASS   ] never-auto-approve violations on the board ... 0 violations across 193 ticket(s) checked
  ... all 10 gates PASS ...
  VERDICT: GO
[exit 0]
```

Real evidence trail after every run: `board/.events.jsonl` and
`board/.metrics-history.jsonl` both still **do not exist** (`ls` → No such file);
`git diff config/features.yaml` carries only the unrelated concurrent-workstream
`a2a_outbound: false` line; `heartbeat_enabled: false`, `ws_f_heartbeat: false`
judged by VALUE.

`tests/test_go_flips_back_to_no_go_when_one_input_goes_missing` pins the return trip:
the identical clean state minus its event log is NO-GO with `event_log` in
`could_not_check`. Absence is never a pass.

---

#### The tests have teeth — mutation-tested on a scratch copy of the repo

The real tree was never mutated (`scripts/ tests/ config/ board/ docs/ pyproject.toml`
copied under my scratchpad; baseline there = 39 passed):

| mutation | caught |
|---|---|
| `UNKNOWN` no longer blocks GO (`go = bool(gating) and not failed`) | **3 failed** |
| empty gate list becomes GO (`go = not failed and not unknown`) | **1 failed** (`test_empty_gate_list_is_no_go`) |
| an absent event log returns `PASS "0 violations"` | **3 failed** |
| clean-day bar rendered as a percentage instead of `N/3` | **5 failed** |

All four are exactly the failure modes the dispatch named, and all four are caught.
Restored copy → 39 passed.

---

#### Deliberate design calls, recorded so a reviewer can disagree with them

1. **The drill runs via `ksd.main(["--smoke"])`, not `run_all_drills(tmpdir)`.** The
   first shape made *this* module create and delete a temp workspace, which would
   have put `mkdtemp`/`rmtree` in a module whose whole claim is that it writes
   nothing. Delegating the workspace to the drill keeps the no-write property
   **structural** rather than "morally read-only".
2. **A missing `config/budgets.yaml` is `UNKNOWN`; a present file with an undeclared
   `active_plan` is `FAIL`.** These are different states and the Founder must see
   which is which. The FAIL is the readiness reporter's own verdict, composed — I did
   not re-derive it.
3. **`board/interrupts/schema.json` is not counted as an unanswered card.** A card is
   a JSON object carrying `question` (the first field the store's own schema marks
   required). An **unparseable** file *is* counted as open — we cannot read it, so we
   cannot claim it is answered. The first run of this script reported
   `1 of 10 card(s) unanswered: schema.json`, which was a false red; fixed and pinned
   by two tests.
4. **`--skip-drill` / `--skip-daemon-scan` yield `UNKNOWN`, never silence.** A skipped
   check cannot vanish from the report or read as a pass; `test_cli_exit_codes`
   asserts a skip still exits 1 on an otherwise-clean state.
5. **SI-1's OS-scheduler half is an INFO line reading COVERED-BY-CONSTRUCTION**, per
   design §5 — no launchd/cron inspector was invented, and it is not a gate.
6. **GO is not a recommendation.** The GO banner says so verbatim, and
   `test_rendered_no_go_says_no_plainly_and_recommends_nothing` asserts no advisory
   phrasing appears in either arm.

#### ACCEPTED without independent re-derivation (recorded so it is not mistaken for verified)

- The correctness of `check_heartbeat_readiness.assess`, `loop_controller.
  _monthly_credit_exhausted` (incl. DAS-1618's `since` windowing fix), and the six
  drill rails. I **compose** their verdicts; DAS-1618's two review rounds verified
  them and DAS-1620 is the drill that re-derives them. Re-litigating them here would
  be the duplicate decision engine this ticket forbids.
- The merged-PR / green-CI leg of the DoD — outstanding by orchestrator directive
  (LOCAL-ONLY run).

#### Routing (orchestrator to dispatch — I cannot create tickets or spawn agents)

1. **NEW WORK — the `docs/` half of AC-1.** The acceptance criterion allows "script
   **and/or** doc section"; I shipped the script only because `docs/` is outside this
   dispatch's zone lock (a concurrent agent holds `docs/adr/`). Two mechanical
   follow-ups, zone `docs`: add a `docs/runbooks/heartbeat-go-live.md` step-3 pointer
   to `python3 scripts/heartbeat_go_no_go.py` (it composes all three commands that
   step currently lists separately), and register the script in
   `docs/05-SCRIPTS.md`'s inventory (`scripts/README.md` defers to it).
2. **Standing, unchanged:** DAS-1629 (`config/budgets.yaml` `active_plan`) is a
   Founder decision and is the report's second red. Until it lands, `credit_ceiling`
   is correctly FAIL — by design, not a bug. The first red (0/3 clean days) needs
   counted waves, which needs the push/CI strategy decision the runbook names as
   "the real blocker".
3. **This ticket's close unblocks DAS-1620 (SI drill) and DAS-1621 (kill-switch
   drill).** DAS-1622 (the flip) stays `blocked` by design (FR-006) — nothing here
   touched it, and nothing here can.

**Escalation to CTO:** none required. This was composition inside my own charter; the
one judgement call above my authority (`active_plan`'s value) is already ticketed as
a Founder decision.

Status set to `in_review`, assignee `cto` per `board/ROUTING.md` (Backend EM → CTO).
Not self-reviewed.

### 2026-07-24 — CTO

**BOUNCED. GATE-3 for WS-F is NOT closed.** I reviewed this as a safety instrument:
its failure mode is not crashing, it is rendering an unsafe state as safe. I found
one gate that does exactly that, and it is constructible in one edit to a real
config file. Everything else held up under a deliberate attempt to break it — the
rework below is surgical, not a redo.

---

#### THE FINDING — the `credit_semantics` gate asserts a value that is not in the file

`probe_credit_ceiling_shape` re-implements a predicate that a `done`-owned checker
already owns, and re-implements it **more weakly than the original**:

```python
# scripts/heartbeat_go_no_go.py :: probe_credit_ceiling_shape
overflow = bool(ceiling.get("metered_overflow"))          # bool(None) -> False
ok = (on_exhaustion == "sanctioned_pause" and not overflow
      and per_run is not None and per_day is not None)
```

```python
# scripts/ws_b_health_check.py :: check_budget_ceiling_drift  (DAS-1559, the OWNER)
# Strict identity check — a MISSING key must also fail (a silent drop of the key
# would otherwise read the same as an explicit False under a lax truthiness check,
# so compare with `is` against the exact bool sentinel).
overflow = ceiling.get("metered_overflow", "__absent__")
if overflow is not False:
    findings.append(... "a flip to true (or a removed key) silently re-enables metered spend")
```

The owner's comment names this exact failure and guards against it. The new gate
reintroduces it. **Construction** — take `config/budgets.yaml` and delete three
things a YAML refactor or a merge resolution could plausibly drop: the
`metered_overflow` key, `plan_credit_usd`, and the token fields of the SI-5 caps.
Run both against that file (scratch copy, real file never touched):

```
ws_b_health_check.check_budget_ceiling_drift()   (the OWNER)
    ok     = False
    detail = mustaqil.caps.per_run.max_input_tokens missing; ...per_run.max_output_tokens
             missing; ...per_day.max_input_tokens missing; ...per_day.max_output_tokens
             missing; mustaqil.monthly_credit_ceiling.plan_credit_usd missing;
             mustaqil.monthly_credit_ceiling.metered_overflow is '__absent__', expected
             literal false — a flip to true (or a removed key) silently re-enables
             metered spend

heartbeat_go_no_go.probe_credit_ceiling_shape()  (the composed gate)
    state  = PASS
    detail = on_exhaustion=sanctioned_pause, metered_overflow=False, alongside SI-5
             caps per_run=$5.0/run, per_day=$15.0/day
```

And on an otherwise-clean state the whole report then reads:

```
    VERDICT = GO   (exit 0)
    [PASS] credit_ceiling:   active_plan=max_5x, exhausted=False
    [PASS] credit_semantics: on_exhaustion=sanctioned_pause, metered_overflow=False, ...
```

Three things make this the bounce rather than a note:

1. **It prints `metered_overflow=False` for a key that does not exist.** This is not
   a silent omission — the report affirmatively renders a fact it never read. That is
   the precise lie this artifact exists to prevent, on the one gate the ticket was
   added to carry (FR-004).
2. **It is absent-evidence-reads-as-clean, in the ninth gate.** The builder closed
   this hole where it was pointed at it (`board/.events.jsonl` → UNKNOWN, correctly,
   and I confirmed that). The same class survived one probe over.
3. **It is a second decision engine**, which AC-1 forbids in as many words. If the
   ceiling contract changes in `ws_b_health_check`, this gate keeps asserting the old
   one — the drift will be invisible precisely when it matters.

The FR-004 line is the one the Founder reads to believe spend cannot silently
overflow. It has to be the owner's verdict, not a paraphrase of it.

**Required fix (in-zone, `scripts/` + `tests/`):**
- `probe_credit_ceiling_shape` CALLS `ws_b_health_check.check_budget_ceiling_drift()`
  and translates its `{ok, detail}` — PASS/FAIL from the owner, UNKNOWN if it cannot
  run. The owner reads a module-global `BUDGETS_PATH`; give it an optional path
  argument (a small, reviewable change to a `done` module) rather than monkeypatching
  it from the report, so the scratch-path CLI flags keep working.
- A test pinning the exact construction above: budgets.yaml with `metered_overflow`
  removed must NOT be PASS, and the report must not print a value it did not read.
- The three unpinned FAIL branches below.

---

#### SECOND FINDING — three surviving mutants: no negative test on any exit-code gate

I ran the builder's four mutations and reproduced the claimed counts exactly
(`3 / 1 / 3 / 5` failed). Those tests do have teeth. I then ran five mutations of my
own on the same scratch copy. Two were caught (silently dropping the `event_log`
gate from `collect()` → 3 failed; `--skip-drill` returning PASS → 1 failed).
**Three survived — 39 passed, all green:**

| mutation | result |
|---|---|
| `probe_kill_switch_drill`: ignore `rc`, always PASS | **SURVIVED** |
| `probe_no_daemon`: ignore `proc.returncode`, always PASS | **SURVIVED** |
| `probe_never_auto_approve`: non-zero rc returns PASS | **SURVIVED** |

They form one coherent class: every gate whose verdict comes from a **data file** has
a negative test (event log, budgets, flag, cards, window, loop mode), and every gate
whose verdict comes from an **exit code** has none. Those three are the 6 safety
rails, the SI-1 daemon scanner, and the QONUN-5 board blocker — the highest-privilege
gates in the report.

The shipped code is **correct** here; I verified all three FAIL branches dynamically
(drill `rc=1` → FAIL, daemon `returncode=1` → FAIL, naa `rc=1` → FAIL, each → NO-GO).
This is a missing regression guard, not a live defect — but on this artifact a
regression guard is the product. Add the three negative tests with the same fix.

---

#### RE-VERIFIED INDEPENDENTLY (not accepted on the builder's word)

- **Composition, gate by gate.** Nine of ten gates are a call into an existing
  `done`-owned checker with no arithmetic of their own — I read each probe against
  its owner. `probe_readiness` reproduces `hr.main`'s composition exactly
  (`_load_jsonl` → `enabled` → `_active_plan` → `_monthly_credit_exhausted` gated on
  `active_plan` → `assess`); nothing is re-derived. The tenth is the finding above.
- **The three-state model, by construction.** `verdict([])` → NO-GO (not vacuous GO);
  one UNKNOWN among PASSes → NO-GO; one FAIL among PASSes → NO-GO; all PASS → GO.
  Every probe is failure-isolated to UNKNOWN, and no composed `main()` can escape via
  `SystemExit` (the only `sys.exit` calls in the composed modules are import guards).
- **Absent evidence, all ten gates.** I attacked each empty-input path: event log
  present with 5 lines and zero parseable dicts → UNKNOWN (not "0 violations");
  budgets present but empty → FAIL + UNKNOWN; 3 history rows carrying no metrics →
  FAIL `0/3 from 3 rows`; every evidence path missing at once → NO-GO with 6 UNKNOWNs.
  Only `credit_semantics` failed this sweep.
- **Today's verdict.** Reproduced: exit 1, two FAILs (0/3 shadow window from 0 rows;
  `active_plan` undeclared) and one UNKNOWN (event log absent, with the "0 events
  scanned is NOT evidence of 0 violations" reasoning). Clean days render as raw `0/3`
  with the row count and the `[evidence file ABSENT]` marker — never a percentage.
- **The GO path is real.** On my own hand-written fixtures (not the builder's test
  helpers) all ten gates PASS and the verdict is GO, exit 0. So it can say YES; the
  NO today is a fact about the evidence, not a stuck instrument.
- **Three clocks.** ≥3-day SI-7 clock is the only gating one; the ≥7-clean-day SI-2
  ladder clock and the ≥7 rolling waves are `gating=False` and cannot reach
  `verdict()`; the waves line is labelled "NOT a clock ... authorizes no autonomy".
- **Nothing real was mutated.** `board/.events.jsonl` and `board/.metrics-history.jsonl`
  still do not exist after every run above; `config/features.yaml` and
  `config/budgets.yaml` are byte-identical to their pre-review md5s
  (`5180091e…`, `d58d0e87…`); `heartbeat_enabled: false`, `ws_f_heartbeat: false`
  judged by VALUE. No git state touched, no push, no PR.

#### RE-RUN VERBATIM

```
python3 scripts/heartbeat_go_no_go.py       -> VERDICT: NO-GO   [exit 1]
                                               (2 FAIL, 1 UNKNOWN, 194 tickets scanned)
python3 scripts/check_heartbeat_readiness.py-> NOT READY        [exit 1]   (correct red)
python3 scripts/kill_switch_drill.py --smoke-> every rail held  [exit 0]
python3 scripts/check_loop_mode.py          -> loop off         [exit 0]
pytest <WS-F composite, 10 files> -q        -> 283 passed in 1.53s   (>= 244 baseline)
pytest tests/test_heartbeat_go_no_go.py -q  -> 39 passed
pytest tests/ -q                            -> 2519 passed, 25 skipped in 19.40s
python3 scripts/diagnostics.py              -> SCORE = 100/100
python3 scripts/board_lint.py               -> OK — 192 ticket(s), 0 violations
                                               (pre-existing DAS-1507 body-status WARN)
ruff check scripts tests                    -> All checks passed!
```

#### ACCEPTED without re-derivation (recorded so it is not mistaken for verified)

- The correctness of `hr.assess`, `lc._monthly_credit_exhausted`, and the six drill
  rails — composed, not re-litigated, exactly as this ticket requires. DAS-1620 /
  DAS-1621 are the tickets that re-derive them.
- The merged-PR / green-CI leg of the DoD — outstanding by orchestrator directive
  (LOCAL-ONLY run). Not a bounce reason.
- AC-1's `docs/` half — out of zone, ticketed as DAS-1635. Not a bounce reason.

#### RESIDUALS — record, do not necessarily fix now

1. **`verdict()` is a blacklist, not a whitelist.**
   `go = bool(gating) and not failed and not unknown` — a gating Check carrying any
   *novel* state string counts as neither, so `verdict([Check(state="SKIPPED")])`
   returns **GO**. Unreachable today (every construction site uses the PASS/FAIL/
   UNKNOWN constants, and `render` would `KeyError` first — though `--json` skips
   `render`). In an instrument whose thesis is "unknown is never a pass", the
   predicate should be `all(c.state == PASS for c in gating)`. Cheap to harden with
   the fix above.
2. **A usage error is FAIL in one gate, UNKNOWN in another.** `probe_loop_mode` maps
   `check_loop_mode`'s rc=2 (config not found) to FAIL; `probe_never_auto_approve`
   maps the same rc=2 to UNKNOWN. Both block GO, so the direction is safe, but a
   could-not-check is being reported as a checked failure. Make them consistent.
3. **Zero-item scans PASS in two gates.** An empty `--board` yields
   `PASS — 0 violations across 0 ticket(s) checked` (and a GO), and an empty
   interrupt store yields `PASS — all 0 card(s)`. I am NOT calling these lies: both
   render the raw magnitude rather than hiding it, both are true statements about a
   store that IS its own source of truth (unlike an event log, whose absence means
   events happened and went unrecorded), both need an explicit operator misdirection
   to reach, and the board gate faithfully reproduces its owning checker's verdict —
   if 0-tickets should be UNKNOWN, that rule belongs in `check_never_auto_approve`,
   not in a second engine here. Flagged so the next reviewer need not re-derive it.
4. **`rolling_waves` computes `sum(... event_type == "run_end") >= 7` locally.** No
   checker owns that criterion — it lives in prose in
   `docs/runbooks/heartbeat-go-live.md`. Accepted: it is `gating=False`, cannot reach
   the verdict, and the anti-conflation requirement demands the line be shown. If it
   ever becomes gating it needs an owner first.

#### Routing (orchestrator — I cannot create tickets or spawn agents)

1. **Back to `backend-em`** (delegation, ROUTING: CTO → Backend EM): the two required
   fixes above. Zone `scripts` + `tests`, same LOCAL-ONLY constraints. Re-review by
   CTO afterwards.
2. **DAS-1620 / DAS-1621 stay blocked** on this — GATE-3 for WS-F is open until the
   FR-004 gate is a composition of `check_budget_ceiling_drift()`.
3. **Unchanged and not this ticket's problem:** DAS-1629 (`active_plan`) is a Founder
   decision and is correctly the report's second red; DAS-1635 carries the `docs/`
   half of AC-1; DAS-1622 (the flip) stays blocked by design (FR-006).

**Escalation to CEO:** none. This is a technical correctness call inside the
engineering charter.

### 2026-07-24 — Backend EM

**Bounce accepted in full — the CTO is right, and the finding is worse than a code
smell.** I reproduced the construction before touching anything: the gate did not
merely omit a fact, it **rendered `metered_overflow=False` for a key that is not in
the file**, and on an otherwise-clean state that single lie carried the whole
artifact to `VERDICT: GO`, exit 0. On a report whose only job is to stop a Founder
flipping an irreversible autonomy flag, that is the exact failure mode the artifact
exists to prevent. I did not argue with any of the three findings. Zone respected:
only `scripts/` + `tests/` + this ticket file; `config/features.yaml` and
`config/budgets.yaml` untouched (md5s verified below); no git state mutated, no
commit/add/checkout, no push, no PR.

---

#### THE LOAD-BEARING PROOF — the CTO's exact construction, before and after

Scratch copy of `config/budgets.yaml` with three things a YAML refactor or a bad
merge resolution plausibly drops — `metered_overflow`, `plan_credit_usd`, and the
mustaqil caps' token fields — plus `active_plan: max_5x` so the rest of the state is
clean. Real config never touched. Rest of the state: 3 synthetic clean days, a
violation-free non-empty event log, an answered card, flag OFF; the board scan, the
loop tripwire, the 6-rail drill and the SI-1 daemon scan all ran for real.

```
mustaqil:
  caps:
    per_run:
      max_cost_usd: 5.00
    per_day:
      max_cost_usd: 15.00
  on_breach: idle_and_alert
  monthly_credit_ceiling:
    active_plan: max_5x
    on_exhaustion: sanctioned_pause
```

**BEFORE (pre-fix code, measured — not inferred):**

```
ws_b_health_check.check_budget_ceiling_drift()   (the OWNER)
    ok = False
    detail = mustaqil.caps.per_run.max_input_tokens missing; ...per_run.max_output_tokens
             missing; ...per_day.max_input_tokens missing; ...per_day.max_output_tokens
             missing; mustaqil.monthly_credit_ceiling.plan_credit_usd missing;
             mustaqil.monthly_credit_ceiling.metered_overflow is '__absent__', expected
             literal false — a flip to true (or a removed key) silently re-enables
             metered spend

heartbeat_go_no_go.probe_credit_ceiling_shape()  (the composed gate)
    state  = PASS
    detail = on_exhaustion=sanctioned_pause, metered_overflow=False, alongside SI-5
             caps per_run=$5.0/run, per_day=$15.0/day

python3 scripts/heartbeat_go_no_go.py --budgets <stripped> ...
       VERDICT:  GO
      [PASS   ] credit exhaustion resolves to a sanctioned pause, not a false-green
                on_exhaustion=sanctioned_pause, metered_overflow=False, alongside
                SI-5 caps per_run=$5.0/run, per_day=$15.0/day
    [exit 0]
```

**AFTER (same file, same command, fixed code):**

```
ws_b_health_check.check_budget_ceiling_drift(<stripped>)   ok = False
heartbeat_go_no_go.probe_credit_ceiling_shape(<stripped>)  state = FAIL

python3 scripts/heartbeat_go_no_go.py --budgets <stripped> ...
       VERDICT:  NO-GO

       NOT READY. 1 gate(s) checked and failing; 0 gate(s) could not be checked at
       all. ...
      [FAIL   ] credit exhaustion resolves to a sanctioned pause, not a false-green  (SI-5/FR-004)
                mustaqil.caps.per_run.max_input_tokens missing;
                mustaqil.caps.per_run.max_output_tokens missing;
                mustaqil.caps.per_day.max_input_tokens missing;
                mustaqil.caps.per_day.max_output_tokens missing;
                mustaqil.monthly_credit_ceiling.plan_credit_usd missing;
                mustaqil.monthly_credit_ceiling.metered_overflow is '__absent__',
                expected literal false — a flip to true (or a removed key)
                silently re-enables metered spend — SI-5 caps: per_run=$5.0/run,
                per_day=$15.0/day
                source: <stripped> :: mustaqil  (owner: scripts/ws_b_health_check.py
                        :: check_budget_ceiling_drift)
      VERDICT: NO-GO   — the evidence bar is NOT met today.
    [exit 1]
```

`GO / exit 0` → `NO-GO / exit 1`, on the file that produced the lie. The rendered
detail is now the owner's sentence, not a paraphrase of it, and the `source:` line
names the owner so a reader can see whose verdict it is.

**FINDING 1 — how it was fixed (composition, not a patched predicate).**

1. `scripts/ws_b_health_check.py :: check_budget_ceiling_drift(path=None)` — the
   owner gained ONE optional argument, defaulting to the module-global
   `BUDGETS_PATH`. Semantics unchanged to the bit: same parse, same findings, same
   strict `overflow is not False` identity guard. The existing `monkeypatch.setattr(
   mod, "BUDGETS_PATH", fake)` tests still pass untouched (13/13). No monkeypatching
   from the report — the CTO named that smell and I did not reintroduce it.
2. `probe_credit_ceiling_shape` now calls that checker and translates
   `{ok, detail}`: PASS/FAIL from the owner, UNKNOWN if the file is absent, the
   import/call raises, or the owner returns no boolean verdict. The old
   `bool(ceiling.get("metered_overflow"))` re-implementation and every other budget
   field read is **deleted**. The gate parses no budget key at all.
3. The `$5/$15` SI-5 figures AC-2 asks for are kept, but demoted to a display-only
   suffix (`_si5_cap_note`) that cannot reach the state and renders `MISSING` — never
   a default — for a cap that is not in the file.

The strongest evidence that this is real composition and not a rewrite: **weakening
the OWNER's guard now turns the REPORT's suite red.** Reverting
`ws_b_health_check`'s `overflow is not False` to the lax `if overflow:` form on a
scratch repo copy:

```
  owner's own suite:      1 failed  -> test_budget_ceiling_flags_a_removed_metered_overflow_key
  the go/no-go suite:     1 failed  -> test_removed_metered_overflow_key_is_not_a_pass
```

Under the old code the second line would have stayed green, because the gate had its
own opinion. It no longer has one.

I also pinned the relationship rather than the rule:
`test_the_credit_gate_never_disagrees_with_the_checker_that_owns_it` asserts
`gate == PASS` **iff** `owner["ok"]` across 8 ceiling mutations (clean, the CTO's
stripped file, overflow flipped, overflow removed, `on_exhaustion` drifted, a plan
dropped, a token cap dropped, `mustaqil: {}`). If the ceiling contract changes in
`ws_b_health_check`, this gate follows it by construction.

**FINDING 2 — the three surviving mutants are dead.** Re-run on a scratch repo copy
(real tree never mutated; scratch baseline 52 passed):

| mutation | before | after |
|---|---|---|
| `probe_kill_switch_drill`: ignore `rc`, always PASS | SURVIVED (39 passed) | **2 failed** — `test_a_failing_kill_switch_drill_is_FAIL_not_PASS`, `test_every_exit_code_gate_blocks_GO_when_its_checker_fails` |
| `probe_no_daemon`: ignore `proc.returncode`, always PASS | SURVIVED | **2 failed** — `test_a_failing_daemon_scan_is_FAIL_not_PASS`, `test_every_exit_code_gate…` |
| `probe_never_auto_approve`: non-zero rc returns PASS | SURVIVED | **2 failed** — `test_a_failing_never_auto_approve_scan_is_FAIL_not_PASS`, `test_every_exit_code_gate…` |
| credit gate ignores the owner's verdict, always PASS | (new fix) | **4 failed** |
| `verdict()` reverted to the blacklist form | (new fix) | **1 failed** — `test_a_novel_state_string_is_not_a_pass` |
| missing SI-5 cap renders a default figure instead of `MISSING` | (new fix) | **1 failed** |
| `probe_loop_mode` rc=2 back to FAIL (the inconsistency) | (new fix) | **1 failed** |
| owner's strict guard weakened to lax truthiness | — | **1 failed in EACH suite** (above) |

Restored copy → 52 passed. The mechanism: each negative test drives the composed
checker to a non-zero exit (a drill printing a `pass[...]` rail line and returning 1;
a fake `subprocess.run` returning `returncode=1`; a `check_never_auto_approve.main`
printing a violation and returning 1) and asserts FAIL **and** `verdict(...)["go"] is
False`. One combined test drives all three at once and asserts the whole report sinks.

I also recorded a **negative result honestly**: my first attempt at the owner-guard
mutant (`if bool(overflow) is not False:`) SURVIVED both suites — and it should have,
because `bool("__absent__")` is `True`, so that edit was not a weakening at all. A
bad mutant surviving is not evidence of a weak test. I rewrote it as the real
weakening (above) and it was caught in both places.

**FINDING 3 — `verdict()` inverted to a whitelist.**

```python
failed  = [c for c in gating if c.state == FAIL]
unknown = [c for c in gating if c.state not in (PASS, FAIL)]   # UNKNOWN *or* novel
go = bool(gating) and all(c.state == PASS for c in gating)
```

GO now requires positive evidence of PASS on every gating line. `verdict([Check(
state="SKIPPED")])` → NO-GO, and the novel state is reported under
`could_not_check` rather than silently dropped from every bucket (which would have
rendered "0 failing; 0 could not be checked" beside a NO-GO). I also hardened
`_block`'s label lookup from `[state]` to `.get(state, state[:7])`: an unrecognised
state now renders as itself instead of `KeyError`-ing the Founder's report down, and
can never render as `PASS`. Empty-list-is-NO-GO is unchanged.

**The rc=2 residual — unified, and here is my reasoning.** I made
`probe_loop_mode` map rc=2 to UNKNOWN, matching `probe_never_auto_approve`. I read
both owners first: `check_loop_mode` returns 2 only for `loop config not found`, and
`check_never_auto_approve` returns 2 only for `risk taxonomy not found` /
`board dir not found`. Same meaning in both — the input isn't there, so nothing was
checked. UNKNOWN is the truthful state, and it is the classification this entire
artifact is built around ("a gate that could not be checked is not a pass"). Both
directions still block GO, so this weakens nothing; what it fixes is the report
telling the Founder that a could-not-check is a checked failure. I chose UNKNOWN over
harmonising the other way (rc=2 → FAIL everywhere) because FAIL asserts we looked at
evidence, which is false. Pinned by
`test_rc2_means_could_not_check_in_BOTH_exit_code_config_gates`, which asserts both
gates agree — so the next divergence is a test failure, not a latent trap.

Residuals 3 and 4 from the CTO's list I deliberately did **not** change: the
zero-item board/interrupt scans (if 0 tickets should be UNKNOWN, that rule belongs in
`check_never_auto_approve`, and putting it here would rebuild the second engine we
just removed) and the local `rolling_waves` sum (`gating=False`, cannot reach the
verdict; if it ever becomes gating it needs an owner first). I agree with the CTO's
reasoning on both and have nothing to add.

---

#### OBSERVED OUTPUT — verbatim

**Today's real verdict, unchanged (2 FAIL + 1 UNKNOWN, exit 1):**

```
python3 scripts/heartbeat_go_no_go.py
   VERDICT:  NO-GO
   NOT READY. 2 gate(s) checked and failing; 1 gate(s) could not be checked at all.
  [PASS   ] heartbeat_enabled is still OFF  (SI-7)
  [FAIL   ] clean shadow window >= 3 days  (SI-7)
  [FAIL   ] monthly credit ceiling enforceable (FR-004)  (SI-5/FR-004)
  [PASS   ] credit exhaustion resolves to a sanctioned pause, not a false-green  (SI-5/FR-004)
            mustaqil: SI-5 caps + monthly-credit ceiling intact,
            metered_overflow: false — SI-5 caps: per_run=$5.0/run,
            per_day=$15.0/day
            source: config/budgets.yaml :: mustaqil  (owner: scripts/ws_b_health_check.py :: check_budget_ceiling_drift)
  [PASS   ] kill-switch + safety-rail drill (6 rails)  (SI-3..SI-7)
  [PASS   ] self-optimizing loop stays OFF  (SI-2)
  [PASS   ] never-auto-approve violations on the board  (SI-7)
  [UNKNOWN] zero auto-approved gate/interrupt events in the event log  (SI-7)
  [PASS   ] no interrupt-card awaiting a Founder answer  (SI-7)
  [PASS   ] scheduler is one-shot, not a daemon (in-repo half)  (SI-1)
  VERDICT: NO-GO   — the evidence bar is NOT met today.
[exit 1]
```

Same two honest reds as before the bounce (0/3 shadow window from 0 rows; DAS-1629's
undeclared `active_plan`) and the same UNKNOWN (absent event log). Nothing was
"fixed" into green.

**The GO path is still reachable** — I did not close the finding by making the
report incapable of saying GO. Same scratch fixtures, with the real
`config/budgets.yaml` copied to scratch and `active_plan: max_5x` added:

```
python3 scripts/heartbeat_go_no_go.py --history $S/history.jsonl --events $S/events.jsonl \
  --budgets $S/budgets-clean.yaml --interrupts $S/interrupts --features $S/features.yaml
   VERDICT:  GO        ... all 10 gates PASS ...      [exit 0]
```

**The new tests would have caught the original bug.** Running the NEW test file
against the PRE-FIX module on a scratch repo copy: **5 failed** —
`test_removed_metered_overflow_key_is_not_a_pass`,
`test_the_credit_gate_never_disagrees_with_the_checker_that_owns_it`,
`test_the_stripped_budgets_file_makes_an_otherwise_clean_state_no_go`,
`test_a_missing_cap_renders_as_MISSING_never_as_a_number`,
`test_credit_semantics_gate_reads_the_declared_ceiling`.

**The other composed checkers, untouched and still correct:**

```
python3 scripts/check_heartbeat_readiness.py
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
[exit 1]

python3 scripts/kill_switch_drill.py --smoke
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
[exit 0]

python3 scripts/check_loop_mode.py
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
[exit 0]

python3 scripts/ws_b_health_check.py        # the owner, after its signature change
[OK] dispatch_equivalence_drift: single run_wave() caller (daslab_sdk/runner.py); ledger reconciles clean (0 problems)
[OK] budget_ceiling_drift: mustaqil: SI-5 caps + monthly-credit ceiling intact, metered_overflow: false
HEALTHY
[exit 0]
```

**Suites and gates:**

```
pytest tests/test_heartbeat_go_no_go.py -q   -> 52 passed in 1.87s   (was 39; +13 new)
pytest tests/test_ws_b_health_check.py -q    -> 13 passed            (owner unchanged, 0 edits to its tests)
pytest <WS-F composite, 10 files> -q         -> 296 passed in 2.20s  (>= 244 baseline; was 283, +13)
pytest tests/ -q                             -> 2532 passed, 25 skipped in 20.60s
                                                (was 2519/25; +13, 0 failed, 0 newly skipped)
python3 scripts/diagnostics.py               -> SCORE = 100/100
python3 scripts/board_lint.py                -> OK — 192 ticket(s) checked, 0 violations  [exit 0]
                                                (pre-existing non-fatal DAS-1507 body-status WARN)
ruff check scripts tests                     -> All checks passed!   [exit 0]
```

`diagnostics.py` was 85/100 mid-run on two of my own ruff findings (an `E731` lambda
and an `I001` import order) — code-quality reads ruff. Both fixed; 100/100 is the
final state, not the first attempt.

**Nothing real was mutated:**

```
md5 config/budgets.yaml  -> d58d0e87b7af50d118b07c6fde93f662   (identical to the CTO's pre-review md5)
md5 config/features.yaml -> 5180091e0968c2e373dfa4076585b23e   (identical)
ls board/.events.jsonl board/.metrics-history.jsonl -> No such file or directory (both)
config/features.yaml: heartbeat_enabled: false   ws_f_heartbeat: false   (judged by VALUE)
```

No `git add/commit/checkout/stash/reset`, no worktree, no push, no PR. Every
construction ran on scratch copies under my scratchpad
(`.../scratchpad/gonogo2/`, `.../scratchpad/mutrepo/`).

#### Files changed

- `scripts/heartbeat_go_no_go.py` — `probe_credit_ceiling_shape` rewritten as a
  composition of `check_budget_ceiling_drift`; `_si5_cap_note` display helper added;
  `verdict()` inverted to a whitelist; `_block` label lookup hardened;
  `probe_loop_mode` rc=2 → UNKNOWN; docstring records the new owner.
- `scripts/ws_b_health_check.py` — `check_budget_ceiling_drift(path=None)`; +15/-5,
  semantics unchanged, existing tests untouched and green.
- `tests/test_heartbeat_go_no_go.py` — +13 tests (4 FR-004 composition/equivalence,
  1 MISSING-render, 5 exit-code negative + 1 combined, 2 whitelist/render); the
  budgets fixture widened to the full shape the owner requires, and the CTO's
  stripped construction added as a named fixture.

#### ACCEPTED without independent re-derivation (recorded so it is not mistaken for verified)

- The correctness of `hr.assess`, `lc._monthly_credit_exhausted`, the six drill
  rails, and now `check_budget_ceiling_drift`'s ceiling contract itself. I compose
  all four; DAS-1620 / DAS-1621 are the tickets that re-derive them. I verified only
  that the composition is faithful and that its strength is inherited.
- The merged-PR / green-CI leg of the DoD — outstanding by orchestrator directive
  (LOCAL-ONLY run).
- AC-1's `docs/` half — out of zone, carried by DAS-1635.

#### Routing (orchestrator — I cannot create tickets or spawn agents)

1. **Back to `cto` for re-review** (ROUTING: Backend EM → CTO). Not self-reviewed.
2. **NEW WORK discovered, small, `scripts` + `tests` zone:** `scripts/ws_b_health_check.py`
   now has one optional-argument caller outside its own workstream (this report).
   `docs/06-maintenance/ws-b-runner-health.md` documents that checker and does not
   mention the new argument or its new consumer. Out of my zone lock (`docs/`);
   worth a one-line note so a future WS-B maintainer knows the ceiling predicate is
   now load-bearing for a Founder-facing artifact and cannot be weakened locally.
   Suggest folding into DAS-1635 (already the `docs/` follow-up for this ticket).
3. **DAS-1620 / DAS-1621** unblock on this ticket's close, as before. **DAS-1629**
   (`active_plan`) remains a Founder decision and correctly the report's second red.
   **DAS-1622** (the flip) stays `blocked` by design (FR-006) — untouched.

**Escalation to CTO:** none required. This was a correctness fix inside my charter;
the one judgement call I made above a mechanical instruction (rc=2 → UNKNOWN rather
than FAIL) is stated with its reasoning above for the CTO to overrule if he disagrees.

Status set to `in_review`, assignee `cto`. AC-1 and AC-2 re-ticked.

### 2026-07-24 — CTO

**ACCEPTED. `status: done`, `verified_by: cto`. GATE-3 for WS-F TEMPO is CLOSED —
this unblocks DAS-1620 and DAS-1621.**

All three findings from my bounce are closed. I re-derived every one of them from my
own constructions rather than re-running the builder's; where the builder offered a
specific experiment as proof, I ran that experiment myself. Nothing below is accepted
on the builder's word except the four items explicitly listed under ACCEPTED. No new
finding. The two reds and one UNKNOWN in today's report are unchanged and remain the
honest state of the evidence.

---

#### FINDING 1 (the false-green FR-004 gate) — CLOSED, verified three ways

**(a) My own construction, rebuilt from scratch.** I wrote my own stripped
`config/budgets.yaml` scratch copy (drop `metered_overflow`, `plan_credit_usd`, and
both windows' token caps) and my own surrounding clean state — 3 hand-written clean
days at T1=0.91/T2=0.02/T3=11/T4=0.55/T5=1.0/`t7_holds`, my own 6-event
violation-free log, my own answered interrupt card, flag OFF. I did not reuse a
fixture the builder made. Same command, only the budgets file swapped:

```
--budgets budgets-clean.yaml    -> VERDICT: GO      all 10 gates PASS    [exit 0]
--budgets budgets-stripped.yaml -> VERDICT: NO-GO   1 FAIL, 0 UNKNOWN    [exit 1]

  [FAIL   ] credit exhaustion resolves to a sanctioned pause, not a false-green  (SI-5/FR-004)
            mustaqil.caps.per_run.max_input_tokens missing;
            mustaqil.caps.per_run.max_output_tokens missing;
            mustaqil.caps.per_day.max_input_tokens missing;
            mustaqil.caps.per_day.max_output_tokens missing;
            mustaqil.monthly_credit_ceiling.plan_credit_usd missing;
            mustaqil.monthly_credit_ceiling.metered_overflow is '__absent__',
            expected literal false — a flip to true (or a removed key)
            silently re-enables metered spend — SI-5 caps: per_run=$5.0/run,
            per_day=$15.0/day
            source: <stripped> :: mustaqil  (owner: scripts/ws_b_health_check.py
                    :: check_budget_ceiling_drift)
```

`grep -c "metered_overflow=False"` on that output: **0**. The gate no longer renders
a fact it never read. My bounce's exact construction now produces the correct answer.

**(b) The composition is real, not a wrapper around a copy.** The strongest test is
not what the gate says about a file — it is what the gate says when the owner
contradicts the file. I forced the owner's return value in both directions:

```
owner forced ok=True   on my STRIPPED file -> gate PASS   (detail: FORCED-OK)
owner forced ok=False  on the CLEAN  file  -> gate FAIL   (detail: FORCED-FAIL)
owner returns no boolean verdict           -> gate UNKNOWN
owner raises                               -> gate UNKNOWN
```

A gate holding any predicate of its own would have disagreed in at least one of the
first two rows. It does not. It also fails safe — a broken owner is UNKNOWN, never a
pass.

**(c) The builder's offered experiment, re-run by me — inherited vs. duplicated
strength.** On a scratch repo copy I reverted the OWNER's strict guard
(`overflow = ceiling.get("metered_overflow", "__absent__"); if overflow is not False:`)
to the lax `if overflow:` form, leaving `scripts/heartbeat_go_no_go.py` **byte-
untouched**:

```
scratch baseline (both suites)          : 3 failed, 62 passed
   (the 3 are pre-existing wave-ledger/attestation failures of the scratch copy,
    unrelated to the ceiling — check_budget_ceiling_drift is HEALTHY there)

owner's guard weakened, report untouched:
  tests/test_ws_b_health_check.py      -> 4 failed  (incl. test_budget_ceiling_flags_a_removed_metered_overflow_key)
  tests/test_heartbeat_go_no_go.py     -> 1 failed  -> test_removed_metered_overflow_key_is_not_a_pass
restored                                -> 3 failed, 62 passed
```

The report's own suite goes red when only the owner is weakened. Under the pre-bounce
code it would have stayed green, because the gate had its own opinion. That is the
difference the bounce was about, and it is now demonstrated rather than asserted.

**Precision correction, not a finding.** The log says the gate "parses no budget key
at all". Strictly it is the *verdict* that parses none: the display-only
`_si5_cap_note` does read `caps.per_run.max_cost_usd` and `caps.per_day.max_cost_usd`
to render the AC-2 figures. I verified structurally that this string cannot reach the
state (the `Check` state is `PASS if result["ok"] else FAIL`, from the owner alone),
that it renders `MISSING` rather than a default for an absent cap, and that it is
exception-isolated. Recorded so the claim is exact.

---

#### FINDING 2 (three surviving exit-code mutants) — CLOSED, re-injected by me

I re-injected all three of my original mutants myself on a scratch repo copy
(baseline there: 52 passed), plus two more:

| mutation (mine, re-injected) | before the fix | now |
|---|---|---|
| `probe_kill_switch_drill`: ignore `rc`, always PASS | SURVIVED (39 passed) | **2 failed** — `test_a_failing_kill_switch_drill_is_FAIL_not_PASS`, `test_every_exit_code_gate_blocks_GO_when_its_checker_fails` |
| `probe_no_daemon`: ignore `proc.returncode`, always PASS | SURVIVED | **2 failed** — `test_a_failing_daemon_scan_is_FAIL_not_PASS`, `test_every_exit_code_gate…` |
| `probe_never_auto_approve`: non-zero rc returns PASS | SURVIVED | **2 failed** — `test_a_failing_never_auto_approve_scan_is_FAIL_not_PASS`, `test_every_exit_code_gate…` |
| `verdict()`: drop the `bool(gating)` empty-list guard | (new) | **1 failed** — `test_empty_gate_list_is_no_go` |
| genuine pre-fix blacklist (BOTH `unknown=` and `go=` lines reverted) | (new) | **1 failed** — `test_a_novel_state_string_is_not_a_pass` |

All three previously-surviving mutants are dead, killed by named tests, and each is
additionally caught by the combined `test_every_exit_code_gate_blocks_GO_when_its_
checker_fails`. Restored copy → 52 passed.

**One honest negative result of my own, recorded so it is not mistaken for a
weakness.** My first blacklist mutant reverted only `go = bool(gating) and not failed
and not unknown` while leaving the widened `unknown = [c for c in gating if c.state
not in (PASS, FAIL)]` in place — that pair is *semantically equivalent* to the
whitelist, so it survived (52 passed), and it should have. Reverting either line
alone (`unknown` narrowed back to `== UNKNOWN`) or both together is caught. The
property is defended in depth by two independent lines; a non-weakening mutant
surviving is not evidence of a weak test. Same class as the builder's own recorded
`bool(overflow) is not False` negative result, which I agree was correctly diagnosed.

---

#### FINDING 3 (`verdict()` as a blacklist) — CLOSED, and the classic trap is NOT open

The residual I raised is fixed by inversion to `all(c.state == PASS for c in gating)`.
The obvious risk of that inversion is that `all([])` is `True` in Python, so the
`bool(gating)` guard is now the ONLY thing standing between an empty gate list and a
vacuous GO. **It survived.** Verified by construction, not through the test suite:

```
EMPTY LIST  (all([]) is True — the classic trap) -> NO-GO  go=False
one PASS                                         -> GO     go=True
one FAIL                                         -> NO-GO  go=False
one UNKNOWN                                      -> NO-GO  go=False
PASS + novel 'SKIPPED'                           -> NO-GO  go=False
novel only / novel '' / novel 'pass' (lowercase) -> NO-GO  go=False
10 PASS                                          -> GO     go=True
9 PASS + 1 UNKNOWN                               -> NO-GO  go=False
```

The novel state is also *accounted for* — it lands in `could_not_check` rather than
vanishing from every bucket (which would have rendered "0 failing; 0 could not be
checked" beside a NO-GO), and `_block`'s hardened `.get(state, ...)` lookup renders it
as itself instead of taking the Founder's report down with a `KeyError`. I confirmed
`render()` survives a novel state. No new hole.

---

#### rc=2 UNIFICATION — ADJUDICATED: **ACCEPTED, not overruled**

The builder asked me to rule on unifying `probe_loop_mode`'s rc=2 to UNKNOWN rather
than harmonising the other way. I read both owners' rc=2 sites myself before ruling:
`scripts/check_loop_mode.py` returns 2 at exactly one site (`loop config not found`);
`scripts/check_never_auto_approve.py` returns 2 at exactly two sites (`risk taxonomy
not found`, `board dir not found`). The builder's premise is factually correct — in
both tools rc=2 means only "the input isn't there", so nothing was examined. FAIL
asserts evidence was examined and found wanting; that assertion would be false.
UNKNOWN is the truthful classification and it is the one this whole instrument is
built around. **Accepted.** Verified both directions still block GO, and that a
genuine rc=1 is still FAIL in both gates:

```
loop_mode  rc=2 (config not found)   -> UNKNOWN   blocks GO
naa        rc=2 (board not found)    -> UNKNOWN   blocks GO
naa        rc=2 (taxonomy missing)   -> UNKNOWN   blocks GO
loop_mode  rc=1 (real violation)     -> FAIL      blocks GO
naa        rc=1 (real violation)     -> FAIL      blocks GO
```

Pinned against future divergence by `test_rc2_means_could_not_check_in_BOTH_exit_
code_config_gates`.

---

#### THE OWNER'S SEMANTICS ARE BIT-IDENTICAL — verified, not assumed

A `path=None` default plus an early return is exactly the shape that quietly changes
behaviour for the no-arg call, so I tested it rather than reading it. I extracted the
PRE-CHANGE `check_budget_ceiling_drift` from `git show HEAD:scripts/ws_b_health_check.py`
and compared old-vs-new across 14 inputs (clean, `metered_overflow` removed / true /
null / `0`, `plan_credit_usd` removed, token caps dropped, `on_exhaustion` drifted,
`mustaqil: {}`, `mustaqil` absent, `caps` absent, empty doc, absent file, malformed
YAML) in three call forms — old-via-global, new-via-global, new-via-explicit-arg:

```
TOTAL DIFFS: 0        (identical {ok, detail} dicts in all 14 x 3 comparisons)
```

Specifically confirmed:
- `__defaults__ == (None,)` — the global is resolved at CALL time, not frozen into a
  default-argument Path snapshot at def time.
- Rebinding the module global (what `monkeypatch.setattr(mod, "BUDGETS_PATH", fake)`
  does) IS honoured by the no-arg call — the existing callers' and tests' mechanism
  is intact.
- Explicit-arg and global-path calls return byte-identical dicts for the same file.
- `git diff` on `tests/test_ws_b_health_check.py` is **empty** — the owner's 13 tests
  are unedited, and 13/13 pass.
- `0` correctly still fails the identity guard (`0 is not False`).

The change is +15/-5 in one function, two `BUDGETS_PATH` references parameterised. I
judge this an acceptable, reviewable change to a `done` module — it removes a
monkeypatch-from-a-consumer smell rather than adding one.

---

#### NO REGRESSION IN THE NINE GATES I ALREADY CLEARED

Re-attacked every degraded-evidence path, not just the one that failed last round:

```
every evidence path missing at once  -> NO-GO   0 PASS / 1 FAIL / 9 UNKNOWN
event log present but EMPTY          -> UNKNOWN  (never "0 violations")
event log present, 4 unparseable rows-> UNKNOWN  (never "0 violations")
3 history rows carrying no metrics   -> FAIL     0/3 from 3 history row(s)
SI-5 caps stripped                   -> FAIL     suffix renders MISSING, not $5.0
heartbeat_enabled ALREADY true       -> FAIL     (not a pass, not a skip)
empty interrupt store                -> PASS     (recorded residual 3, unchanged)
```

No gate turns absent evidence into a PASS. The read-only property re-verified
empirically, not by inspection: md5 snapshot of **486** files under
`config/ board/ scripts/ tests/` before and after two full runs (text + `--json`) —
**identical, zero bytes written**; the three structural no-write tests still present
and green.

Incidental corroboration that the composed checkers really run: my first hand-written
event log was rejected by the `event_log` gate. It was my fixture that was wrong — an
`interrupt_answer` with `decision: granted` and no `approved_by`/`operator` is a
genuine SI-7 violation under the owner's own rule (unattributed grant ⇒ auto actor).
The gate reproduced its owner faithfully against data I invented to be clean.

**Today's real verdict, unchanged:** exit 1, two FAILs (0/3 shadow window rendered as
raw `0/3 consecutive clean day(s) from 0 history row(s) [evidence file ABSENT]` — no
percentage; DAS-1629's undeclared `active_plan`) and one UNKNOWN (event log absent,
with the "0 events scanned is NOT evidence of 0 violations" reasoning). The three
clocks are still carried separately and both non-gating ones are labelled NOT a
blocker. **GO is still reachable** — my own clean fixtures produce all 10 PASS, exit 0.

#### RE-RUN VERBATIM

```
python3 scripts/heartbeat_go_no_go.py        -> VERDICT: NO-GO   [exit 1]  (2 FAIL, 1 UNKNOWN)
python3 scripts/check_heartbeat_readiness.py -> NOT READY        [exit 1]  (correct red)
python3 scripts/kill_switch_drill.py --smoke -> SI-3..SI-2 all ok, every rail held  [exit 0]
python3 scripts/check_loop_mode.py           -> loop off — mode 'shadow'  [exit 0]
python3 scripts/ws_b_health_check.py         -> HEALTHY          [exit 0]
pytest tests/test_heartbeat_go_no_go.py -q   -> 52 passed in 1.28s   (was 39; +13)
pytest tests/test_ws_b_health_check.py -q    -> 13 passed in 0.19s   (unedited)
pytest <WS-F composite, 10 files> -q         -> 296 passed in 1.67s  (>= 244 baseline)
pytest tests/ -q                             -> 2532 passed, 25 skipped in 21.31s
python3 scripts/diagnostics.py               -> SCORE = 100/100
python3 scripts/board_lint.py                -> OK — 193 ticket(s), 0 violations  [exit 0]
                                                (pre-existing non-fatal DAS-1507 body-status WARN)
ruff check scripts tests                     -> All checks passed!  [exit 0]

md5 config/budgets.yaml  -> d58d0e87b7af50d118b07c6fde93f662   (unchanged)
md5 config/features.yaml -> 5180091e0968c2e373dfa4076585b23e   (unchanged)
ls board/.events.jsonl board/.metrics-history.jsonl -> No such file or directory (both)
config/features.yaml: heartbeat_enabled: false   ws_f_heartbeat: false   (judged by VALUE)
```

No git state mutated — no `add/commit/checkout/reset/stash`, no worktree, no push, no
PR. Zone respected on my side: this ticket file plus `board/.arcrift-outbox.jsonl`
only; nothing under `docs/`. Backend EM's diff is confined to
`scripts/ws_b_health_check.py` (+2 untracked new files) — `docs/` untouched by them
too, so the concurrent `docs/06-maintenance/` editor was not disturbed.

#### RE-VERIFIED INDEPENDENTLY (my own constructions, this round)

- The stripped-budgets construction, rebuilt from scratch → NO-GO/exit 1 with the
  owner's findings verbatim, zero invented values.
- The gate holds no predicate — forced-owner-verdict test in both directions.
- Inherited strength — owner-guard weakening turns the report's suite red.
- Owner bit-identity — 14 inputs x 3 call forms, 0 diffs; global rebinding honoured;
  owner's 13 tests unedited and green.
- Three exit-code mutants re-injected by me — all now caught.
- `verdict()` whitelist over an empty list → NO-GO; `bool(gating)` guard survived.
- rc=2 in both config gates → UNKNOWN; rc=1 → FAIL; both block GO.
- Read-only, empirically: 486-file md5 snapshot identical across two full runs.
- Degraded-evidence sweep over all ten gates; today's verdict and the three-clock
  separation unchanged.

#### ACCEPTED without independent re-derivation (recorded so it is not mistaken for verified)

- The correctness of `hr.assess`, `lc._monthly_credit_exhausted`, the six drill rails,
  and `check_budget_ceiling_drift`'s ceiling contract itself. This ticket composes all
  four; re-litigating them here would be the second decision engine AC-1 forbids.
  DAS-1620 / DAS-1621 are the tickets that re-derive them.
- The merged-PR / green-CI leg of the DoD — outstanding by orchestrator directive
  (LOCAL-ONLY run). Explicitly NOT a bounce reason.
- AC-1's `docs/` half — out of zone, carried by DAS-1635. Not a bounce reason.
- The `docs/06-maintenance/ws-b-runner-health.md` note about the owner's new optional
  argument — ticketed as DAS-1636, out of my zone. Not a bounce reason.

#### RESIDUALS CARRIED FORWARD (recorded, deliberately not fixed)

Unchanged from my bounce, and I agree with the builder's reasoning for leaving both:
zero-item board/interrupt scans PASS (if 0 tickets should be UNKNOWN that rule belongs
in `check_never_auto_approve`, not in a second engine here), and `rolling_waves`
computes its own `>= 7` sum locally (`gating=False`, cannot reach the verdict; if it
ever becomes gating it needs an owner first). Neither can affect a Founder decision
today. New, minor: the `_si5_cap_note` display helper is the one place the report
reads a budget field directly — state-isolated and verified as such, but it is the
line to re-check if the SI-5 cap shape ever moves.

#### GATE DECISION

**GATE-3 (Development) for WS-F TEMPO is CLOSED.** The Founder-facing go/no-go
artifact composes ten gates from ten `done`-owned checkers, owns no predicate of its
own, cannot write, cannot recommend, treats absent evidence as NOT READY, and — the
thing this round was about — inherits its FR-004 strength from the checker that owns
the ceiling contract rather than duplicating it. It says NO today, for two real
reasons and one absent evidence source, and it can still say YES on clean evidence.

**This unblocks DAS-1620 (SI drill) and DAS-1621 (kill-switch drill).**

#### Routing (orchestrator — I cannot create tickets or spawn agents)

1. **DAS-1620 and DAS-1621 are now unblocked** by this ticket's close.
2. **DAS-1635** carries AC-1's `docs/` half; **DAS-1636** carries the
   `docs/06-maintenance/ws-b-runner-health.md` note that
   `check_budget_ceiling_drift`'s ceiling predicate is now load-bearing for a
   Founder-facing artifact and must not be weakened locally. Both zone `docs`.
3. **DAS-1629** (`config/budgets.yaml` `active_plan`) remains a Founder decision and
   is correctly the report's second red. **DAS-1622** (the flip) stays `blocked` by
   design (FR-006) — untouched by this ticket and untouchable by it.
4. **Carried at workstream close:** the merged-PR / green-CI leg of the DoD, deferred
   here by orchestrator directive (LOCAL-ONLY run).

**Escalation to CEO:** none. Technical correctness call inside the engineering
charter. Not self-reviewed — I did not author any of the code I accepted.
