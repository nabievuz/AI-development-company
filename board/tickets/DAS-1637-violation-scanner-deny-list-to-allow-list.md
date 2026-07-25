---
id: DAS-1637
title: Replace the gate-approval violation deny-list with a human-actor allow-list
status: done
assignee: cto
author: qa-lead
verified_by: cto
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [SC-002]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1621]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Found by QA Lead in the DAS-1621 review — the last technical review before WS-F
rests at its Founder gate. Not a bounce (the scanner is DAS-1478 machinery, reused
unmodified exactly as that ticket required), but load-bearing at go-live.**

`scripts/kill_switch_drill.py :: scan_gate_approval_violations` is a **deny-list**.
It flags approvals attributed to a known-automated actor — `AUTO_ACTORS` =
heartbeat / scheduler / cron / bot / agent / … — and passes everything else as
human.

**In DasLab, every actor except the Founder is an agent.** So an approval signed by
an agent *role key* reads as human and is silently missed. Confirmed by the
reviewer's positive-control battery against the real scanner:

| seeded event | verdict |
|---|---|
| `gate_check` GATE-5 `approved`, `approved_by: qa-lead` / `claude` / `subagent` | **not flagged** |
| `approval` `approved`, `approved_by: orchestrator` | **not flagged** |
| `interrupt_answer` `answered`, `approved_by: cto` | **not flagged** |
| `config_write` setting `heartbeat_enabled: true` | **not flagged** (no flag-flip rule exists at all) |

The controls behaved correctly — it does catch `approval: auto`,
`approved_by: heartbeat`, `auto_approved: true`, `resumed_by: scheduler`, and it
correctly does not flag `approved_by: founder` or a pending gate. The logic works;
the **direction** is wrong.

**Blast radius, and why the timing matters.**
`heartbeat_go_no_go.probe_event_log_violations` consumes this scanner. Today it
returns `UNKNOWN` only because `board/.events.jsonl` does not exist. The moment a
real event log accrues, it flips to a *computed* `PASS` — DAS-1619's own transcript
already shows `[PASS] 0 violations across 6 event(s) scanned`. **An agent-signed
GATE-5 approval would then read clean in the artifact the Founder consults before an
irreversible autonomy flip.** The defect is inert precisely as long as the system has
no history, and arms itself exactly when it starts having one.

**The fix — invert the direction.**
- Replace the deny-list with a **human-actor allow-list**: an approval is valid only
  if attributed to an actor on the allow-list (today: the Founder). Anything else —
  including an unrecognised or absent actor — is a violation. Unknown must fail
  closed, which is the whole point of the inversion.
- Add an explicit rule for a `heartbeat_enabled` write. There is currently **no**
  flag-flip rule; a `config_write` turning the flag on is not flagged by anything.
- Keep every currently-caught case caught — the existing controls must still pass.

**Test it with the reviewer's battery, not a happy path.** Every row in the table
above must flag after the fix, and every listed control must still behave. A test
that only shows `approved_by: heartbeat` is caught would have passed against the
buggy code.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT weaken any currently-caught case to make
the inversion simpler. Do NOT write to the real `board/.events.jsonl` — it must stay
absent; seeded events belong in a scratch store.

## Acceptance criteria
- [x] `scan_gate_approval_violations` uses a human-actor allow-list; an unrecognised or absent actor is a violation (fails closed).
- [x] An explicit rule flags a `heartbeat_enabled` write in the event stream.
- [x] Every row of the reviewer's positive-control table flags after the fix — demonstrated with verbatim output.
- [x] Every previously-caught case still caught, and `approved_by: founder` / a pending gate still correctly not flagged.
- [x] `heartbeat_go_no_go.probe_event_log_violations` still returns UNKNOWN on an absent log (the absence-is-not-evidence property must not regress).
- [x] `kill_switch_drill --smoke` 6 rails green; `diagnostics.py` 100/100; full suite green; `board/.events.jsonl` still absent; no `project:` field (R9).

## Log
### 2026-07-24 — QA Lead
Found during the DAS-1621 review by seeding a positive-control battery against the
real scanner rather than accepting its clean result. Recorded by the orchestrator in
the same run. Explicitly NOT bounced onto DAS-1621: that ticket required reusing
DAS-1478's drill machinery unmodified, every one of its criteria genuinely holds, and
no rail failed. Hardening the scanner was outside that ticket's zone (`tests/` + the
ticket file) and outside a reviewer's authority to author. Filed so the Founder gate
does not inherit the gap silently.

### 2026-07-24 — QA Engineer

**Change (`scripts/kill_switch_drill.py`).** Inverted `scan_gate_approval_violations`
from deny-list to allow-list:
- New `ALLOWED_HUMAN_ACTORS = frozenset({"founder"})` + `_actor_is_human()` (fail-closed:
  unrecognised/blank/absent ⇒ NOT human). `_actor_is_auto()` kept only as a `not
  _actor_is_human()` back-compat shim so no other caller in the repo breaks; the old
  `AUTO_ACTORS` deny-list is retained *unused*, marked DEPRECATED, purely so an
  external importer sees a pointer to the replacement — the scanner no longer
  consults it anywhere.
- All three deny-list call sites (`gate_check`/`interrupt_answer` GRANTED-decision
  check, the bare `approval` event check, the `interrupt_answered_by`/`resumed_by`
  check) now gate on `not _actor_is_human(actor)` instead of `_actor_is_auto(actor)`.
  There is no third "on neither list → pass" branch — every actor is either on the
  allow-list or is a violation.
- New `_config_write_flips_heartbeat_on()` + rule: an `event_type == "config_write"`
  event whose `key`/`field`/`setting` (or a `changes` dict key) is `heartbeat_enabled`
  with a truthy `value`/`new_value` is now a violation, unconditionally — this scanner
  only ever sees a log line, not who ran the Founder-only flip procedure, so no actor
  gets a pass on the flag-flip rule itself. Flipping the flag OFF, or writing an
  unrelated config key, is correctly NOT flagged (tested).

**Where the allow-list lives, and why (per the ticket's ask to justify this).** Chose
a code constant (`ALLOWED_HUMAN_ACTORS` in `scripts/kill_switch_drill.py`) over a
governed config file. Two reasons, one structural and one on the merits:
(1) structural — this ticket's zone lock is `scripts/` + `tests/`; `config/` is
out of scope for a QA-Eng ticket, so a config-file allow-list wasn't available here
regardless of preference. (2) on the merits — widening who may sign a gate is exactly
the kind of change that should cost a PR + CI review, not a lower-ceremony YAML edit;
a hard-coded *single* string would indeed get worked around by the first second human
(exactly the risk flagged in the ticket), but a `frozenset` of arbitrarily many
allow-listed actors, reviewed in code, avoids that failure mode without moving the
governance boundary into a file that a looser process could touch. Documented in a
docstring comment at the constant: if DasLab later needs the list rotated without a
code deploy (e.g. multiple human operators), promote it to `config/rbac.yaml` (which
already models actor/role policy) behind its own ADR — flagged as a deliberate
non-decision here, not a silent default.

**Tests (`tests/test_kill_switch_drill.py`).** Added `TestAllowListInversion` —
the reviewer's full positive-control battery plus the regression/negative controls,
run live against the real scanner (not asserted from memory):

```
FLAGGED      | gate_check GATE-5 approved_by=qa-lead
FLAGGED      | gate_check GATE-5 approved_by=claude
FLAGGED      | gate_check GATE-5 approved_by=subagent
FLAGGED      | approval approved_by=orchestrator
FLAGGED      | interrupt_answer answered approved_by=cto
FLAGGED      | config_write heartbeat_enabled=true
FLAGGED      | approval: auto                              (regression control, still caught)
FLAGGED      | approved_by=heartbeat                        (regression control, still caught)
FLAGGED      | auto_approved: true                          (regression control, still caught)
FLAGGED      | resumed_by=scheduler                         (regression control, still caught)
not flagged  | approved_by=founder (should NOT flag)
not flagged  | pending gate (should NOT flag)
```
Also added: `config_write heartbeat_enabled=false` → not flagged (only ON is
dangerous); `config_write` on an unrelated key → not flagged.

**UNKNOWN-on-absent-log property (must not regress).** Ran
`heartbeat_go_no_go.probe_event_log_violations()` directly against a path that does
not exist:
```
state: UNKNOWN | detail: COULD NOT CHECK — event log ABSENT (.../definitely-absent-events.jsonl);
0 events scanned is NOT evidence of 0 violations
```
Confirmed `chk.state == UNKNOWN`. This path is untouched by the scanner-logic change
(it short-circuits on `events_path.is_file()` before ever calling
`scan_gate_approval_violations`), and `tests/test_heartbeat_go_no_go.py::
test_absent_event_log_is_unknown_not_pass` already covers it and still passes.

**Full verification (observed, not claimed):**
- `python3 -m pytest tests/test_kill_switch_drill.py -q` → `38 passed`
- `python3 -m pytest tests/test_heartbeat_go_no_go.py -q` → `52 passed`
- WS-F composite (`test_kill_switch_drill.py` + `test_heartbeat_go_no_go.py` +
  `test_check_heartbeat_readiness.py` + `test_no_daemon.py`) → `147 passed`
- Full repo suite `python3 -m pytest -q` → `2546 passed, 25 skipped` (>= prior
  baseline; zero failures)
- `python3 scripts/kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok SI-4=ok
  SI-5=ok SI-6=ok SI-7=ok SI-2=ok` — `OK — every safety rail held`, exit 0
- `python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO`, exit 1 (expected —
  clean-shadow-window and monthly-credit-ceiling gates are still unmet; event-log
  gate correctly shows `[UNKNOWN] ... event log ABSENT (board/.events.jsonl)`)
- `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY`, exit 1
  (expected — same underlying blockers; explicitly NOT "fixed", per instruction)
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`
- `python3 scripts/board_lint.py` → `OK — 194 ticket(s) checked, 0 violations`
  (one pre-existing, unrelated WARN on DAS-1507 body prose)
- `ruff check scripts tests` → `All checks passed!`
- `ls board/.events.jsonl board/.metrics-history.jsonl` → both `No such file or
  directory` (still absent, confirmed post-run)
- `git diff --stat config/loop.yaml config/budgets.yaml config/features.yaml` →
  only `config/features.yaml | 1 +` — that one line is **pre-existing** from an
  unrelated A2A workstream already modified in this checkout before this ticket
  was dispatched (visible in the session's initial `git status`); this ticket
  touched no file under `config/` (zone lock: `scripts/` + `tests/` + this ticket
  file only). `config/loop.yaml` and `config/budgets.yaml` diff empty.
- Changed files, confirmed via `git diff --stat`: `scripts/kill_switch_drill.py`
  (+108/-17 across the invert), `tests/test_kill_switch_drill.py` (+88, new
  `TestAllowListInversion` class), this ticket file.

**Process note — no branch/PR.** The dispatch's HARD CONSTRAINTS for this run are
LOCAL-ONLY and explicitly forbid any git state mutation (no `add`/`commit`/etc.) or
remote push/PR. That is narrower than `engineering/AGENTS.md` §2's normal
one-issue-one-branch-one-PR rule and `board/README.md`'s `in_review` requires a
pushed branch/PR. Work is complete and fully verified as uncommitted local edits;
routing to QA Lead as `in_review` per role overlay ("never self-review"), but the
actual branch/commit/PR step needs to happen in a session permitted to mutate git —
flagging this explicitly rather than silently treating "verified locally" as
equivalent to the board's normal `in_review` bar.

All acceptance criteria checked below reflect what was directly observed above, not
assumed.

### 2026-07-24 — Orchestrator (orchestrator-recorded)
Routing correction at wave collect. This ticket was authored BY qa-lead (who found the
defect while reviewing DAS-1621) and qa-eng then handed it back to qa-lead on setting
`in_review` — making assignee == author, which `board_lint` R-no-self-review fails
fail-closed and which dropped `diagnostics.py` to 85/100 on the Consistency dimension.
Reassigned to **cto**, qa-lead's reviewer per `board/ROUTING.md` (the standard
"manager is the author -> climb one level" resolution). No work was re-done; only the
reviewer assignment changed.

Outstanding for the reviewer: the merged-PR / green-CI leg of the DoD. This entire run
was LOCAL-ONLY by orchestrator directive, so `scripts/kill_switch_drill.py` and
`tests/test_kill_switch_drill.py` are uncommitted. That is a real gap against
`board/README.md`'s `in_review` bar, correctly flagged by the builder rather than
silently treated as satisfied, and it is the orchestrator's step to carry — not a
bounce reason.

### 2026-07-24 — CTO (review — ACCEPTED)

Independent review as qa-lead's reviewer (author qa-lead found the defect, qa-eng
built the fix; I am independent of both). **Nothing below is taken from the builder's
transcript — every claim was re-derived by running the code.** Two scratch probes
(seeded events only; the real `board/.events.jsonl` was never created and is still
absent) + the full command battery.

**RE-VERIFIED (I ran it myself).**

*A. Fail-closed is real; no surviving third actor branch.* 86 asserted seeded cases,
`86 passed / 0 failed`. All three call sites (L205 GRANTED-decision, L207 bare
`approval`, L212 `interrupt_answered_by`/`resumed_by`) gate on `not
_actor_is_human(...)`; there is no "on neither list ⇒ pass" path. Every odd-typed
actor fails closed and is FLAGGED: `None`, `0`, `1`, `42`, `{}`, `{"name":
"founder"}`, `["founder"]`, `("founder",)`, `True`, `False`, `b"founder"`, `3.14`,
key absent, `"   "`. **`{"name": "founder"}` and `["founder"]` are correctly
violations** — `str(value or "").strip().lower()` renders them `"{'name':
'founder'}"` / `"['founder']"`, which are not on the allow-list. That is the right
answer: a structured value the scanner does not understand must not be read as a
human. Near-miss spellings all flag (`founder-bot`, `co-founder`, `founders`,
`founder2`, `the founder`, `found er`, and a Cyrillic-о homoglyph `fоunder`).
Case/whitespace variants of the real actor (`Founder`, `FOUNDER`, `  founder  `,
`\tfounder\n`) correctly do NOT flag. Both actor fields are covered: `operator=`
behaves identically to `approved_by=` (fallback verified in both directions). Every
member of `_GRANTED` (`approved`/`signed`/`passed`/`granted`/`answered`/`resumed`),
in both the `decision` and the `status` field, flags for an agent actor.

*B. The deprecated shim is genuinely inert — mutation-proved, not read.*
`AUTO_ACTORS` has **0** references after its own definition (source-sliced, not
eyeballed). Mutation test: with `AUTO_ACTORS` set to `frozenset()`, and again
**poisoned** to `frozenset({"founder","qa-lead","heartbeat","cron","scheduler",""})`,
the scanner's verdicts over a 6-case battery were byte-identical to baseline
(`[1,1,0,1,1,1]` in all three runs). A consulted deny-list could not survive that.
Repo-wide grep (`--include='*.py' '*.md' '*.yml' '*.yaml'`, whole tree, not just
`scripts/*.py`): the **only** definition and the **only** call site of
`_actor_is_auto` are inside `kill_switch_drill.py` itself; no other module, test, or
tool imports `AUTO_ACTORS` or `_actor_is_auto`. So redefining `_actor_is_auto` as
`not _actor_is_human()` breaks no caller. Behavioural check anyway: the shim is
equivalent to `not _actor_is_human` on every probe value, and **every** legacy
deny-list member still classifies as auto — the inversion is a strict superset, not
a trade.

*C. Positive-control battery, verbatim (my seeding, my scratch store).*
```
FLAGGED     | n=1 | gate_check GATE-5 approved approved_by=qa-lead
FLAGGED     | n=1 | gate_check GATE-5 approved approved_by=claude
FLAGGED     | n=1 | gate_check GATE-5 approved approved_by=subagent
FLAGGED     | n=1 | approval approved approved_by=orchestrator
FLAGGED     | n=1 | interrupt_answer answered approved_by=cto
FLAGGED     | n=1 | config_write heartbeat_enabled=true
not flagged | n=0 | gate_check GATE-5 approved approved_by=founder
not flagged | n=0 | gate_check GATE-5 PENDING approved_by=''
not flagged | n=0 | canonical clean synthetic log (_synthetic_event_log)
FLAGGED     | n=1 | approval: auto (approved_by=founder)      [regression control]
FLAGGED     | n=1 | approved_by=heartbeat                     [regression control]
FLAGGED     | n=1 | auto_approved: true                       [regression control]
FLAGGED     | n=1 | resumed_by=scheduler                      [regression control]
FLAGGED     | n=1 | interrupt_answered_by=loop_controller     [regression control]
FLAGGED     | n=1 | ... all 14 legacy AUTO_ACTORS members, individually
```

*D. `heartbeat_go_no_go.probe_event_log_violations` — property intact AND still
binding.* Run directly against the consumer, not asserted from the code path:
```
[absent log]  state=UNKNOWN | COULD NOT CHECK — event log ABSENT (...definitely-absent-events.jsonl);
                              0 events scanned is NOT evidence of 0 violations
[empty log]   state=UNKNOWN | COULD NOT CHECK — event log present but EMPTY (...)
[real log]    state=UNKNOWN | COULD NOT CHECK — event log ABSENT (board/.events.jsonl)
```
A stricter scanner did not turn "no log" into a computed verdict in **either**
direction. I also checked the non-vacuous direction, which is the half that would
make UNKNOWN meaningless if it were broken: on a **populated scratch** log the probe
returns `FAIL | 1 auto-approved gate/approval event(s) across 2 event(s)` for an
agent-signed GATE-5, `PASS | 0 violations across 2 event(s) scanned` for a
founder-signed one, and `FAIL` for a seeded `config_write` flip. The gate discriminates;
UNKNOWN is a real third state, not a stuck one. `board/.events.jsonl` re-checked after
every probe: **still absent**.

**ADJUDICATED (my call, recorded so it is not re-litigated).**

*E. Where the allow-list lives — the builder's choice is UPHELD, on the merits, not
on the zone lock.* `config/rbac.yaml` models *agent role → permission*; every
principal in it is an agent. `ALLOWED_HUMAN_ACTORS` answers a categorically different
question — *which principal is a human at all*. Merging the two would put a
human-principal registry inside the agent-permission file, where an ordinary "grant
this role a tool" edit sits one line away from, and reads confusingly like, granting
that role humanity. That is a bad adjacency for the single most security-critical
predicate in SI-7. The ceremony argument is also correct and I endorse it: widening
who may sign a Founder gate should cost a PR + CI + CODEOWNERS review, not a
lower-ceremony YAML edit. The zone-lock argument (b) is true but is the *weaker* leg;
I am accepting on the merits so the decision does not evaporate the moment a ticket
has `config/` in zone. **Binding:** `ALLOWED_HUMAN_ACTORS` is the SSOT for human
principals in the SI-7 scanner; adding an entry requires security-lead review;
promoting it to a governed config file requires its own ADR. The builder's documented
promotion-behind-an-ADR non-decision is hereby ratified as a decision: **not
promoting, today.** No ADR is needed to keep the status quo; one is required to change
it. (Within CTO charter: architecture decisions + ADR approval.)

*F. The flag-flip rule's scope — a definite verdict.* It is **correct but narrow, and
it fails OPEN on a value it cannot parse.** Confirmed working, both directions:
`key`/`field`/`setting`/`new_value` spellings, a `changes` dict, and `value` given as
`True` / `"true"` / `"True"` / `1` / `"1"` / `"yes"` / `"on"` / `"TRUE "` all FLAG;
`heartbeat_enabled` set to `False` / `"false"` / `0`, and any unrelated key
(`some_other_flag`, `a2a_outbound_enabled`), correctly do NOT flag. So: turning the
flag OFF is not flagged, an unrelated key is not flagged, and truthiness is handled
for every spelling a YAML/JSON writer would plausibly emit for "on". **But a flip CAN
be expressed in a form that slips past.** Verbatim, from my probe:
```
not flagged | config_write {'key': 'heartbeat_enabled'}                       # key named, no value
not flagged | config_write {'key': 'heartbeat_enabled', 'value': None}
not flagged | config_write {'key': 'heartbeat_enabled', 'value': 'enabled'}
not flagged | config_write {'key': 'heartbeat_enabled', 'old_value': False, 'new_value': True, 'value': None}
not flagged | config_write {'key': 'features.heartbeat_enabled', 'value': True}
not flagged | config_write {'changes': {'features': {'heartbeat_enabled': True}}}
not flagged | config_write {'path': 'config/features.yaml', 'content': 'heartbeat_enabled: true'}
not flagged | event_type='Config_Write' | 'config_change' | 'feature_flag_write'
```
Note the fourth line specifically: `ev.get("value", ev.get("new_value"))` falls back to
`new_value` only when `value` is **absent**, not when it is present-and-null — so an
`old_value`/`new_value` diff shape that also carries an explicit `"value": null` reads
as not-a-flip. That is a small real wart, not a theoretical one.

**Why that is a recorded residual and not a bounce.** (1) It is not a regression — before
this ticket there was **no** flag-flip rule at all; every shape above was equally
unflagged, plus the ones that now flag. (2) `config_write` is **not** in
`dgox.events._VALID_EVENT_TYPES` (verified) — the sanctioned writer would *reject* such
an event, so no producer exists and every shape here is a forward guess. Pinning an exact
shape now would invent a contract the eventual producer ticket should own. (3) Decisively:
the Founder-visible claim about the flag does **not** rest on this rule.
`heartbeat_go_no_go.probe_flag` reads `config/features.yaml` through
`feature_flags.enabled()` as its own gating line and FAILs if the flag is already true
(observed this run: `[PASS] heartbeat_enabled is still OFF — false (shadow)`). The
event-log rule is a secondary tripwire, so a slipped shape cannot manufacture a
"flag is off" false clean in the artifact.

*G. One residual I am recording that nobody asked about — the same defect shape, one
level up.* `_GRANTED` is itself an **allow-list of grant verbs**, which means an
*unrecognised* verb reads as "not granted" ⇒ pass. Verbatim: `gate_check
decision='accepted' | 'ok' | 'signed_off' | 'complete' approved_by=qa-lead` → **not
flagged**. Likewise `event_type` is the one field the scanner does *not* normalise
(actor and `decision` are both `.strip().lower()`-ed), so `event_type='GATE_CHECK'` /
`'Gate_Check'` / `'gate_check '` / `'gate_decision'` / `'aadl_gate'` carrying an
agent-approved GATE-5 → **not flagged**. This is DAS-1478 shape, byte-identical before
and after this ticket (`approval` events are immune — L207 flags any non-human approver
regardless of verb), and it is outside this ticket's stated criteria. But the inversion
is precisely what makes agent-signed events matter, so the *severity* of it rose today
even though the *behaviour* did not. It cannot be fixed by inverting `_GRANTED` — a
`decision: "rejected"` by `qa-lead` must NOT flag — it needs a "clearly-not-granted"
set (pending/rejected/failed/open/blocked) with unknown verbs treated as granted, which
is a design call with a false-positive cost. **Routed as a follow-up, not a bounce.**

**Command battery — re-run by me, verbatim.**
- `python3 scripts/kill_switch_drill.py --smoke` →
  `pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok` /
  `kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval
  violations, loop off).` — **exit 0**
- `python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO` — **exit 1**. Gating lines:
  `[PASS] heartbeat_enabled is still OFF`, `[FAIL] clean shadow window >= 3 days`
  (0/3, evidence file ABSENT), `[FAIL] monthly credit ceiling enforceable`
  (`active_plan=undeclared`), `[PASS] kill-switch drill (6 rails)`, `[PASS] loop stays
  OFF`, `[PASS] never-auto-approve 0 violations across 196 ticket(s)`, `[UNKNOWN] event
  log ABSENT`, `[PASS] interrupt-cards`, `[PASS] no daemon`. The two FAILs and the one
  UNKNOWN are the pre-existing WS-F blockers, unrelated to this change.
- `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY` — **exit 1**.
  That red is **CORRECT** and must stay red: 0/3 clean shadow days + an undeclared
  monthly credit plan. Nothing in this ticket should have moved it, and nothing did.
- WS-F composite (`test_kill_switch_drill` + `test_heartbeat_go_no_go` +
  `test_check_heartbeat_readiness` + `test_no_daemon`) → **147 passed**, 0 failed.
- Full repo suite `python3 -m pytest -q` → **2546 passed, 25 skipped**, 0 failed
  (judged on zero failures + no lost coverage, not on a hardcoded count).
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`, exit 0 (the 85/100 Consistency
  drop from the self-review routing is cleared).
- `python3 scripts/board_lint.py` → `OK — 194 ticket(s) checked, 0 violations`
  (one pre-existing non-fatal WARN on DAS-1507 prose, unrelated).
- `ruff check scripts tests` → `All checks passed!`
- `ls board/.events.jsonl` → `No such file or directory`, re-checked after every probe.
  Seeded events lived only in `/var/folders/.../das1637-cto-*` scratch paths.

**On the missing branch/PR leg.** Not a bounce, per the orchestrator directive and
because it is not the builder's to fix under a no-git-mutation dispatch. Recording it
plainly rather than letting `done` imply it: `scripts/kill_switch_drill.py` and
`tests/test_kill_switch_drill.py` are **uncommitted local edits**. `done` here means
*the engineering judgment is closed and the work is verified*; the merged-PR/green-CI
half of `board/README.md`'s DoD is carried by the orchestrator in a git-permitted
session. If that commit never happens, this fix does not exist — the ticket being
`done` does not change that.

**Verdict: ACCEPT.** The inversion is real, fail-closed, mutation-proved inert on its
shim, non-regressive on every previously-caught case, and the absence-is-not-evidence
property survived. Two residuals recorded (F, G) and routed as one follow-up ticket for
when `config_write` becomes a real event type: (i) make the flag-flip rule fail CLOSED
on a `heartbeat_enabled`-keyed write whose value it cannot parse, fix the
`value: null` / `new_value` fallback, and re-derive key/event-type spellings from the
producer's schema; (ii) normalise `event_type` and decide the grant-verb policy so an
unknown verb cannot read as "not granted".
