---
id: DAS-1639
title: The per-day rail enforces the informational org cap instead of the MUSTAQIL SI-5 ceiling
status: done
assignee: cto
verified_by: cto
author: sre-lead
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1632]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Found by SRE Lead while reviewing DAS-1632. Pre-existing, out of that ticket's
scope (it explicitly forbade touching caps), and plausibly more material than the
window defect it was reviewing.**

`scripts/loop_controller.py :: _per_day_budget_exceeded` reads
`caps.per_day.max_cost_usd` = **$500/day** — the org-level block that
`config/budgets.yaml` itself describes as *informational*.

The MUSTAQIL SI-5 ceiling is `mustaqil.caps.per_day.max_cost_usd` = **$15/day**, and
**nothing in the tick path reads it.** Meanwhile `scripts/heartbeat_go_no_go.py`
reports `$15.0/day` as the SI-5 cap to the Founder.

**So the documented ceiling and the enforced ceiling differ by 33x, and the
Founder-facing artifact reports the documented one.** This is the same family as the
D1 window defect — a rail reading the wrong number — on a different axis: wrong cap
rather than wrong window.

**Direction of the fix is safe, but it is still a cap change.** Enforcing $15
*tightens* the rail, so it cannot widen autonomy. It nonetheless changes when
dispatch stops, so it needs its own ticket, its own review, and an explicit
confirmation that the tighter cap is intended — which is precisely why the DAS-1632
reviewer routed it here instead of fixing it in passing.

**Verify the intent before changing the number.** Read `config/budgets.yaml` and
ADR-0042 (SI-5.1: the ceiling is an outer cap alongside per-run/per-day,
tightest-constraint-wins, one accountant). Confirm which block SI-5 actually
designates, and confirm the go/no-go report's `$15.0/day` is reading the block you
conclude is authoritative. If the two disagree even after your fix, say so loudly —
a rail and a report that quote different ceilings is the defect, not the specific
number.

**Do not widen anything.** If your reading concludes the enforced cap should be the
looser $500, stop and report rather than raising the ceiling; that would be a
Founder-visible autonomy change, not an engineering fix.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT edit `config/budgets.yaml` — this ticket
changes which existing key the rail READS, not any key's value. `git diff` on all
three config files must be empty at the end.

**Reviewer note (ROUTING):** this ticket's author is `sre-lead`. When it reaches
`in_review`, assign it to **`cto`**, not `sre-lead` — the "manager is the author →
climb one level" rule. Assigning it back to the author trips the no-self-review lint
(board_lint R8 + the diagnostics Consistency dimension, worth 15 points).

## Acceptance criteria
- [x] The rail reads the block SI-5 actually designates, with the reasoning recorded against `config/budgets.yaml` + ADR-0042 — not chosen by which number looks right.
- [x] The rail and `heartbeat_go_no_go.py` quote the SAME ceiling; any residual disagreement reported loudly rather than reconciled silently.
- [x] A test pins the enforced cap to the authoritative key, so a future rename or reshuffle of `budgets.yaml` fails loudly instead of silently re-pointing at a looser block.
- [x] No cap VALUE changed; `git diff config/budgets.yaml` empty. Nothing widened.
- [x] `check_heartbeat_readiness.py` still NOT READY (0/3, `active_plan is undeclared`); `kill_switch_drill --smoke` 6 rails green; `DECISIONS` unchanged.
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — SRE / DevOps Lead
Found during the DAS-1632 review by checking WHICH cap the rail reads, not just
whether the window arithmetic was right — the window fix was correct and the number
it was applied to was not. Recorded by the orchestrator in the same run. Deliberately
not fixed in DAS-1632: that ticket's constraints forbade touching caps, and a cap
change deserves its own review even when it tightens.

### 2026-07-24 — SRE Engineer

**1. Which block SI-5 designates — reasoning, not the number that looks right.**

- `config/budgets.yaml` self-describes the top-level `caps:` block, verbatim, as
  "Per-run caps (informational — not a blocking gate until C1 is promoted)"
  (line 40). The `mustaqil:` block's own comment says its `caps` "are the
  runner's HARD dispatch ceiling (self-imposed autonomy budget, stricter than
  the shared gate — SI-5)" and "A `--tick` that would breach either evaluates
  to idle + alert" (lines 69–72). The document names its own SI-5 block
  explicitly, in its own text — it is `mustaqil.caps`, not the informational
  top-level `caps`.
- ADR-0042 SI-5.1 confirms this at the enforcement-point level: "`mustaqil.
  monthly_credit_ceiling...` is a third dispatch ceiling, evaluated in addition
  to `caps.per_run` and `caps.per_day`" where, per the ADR's own §Relates and
  §Context, those `caps.per_run`/`caps.per_day` references are the `mustaqil:`
  sub-block throughout — the whole addendum is about the MUSTAQIL runner's
  dispatch ceiling, never the org-wide informational block. SI-5.2 clause 6
  makes it unambiguous by naming the exact defect this ticket fixes: "The
  shipped `_per_day_budget_exceeded` still aggregates lifetime and therefore
  does not yet satisfy this clause; that is a known, separately-ticketed
  defect (DAS-1632)" — i.e. the ADR already treats `_per_day_budget_exceeded`
  as implementing the `mustaqil` SI-5 per-day ceiling, window bugs aside.
- `docs/specs/010-mustaqil-ws-f-tempo/SPEC.md` FR-004: the monthly credit
  ceiling is "an additional hard dispatch ceiling the heartbeat honors,
  alongside — never in place of — the SI-5 per-run/per-day caps in
  `config/budgets.yaml`" — and `scripts/ws_b_admission.py` (the admission path
  SPEC-010 cites for those same SI-5 per-run/per-day caps) already reads
  `mustaqil.get("caps")` exclusively (`load_mustaqil_budgets` → `caps =
  mustaqil.get("caps")`, ws_b_admission.py:215) — never the top-level block.
  `scripts/ws_b_health_check.py` and `scripts/heartbeat_go_no_go.py` (its
  `_si5_line` helper, lines 237–246) likewise both read only
  `mustaqil.caps.{per_run,per_day}.max_cost_usd` and label it "SI-5 caps" —
  every other SI-5 consumer in the repo already agrees the `mustaqil:` block
  is the ceiling; `loop_controller.py`'s `_per_day_budget_exceeded` was the
  sole outlier reading the informational block.
- Conclusion: SI-5 designates `mustaqil.caps.per_day.max_cost_usd` = **$15/day**.
  The $500 org-wide block is informational per its own comment and is not
  promoted by anything read above. Direction is tightening only — no widening.

**2. Fix.** `scripts/loop_controller.py::_per_day_budget_exceeded` now loads the
`mustaqil:` block via `ws_b_admission.load_mustaqil_budgets` (the SAME reader
`_monthly_credit_exhausted` already uses — ADR-0042 SI-5.1 "one accountant, no
second one" applied here by analogy: both SI-5 spend rails now go through one
loader instead of two ad-hoc YAML reads) and reads
`mustaqil.caps.per_day.max_cost_usd` instead of the top-level `caps.per_day.
max_cost_usd`. No other caller of `load_mustaqil_budgets` or of the top-level
`caps:` block was touched (`ws_b_admission.py`, `alerting.py`,
`ws_b_health_check.py` unchanged) — verified by full-suite green below.

**3. Rail vs. report — same ceiling, verified.** `heartbeat_go_no_go.py`
already read `mustaqil.caps.per_day.max_cost_usd` (its `_si5_line` helper) —
it was never the wrong side of the disagreement; the rail was. Re-ran it after
the fix: prints `SI-5 caps: per_run=$5.0/run, per_day=$15.0/day`. Rail and
report now cite the identical key and value. No residual disagreement to
report.

**4. Test.** Added `test_per_day_budget_resolves_from_mustaqil_key_not_org_
informational_block` (`tests/test_loop_controller.py`) — deliberately not a
bare `== 15.0` check. The fixture sets CONTRADICTORY values: top-level
`caps.per_day.max_cost_usd: 500` (would not breach) vs. `mustaqil.caps.per_day.
max_cost_usd: 15` (does breach) against the same ~$20 spend; asserts the rail
follows the `mustaqil` value. If a future rename/reshuffle silently re-points
the rail at the org block, this flips True→False and fails loudly. Also
updated the existing fixture `_write_per_day_budgets_with_pricing` (used by 4
other tests) to write the cap under `mustaqil.caps.per_day` only — it no
longer writes a top-level `caps.per_day` at all, so those tests are equally
load-bearing (a regression back to the informational block reads cap_usd=0,
never breaches, and `test_per_day_budget_true_when_spend_is_today` fails).
Also updated `scripts/kill_switch_drill.py::_write_budgets` to write the same
key so the drill fixture exercises the key the rail actually reads (its
`drill_budget_caps` per-run sanity check against the REAL `caps.per_run`
top-level block is untouched — that check inspects the real SSOT's shape, not
tick-time enforcement).

**Observed evidence (verbatim):**
```
BEFORE FIX would read caps.per_day.max_cost_usd = $500.0 -> exceeded = False
AFTER  FIX reads mustaqil.caps.per_day.max_cost_usd = $15.0 -> exceeded = True
  (same fixture: ~$20 opus spend today, real config/budgets.yaml)
```
Through `tick()` itself (not just the helper), same $20 spend, real
`config/budgets.yaml`, `config/loop.yaml`, `config/features.yaml`:
```
decision: {'action': 'idle', 'trigger': 'cron_tick',
  'reason': 'cron_tick: pending board work — dispatch the next wave; dispatch
  withheld — per-day budget cap already breached (SI-5)'}
safety_rails: {'break_glass_active': False, 'in_quiet_hours': False,
  'per_day_budget_exceeded': True, 'monthly_credit_exhausted': False}
```
`heartbeat_go_no_go.py` after the fix: `SI-5 caps: per_run=$5.0/run,
per_day=$15.0/day` (matches the enforced key/value exactly).

`python3 scripts/check_heartbeat_readiness.py` → exit 1, VERDICT NOT READY,
`0/3 consecutive clean day(s)`, blocker `monthly credit ceiling not
enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared` (red
is correct — unrelated Founder-gated blocker, DAS-1629).

`python3 scripts/kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok
SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok` — `EXIT=0`.

`python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO — the evidence bar
is NOT met today.` — `EXIT=1` (read directly, not through a pipe).

`flow_router.DECISIONS` → `['dispatch', 'idle', 'validate']` — unchanged,
exactly the closed alphabet.

`python3 -m pytest tests/` → `2553 passed, 25 skipped` (>= prior baseline; 0
failed). Targeted subset (loop_controller/kill_switch/heartbeat/flow_router/
ws_b) → `266 passed, 1 skipped`.

`python3 scripts/diagnostics.py` → `SCORE = 100/100` (all 8 dimensions green,
including Consistency 15/15 — no self-review issue since status here is set
to `in_review` with `assignee: cto`, not `sre-lead`).

`python3 scripts/board_lint.py` → `OK: 197 ticket(s) checked, 0 violations`
(one pre-existing unrelated WARN on DAS-1507, not from this ticket).

`ruff check scripts tests` → `All checks passed!`

`git diff config/budgets.yaml config/loop.yaml` → both empty (verified).
`config/features.yaml` carries only the pre-existing unstaged `a2a_outbound:
false` line from earlier in this run — not touched here.

**Files touched:** `scripts/loop_controller.py` (`_per_day_budget_exceeded`),
`scripts/kill_switch_drill.py` (`_write_budgets` fixture),
`tests/test_loop_controller.py` (new pin test + updated fixture), this ticket.
Zone lock (`scripts/` + `tests/` + ticket file) held; nothing under `docs/`,
`config/`, or `tools/` touched.

Routing to **`cto`** per the reviewer note (author `sre-lead` → climb one
level, no-self-review). `status: in_review`.

### 2026-07-24 — CTO (review)

**Verdict: ACCEPTED.** `in_review` → `done`, `verified_by: cto`. I am independent
of both the finder (`sre-lead`) and the builder (`sre-eng`). A 33x tightening of a
dispatch rail is a real behavioural change even though it cannot widen autonomy, so
I re-derived the authority question from the sources rather than accepting the
builder's summary, and re-ran every gate myself.

**RE-VERIFIED BY ME (not accepted on the builder's word).**

*1. Which block SI-5 designates — read at source, and the answer is stronger than
the ticket argued.* `config/budgets.yaml:40` says verbatim
`# Per-run caps  (informational — not a blocking gate until C1 is promoted)`, and
lines 68–72 say the `mustaqil:` `per_run`/`per_day` caps "are the runner's HARD
dispatch ceiling (self-imposed autonomy budget, stricter than the shared gate —
SI-5)". Both quotes are exact. The decisive text, which the builder did not cite,
is **ADR-0027 SI-5 itself** (`docs/adr/0027-scheduler-safety.md:157-160`): *"Caps
are read from `budgets.yaml` (currently informational until the C1 cost-gate is
promoted per ADR 0020's data discipline); **the heartbeat treats them as its hard
dispatch ceiling regardless of the org-wide gate promotion state — a self-imposed
autonomy budget stricter than the shared gate.**"* `budgets.yaml`'s `mustaqil:`
comment is a verbatim echo of that closing clause. So the org-wide block IS "the
shared gate"; the heartbeat's ceiling is by definition the thing that is *stricter
than* it. Reading the shared gate as the ceiling contradicts the sentence that
defines the ceiling. Conclusion confirmed independently:
**SI-5 = `mustaqil.caps.per_day.max_cost_usd` = $15/day.**

*2. The "until C1 is promoted" escape hatch — checked, and it is not load-bearing
either way.* C1 is **not** promoted: `.github/workflows/ci.yml:157` runs
`python3 scripts/check_cost.py` with **no `--max`**, and `check_cost.py`'s own
header states the lever "does NOT block CI unless the caller passes `--max`" — no
caller anywhere passes it. And even a future promotion would not move this
decision: ADR-0027 SI-5 binds the heartbeat to the stricter self-imposed budget
*"regardless of the org-wide gate promotion state"*. Promotion would make $500 a
second, looser org gate — never the tick-time ceiling. The premise holds.

*3. Nothing widened.* `git diff config/budgets.yaml config/loop.yaml` → **0 bytes**
(measured, not eyeballed); `budgets.yaml` does not appear in `git status` at all.
`config/features.yaml`'s only diff hunk is the pre-existing `a2a_outbound: false`
line; `heartbeat_enabled` reads `false` **by value** (`config/features.yaml:12`).
The change is strictly *which key is read*.

*4. The "one accountant" refactor disturbed no other caller.* Every caller of
`ws_b_admission.load_mustaqil_budgets` enumerated: `loop_controller`
`_per_day_budget_exceeded` (this ticket, new) and `_monthly_credit_exhausted`
(DAS-1618); `heartbeat_go_no_go.py:237` (display only); `ws_b_admission.py:323`
(`admit`) and `:429` (CLI). Every reader of the top-level `caps:` block
enumerated: `check_cost.py:87` (C1 `--max` lever), `alerting.py:96`
(`budget_governor`, fed a caller-supplied dict), `kill_switch_drill.py:397-398`
(real-SSOT shape check). `scripts/ws_b_admission.py`, `scripts/alerting.py` and
`scripts/check_cost.py` are **not in `git status`** — untouched, so none of them
can have changed behaviour.

*5. Failure modes — the rail FAILS OPEN, and I am recording that explicitly
because it is the question this ticket family is about.* Measured against the
shipped code, `_per_day_budget_exceeded` returns **`False` (= no cap enforced,
dispatch NOT withheld)** for all of: missing budgets file, unparseable YAML,
absent `mustaqil:` block, absent `mustaqil.caps`, absent `caps.per_day`. This is
pre-existing and unchanged in direction by this ticket, and it is **not** left
unguarded: I verified the compensating control is fail-**CLOSED** on the exact
same five inputs — `ws_b_health_check.check_budget_ceiling_drift` returns
`ok=False` for every one of them (`no top-level mustaqil: block`, `mustaqil.caps
missing`, `mustaqil.caps.per_day.* missing`, `failed to parse`, missing file), and
`heartbeat_go_no_go.py` composes that verdict into its FR-004 gate rather than
paraphrasing it. So a `budgets.yaml` that would silently disable the rail cannot
pass go/no-go, and the heartbeat cannot be enabled. The layering is defensible and
I accept it. One residual is logged below: the helper's docstring calls this
"failure-safe … the heartbeat is conservative: if in doubt, idle", which is
**inaccurate** — returning `False` idles nothing; it stands the rail down.

*6. The pin test genuinely pins — proven by mutation, not by reading it.* I
re-pointed `_per_day_budget_exceeded` at the top-level `caps.per_day` block on a
scratch copy (a pytest plugin substituting an otherwise-identical function, DAS-1632
windowing left intact, repo untouched) and re-ran the full suite:
```
2 failed, 2551 passed, 25 skipped
FAILED tests/test_loop_controller.py::test_per_day_budget_resolves_from_mustaqil_key_not_org_informational_block
FAILED tests/test_loop_controller.py::test_per_day_budget_true_when_spend_is_today
```
Exactly the two tests the builder predicted, and no others. The pin is a
contradictory-values test ($500 top-level vs $15 `mustaqil` against the same ~$20
spend), not a bare `== 15.0` — moving $15 into the wrong block would still fail it.
Noted: the `kill_switch_drill` fixture writes the cap under **both** blocks, so the
SI-5 drill is not key-discriminating and stayed green under the mutation; the pin
test carries that duty alone. Acceptable, recorded.

*7. Fixtures are contract-corrections, not test-fitting.* `kill_switch_drill.
_write_budgets` and `_write_per_day_budgets_with_pricing` now write the cap under
the key the rail actually reads. In both the assertion is untouched and still
behavioural (`per_day_budget_exceeded is True` → `IDLE`); only the *input* moved to
the authoritative key. The drill's separate real-SSOT shape check is untouched. No
assertion was relaxed anywhere.

*8. Through `tick()`, against the REAL `config/budgets.yaml` — my own run:*
```
--- SAME-DAY $20 spend ---
  decision    : {'action': 'idle', 'trigger': 'cron_tick', 'reason': 'cron_tick: pending board work — dispatch the next wave; dispatch withheld — per-day budget cap already breached (SI-5)'}
  safety_rails: {'break_glass_active': False, 'in_quiet_hours': False, 'per_day_budget_exceeded': True, 'monthly_credit_exhausted': False}
--- PRIOR-DAY $20 spend ---
  decision    : {'action': 'dispatch', 'trigger': 'cron_tick', 'reason': 'cron_tick: pending board work — dispatch the next wave'}
  safety_rails: {'break_glass_active': False, 'in_quiet_hours': False, 'per_day_budget_exceeded': False, 'monthly_credit_exhausted': False}
  resolved cap: mustaqil.caps.per_day.max_cost_usd = 15.0
  DECISIONS: ['dispatch', 'idle', 'validate']  == {dispatch,validate,idle}: True
```
$20 is over $15 and under $500: it now idles where it previously would have
dispatched. Same spend on the prior UTC day still dispatches — DAS-1632's windowing
holds through the fix. Decision alphabet unchanged.

**THE HEADLINE FINDING, STATED EXPLICITLY (AC #2).** The **enforced** SI-5 per-day
ceiling and the **reported** one now agree: the rail resolves
`config/budgets.yaml :: mustaqil.caps.per_day.max_cost_usd` = **$15.0/day**, and
`heartbeat_go_no_go.py` prints `SI-5 caps: per_run=$5.0/run, per_day=$15.0/day`
sourced from `config/budgets.yaml :: mustaqil`. **Same key, same value, same
file.** The 33x rail/report divergence is closed. The report was never on the wrong
side — the rail was, and the rail moved to meet it.

**RE-RUN GATES (verbatim, my run, not copied):**
```
check_heartbeat_readiness.py  -> EXIT=1  VERDICT: NOT READY
                                 "0/3 consecutive clean day(s)"
                                 "monthly credit ceiling not enforceable:
                                  mustaqil.monthly_credit_ceiling.active_plan is undeclared"
kill_switch_drill.py --smoke  -> EXIT=0  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
heartbeat_go_no_go.py         -> EXIT=1  VERDICT: NO-GO — the evidence bar is NOT met today.
                                 (exit code read directly, not through a pipe)
pytest tests/                 -> 2553 passed, 25 skipped
WS-F composite subset         -> 234 passed  (loop_controller, kill_switch_drill,
                                 heartbeat_go_no_go, flow_router, ws_b_admission,
                                 check_heartbeat_readiness, cost_ledger)
diagnostics.py                -> SCORE = 100/100
board_lint.py                 -> OK: 197 ticket(s) checked, 0 violations
                                 (1 pre-existing non-fatal WARN on DAS-1507)
ruff check scripts tests      -> All checks passed!
```
The two red results are the CORRECT red: `NOT READY` / `NO-GO` are Founder-gated
blockers (undeclared `active_plan`, DAS-1629 / insufficient shadow window), not
regressions. No suite-count equality was asserted; counts are recorded as
observations.

**ACCEPTED WITHOUT RE-DERIVATION** (judged, low-risk, disclosed by the builder):
the ADR-0042 SI-5.2 clause-6 citation and the SPEC-010 FR-004 quote — both
corroborate a conclusion I established independently from ADR-0027 + `budgets.yaml`,
so nothing rests on them alone.

**RESIDUALS — reported loudly per AC #2, none blocking, none of which changes any
enforced number. All are `scripts/`-zone follow-ups for the orchestrator to route:**

- **R1 (doc/label, same family as this defect).** `kill_switch_drill.py:395-401`
  reads the REAL top-level `caps.per_run`/`caps.per_day` under the comment
  *"Per-run cap presence in the REAL SSOT — a hard dispatch ceiling (ADR-0027
  SI-5)"*. By this ticket's own (now-ratified) conclusion that label is wrong: it
  inspects the **informational** block. Harmless today — it is a presence/shape
  assertion, enforces nothing, and both blocks exist with sane values — but it is
  literally "a check whose label says SI-5 while reading the org block", the exact
  family DAS-1639 closes. Recommend a follow-up that either re-points it at
  `mustaqil.caps.per_run` or relabels it as an org-block shape check.
- **R2 (misleading docstring on a safety rail).** `_per_day_budget_exceeded`'s
  "failure-isolated … the heartbeat is conservative: if in doubt, idle" describes
  fail-closed behaviour; the code fails **open** (§5 above). A future reader could
  trust the comment over the code on a safety rail. Comment-only fix; no
  behavioural change intended or wanted.
- **R3 (fixture-isolation leak, pre-existing).** `_per_day_budget_exceeded` calls
  `aggregate_spans(events_path, since=...)` **without** `budgets_path`, so tier
  *pricing* always resolves from the real `config/budgets.yaml` even when a caller
  injects a scratch budgets file — unlike `_monthly_credit_exhausted`, which passes
  it. Inert in production (there `budgets_path` IS the real file), but it means
  `tiers:` in every test/drill fixture is decorative and a fixture with different
  prices would be silently ignored. Pre-existing (the original line was
  `aggregate_spans(events_path)`), out of this ticket's scope.
- **R4 (scope note, not a defect).** The rail now consults only the `mustaqil`
  cap, so if the org-informational block were ever tightened *below* $15 it would
  not bind at tick time. Correct as built — that block is informational by its own
  text and ADR-0027 ties the heartbeat to the self-imposed budget "regardless of the
  org-wide gate promotion state" — but recorded so a future tightest-wins reading of
  `docs/design/ws-f-tempo-verification.md:72` ("`caps.per_run`/`caps.per_day` **and**
  the stricter `mustaqil.caps.*`") is not mistaken for a regression.
- **R5 (cosmetic).** The go/no-go helper is named `_si5_cap_note`
  (`scripts/heartbeat_go_no_go.py:225`), not `_si5_line` as the review brief and
  this ticket's log call it. Substance verified at source; naming nit only.

**Git-law note:** merged-PR / green-CI remains outstanding for this ticket by
standing orchestrator directive (local-only run, no remote). `done` here attests
the engineering verdict and the evidence above, not a merge.
