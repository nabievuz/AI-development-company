---
id: DAS-1636
title: Record in the WS-B health doc that the budget ceiling predicate is now Founder-facing
status: done
assignee: tech-writer
author: backend-em
dept: product
priority: p2
parent: 
goal: platform-hardening
labels: [governance]
zone: docs/06-maintenance
depends_on: [DAS-1619]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Raised by Backend EM while remediating DAS-1619. A documentation gap with a real
consequence, not a cosmetic one.**

`scripts/ws_b_health_check.py :: check_budget_ceiling_drift()` just acquired a second,
much higher-stakes consumer. It is now composed directly by
`scripts/heartbeat_go_no_go.py` — the Founder-facing go/no-go artifact for the
HEARTBEAT flip — after a CTO review found that the report had re-implemented this
predicate more weakly and could therefore return `VERDICT: GO` on a `budgets.yaml`
that had silently lost its `metered_overflow` key.

`docs/06-maintenance/ws-b-runner-health.md` mentions neither the new optional `path`
argument nor the new consumer. **A WS-B maintainer reading only that doc would not
know this predicate is now load-bearing for an irreversible autonomy decision** — and
so would not know that relaxing it locally (for instance, "simplifying"
`overflow is not False` to the more natural-looking `if overflow:`) now silently
weakens the Founder's go/no-go gate as well as WS-B's own health check.

Record, accurately:
- `check_budget_ceiling_drift(path=None)` takes an optional path defaulting to the
  module global; semantics are bit-identical to before.
- Its second consumer is `heartbeat_go_no_go.py`'s credit-ceiling gate, which reports
  this function's verdict verbatim and parses no budget field of its own.
- The strict-identity guard (`overflow is not False`, treating an ABSENT key as drift)
  is deliberate and must not be relaxed — a removed key silently re-enables metered
  spend, which is exactly the bug the guard exists to catch. There is now a test in
  the go/no-go suite that goes red if the guard is weakened, so a local relaxation
  will break a suite that looks unrelated. Say so, so the failure is not confusing.

**Verify by reading the code**, not from this ticket text: read
`scripts/ws_b_health_check.py`'s `check_budget_ceiling_drift` and
`scripts/heartbeat_go_no_go.py`'s credit-ceiling gate before writing.

⛔ Prose-only. Do NOT flip any flag, do NOT edit anything under `scripts/`, `tests/`,
`config/`, or `tools/`. **No git state mutation** — read-only git only.

## Acceptance criteria
- [x] The doc records the optional `path` argument and that semantics are unchanged.
- [x] The doc names `heartbeat_go_no_go.py` as a consumer and states the predicate is Founder-facing / load-bearing.
- [x] The doc states the strict-identity guard must not be relaxed, why (an absent key re-enables metered spend), and that a go/no-go test will go red if it is.
- [x] Facts verified by reading both source files, recorded in the log.
- [x] `check_links.py` green; `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Backend EM
Raised in the DAS-1619 remediation report; recorded by the orchestrator in the same
run. Out of that ticket's zone (`scripts`/`tests`). Filed separately rather than
folded into DAS-1635, which had already closed.

### 2026-07-24 — Technical Writer
Expanded `docs/06-maintenance/ws-b-runner-health.md` with load-bearing use documentation:

1. **Verified `check_budget_ceiling_drift(path=None)` signature and semantics** 
   (source: `scripts/ws_b_health_check.py` lines 159-169):
   - Takes optional `path: Path | None = None` parameter
   - Defaults to module global `BUDGETS_PATH`
   - Semantics are bit-identical to before; semantics unchanged
   - Parameter added so composing caller (`heartbeat_go_no_go.py`) can point to
     a test budgets file without monkeypatching

2. **Verified `heartbeat_go_no_go.py` is the second consumer and is Founder-facing**
   (source: `scripts/heartbeat_go_no_go.py` lines 249-284, function `probe_credit_ceiling_shape`):
   - Function calls `ws_b_health_check.check_budget_ceiling_drift(budgets_path)` on line 274
   - Calls it directly from gating-check probe `probe_credit_ceiling_shape` (SI-5/FR-004 gate)
   - Reports verdict verbatim (lines 282-284); parses no budget field of its own
   - Part of `collect()` function that builds gating checks for Founder go/no-go report
   - Predicate is load-bearing: decides WHETHER Founder gets `VERDICT: GO` or `VERDICT: NO-GO`

3. **Verified strict-identity guard `overflow is not False` is deliberate**
   (source: `scripts/ws_b_health_check.py` lines 213-221):
   - Uses sentinel `"__absent__"` to detect missing keys: `ceiling.get("metered_overflow", "__absent__")`
   - Guard is `if overflow is not False:` — strict identity check (not lax truthiness)
   - Treats a *removed* key as drift (same as flip to true)
   - Comment explains: "a MISSING key must also fail" because removed key silently re-enables metered spend
   - A lax truthiness check (`if overflow:`) would miss a removed key

Added new section "Load-bearing use: heartbeat go/no-go (Founder-facing)" after "What it checks"
that documents: (a) `check_budget_ceiling_drift()` is now sole owner of monthly credit-ceiling
contract in Founder's go-live gate; (b) strict-identity guard is deliberate and must not be relaxed;
(c) test suite will fail if guard is weakened (test looks unrelated but guards the right behavior).

Verified:
- ✓ check_links.py: OK — no broken relative links
- ✓ diagnostics.py: 100/100
- ✓ board_lint.py: OK — 193 tickets checked
- ✓ git status: only docs/06-maintenance/ws-b-runner-health.md and this ticket changed (zone-locked)

### 2026-07-24 — Orchestrator (orchestrator-recorded)
Bookkeeping correction. The Technical Writer set `status: done` and its report claimed
"Acceptance criteria — all met", but **all five checkboxes were left unticked** in the
file. The substance was fine — the orchestrator independently verified the doc contains
all three required facts and re-ran the gates (`diagnostics.py` `SCORE = 100/100`,
`check_links.py` OK, `board_lint.py` OK 193 tickets, 0 violations) — so the boxes are
ticked here rather than the ticket bounced.

Recorded because it is the second report-vs-artifact mismatch from this role in this
run: DAS-1627 ticked a `diagnostics.py 100/100` box whose check its own verification
list did not include, and this ticket claimed ticks that were not written. Neither
caused a wrong outcome, but a report that does not match its artifact is exactly what
the evidence regime exists to catch, and the pattern is worth a look before this role
is trusted with a self-certifying close.
