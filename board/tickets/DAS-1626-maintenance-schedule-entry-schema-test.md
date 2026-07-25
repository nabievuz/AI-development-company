---
id: DAS-1626
title: Add a schema test over every maintenance schedule entry so a renamed key or dead path fails loudly
status: done
assignee: qa-lead
verified_by: qa-lead
author: backend-em
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [governance]
zone: tests
depends_on: [DAS-1624]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Raised by Backend EM during the DAS-1624 review. Pre-existing house-wide gap —
NOT introduced by DAS-1624**, which is why it is its own ticket rather than a
bounce.

`scripts/stage_gate.py`'s `maintenance_schedule()` now declares **10**
`recurring_runs` entries (one per workstream health check). No test asserts the
key set of those entries. Verified during the review: renaming `config` →
`configs` on **any** of the 10 entries still passes the full suite (37 passed).
The same holds for a `command` path that no longer exists on disk — a health
check silently stops being runnable and nothing goes red.

This is the classic dead-config failure: the scheduler declares work that cannot
execute, and the only symptom is the absence of a signal.

**The fix — one schema test over ALL entries, not a per-entry assertion.** A test
that enumerates the 10 entries by hand rots exactly as fast as the thing it
guards; it must iterate whatever `maintenance_schedule()` returns so entry 11
is covered on the day it is added:
- every entry carries the required key set (`name`, `kind`, `command`, `cadence`,
  `config`, `safety`);
- `command[1]` resolves to a file that exists on disk;
- `config` resolves to a file that exists on disk;
- `kind` is unique across all entries (the review confirmed this holds today —
  lock it in).

Prove the test earns its keep: mutate a key name and a command path on a scratch
copy, confirm the test goes red for each, and record that in the log. A schema
test that cannot fail is the same bug one level up.

## Acceptance criteria
- [x] A single schema test iterates every entry `maintenance_schedule()` returns — no hand-enumerated list of the 10 current entries.
- [x] It asserts the required key set (see Log: `config` enforced as present-must-resolve rather than universally-required — 2/10 entries genuinely lack it today, reported as a routing item, not papered over), that `command[1]` (where applicable) and `config` (where present) resolve on disk, and that `kind` is unique.
- [x] Demonstrated red on a renamed key AND on a non-existent command path (scratch copies only; real `scripts/stage_gate.py` never edited — see Log for the pre-existing/unrelated diff explanation).
- [x] Full suite still green (2471 passed, 25 skipped); `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9, confirmed absent from frontmatter).

## Log
### 2026-07-24 — Backend EM
Raised as R1 in the DAS-1624 review report; recorded by the orchestrator in the
same run. Explicitly pre-existing — DAS-1624's own entry was verified conformant
(key set programmatically identical to `ws-e-tenant-health` / `ws-h-control-health`,
`kind` unique, both paths resolving, and a sweep of all 10 entries for unresolvable
paths returned `[]`). This ticket guards the *next* entry, not that one.

### 2026-07-24 — QA Engineer

**Finding first (routing item, not fixed — zone lock forbids editing `scripts/`):**
The ticket's premise that all 10 entries share the identical key set
`{name, kind, command, cadence, config, safety}` does not hold today.
Inspected `maintenance_schedule()` programmatically:

```
health-tick            ['cadence', 'command', 'config', 'kind', 'name', 'safety']
golden-eval            ['cadence', 'command', 'kind', 'name', 'safety']       # no "config"
memory-hygiene         ['cadence', 'command', 'kind', 'name', 'safety']       # no "config"
ws-a-tool-edge-health  ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-b-runner-health     ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-d-lens-health       ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-c-loop-health       ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-e-tenant-health     ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-h-control-health    ['cadence', 'command', 'config', 'kind', 'name', 'safety']
ws-a2a-outbound-health ['cadence', 'command', 'config', 'kind', 'name', 'safety']
```

`golden-eval` (WS6) and `memory-hygiene` (WS4) have no `config` key — no
`docs/06-maintenance/*.md` doc backs either of them (confirmed: `ls
docs/06-maintenance/` lists only the 7 `ws-*-health.md` files, nothing for
golden-eval or memory-hygiene). `memory-hygiene`'s `command` is
`["prune_memory"]` (an ArcRift MCP call), a single element with no `command[1]`
to resolve — it is not a `python3 <script>` invocation at all. Making
`config`/`command[1]`-resolves universally required, as the ticket text
proposes, would make the schema test fail red against the current, unmodified
`scripts/stage_gate.py` — i.e. it would not be a false positive, it would
correctly flag that 2 of 10 recurring runs have no linked runbook doc. Per the
task's own instruction not to quietly patch what the test is meant to catch, I
did not weaken this into silence, but I also did not encode a schema the real
file cannot pass while `scripts/` is under zone lock. **Routing to Backend EM /
QA Lead: either (a) add a `docs/06-maintenance/*.md` for golden-eval and
memory-hygiene and normalize `config` onto all 10 entries, or (b) formally
accept `config` as optional in the schema.** I built the test to reflect what
is actually true and safe today (config optional; when present it must
resolve) so it does not block this ticket, but the gap is real and should be
closed deliberately, not by omission.

**What I built.** Added `test_maintenance_schedule_entries_conform_to_schema`
to `tests/test_stage_gate.py` (existing file — natural home, sits directly
after the pre-existing `test_maintenance_schedule_ws4_heartbeat_and_ws6_evals`).
It iterates `sg.maintenance_schedule()["recurring_runs"]` directly — no
hand-enumerated list of the 10 current entries — and asserts, per entry:
- required base keys `{name, kind, command, cadence, safety}` present;
- no keys outside `{name, kind, command, cadence, safety, config}` — this is
  what actually catches a rename generically: `config` -> `configs` leaves
  `config` merely absent (fine, since it's optional) but leaves `configs`
  behind as an unrecognized stray key, which fails;
- if `config` is present, it resolves to a file on disk;
- if `command[0] == "python3"`, `command[1]` resolves to a file on disk
  (covers 9/10 entries; `memory-hygiene` is exempt, not a script invocation);
- `kind` is unique across all entries (checked via `len(kinds) ==
  len(set(kinds))`).

**Proved it earns its keep — red demonstrated on scratch copies only, real
file never edited.** Copied `scripts/stage_gate.py` to
`/private/tmp/claude-501/-Users-owner-DasLab/4454827f-8a8c-427a-95b0-1b6d6ca78d32/scratchpad/das1626/`
as `stage_gate_renamed.py` and `stage_gate_deadpath.py`, mutated each with a
Python script (not by hand-editing in an editor), loaded each via
`importlib.util.spec_from_file_location` and ran the same assertions inline.
Verbatim output:

```
[renamed-key (config->configs on ws-a-tool-edge-health)] RED (expected) -> AssertionError: ws-a-tool-edge-health: unrecognized key(s) ['configs'] (typo or rename?)
[dead-command-path (ws-b-runner-health)] RED (expected) -> AssertionError: ws-b-runner-health: command[1] 'scripts/ws_b_health_check_DOES_NOT_EXIST.py' does not resolve to a file on disk
```

(First attempt at the rename mutation surfaced its own lesson: making `config`
purely optional with no extra-key check meant the rename silently passed —
`PASSED (unexpected)` — because the entry simply lost an optional key. Fixed by
adding the "no unrecognized keys" assertion above, which does catch it. Kept
that iteration in case it's useful to a reviewer trying to understand why the
extra-key check exists.)

**Verification, verbatim:**

`python3 -m pytest tests/test_stage_gate.py -k schema -q`
```
collected 25 items / 23 deselected / 2 selected
tests/test_stage_gate.py ..                                              [100%]
2 passed, 23 deselected in 0.08s
```

`python3 -m pytest tests/test_stage_gate.py -q`
```
collected 25 items
tests/test_stage_gate.py .........................                       [100%]
25 passed in 0.08s
```

`python3 -m pytest -q` (full suite)
```
2471 passed, 25 skipped in 18.38s
```
(Observed unrelated `s` skips under `tests/test_ws_h_control_plane.py` /
`tests/test_ws_a_browser_tool_egress.py` / `tests/test_ws_b_negative_paths.py`
etc. — pre-existing skip markers, not caused by this change; no failures.)

`python3 scripts/diagnostics.py` → `SCORE = 100/100`.

`python3 scripts/board_lint.py`
```
board_lint: 1 body-status warning(s) (non-fatal — DAS-1507 pre-existing, unrelated)
board_lint: OK — 187 ticket(s) checked, 0 violations.
```

`ruff check tests` → `All checks passed!`

`git diff config/features.yaml` → empty (confirmed clean, no flag touched).

`git diff scripts/stage_gate.py` → **NOT empty** at verification time, but not
from any edit by me — I never called Edit/Write on that file this session,
only Read/`python3 -c "import stage_gate"`. The diff present (16 insertion
lines, `index 783d32d..92eb613`) adds the `ws-a2a-outbound-health` entry that
was already visible in my initial read of the file — it is uncommitted work
from the a2a workstream (DAS-1608–1614, consistent with the many uncommitted
a2a-related files already showing in the branch's `git status` at session
start) that landed in the working tree independently of this ticket, not a
duplicate (`grep -c '"name":' scripts/stage_gate.py` still returns 10, one
`ws-a2a-outbound-health` occurrence). Flagging for the orchestrator/reviewer
so it isn't mistaken for QA-Eng scope creep; DAS-1626's own zone lock
(`tests/` + this ticket file) was respected.

**Status:** `in_review`, routed to QA Lead. All acceptance criteria met against
the schema the code actually implements today; the config/command[1]
universality gap on `golden-eval` and `memory-hygiene` is reported above as a
routing item for Backend EM, not silently absorbed into the test.

### 2026-07-24 — QA Lead (review — CLOSED)

**Verdict: accepted, `done`.** Reviewed as GATE-4 owner. I did not read the
builder's evidence and agree with it — I re-derived it. Everything below marked
*re-verified* was run by me from scratch; everything marked *accepted* was taken
on the builder's word.

**Method (stronger than the builder's own proof).** The builder demonstrated red
by re-implementing the assertions inline against a mutated module — that proves
the *logic* is sound but not that the *shipped test* is. I instead loaded
`tests/test_stage_gate.py` itself via `importlib`, monkey-patched
`sg.maintenance_schedule` in memory, and invoked the real
`test_maintenance_schedule_entries_conform_to_schema` object for every case.
Harness: `<scratchpad>/qa1626/harness.py`; mutated copies of `stage_gate.py`
written only into that scratchpad (`sg_renamed.py`, `sg_deadpath.py`,
`sg_deadconfig.py`, `sg_renamed_cadence.py`). **20/20 cases matched expectation.**

*Re-verified — the test is generic, and entry 11 IS evaluated.* Appended an 11th
entry (`ws-z-future-health`) to the returned schedule and ran the shipped test.
Conformant → PASS. Then eight separate malformations of that same 11th entry,
each → RED with the entry named in the message: dead `config` path, dead
`command[1]`, renamed key (`safety`→`safeties`), missing `cadence`, duplicate
`kind` (`ws-a-eval`), `command` not a list, `python3` with no script argument,
stray extra key (`owner`). Confirmed by reading the diff that no assertion
mentions any entry name — the only occurrences of `memory-hygiene`/`golden-eval`
in the file are in the explanatory comment block, never in code.

*Re-verified — both demonstrated-red cases, on my own scratch copies:*
```
[renamed key config->configs (ws-a-tool-edge-health)] RED -> AssertionError: ws-a-tool-edge-health: unrecognized key(s) ['configs'] (typo or rename?)
[dead command[1] path (ws-b-runner-health)]           RED -> AssertionError: ws-b-runner-health: command[1] 'scripts/ws_b_health_check_GONE.py' does not resolve to a file on disk
[dead config path (ws-c-loop-health)]                 RED -> AssertionError: ws-c-loop-health: config 'docs/06-maintenance/ws-c-loop-health-GONE.md' does not resolve to a file on disk
[renamed cadence->cadance (golden-eval, no config)]   RED -> AssertionError: golden-eval: missing required key(s) ['cadence']
```

*Re-verified — the builder's load-bearing claim about the no-unrecognized-keys
assertion is TRUE.* I ran the identical `config`→`configs` mutation against a
byte-equivalent copy of the shipped test with **only** that one assertion
removed:
```
[config->configs rename WITHOUT the extra-key assert] expected PASS, got PASS
[config->configs rename WITH    the extra-key assert] expected RED,  got RED
```
That is a direct, isolated confirmation: with `config` optional, a rename merely
looks like an absent optional key; the extra-key assertion is the *only* thing
standing between this test and silently missing exactly the failure the ticket
was written to catch. It is not decoration — it is the mechanic.

*Re-verified — no dead assertions.* Every one of the eight assertions in the new
test has a reachable red path, each exercised above (`assert runs` → RED on an
empty `recurring_runs`; missing-required → RED both on entry 11 and on an
existing entry stripped of `kind`; duplicate-`kind` → RED both for a new
colliding entry and for two existing entries). Nothing in this test is dead
weight.

*Judgement call on `config` — I endorse the builder's call, with one
reservation recorded.* The ticket text asserted a schema the repo does not
satisfy. Encoding it would have made the test red against a `scripts/stage_gate.py`
that is *correct*, which converts a genuine open question ("must every scheduled
run have a runbook a human can read?") into a permanently broken build. That
question is a standard to be set deliberately, not a fact a test may assume;
deferring it to DAS-1631 (which I have read — it states both options, requires an
explicit recorded decision, and explicitly requires the `command[1]` rule be
stated structurally rather than by name) is the right call and adequately covers
the gap. The reservation, measured not asserted: I probed the residual exposure by
deleting the `config` key outright from all 10 entries — the test **PASSES**. So a
future entry 11 that ships with no runbook doc at all is invisible until DAS-1631
lands. That is a real hole, but it is narrower than the one this ticket closed
(rename/dead-path, both now caught), it is ticketed rather than forgotten, and the
p2 exposure window is small. **Concrete input for DAS-1631, whichever branch is
chosen:** if (b) "accept optional" wins, freeze the exemption as an explicit
allowlist assertion (`entries lacking config == {"golden-eval",
"memory-hygiene"}`) so a *new* config-less entry still goes red — that gets full
strictness today without the test failing against the real file. Not a bounce
condition; work for the follow-up.

*Re-verified — the `memory-hygiene` exemption is structural, not by-name.* The
guard keys on `command[0] == "python3"`, so an MCP-call entry (`["prune_memory"]`)
is exempted by its *shape*. Any future non-script entry is covered automatically
and any future `python3` entry is caught automatically — this will not rot.

**Verification re-run by me, verbatim:**
```
$ python3 -m pytest tests/test_stage_gate.py -q
25 passed in 0.48s

$ python3 -m pytest -q
2471 passed, 25 skipped in 18.80s

$ python3 scripts/diagnostics.py
SCORE = 100/100

$ python3 scripts/board_lint.py
board_lint: 1 body-status warning(s) (non-fatal — DAS-1507, pre-existing/unrelated)
board_lint: OK — 188 ticket(s) checked, 0 violations.

$ ruff check tests
All checks passed!

$ git diff config/features.yaml
(empty — no flag touched)

$ python3 scripts/check_dependency_graph.py
OK: dependency graph acyclic, no dangling deps (126 ticket(s) declare depends_on).

$ python3 scripts/check_never_auto_approve.py
OK: 190 tickets checked, no never-auto-approve violations.
```

*Accepted, not re-derived:* the builder's narrative of its own first failed
attempt (I re-proved the claim itself, not its history).

**On the `scripts/stage_gate.py` diff the builder flagged:** confirmed non-empty
and confirmed NOT this ticket's doing — it is DAS-1624's `ws-a2a-outbound-health`
entry, uncommitted because this whole run is local-only. Correctly flagged by the
builder; explicitly not scope creep, not reverted.

**DoD note:** the merged-PR / green-CI leg is outstanding by orchestrator
directive (local-only run, no branch/PR/commit). Not a review defect; recorded so
the gap is visible at commit time.

**GATE-4 judgment: PASS.** The schema test earns its keep — proven, not asserted.
