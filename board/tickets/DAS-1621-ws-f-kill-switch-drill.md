---
id: DAS-1621
title: WS-F Testing — kill-switch and break-glass drill, zero gate violations
status: done
assignee: qa-lead
verified_by: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [SC-002]
labels: [governance, security]
zone: tests
depends_on: [DAS-1620]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-F, part 2).** Run the dedicated
kill-switch / break-glass safety-rail drill, reusing DAS-1478's existing drill
machinery rather than authoring a new one, and confirm SI-3 and SI-6 hold under
WS-F's closure.

- **SI-3 (break-glass honored):** activate `scripts/break_glass.py`, confirm a
  `--tick` consults `is_active(now)` and dispatches nothing while active; confirm
  auto-expiry at 60 minutes; confirm the heartbeat never activates/clears
  break-glass itself.
- **SI-6 (max-concurrent-waves = 1):** confirm a `--tick` firing while a prior
  heartbeat-dispatched wave is in flight evaluates to idle (no overlapping wave).
- **Event-log check:** scan `board/.events.jsonl` / interrupt-card records for the
  drill window and confirm **zero gate/approval violations** — no auto-approved
  gate, no auto-answered interrupt-card, no `heartbeat_enabled` write.

## Acceptance criteria
- [x] Break-glass drill run: dispatch correctly halts while active, resumes only
      after expiry/deactivation, auto-expiry confirmed at 60 minutes.
- [x] Max-concurrent-waves = 1 confirmed: an overlapping `--tick` evaluates to idle.
- [x] Event log scanned for the drill window: **zero** gate/approval violations
      recorded — this is SC-002's pass condition, stated plainly in the log
      (see log for exactly what was and was not covered — `board/.events.jsonl`
      does not exist; the scan that produced "zero violations" ran over the
      drill's own synthetic/scratch event streams, not a real event log).
- [x] `diagnostics.py` 100/100; reuses (does not fork) DAS-1478's drill tests; merged
      PR if any code changed, else a recorded local-run transcript.
- [x] **Reviewed (QA Lead, GATE-4 owner):** SI-3 structural proof independently
      re-derived, 60-minute expiry boundary re-measured, SI-6 confirmed
      non-vacuous, event-log honesty confirmed. **GATE-4 for WS-F TEMPO closed.**

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Testing, part 2). Dedicated kill-switch/break-glass
drill (SI-3/SI-6) reusing DAS-1478's existing machinery; confirms zero gate/approval
violations in the event log per SPEC-010 SC-002.

### 2026-07-24 — QA Engineer

Ran the AADL Stage 4 part-2 kill-switch/break-glass drill. Read-only git,
zone-locked to `tests/` + this ticket file, local-only, no push. **Reused**
DAS-1478's existing drill machinery (`scripts/kill_switch_drill.py`,
`scripts/break_glass.py`) — authored no second drill, only a scratchpad driver
script that calls the real functions (`loop_controller.tick`, `break_glass.*`,
`kill_switch_drill.scan_gate_approval_violations`).

**Pre-check — no counted-wave state exists in the repo:**
```
ls board/.events.jsonl board/.metrics-history.jsonl
→ ls: board/.events.jsonl: No such file or directory
  ls: board/.metrics-history.jsonl: No such file or directory
```
Both confirmed absent before and after this run (re-checked at the end;
`git status --short` shows neither file — no synthetic state was ever written
to the real repo).

**SI-3 — break-glass honored.**
`python3 scripts/kill_switch_drill.py --smoke` →
```
kill-switch-drill: running 1 pass(es) of the 6 safety rails...
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```
exit 0.

Extended manually beyond the smoke pass (scratchpad driver
`das1621_drill.py`, isolated scratch dir, never touches real config/board
state) to nail down the two things the ticket calls out specifically:
- Activated break-glass via `break_glass.build_activation` +
  `break_glass.append_event` (the same functions the CLI `activate` verb
  calls) against a scratch events file. `is_active()` true at T0, T0+30m,
  T0+59m59s; **false at T0+60m and T0+90m** — auto-expiry confirmed exactly
  at the 60-minute boundary (window is `start <= now < start + 60min`).
- `--tick` at T0+15m (break-glass engaged): `decision.action == "idle"`,
  reason includes `"break-glass override active (SI-3)"`,
  `safety_rails.break_glass_active == True`. **No dispatch.**
- `--tick` at T0+90m (auto-expired): `decision.action == "dispatch"`,
  `safety_rails.break_glass_active == False`. Dispatch resumed with zero
  manual deactivation step — bounded stop confirmed.
- Scratch `events.jsonl` line count before vs. after both ticks: **1 → 1**.
  `loop_controller.tick` never appended to the break-glass/event store —
  it is a pure evaluator (`tick()`'s own docstring: "never mutates
  anything"), consistent with the assertion.

**SI-3 structural proof — heartbeat cannot clear its own kill switch.**
This is the invariant that matters most, verified structurally, not just
behaviourally:
- `grep -rn "break_glass" scripts/*.py` outside `break_glass.py` and
  `kill_switch_drill.py` shows only three importers:
  `loop_controller.py` (imports `is_active` — read-only),
  `flow_router.py` (a `break_glass_active: bool` field/flag — read-only
  data in, no break_glass import at all), and `alerting.py` (imports
  `break_glass.is_active` for a status reading — read-only).
- `break_glass.append_event` (the ONLY function in the whole module that
  writes to the break-glass event store) is called from exactly two
  places: `break_glass.py`'s own `activate` CLI subcommand, and
  `kill_switch_drill.py`'s `drill_break_glass()` — which writes only to an
  isolated `work_dir / "bg.events.jsonl"` scratch file inside a
  `tempfile.mkdtemp()` directory, never `board/.events.jsonl`.
- AST-walked `scripts/loop_controller.py` and `scripts/flow_router.py` for
  any `Call` node named `append_event`, `activate`, `write_text`, or
  `open`: **zero matches in both files.** There is no write path, direct
  or transitive, from a tick or the router to break-glass state.
- `heartbeat_enabled` write path: `scripts/feature_flags.py` exposes
  `DEFAULTS`, `load`, `enabled`, `main` — **no writer function exists in
  the module.** `grep -rn "heartbeat_enabled" scripts/*.py config/*.yaml`
  shows every scripts/ hit is a read (`_ff_enabled`, `feature_flags.enabled`)
  or a print/string describing the Founder-only manual edit
  (`heartbeat_go_no_go.py`'s `THE_FLIP` constant, printed never executed).
  The only `write_text` writing a `heartbeat_enabled:` line anywhere in
  `scripts/` is `kill_switch_drill.py:_write_flags`, and it writes to an
  isolated scratch `work_dir / "features.yaml"`, never
  `config/features.yaml`. Confirmed `config/features.yaml` untouched
  (`git status --short` — no diff on that file from this ticket's work).

**SI-6 — max-concurrent-waves = 1.**
From the `--smoke` composite: `SI-6=ok`. Manually reproduced in isolation:
seeded a scratch event store with one `run_start` event and no matching
`run_end` (a wave in flight), then ran `--tick`: `decision.action ==
"idle"`, reason includes `"a wave is already in flight, max 1 (SI-6)"`.
No overlapping wave dispatched.

**Event-log check — stated plainly, not fudged.**
`board/.events.jsonl` **does not exist** in this repo. Zero events scanned
there is **not** evidence of zero violations in a live drill window — it is
absence of evidence, because no counted heartbeat wave has ever landed
(consistent with `heartbeat_go_no_go.py`'s own `[UNKNOWN] zero
auto-approved gate/interrupt events in the event log` gate, re-run below,
which correctly refuses to call this a PASS). What WAS scanned, honestly:
the drill's own synthetic/scratch event streams — the scratch break-glass
events file, the scratch SI-6 in-flight-run stream, and
`kill_switch_drill._synthetic_event_log()`'s canonical clean log (a
PENDING gate, an unanswered interrupt-card, and one genuine
`approved_by: founder` approval — none of which are auto-approvals) — via
`kill_switch_drill.scan_gate_approval_violations()`, the same scanner
`--smoke`'s SI-7 rail uses. Result: **8 synthetic events scanned, 0
violations.** Coverage statement: this proves the scanner is clean over
everything the drill itself generates in this run; it does **not** and
cannot establish anything about `board/.events.jsonl` because that log has
no rows. `board/.events.jsonl` and `board/.metrics-history.jsonl` were NOT
created in the real repo — both confirmed absent again after this drill.

**Composite/regression suites (verbatim):**
```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py tests/test_heartbeat_go_no_go.py \
  tests/test_check_break_glass_review.py -q
→ 283 passed in 1.55s, exit 0
```
Pass predicate: `exit 0 ∧ 0 failed ∧ 0 errors ∧ collected >= 195` (never
`== N`, per design §2.0 count discipline). 283 >= 195 baseline. **PASS.**

```
python3 -m pytest -q   (full repo suite)
→ 2532 passed, 25 skipped in 19.36s, exit 0
```

```
python3 scripts/heartbeat_go_no_go.py
→ VERDICT: NO-GO. NOT READY. 2 gate(s) failing, 1 UNKNOWN (event log
  ABSENT — correctly refuses to call it clean).
exit 1
```
Correct current state — expected and NOT "fixed."

```
python3 scripts/check_heartbeat_readiness.py
→ VERDICT: NOT READY. Blockers: insufficient clean shadow window
  (0/3), monthly credit ceiling not enforceable (plan undeclared).
exit 1
```
Correct current state — that red is CORRECT and was left untouched.

```
python3 scripts/diagnostics.py
→ SCORE = 100/100, exit 0
```
```
python3 scripts/board_lint.py
→ OK: 193 ticket(s) checked, 0 violations (1 pre-existing non-fatal WARN
  on DAS-1507, unrelated to this ticket). exit 0
```
```
ruff check scripts tests
→ All checks passed! exit 0
```

**Defects found this run:** none. No auto-approved gate, no auto-answered
interrupt-card, no `heartbeat_enabled` write, no break-glass write from any
tick/wave/drill path — verified structurally (grep + AST walk), not
concluded from a passing test alone. Adversarial pass targeting a third
defect after DAS-1620's two real ones found nothing exploitable.

**Result:** SI-3 and SI-6 both hold. GATE-4 for WS-F is closed (this ticket
+ DAS-1620, `done`). `status: in_review`, routed to QA Lead per
`board/ROUTING.md` (never self-review). No code changed in this ticket —
only this file was edited (zone lock: `tests/` + this ticket; no test
files needed new authorship since DAS-1478's existing suite already covers
the rails exercised).

### 2026-07-24 — QA Lead

Review of QA Engineer's part-2 drill. I am GATE-4 accountable and the last
technical reviewer of WS-F, so I re-derived the load-bearing claims myself
rather than re-running the builder's commands. Read-only git, no worktree;
edited only this file. Separating **what I re-verified** from **what I
accepted** below.

#### RE-VERIFIED INDEPENDENTLY (my own constructions, not the builder's)

**1. SI-3 structural proof — re-derived, and strengthened.**
I did not reuse the builder's grep. Their search was scoped to `scripts/*.py`,
which misses nested packages (`scripts/dgox/`, `scripts/cost/`,
`scripts/a2a_intake/`) and all of `tools/`. I re-ran it repo-wide over every
`*.py`:
- **Importers of `break_glass`** — the builder listed three; there are in fact
  **four**: `loop_controller.py` (`is_active`, read-only), `alerting.py`
  (`is_active`, read-only), `flow_router.py` (a plain `break_glass_active: bool`
  field, no import at all), and — omitted from their enumeration —
  `check_break_glass_review.py` (`import break_glass as bg`). I checked that
  fourth one: its only `write` calls are `sys.stderr.write` (L95/104/106); it
  has no `append_event`, no file open in a write mode. **Read-only. The
  omission does not change the conclusion.**
- **Callers of `append_event`** repo-wide: `break_glass.py`'s own `activate`
  verb, `kill_switch_drill.drill_break_glass()` (scratch `work_dir` only), and
  tests. Confirmed.
- **Writers to the shared store `board/.events.jsonl`** — this is where the
  builder's framing was too narrow. `tools/a2a/endpoint.py`,
  `tools/a2a/publish.py`, `scripts/a2a_intake/intake.py` and
  `scripts/dgox/events.py` all append to the *same file* `break_glass.is_active`
  reads. I checked whether any of them can forge an activation:
  `grep -rn 'break_glass_activation' --include='*.py' .` → **exactly one hit,
  `scripts/break_glass.py:37`**. Every other writer hard-codes its own
  `event_type` (`a2a_call`, `a2a_publish`, `span`, …); caller-controlled data
  lands only in nested keys (`redacted_payload`) or unrelated top-level keys
  (`principal_id`), and `iter_activations` matches on top-level `event_type`
  only. `json.dumps` escapes newlines, so no line-injection either. **Not
  forgeable.**
- **AST walk**, mine, broader than the builder's four-name list — I scanned
  every `Call` node in `scripts/` + `tools/` for `unlink`, `remove`, `rename`,
  `truncate`, `rmtree`, `move`, `write_text`, `write_bytes`, and `open()` with
  any truncating mode. `loop_controller.py` surfaced 3 hits which I ran down
  individually: all three are `datetime.replace(...)` (L267/269/271), **not**
  `Path.replace`. `flow_router.py`: zero. Confirmed no write path from tick or
  router.
- **The clearing direction — the check the builder did not make.** Blocking
  writes is the easy half; the dangerous half is *clearing*. Across every module
  that references the event store, **no code path anywhere truncates, rewrites,
  renames or unlinks `board/.events.jsonl`** — every writer opens mode `"a"`,
  and `scripts/dgox/events.py` has no compact/rotate/prune function. Combined
  with `active_overrides` being a pure function of `(created_at, window)` with
  **no deactivation event type in the alphabet**, `is_active` is **monotone in
  an append-only log**. I proved this behaviourally too: appended a forged
  `break_glass_deactivation`, a `window_minutes: -600` activation, a
  `window_minutes: 0` activation, a `break_glass_review`, and a `run_end` to a
  live override — `is_active` stayed **True** through all five. *An appender
  cannot turn the kill switch off.* That is the invariant this ticket needed
  and it holds by construction, not by test.
- `heartbeat_enabled`: `feature_flags.py` exposes `DEFAULTS`/`load`/`enabled`/
  `main` — no writer. `config/features.yaml` is dirty in the working tree, so I
  read the diff rather than trusting the builder: the only added line is
  `a2a_outbound: false` (DAS-1607); **`heartbeat_enabled: false` unchanged at
  L12.** Confirmed.

**2. Auto-expiry at exactly 60 minutes — re-measured on my own clock.**
Seven boundary instants, my harness, not theirs:
`T0-1s`→False · `T0`→True · `T0+59m59s`→True · **`T0+59m59.999999s`→True** ·
**`T0+60m00s`→False** · `T0+60m1s`→False · `T0+90m`→False.
Half-open window `start <= now < start+60min` confirmed to microsecond
resolution at both edges. No off-by-one. The builder's report matches.

**3. SI-6 genuinely binds — and I checked it is not vacuous.**
Open `run_start` with no `run_end` → `action == "idle"`, reason
`"a wave is already in flight, max 1 (SI-6)"`. The non-vacuity controls the
builder did not run: a **closed** prior wave (`run_start` + matching `run_end`)
→ `"dispatch"`; an **empty** log → `"dispatch"`; two starts with only one
closed → `"idle"`. So the rail discriminates rather than always idling.
Also confirmed the tick is a pure evaluator: event store **byte-identical
(327B → 327B)** across a blocked tick and a resumed tick.

**4. Event-log honesty — the failure mode this run was already bounced for.**
Verified the builder did **not** launder absence into a pass. Their log states
`board/.events.jsonl` does not exist, calls zero-events "absence of evidence,"
names exactly what was scanned (8 synthetic/scratch events), and states the
coverage limit explicitly. The criterion text carries the caveat inline rather
than reading as a clean real-log pass. Re-confirmed **now**: `ls` →
both `board/.events.jsonl` and `board/.metrics-history.jsonl` **still absent**;
`git status --short` shows neither. `heartbeat_go_no_go.py` independently
agrees, returning `[UNKNOWN] ... 0 events scanned is NOT evidence of 0
violations` rather than PASS. **Honest.**

**5. No fork.** `git diff --stat -- scripts/kill_switch_drill.py
scripts/break_glass.py` → **empty**; `git status --porcelain` on both → **0
entries**. No untracked drill script was authored (`grep -iE 'drill|1621'` over
untracked files → 0). The only file this ticket touched is itself. Confirmed
reuse, not fork.

#### DEFECT HUNT — what I tried, and what I found

The builder reported zero defects; two real ones were found in this path earlier
today, so I went looking rather than accepting. Attempts: (a) indirect writers to
break-glass state via nested packages and `tools/` — none; (b) forged activation
via the A2A external-caller path into the shared event store — blocked, event
types are hard-coded; (c) `subprocess`/`os.system` shell-out to
`break_glass.py activate` from a tick path — none; (d) truncate/unlink/rotate of
the event store to *clear* an override — none exists; (e) forged
deactivation/negative-window events — monotonicity holds; (f) `max_concurrent_waves`
poisoning (`0` → falsy → defaults to 1; negative → `len() >= -1` → always idle,
fail-safe); (g) non-vacuity of the SI-6 and SI-3 rails — both discriminate.
All clean. **One real gap found, in (h):**

**FINDING (non-blocking for this ticket, must not be inherited silently) —
`kill_switch_drill.scan_gate_approval_violations` is a DENY-LIST and misses an
agent-signed gate.** The scanner flags an approval only when the actor is in
`AUTO_ACTORS` (`heartbeat`, `scheduler`, `cron`, `bot`, `agent`, …) or an
`approval: auto*` / `auto_approved: true` marker is present. I ran a positive-
control battery against it. Correctly caught: `approval: auto`, `approved_by:
heartbeat`, `auto_approved: true`, `resumed_by: scheduler`. Correctly *not*
caught (false-positive controls): a genuine `approved_by: founder`, a pending
gate. **Silently missed:**

| seeded event | scanner verdict |
|---|---|
| `gate_check` GATE-4 `decision: approved`, `approved_by: qa-lead` | **not flagged** |
| `gate_check` GATE-5 `decision: approved`, `approved_by: claude` | **not flagged** |
| `gate_check` GATE-5 `decision: approved`, `approved_by: subagent` | **not flagged** |
| `approval` `decision: approved`, `approved_by: orchestrator` | **not flagged** |
| `interrupt_answer` `decision: answered`, `approved_by: cto` | **not flagged** |
| `config_write` `field: heartbeat_enabled, value: true` | **not flagged** (no rule for a flag-flip event at all) |

Every DasLab actor except the Founder is an agent, so a *role-key-attributed*
auto-approval reads as a human approval. **Blast radius:**
`heartbeat_go_no_go.probe_event_log_violations` (L400) consumes this exact
scanner. Today that gate is `UNKNOWN` because the log is absent — so the gap is
**dormant and blocks nothing now**. But the moment a real event log accrues
(precisely the go-live path this workstream exists to inform) that gate flips to
a computed `PASS` — DAS-1619's own transcript already shows the shape,
`[PASS] ... 0 violations across 6 event(s) scanned`. An agent-signed GATE-5
would then read as clean.

**Why this is not a bounce:** the scanner is DAS-1478 machinery, pre-existing
and explicitly *reused unmodified* as this ticket required; DAS-1621's own
criteria (SI-3, SI-6, event-log honesty, no fork) all genuinely hold; and no
rail failed. Hardening the scanner is new work outside this ticket's zone
(`tests/` + this file) and outside a reviewer's authority to author here.
**Routed to the orchestrator as new work** (suggested: allow-list of human
actors instead of a deny-list, plus an explicit `heartbeat_enabled`-write rule;
next free id DAS-1637; owner qa-eng, reviewer qa-lead). Recording it here so the
Founder gate does not inherit it silently.

#### ACCEPTED WITHOUT INDEPENDENT RE-DERIVATION
- The builder's scratchpad driver `das1621_drill.py` itself (not in the repo; I
  wrote and ran my own harness instead, so their script is not load-bearing).
- The 8-synthetic-event count in their scan — the number is immaterial given the
  coverage caveat is stated correctly and the underlying store is absent.
- Merged-PR / green-CI, outstanding by orchestrator directive (local-only run).
  No code changed in this ticket, so there is nothing to merge.

#### VERBATIM RE-RUNS (mine, this session)
```
python3 scripts/kill_switch_drill.py --smoke
→ kill-switch-drill: running 1 pass(es) of the 6 safety rails...
  OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
    pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
  kill-switch-drill: OK — every safety rail held on every pass
  (zero gate/approval violations, loop off).            exit 0
```
```
python3 scripts/heartbeat_go_no_go.py
→ VERDICT: NO-GO. 2 gate(s) checked and failing; 1 UNKNOWN
  ([UNKNOWN] zero auto-approved gate/interrupt events — event log ABSENT).
                                                        exit 1   (CORRECT)
```
```
python3 scripts/check_heartbeat_readiness.py
→ VERDICT: NOT READY. Blockers: insufficient clean shadow window (0/3);
  monthly credit ceiling not enforceable (active_plan undeclared).
                                                        exit 1   (CORRECT — red is right)
```
```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py tests/test_heartbeat_go_no_go.py \
  tests/test_check_break_glass_review.py -q
→ 283 passed in 1.59s                                   exit 0
```
Pass predicate (no hardcoded equality): `exit 0 ∧ 0 failed ∧ 0 errors ∧
collected >= 195`. 283 >= 195. **PASS.**
```
python3 -m pytest -q       → 2532 passed, 25 skipped in 19.55s      exit 0
python3 scripts/diagnostics.py → SCORE = 100/100                    exit 0
python3 scripts/board_lint.py  → OK: 193 ticket(s), 0 violations
                                 (1 pre-existing non-fatal WARN, DAS-1507)  exit 0
ruff check scripts tests       → All checks passed!                 exit 0
```
Repo state after review: `board/.events.jsonl` and
`board/.metrics-history.jsonl` **still absent**; `scripts/kill_switch_drill.py`
and `scripts/break_glass.py` **unmodified**; `heartbeat_enabled` **still
false**. No git state mutated.

#### DECISION
SI-3 and SI-6 both hold — verified structurally *and* behaviourally, by my own
constructions. The event-log claim is honestly scoped. No fork. No rail failed.
**GATE-4 for WS-F TEMPO is CLOSED.** This is the last gate any agent can close
in this workstream: WS-F now **rests at its Founder gate**. DAS-1622 (the
`heartbeat_enabled: false → true` flip) is **blocked by design, Founder-only**
(QONUN-5 / ADR-0027 SI-7 / SPEC-010 FR-006 — no agent may make that edit), and
DAS-1623 sits behind it. `status: done`, `verified_by: qa-lead`.
