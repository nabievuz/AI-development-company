---
id: DAS-1635
title: Point the go-live runbook and the scripts index at the go/no-go report
status: done
assignee: tech-writer
author: backend-em
dept: product
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-002, FR-003]
labels: [governance]
zone: docs/runbooks
depends_on: [DAS-1619]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**The documentation half of DAS-1619's acceptance criteria, which that ticket could
not do — it was zone-locked to `scripts/` and `tests/`.**

`scripts/heartbeat_go_no_go.py` now exists: the single Founder-facing go/no-go
artifact for the HEARTBEAT flip, composing ten gates from existing checkers. Nothing
in the documentation points at it, so the Founder standing at the flip decision has
no route from the runbook to the report built for exactly that moment.

Two additions:
1. A **step-3 pointer** in `docs/runbooks/heartbeat-go-live.md` naming
   `scripts/heartbeat_go_no_go.py` and the exact command to run.
2. Register the script in `docs/05-SCRIPTS.md` (note: `scripts/README.md` defers to
   that file — check the convention before writing, and follow whichever the repo
   actually uses).

**Verify what you write by running it**, not by reading DAS-1619's report. In
particular the artifact's three-state output is the thing worth describing
accurately: it reports `PASS` / `FAIL` / `UNKNOWN`, where UNKNOWN means *could not
check* and never counts as a pass, and an empty gate list is NO-GO. Today it exits 1
with `VERDICT: NO-GO` on two FAILs (0/3 shadow window from 0 rows; `active_plan`
undeclared) and one UNKNOWN (`board/.events.jsonl` absent). Describe it as it is —
do not imply it currently blesses a flip.

**Do not disturb the runbook's Founder-flip section semantics.** That section was
deliberately left byte-identical through DAS-1617's GATE-2 addendum; the flip stays a
Founder-only act. You are adding a pointer to a report, not changing what authorises
the flip. Preserve the three-clock separation the GATE-2 addendum established: the
≥3-day SI-7 heartbeat clock, the ≥7-clean-day SI-2 ladder clock, and the ≥7 rolling
waves VERSION criterion, which is not a clock at all.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT edit anything under `scripts/`, `tests/`,
`config/`, or `tools/`. **No git state mutation** (`add`/`commit`/`reset`/`stash`/
`checkout`) — read-only git only.

## Acceptance criteria
- [x] `docs/runbooks/heartbeat-go-live.md` step 3 points at `scripts/heartbeat_go_no_go.py` with the exact command, verified by running it.
- [x] The script registered in the repo's scripts index, following whichever of `docs/05-SCRIPTS.md` / `scripts/README.md` the convention actually designates.
- [x] The three-state (PASS/FAIL/UNKNOWN) semantics described accurately, including that UNKNOWN is never a pass and today's verdict is NO-GO.
- [x] The Founder-flip section's semantics and the three-clock separation both preserved.
- [x] `check_links.py` green; `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Backend EM
Raised in DAS-1619's close report as the doc half it was zone-locked out of;
recorded by the orchestrator in the same run.

### 2026-07-24 — Technical Writer
**Runbook (docs/runbooks/heartbeat-go-live.md):** Added step-3 pointer to `python3 scripts/heartbeat_go_no_go.py` with exact command, introduction of three-state semantics (PASS/FAIL/UNKNOWN), exit codes (0 = VERDICT: GO, 1 = VERDICT: NO-GO), and explicit note that UNKNOWN never counts as a pass. Preserved existing individual checks as alternative and maintained Founder-flip section byte-identical semantics and three-clock separation (SI-7 ≥3-day heartbeat clock, SI-2 ≥7-day ladder clock, VERSION ≥7-rolling-waves release criterion).

**Scripts index (docs/05-SCRIPTS.md):** Added new "Readiness Verification (Founder-facing)" section with entry for `heartbeat_go_no_go.py`, matching established house style. Described script as Founder readiness report for HEARTBEAT flip (ADR-0027 SI-1..SI-7), composing ten gates from existing checkers, reporting PASS/FAIL/UNKNOWN states with explicit emphasis on exit codes and that UNKNOWN never counts as a pass, and caveat that script cannot write config files.

**Verified by running script:** Exit code 1, VERDICT: NO-GO due to 2 FAILs (clean shadow window 0/3 days from 0 history rows; monthly_credit_ceiling active_plan undeclared) and 1 UNKNOWN (board/.events.jsonl absent). Script accurately documents that it cannot approve anything and has no code path that writes config files.

**Validation:** ✓ check_links.py clean; ✓ diagnostics.py 100/100; ✓ board_lint.py clean; ✓ git status confirms only docs/ zone modified (docs/05-SCRIPTS.md, docs/runbooks/heartbeat-go-live.md); ✓ no project: field in ticket (R9 compliant).
