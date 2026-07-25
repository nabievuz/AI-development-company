---
id: DAS-1624
title: A2A follow-up — author the A2A health-check script and register it in the maintenance schedule
status: done
assignee: backend-em
verified_by: backend-em
author: product-analyst
dept: engineering
priority: p2
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [SC-003, SC-005]
labels: [security]
zone: scripts
depends_on: [DAS-1614]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Follow-up raised by DAS-1614 (A2A GATE-6 Maintenance).** DAS-1614 authored
`docs/06-maintenance/ws-a2a-outbound-health.md` under a `docs/06-maintenance/`
zone lock, so it could not touch `scripts/`. Two `scripts/`-zone gaps remain,
both mechanical, both required for the A2A health doc to behave like its six
siblings rather than being a doc no runner ever executes.

**1. No `scripts/` health-check runner exists for A2A.** Every sibling
workstream health doc is backed by a real script — `ws_e_health_check.py`,
`ws_h_health_check.py`, and so on — invoked by
`stage_gate.maintenance_schedule()`. A2A has the doc but no runner. Author the
runner by **composing checks that already exist**; do NOT author a second
diagnostics harness, a second in-tenant checker, or a second test runner:
- in-tenant boundary drift — reuse `scripts/check_in_tenant.py` (SC-003).
- flag/publish-state drift — compare `a2a_outbound` in `config/features.yaml`
  against the `a2a_publish` events in `board/.events.jsonl`. The event shape is
  `tools/a2a/publish.py`'s `build_publish_event`; read it, do not restate it
  from memory. Baseline today is flag OFF with zero publish events.
- negative-test drift — re-run DAS-1612's suite
  (`tests/test_a2a_outbound_endpoint.py`, `tests/test_a2a_intake.py`).
Match the sibling contract exactly: `--json` output, and a non-zero exit is an
ALERT routed to a follow-up ticket — never silently retried, never auto-fixed.

**2. Not registered in `stage_gate.maintenance_schedule()`.** Add the
`ws-a2a-outbound-health` entry pointing at the new runner and at
`docs/06-maintenance/ws-a2a-outbound-health.md`, mirroring the `ws-e-tenant-health`
/ `ws-h-control-health` entries (`name`, `kind`, `command`, `cadence`, `config`,
`safety`).

**3. `a2a_outbound` is absent from `scripts/feature_flags.py`'s `DEFAULTS`.**
This is a consistency gap, **not** a live defect, and it must not be
"fixed" by rewiring the endpoint. `tools/a2a/endpoint.py` deliberately uses its
own dedicated line-scan reader `is_enabled()` (mirroring `scripts/rbac.py`), and
that reader honours a Founder flip in `config/features.yaml` correctly — this is
documented at `tools/a2a/endpoint.py:25-29`. The risk is only that a *future*
consumer calling `feature_flags.enabled("a2a_outbound")` would get a silent
`False` because `load()` filters to keys in `DEFAULTS`. Add the key to `DEFAULTS`
(default `False`) so both readers agree. Leave `endpoint.py`'s reader alone and
update its now-stale "NOT yet in DEFAULTS" comment.

⛔ Do NOT flip `a2a_outbound`. Publishing the endpoint is a Founder-only act
(QONUN-5, FR-003); the flag stays `false` and this ticket changes no dispatch or
board behavior (SC-005).

## Acceptance criteria
- [x] An A2A health-check runner exists under `scripts/`, composes the three existing checks above, supports `--json`, and its observed output is recorded in the ticket log.
- [x] `stage_gate.maintenance_schedule()` has a `ws-a2a-outbound-health` entry mirroring the sibling schema and pointing at the runner plus the existing health doc.
- [x] `a2a_outbound` present in `feature_flags.DEFAULTS` (default `False`); `feature_flags.enabled("a2a_outbound")` and `endpoint.is_enabled()` agree in both flag states; the stale comment at `tools/a2a/endpoint.py:25-29` corrected.
- [x] `a2a_outbound` still reads `false`; `git diff config/features.yaml` is empty.
- [x] `diagnostics.py` 100/100; `board_lint`/validators green; A2A test suite still passes; no `project:` field (R9).

## Log
### 2026-07-24 — Product Analyst
Raised as an explicit follow-up in DAS-1614's GATE-6 close report (two
`scripts/`-zone items the maintenance ticket's zone lock put out of reach).
Recorded by the orchestrator during the same run. Item 3 was **verified as a
consistency gap, not a live defect**, before this ticket was written: the A2A
endpoint's dedicated `is_enabled()` line-scan reader does honour a config flip,
so no A2A behavior is currently wrong. Does not reopen any closed A2A gate —
GATE-1..GATE-6 (DAS-1607..DAS-1614) all stay `done`.

### 2026-07-24 — Backend Engineer 1

All three `scripts/`-zone items done, composing existing checks only (no
second diagnostics harness, in-tenant checker, test runner, or flag reader).

**1. Runner authored:** `scripts/ws_a2a_health_check.py`, mirroring
`ws_e_health_check.py`/`ws_h_health_check.py` (module-level `_load_module`
reuse pattern, `--json` flag, `run()`/`main()` shape, exit 0=healthy/1=ALERT,
never auto-fixes/auto-retries). Three checks:
- `check_in_tenant_drift()` — reuses `scripts/check_in_tenant.py: evaluate()`
  over `config/tenant_boundary.yaml`.
- `check_flag_publish_drift()` — reuses `scripts/feature_flags.py: enabled()`
  (now that `a2a_outbound` is in `DEFAULTS`, see item 3) against the newest
  `event_type == "a2a_publish"` record in `board/.events.jsonl` (event shape
  read verbatim from `tools/a2a/publish.py: build_publish_event`, not
  restated from memory). Zero events + flag OFF reports OK, not an error.
- `check_negative_test_drift()` — re-runs
  `tests/test_a2a_outbound_endpoint.py` + `tests/test_a2a_intake.py` via a
  plain `pytest` subprocess (no new runner).

Observed output (verbatim, this run):
```
$ python3 scripts/ws_a2a_health_check.py
A2A OUTBOUND health check (GATE-6 Maintenance, DAS-1614/DAS-1624)
============================================================
[OK] in_tenant_drift: TN-1 holds: all 7 declared endpoint(s) in-tenant (model call excepted)
[OK] flag_publish_drift: 'a2a_outbound' is false and zero 'a2a_publish' events are logged — honest baseline (armed, never published), no drift
[OK] negative_test_drift: negative-test suite green: ============================== 95 passed in 0.17s ==============================
------------------------------------------------------------
HEALTHY
EXIT=0
```
`--json` produces the same three checks as machine-readable JSON, `"healthy": true`, exit 0 (verified).

**2. Registered** `ws-a2a-outbound-health` in `scripts/stage_gate.py:
maintenance_schedule()`, mirroring the `ws-e-tenant-health` /
`ws-h-control-health` entry schema (`name`, `kind`, `command`, `cadence`,
`config` pointing at the existing `docs/06-maintenance/ws-a2a-outbound-health.md`,
`safety`). Verified via `tests/test_stage_gate.py` (24 passed) plus a new
`test_maintenance_schedule_registers_the_ws_a2a_health_check` in the new test
file below.

**3. `a2a_outbound: False` added to `scripts/feature_flags.py`'s `DEFAULTS`**
(consistency fix, not a behavior change — `endpoint.py`'s dedicated
`is_enabled()` line-scan reader is untouched and still does its own read).
Corrected the now-stale "NOT yet in DEFAULTS" comment at
`tools/a2a/endpoint.py:25-29`. Proved the two readers agree in BOTH flag
states using scratch config copies in the scratchpad directory (never the
real `config/features.yaml`):
```
false feature_flags.enabled= False endpoint.is_enabled= False AGREE
true feature_flags.enabled= True endpoint.is_enabled= True AGREE
```

**New test file:** `tests/test_ws_a2a_health_check.py` (13 tests), mirroring
`tests/test_ws_h_health_check.py`'s style — covers all three checks'
happy/drift paths plus the CLI and schedule-registration assertions.

**Verification (observed output, verbatim):**
```
$ python3 -m pytest tests/test_a2a_outbound_endpoint.py tests/test_a2a_intake.py tests/test_ws_a2a_health_check.py tests/test_stage_gate.py -q
132 passed in 1.15s

$ python3 -m pytest -q   (full suite)
2452 passed, 25 skipped in 18.04s

$ python3 scripts/diagnostics.py
SCORE = 100/100

$ python3 scripts/board_lint.py
board_lint: OK — 181 ticket(s) checked, 0 violations.
(one pre-existing unrelated WARN on DAS-1507 body-status prose, non-fatal)

$ git diff config/features.yaml
(empty)
```

Files touched: `scripts/ws_a2a_health_check.py` (new),
`tests/test_ws_a2a_health_check.py` (new), `scripts/stage_gate.py` (registered
entry), `scripts/feature_flags.py` (DEFAULTS entry),
`tools/a2a/endpoint.py` (comment correction only, `is_enabled()` reader
untouched), this ticket file. No edits under `docs/design/`,
`docs/runbooks/`, `docs/adr/`, `docs/06-maintenance/`, or `config/` — zone
lock held. `a2a_outbound` was never flipped.

Per the dispatch's local-only/no-commit constraint, no branch/commit/PR was
created this run — the orchestrator commits at workstream close. Setting
`status: in_review`, `assignee: backend-em` per ROUTING.md (author's manager,
never the author) so a reviewer can close the loop once the change is
committed/branched per the standard one-issue/one-branch/one-PR flow.

### 2026-07-24 — Backend EM

**REVIEW — ACCEPTED. `status: done`, `verified_by: backend-em`.** I did not
author any of this work; I re-ran every claim myself rather than trusting the
builder's log. Nothing below is copied from the builder's entry.

**A. Composition, not a fork (structural read + run).** `scripts/ws_a2a_health_check.py`
loads `scripts/check_in_tenant.py` and `scripts/feature_flags.py` through the
same module-level `_load_module` pattern `ws_e_health_check.py` uses, and calls
`cit.evaluate(data)` / `ff.enabled(FLAG, FEATURES_PATH)` — no reimplemented
boundary evaluator, no second flag parser, no second diagnostics harness. The
third check is a plain `subprocess.run([sys.executable, "-m", "pytest", ...])`
over DAS-1612's two files — no new test runner. Observed, this run:

```
$ python3 scripts/ws_a2a_health_check.py
A2A OUTBOUND health check (GATE-6 Maintenance, DAS-1614/DAS-1624)
============================================================
[OK] in_tenant_drift: TN-1 holds: all 7 declared endpoint(s) in-tenant (model call excepted)
[OK] flag_publish_drift: 'a2a_outbound' is false and zero 'a2a_publish' events are logged — honest baseline (armed, never published), no drift
[OK] negative_test_drift: negative-test suite green: ============================== 95 passed in 0.70s ==============================
------------------------------------------------------------
HEALTHY
EXIT=0

$ python3 scripts/ws_a2a_health_check.py --json
{
  "healthy": true,
  "checks": {
    "in_tenant_drift": {"ok": true, "detail": "TN-1 holds: all 7 declared endpoint(s) in-tenant (model call excepted)"},
    "flag_publish_drift": {"ok": true, "detail": "'a2a_outbound' is false and zero 'a2a_publish' events are logged — honest baseline (armed, never published), no drift"},
    "negative_test_drift": {"ok": true, "detail": "negative-test suite green: ============================== 95 passed in 0.19s =============================="}
  }
}
EXIT=0
```

Also verified READ-ONLY empirically: `shasum` of `config/features.yaml` and
`config/tenant_boundary.yaml` before/after a full run — both UNCHANGED; the
ledger `board/.events.jsonl` does not exist at all on this checkout, and the
run did not create it.

**B. Sibling-house-pattern conformance.** Compared shape against
`ws_e_health_check.py` and `ws_h_health_check.py`: identical `--json` schema
(`{"healthy": bool, "checks": {name: {"ok": bool, "detail": str}}}`), identical
`run()`/`main(argv)` split, identical `return 0 if result["healthy"] else 1`,
identical human-mode `[OK]`/`[ALERT]` lines plus the
`HEALTHY` / `UNHEALTHY — surface as alert / follow-up ticket, do not ignore`
footer, and the same module-docstring contract ("a non-zero exit is an ALERT …
never a silent skip / auto-fix / auto-retry", "never opens a ticket … no
autonomous self-modification (ADR-0029 G5)"). **No divergence found** that would
make the A2A entry behave differently from its siblings under the same scheduler.

**C. Drift paths PROBED, not assumed (scratch copies only — the real `config/`,
`board/.events.jsonl` and `tests/` were never mutated).** A check that cannot go
red is not a check, so I forced each one red:

```
PROBE A (a2a endpoint repointed at a hosted relay):
  {"ok": false, "detail": "a2a_outbound (role=a2a) resolves to an EXTERNAL host: https://a2a-relay.example.com"}
PROBE A control (real config): {"ok": true, ...}
PROBE B1 (flag ON, zero a2a_publish events):
  {"ok": false, "detail": "'a2a_outbound' reads true in <scratch>/features_on.yaml but zero 'a2a_publish' events are logged in board/.events.jsonl — a flag flip with no corresponding Founder-attributed publish event"}
PROBE B2 (logged allow publish act, flag OFF):
  {"ok": false, "detail": "newest 'a2a_publish' event (decision='allow', flag_state=True) implies 'a2a_outbound' should read True but the live config reads False"}
PROBE B3 control (flag ON + matching allow event): {"ok": true, ...}
PROBE B4 control (flag OFF + zero events):        {"ok": true, ... honest baseline ...}
PROBE C (forced failing test file): ok=False | "negative-test suite failed (exit=1): F ..."
```

Both drift directions the ticket names go red, and both honest-baseline
directions stay green — the check discriminates, it does not always-OK.

**D. Schedule entry — schema + path resolution independently checked.**
`maintenance_schedule()` now has 10 `recurring_runs`. The new entry's key set is
`['cadence','command','config','kind','name','safety']` — **exactly the same key
set as `ws-e-tenant-health` and `ws-h-control-health`** (asserted
programmatically, not eyeballed). `kind: ws-a2a-eval` is unique across all 10
entries; `cadence: daily` matches siblings. Both paths resolve:
`scripts/ws_a2a_health_check.py` → exists,
`docs/06-maintenance/ws-a2a-outbound-health.md` → exists. I also swept ALL 10
entries for unresolvable `command`/`config` paths: `[]`.

**E. Mutation-tested the test file — the 13 tests are not tautologies.** I made
each check silently always-OK in a scratch-backed copy of the runner, ran the
suite, and restored the file byte-identical (`cmp` clean; `git diff --stat
scripts/stage_gate.py` back to its original 16-line insertion):

| mutation | result |
|---|---|
| `check_flag_publish_drift` → always `ok: True` | **2 failed**, 11 passed (`..._flags_flag_on_with_zero_events`, `..._flags_a_rollback_that_outran_the_ledger`) |
| `check_in_tenant_drift` → always `ok: True` | **2 failed**, 11 passed (`..._flags_a_missing_boundary_file`, `..._flags_an_external_endpoint`) |
| `check_negative_test_drift` → always `ok: True` | **1 failed**, 12 passed (`..._flags_a_missing_test_file`) |
| schedule `command` → `ws_a2a_health_check_TYPO.py` | **1 failed** (`test_maintenance_schedule_registers_the_ws_a2a_health_check`) — a wrong command path DOES fail loudly |
| schedule key `config` → `configs` | **37 passed** — NOT caught (see residual R1) |

Every check therefore has at least one test that goes red when it is silently
broken. Command-path *existence* is additionally covered transitively by
`test_cli_exits_zero_when_healthy`, which subprocess-runs the real script.

**F. Item-3 consistency fix re-proved with MY OWN scratch copies.**
`a2a_outbound: False` is present in `feature_flags.DEFAULTS`.
`tools/a2a/endpoint.py: is_enabled()` is UNCHANGED — confirmed by
`git diff tools/a2a/endpoint.py`, whose entire diff is the module-docstring
comment block at lines 25-32; the line-scan reader body is untouched and is NOT
rewired to `feature_flags.enabled()`. Rather than a minimal one-line flag file I
used a **full copy of the real `config/features.yaml`** (inline trailing comment
and all — the harder case for a line-scan reader) with only the `a2a_outbound`
value substituted:

```
false feature_flags.enabled=False endpoint.is_enabled=False AGREE
true  feature_flags.enabled=True  endpoint.is_enabled=True  AGREE
missing-file: False False      (both fail-safe to OFF)
malformed:    False False      (both fail-safe to OFF)
```

The corrected comment at `tools/a2a/endpoint.py:25-32` is now accurate: the key
IS in `DEFAULTS` as of this ticket, and the stated reason for keeping the
dedicated reader (independent trust boundary, fail-safe-to-OFF) matches the code.

**G. Gates re-run by me, verbatim:**

```
$ python3 -m pytest tests/test_ws_a2a_health_check.py tests/test_stage_gate.py tests/test_a2a_outbound_endpoint.py tests/test_a2a_intake.py -q
132 passed in 1.25s

$ python3 -m pytest -q          (full suite — DEFAULTS gained a key, so I re-ran everything)
2452 passed, 25 skipped in 19.83s

$ python3 scripts/diagnostics.py
SCORE = 100/100

$ python3 scripts/board_lint.py
board_lint: OK — 182 ticket(s) checked, 0 violations.
(plus the pre-existing non-fatal DAS-1507 body-status WARN, unrelated)

$ python3 scripts/check_never_auto_approve.py
OK: 184 tickets checked, no never-auto-approve violations.
$ python3 scripts/check_dependency_graph.py
OK: dependency graph acyclic, no dangling deps (120 ticket(s) declare depends_on).
$ python3 scripts/check_spec_consistency.py
OK: 10 SPEC.md file(s) checked, structure + ticket refs consistent.
$ python3 scripts/check_comm_flows.py
check_comm_flows: OK — 0 referenced route(s) ... all declared (60 routes).
$ ruff check scripts/ws_a2a_health_check.py tests/test_ws_a2a_health_check.py
All checks passed!

$ git diff config/features.yaml
(empty)
$ grep -o '^a2a_outbound: [a-z]*' config/features.yaml
a2a_outbound: false
```

**The surface stays merged-but-dark.** `a2a_outbound` still reads `false`, zero
`a2a_publish` events, zero `a2a_call` events, no ledger file. Nothing in this
review changed that.

**Accepted without independent re-derivation (declared honestly):** the builder's
narrative of *why* each design choice was made (I verified the resulting code and
behavior, not the reasoning path), and the historical claim that item 3 was a
consistency gap rather than a live defect at the time DAS-1614 wrote it (I
verified only today's post-fix state, which is correct).

**Definition of Done — outstanding leg.** Per `board/README.md`, engineering
`done` normally requires a merged PR with green CI. This entire run is
**local-only by orchestrator directive** (no push / no PR / no commit; the
orchestrator commits at workstream close), so the builder correctly could not
open one. I am NOT bouncing for that. **The merged-PR / green-CI leg remains
outstanding and is the orchestrator's step at workstream close.** Everything
within this ticket's own control is verified complete.

**Residuals — routed as findings, NOT bounce reasons (both outside this
ticket's `zone: scripts` and outside my review zone lock):**

- **R1 — house-wide test gap, pre-existing, not introduced here.** No
  `maintenance_schedule()` test asserts the *key set* of a `recurring_runs`
  entry, so renaming `config` → `configs` on ANY of the 10 entries (including
  the six pre-existing siblings) still passes the full suite. The A2A entry is
  exactly as covered as its siblings, so this is not a DAS-1624 defect; it is an
  engine-wide hardening candidate (one schema test over all `recurring_runs`
  entries asserting the required keys and that `command[1]`/`config` resolve on
  disk). Suggest a new `zone: scripts`/`tests` platform ticket.
- **R2 — `docs/06-maintenance/ws-a2a-outbound-health.md` is now stale because
  this ticket landed.** Two passages are contradicted by the merged code: (a)
  the "Known gap, logged honestly, not fixed here" block claiming
  `feature_flags.DEFAULTS`/`load()` "does not include `a2a_outbound`" and that
  `feature_flags.enabled("a2a_outbound")` "always resolves `False`" — no longer
  true as of this ticket; and (b) the "Cadence and registration" section stating
  the runner / `recurring_runs` wiring is "follow-up work for a `zone: scripts`
  ticket" not yet done — it is now done, and the doc never names
  `scripts/ws_a2a_health_check.py` as its runner. `docs/06-maintenance/` is
  outside my zone lock this wave, so I did not edit it. Needs a small
  `zone: docs` de-stale ticket. No behavior is wrong — the registered `config`
  path resolves and the runner runs; only the prose lags.
- **R3 — cosmetic nit, no action required.** `check_flag_publish_drift`'s
  flag-ON/zero-events message hardcodes the literal string
  `board/.events.jsonl` in its prose even when `EVENTS_PATH` is redirected
  (visible in PROBE B1 above). Message text only; the comparison itself uses the
  live `EVENTS_PATH`. Sibling health checks share the same style. Not worth a
  ticket on its own.
