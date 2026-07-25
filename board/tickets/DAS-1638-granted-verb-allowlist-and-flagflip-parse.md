---
id: DAS-1638
title: Close the grant-verb allow-list gap and make the flag-flip rule fail closed on an unparseable value
status: done
assignee: qa-lead
author: cto
verified_by: qa-lead
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [SC-002]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1637]
created: 2026-07-24
updated: 2026-07-25
---

## Description

**Found by the CTO while reviewing DAS-1637. Two items; the second is the same
defect shape one level up and is PRE-EXISTING since DAS-1478.**

### 1. `_GRANTED` is an allow-list of grant verbs — an unknown verb reads as clean

`scripts/kill_switch_drill.py :: scan_gate_approval_violations` decides a gate was
granted by matching the decision against `_GRANTED`. An unrecognised verb —
`accepted`, `ok`, `signed_off` — is therefore treated as **not granted**, so an
agent-signed approval carrying that verb passes. Compounding it, `event_type` is the
one field never normalised (both the actor and `decision` are), so `GATE_CHECK`,
`gate_decision`, or `aadl_gate` carrying an agent-approved GATE-5 slips as well.

This is exactly the direction bug DAS-1637 just fixed for actors, surviving one field
over. `approval` events are immune; `gate_check` / `interrupt_*` are not — and
`gate_check` IS a real, produced event type today.

**It cannot be fixed by simply inverting `_GRANTED`** — a genuine
`decision: "rejected"` by an agent must NOT flag. The shape needed is a
**"clearly-not-granted" set**, with **unknown verbs treated as granted** (fail closed
toward flagging). Normalise `event_type` the same way actor and decision already are.

### 2. The flag-flip rule is correct but narrow, and fails OPEN on an unparseable value

`_config_write_flips_heartbeat_on()` handles ON / OFF / unrelated-key correctly and
catches every plausible truthy spelling. These slip: `{"key":"heartbeat_enabled"}`
with no value; `value: None`; `value: "enabled"`; dotted
`features.heartbeat_enabled`; a nested `changes` shape; `path` + `content`; and
`event_type` case/spelling variants. There is also a concrete wart:
`ev.get("value", ev.get("new_value"))` falls back only when `value` is **absent**, so
`{"value": None, "new_value": True}` reads as not-a-flip.

Make it **fail closed**: a write keyed on `heartbeat_enabled` whose value cannot be
parsed is a violation, not a pass. Fix the `value: null` / `new_value` fallback.
Re-derive the key and event-type spellings from the producer's schema rather than
guessing.

**Why item 2 was not a bounce on DAS-1637** (do not re-litigate): it is not a
regression — there was no flag-flip rule at all before; `config_write` is **not** in
`dgox.events._VALID_EVENT_TYPES`, so no producer exists yet and any shape is a
forward guess; and decisively, `heartbeat_go_no_go.probe_flag` reads
`config/features.yaml` as its own gating line, so a slipped shape cannot manufacture
a Founder-visible false clean about the flag itself.

**Sequencing note:** item 2's full fix wants `config_write` to be a real event type
with a schema. If it still is not when this ticket is worked, harden what can be
hardened (fail-closed on unparseable, the `value: null` fallback) and record the
schema-dependent parts as explicitly deferred rather than guessing more shapes.

**Test with a seeded battery, not a happy path** — the same technique that found both
of these. Every slipping case above must flag afterwards; `decision: "rejected"` by an
agent must still NOT flag; and every case DAS-1637 made flag must keep flagging.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT write to the real `board/.events.jsonl` —
seeded events go in a scratch store. Do NOT weaken any currently-caught case.

## Acceptance criteria
- [x] Grant detection uses a "clearly-not-granted" set with unknown verbs treated as granted; `decision: "rejected"` by an agent still does NOT flag.
- [x] `event_type` normalised consistently with actor and decision; `GATE_CHECK` / `gate_decision` / `aadl_gate` variants no longer slip.
- [x] The flag-flip rule fails CLOSED on a `heartbeat_enabled`-keyed write whose value cannot be parsed; the `value: null` / `new_value` fallback fixed.
- [x] Every listed slipping case demonstrated flagging, with verbatim before/after output; every DAS-1637 case still flags; `approved_by: founder` and a pending gate still do not.
- [x] `probe_event_log_violations` still returns UNKNOWN on an absent log (absence-is-not-evidence must not regress).
- [x] `kill_switch_drill --smoke` 6 rails green; `diagnostics.py` 100/100; full suite green; `board/.events.jsonl` still absent; no `project:` field (R9).

## Log
### 2026-07-24 — CTO
Found while reviewing DAS-1637's actor allow-list inversion, by probing the shape of
the adjacent checks rather than stopping at the one that was fixed. Item 1 predates
DAS-1637 (DAS-1478 machinery); item 2 is a narrowness in the rule DAS-1637 added.
Recorded by the orchestrator in the same run. DAS-1637 was accepted on its own merits
— neither item is a defect in what that ticket delivered.

### 2026-07-25 — QA Engineer

**Note on baseline:** the repo's `HEAD` commit predates DAS-1637 (its edit to
`scripts/kill_switch_drill.py` is itself an uncommitted working-tree change in
this checkout). The verified "before" state below is therefore the DAS-1637
(pre-DAS-1638) code, reconstructed verbatim from the pre-edit read of the file
at the start of this ticket — not `git show HEAD`.

**Item 1 — grant-verb allow-list → "clearly-not-granted" set, fail-closed.**
Replaced `_GRANTED` (kept only as a deprecated alias) with `_NOT_GRANTED =
{rejected, denied, declined, revoked, withdrawn, pending, deferred, blocked,
waiting, open, unanswered, unresolved, raised}`. The grant check is now
`decided not in _NOT_GRANTED and not _actor_is_human(approver)` — an
unrecognised verb is GRANTED by default. Added `_normalize_event_type()` +
`_EVENT_TYPE_ALIASES` (gate_check/gate-check/gatecheck/gate_decision/
gate-decision/gatedecision/aadl_gate/aadl-gate/aadlgate → `gate_check`, plus
config_write/interrupt_* case variants) and applied it once at the top of
`scan_gate_approval_violations`, so the `config_write` flip-rule comparison
inherits the same normalisation for free.

**Boundary-case reasoning (as the ticket asked):** `decision: ""`, a missing
`decision` key, `decision: None`, and a non-string decision (e.g. `True`) all
collapse via the existing `str(x or "").strip().lower()` normalisation to a
string not in `_NOT_GRANTED` — none of them is an unambiguous rejection/
pending/open signal, so they land on the GRANTED side of the fail-closed
line, same as any other unrecognised verb. This only bites when the actor is
ALSO non-human (the check is an AND); a human-attributed event never flags
regardless of how ambiguous the decision text is. Verified with a seeded case
for each (missing / `""` / `None` / non-string) plus two rejection controls
(`rejected`, `denied`) that must NOT flag.

**Item 2 — flag-flip fails closed.** Added `_parse_flag_bool()` (three-way:
`True`/`False`/`None`-unparseable, replacing the loose `_truthy` boolean-only
check for this rule) and `_resolved_flag_value()` (prefers `value` over
`new_value`, falling back whenever `value` is absent OR explicitly `None` —
fixes the `{"value": None, "new_value": True}` wart, where the old
`ev.get("value", ev.get("new_value"))` only fell back on an absent key).
`_config_write_flips_heartbeat_on` now flags whenever the resolved value
parses to `True` OR `None` (unparseable); only an unambiguous `False` is
safe. Re-checked the sequencing precondition: `config_write` is still NOT in
`dgox.events._VALID_EVENT_TYPES` (`scripts/dgox/events.py` — confirmed no
producer exists). Hardened per the sequencing note: fail-closed-on-
unparseable, the null/new_value fallback, and the nested `changes` shape.
Explicitly DEFERRED (documented in the docstring, not guessed): a dotted
`features.heartbeat_enabled` key spelling, and a `path`+`content` file-write
shape — both need the real producer schema, not another guess.
`event_type` case/spelling variants for `config_write` itself are already
covered for free by item 1's shared `_normalize_event_type`.

**Seeded battery — verbatim before/after (OLD = reconstructed DAS-1637 code,
NEW = this ticket's working tree):**

```
label                                                                   OLD(1637)  NEW(1638)
--------------------------------------------------------------------------------------------
item1: unknown verb 'accepted' by agent                                         0          1
item1: unknown verb 'ok' by agent                                               0          1
item1: unknown verb 'signed_off' by agent                                       0          1
item1: event_type GATE_CHECK (upper)                                            0          1
item1: event_type gate_decision alias                                           0          1
item1: event_type aadl_gate alias                                               0          1
item1: missing decision field, agent actor                                      0          1
item1: decision='' empty string, agent actor                                    0          1
item1: decision=None, agent actor                                               0          1
item1: decision=True (non-string), agent actor                                  0          1
item1 CONTROL: decision='rejected' by agent must NOT flag                       0          0
item1 CONTROL: decision='denied' by agent must NOT flag                         0          0
item2: key only, no value                                                       0          1
item2: value=None, no new_value                                                 0          1
item2: value='enabled' (unparseable string)                                     0          1
item2: changes={'heartbeat_enabled': True}                                      1          1
item2: changes={'heartbeat_enabled': 'enabled'} (unparseable)                   0          1
item2: value=None, new_value=True (the fallback wart)                           0          1
item2: event_type CONFIG_WRITE (upper)                                          0          1
item2 CONTROL: value=False must NOT flag                                        0          0
item2 CONTROL: value='off' must NOT flag                                        0          0
item2 CONTROL: unrelated key must NOT flag                                      0          0
item2 CONTROL: value=None new_value=False must NOT flag                         0          0
DAS-1637: gate_check approved_by qa-lead                                        1          1
DAS-1637: approval approved_by orchestrator                                     1          1
DAS-1637: interrupt_answer answered_by cto                                      1          1
DAS-1637: config_write heartbeat_enabled=True                                   1          1
DAS-1637: config_write heartbeat_enabled=False (not flagged)                    0          0
DAS-1637: approval='auto'                                                       1          1
DAS-1637: approved_by heartbeat                                                 1          1
DAS-1637: auto_approved=True                                                    1          1
DAS-1637: resumed_by scheduler                                                  1          1
DAS-1637 CONTROL: approved_by founder must NOT flag                             0          0
DAS-1637 CONTROL: pending gate must NOT flag                                    0          0

== synthetic clean log (incl. raised/unanswered interrupt-card) ==
OLD(1637) violations: 0
NEW(1638) violations: 0
```

Every listed slipping case flips 0→1; every DAS-1637 control stays 1; every
"must not flag" control (rejected/denied verbs, OFF writes, unrelated key,
founder approval, pending gate) stays 0 on both sides; the synthetic clean
log — including its raised-but-unanswered interrupt-card (`status: "open"`,
now explicitly in `_NOT_GRANTED`) — stays 0 violations both before and after.

Added the same cases (plus a couple more) as real pytest cases in
`tests/test_kill_switch_drill.py` (`TestGrantVerbFailClosed`,
`TestFlagFlipFailClosed`, and one clean-log regression case in
`TestScanGateApprovalViolations`).

**Full verification run:**
- `python3 -m pytest tests/test_kill_switch_drill.py -q` → 62 passed.
- `python3 scripts/kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok
  SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok`, exit 0.
- `python3 scripts/heartbeat_go_no_go.py` → VERDICT: NO-GO, exit 1. Gate
  `zero auto-approved gate/interrupt events in the event log` still reports
  `[UNKNOWN] COULD NOT CHECK — event log ABSENT (board/.events.jsonl)` —
  `probe_event_log_violations` did not regress into a computed verdict on an
  absent log.
- `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY`, exit
  1 (correct red — not "fixed").
- WS-F composite: `python3 -m pytest tests/test_kill_switch_drill.py
  tests/test_heartbeat_go_no_go.py tests/test_check_heartbeat_readiness.py
  tests/test_no_daemon.py -q` → 171 passed.
- Full repo suite: `python3 -m pytest -q` → 2577 passed, 25 skipped.
- `python3 scripts/diagnostics.py` → SCORE = 100/100 (all 6 dimensions,
  including Consistency 15/15 and Testing 25/25).
- `python3 scripts/board_lint.py` → `OK — 198 ticket(s) checked, 0
  violations` (exit 0; one pre-existing unrelated body-status WARN on
  DAS-1507, not from this ticket).
- `ruff check scripts tests` → `All checks passed!`
- Confirmed `board/.events.jsonl` still absent (`test -f` → not found); no
  `project:` field added anywhere (zone lock: only
  `scripts/kill_switch_drill.py`, `tests/test_kill_switch_drill.py`, and this
  ticket file touched).

Every AC verified and ticked. Setting `status: in_review`, `assignee:
qa-lead` per ROUTING.md (author is `cto`; QA Engineer never self-reviews).

### 2026-07-25 — QA Lead (review — ACCEPTED)

Independent review as reviewer (author `cto`; builder `qa-eng`; I am
independent of both). **Nothing below is lifted from the builder's transcript —
every number was re-derived by running the code.** I reconstructed the DAS-1637
baseline from the current source by reverse-patching the four DAS-1638 hunks
(each reverse-patch asserted present, so a drifted reconstruction fails loud) —
not from `git show HEAD`, which predates both tickets. Seeded events lived only
in `/var/folders/.../` + a scratchpad script; `board/.events.jsonl` was never
created and is still ABSENT (re-checked after every probe).

**RE-VERIFIED (I ran it — 62-case battery, OLD-vs-NEW, all matched expectation).**

*Item 1 — grant detection is fail-closed.* Every unknown verb by an agent flags
0→1: `accepted`, `ok`, `signed_off`, `complete`, `TASDIQLANDI`. Every event-type
alias flags 0→1: `GATE_CHECK`, `gate_check ` (trailing space), `gate_decision`,
`aadl_gate`, `Gate-Check`, `APPROVAL`, `Interrupt-Answer`. Every ambiguous/absent
decision by an agent flags 0→1: missing key, `""`, `None`, non-string `True`.
Controls stay 0/0: `rejected`/`denied`/`pending` by an agent, interrupt-card
`open`/`unanswered`.

*Item 2 — the AND-gate is genuinely load-bearing (review focus #2).* A
human-attributed (`founder`) event with a garbage/missing/None/non-string
decision does NOT flag — verified across seven variants including
`operator: founder`, `  FOUNDER `, and a bare `approval` event by founder. There
is no path where the decision check fires independently of the actor check: the
grant branch is `(decided not in _NOT_GRANTED and not _actor_is_human(approver))`
— an AND — and the bare-`approval` branch is also gated on `not _actor_is_human`.

*Item 2 — flag-flip fails closed.* All unparseable/ON shapes flag 0→1: key-only,
`value:None`, `value:"enabled"`, the `{"value":None,"new_value":True}` wart,
`value:2`, `value:[]`, `changes` unparseable, `CONFIG_WRITE`/`config-write`
aliases, `field=`/`setting=` spellings. Controls stay 0: `False`/`"off"`/`0`,
`value:None new_value:False`, `changes:False`, unrelated key (with and without a
truthy value).

*Every DAS-1637 case still flags (review focus #4).* qa-lead/claude/subagent
gate keys, `approval` by orchestrator, `interrupt_answer` by cto, `approval:auto`,
`approved_by:heartbeat`, `auto_approved:true`, `resumed_by:scheduler`,
`interrupt_answered_by:loop_controller`, `config_write heartbeat_enabled=True` —
all 1. Founder-approved / pending-gate / OFF-write controls all 0.

*Normalisation applied once, no downstream gap (review focus #5).*
`_normalize_event_type` is called once at the top of the scan; the two downstream
comparisons (`et in ("approval","gate_check","interrupt_answer","interrupt_card")`
and `et == "config_write"`) both expect the canonical form. An event type not in
the alias map passes through unchanged (`totally_unknown_type`, `span`,
`run_start` → identity; `"  Wave  "` → `wave`; `None`/`0` → `""`) — closes known
aliases without inventing membership.

*UNKNOWN-on-absent must not regress AND must still discriminate (review focus #6).*
Run end-to-end through `heartbeat_go_no_go.probe_event_log_violations`, not
asserted from the code path: absent → UNKNOWN; agent-signed GATE-5 → FAIL;
founder-signed GATE-5 → PASS; the DAS-1638 unknown-verb agent GATE-5
(`GATE_CHECK`/`signed_off`) → FAIL; a seeded `config_write value:"enabled"` →
FAIL. A real third state, not a stuck one.

**ACCEPTED (my adjudication).**

*False-positive risk — assessed on real streams, not abstractly (review focus #1).*
The inversion's new risk is spurious flags on legitimate non-grant verbs the set
omits. I enumerated the actual producer surface instead of reasoning about it:
the scanner only engages its grant logic for `event_type` ∈
{`approval`,`gate_check`,`interrupt_answer`,`interrupt_card`}, and **no code in
the repo emits any of those event types today** — the ten `build_*` functions in
`dgox/events.py` produce routing_decision / agent_invocation / run_start /
run_end / wave / checkpoint / cache_hit / span / ticket_completion / replanned,
none of which touch the grant branch. Confirmed by grep across all non-test,
non-drill `*.py`. My false-positive sweep bears this out: all four real
`dgox.build_*` events → 0 violations; all 16 `_VALID_EVENT_TYPES` fed bare flag
only `approval`+`gate_check` (an approval/gate with no attributed human IS the
auto-approval this guards — correct, not spurious); all 10 real
`board/interrupts/*.json` card bodies fed through the scanner → 0 violations
(they carry no `event_type`, so `et==""` and the branch is never entered — and
cards are scanned by `probe_interrupt_cards`, a separate line, not by this one).
So there is **no live false-positive surface**: `_NOT_GRANTED` already covers the
interrupt-card `open`/`unanswered`/`raised`/`pending` and gate rejection
vocabulary that exists. Completeness beyond that is a forward concern that must
be reconciled WHEN the `gate_check`/`approval` producer is actually built (a
future ticket owning that schema) — same posture the builder and CTO recorded.
**Not a bounce: crying-wolf requires a wolf, and no producer feeds these types
yet.**

*Deferral is honest (review focus #7).* Re-checked: `config_write` is NOT in
`dgox.events._VALID_EVENT_TYPES` (verified against the frozenset) — no sanctioned
producer, so the dotted-key and `path`+`content` shapes are a forward guess,
correctly DEFERRED in the docstring rather than silently dropped. Hardened what
exists: fail-closed-on-unparseable, the `value:null`/`new_value` fallback, the
`changes` shape, and event-type case/spelling variants (via the shared
normaliser).

**Command battery — re-run by me, verbatim.**
- `python3 scripts/kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok SI-4=ok
  SI-5=ok SI-6=ok SI-7=ok SI-2=ok`, `OK — every safety rail held`, **exit 0**.
- `python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO`, **exit 1**;
  event-log gate `[UNKNOWN] ... event log ABSENT (board/.events.jsonl)` — no
  regression into a computed verdict on an absent log.
- `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY`,
  **exit 1** — correct red (pre-existing WS-F blockers), not "fixed".
- WS-F composite (`test_kill_switch_drill` + `test_heartbeat_go_no_go` +
  `test_check_heartbeat_readiness` + `test_no_daemon`) → **171 passed**, 0 failed.
- Full repo suite `python3 -m pytest -q` → **2577 passed, 25 skipped**, 0 failed
  (judged on zero failures + coverage grown: 62 kill-switch cases vs the
  DAS-1637 baseline of 38; new `TestGrantVerbFailClosed`, `TestFlagFlipFailClosed`,
  and a clean-log regression case — not on a hardcoded count).
- `python3 scripts/diagnostics.py` → `SCORE = 100/100` (Consistency 15/15,
  Testing 25/25).
- `python3 scripts/board_lint.py` → `OK — 198 ticket(s) checked, 0 violations`
  (one pre-existing, unrelated body-status WARN on DAS-1507).
- `ruff check scripts tests` → `All checks passed!`.
- `board/.events.jsonl` → ABSENT (re-checked after every probe); no `project:`
  field on this ticket; zone lock respected (only `scripts/kill_switch_drill.py`,
  `tests/test_kill_switch_drill.py`, and this ticket file touched).

**Verdict: ACCEPTED.** All six acceptance criteria hold against re-derived
evidence. Outstanding by orchestrator directive (NOT a bounce reason): the
merged-PR / green-CI leg of the DoD — this run is LOCAL-ONLY, so
`scripts/kill_switch_drill.py` + `tests/test_kill_switch_drill.py` remain
uncommitted; the branch/commit/PR/merge step is the orchestrator's to carry in a
git-mutation-permitted session.
