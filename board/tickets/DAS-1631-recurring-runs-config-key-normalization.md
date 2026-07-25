---
id: DAS-1631
title: Decide whether every recurring run needs a linked runbook doc or config stays optional
status: done
assignee: cto
author: qa-eng
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [governance]
zone: scripts
depends_on: [DAS-1626]
verified_by: cto
created: 2026-07-24
updated: 2026-07-25
---

## Description

**Genuine finding surfaced by DAS-1626, deliberately not fixed there** (that
ticket was zone-locked to `tests/`, and per its own instruction a test must not
quietly patch the thing it exists to catch).

DAS-1626's premise — that all 10 `recurring_runs` entries in
`scripts/stage_gate.py`'s `maintenance_schedule()` share the key set
`{name, kind, command, cadence, config, safety}` — **is false today.** Measured
programmatically:

- `golden-eval` (WS6) and `memory-hygiene` (WS4) carry **no `config` key**, and no
  `docs/06-maintenance/*.md` backs either of them (that directory holds only the
  seven `ws-*-health.md` files).
- `memory-hygiene`'s `command` is `["prune_memory"]` — an ArcRift MCP call, a
  single element with no `command[1]` to resolve. It is not a `python3 <script>`
  invocation at all.

So enforcing the literal schema would fail red against the current, unmodified
`scripts/stage_gate.py` — and that red would be **correct**, not a false positive:
it would be flagging that 2 of 10 recurring runs have no linked runbook doc.
DAS-1626 shipped the schema test matching what is actually true today (`config`
optional, but must resolve when present, plus a no-unrecognized-keys assertion that
catches renames) so the gap is visible rather than encoded as silence.

**The decision to make — either is defensible, but it must be deliberate:**
- **(a) Normalize:** author a `docs/06-maintenance/*.md` for `golden-eval` and
  `memory-hygiene`, add `config` to both entries, and tighten the schema test to
  require `config` universally. This treats "every scheduled run has a runbook a
  human can read" as the standard.
- **(b) Accept optional:** formally record `config` as optional in the schema, with
  the reasoning for why these two runs legitimately need no linked doc, so this is
  not re-flagged every time someone reads the schedule.

If you choose (a), the `memory-hygiene` `command[1]` exemption still needs an
explicit rule — an MCP call is structurally not a script path, and the schema
should say so rather than special-casing by name.

## Acceptance criteria
- [x] An explicit decision recorded with reasoning — **(a) NORMALIZE**. Recorded below and in code.
- [x] (a): both docs authored (`docs/06-maintenance/golden-eval.md`, `docs/06-maintenance/memory-hygiene.md`), both entries carry `config`, and the schema test tightened to require `config` universally — with a scratch-copy test demonstrating a new config-less entry fails RED (`test_new_config_less_entry_fails_schema`).
- [ ] (b) not chosen — N/A.
- [x] The `command[1]` rule stated structurally (`command[0] == "python3"` ⇒ script path must resolve; an MCP-tool-call command like `["prune_memory"]` is exempt by command SHAPE, never by entry name).
- [x] Full suite green (2578 passed, 25 skipped); `diagnostics.py` 100/100; `board_lint` OK (198 tickets, 0 violations); `check_links` OK; `ruff` clean on changed files; no `project:` field (R9).

## Log
### 2026-07-24 — QA Engineer
Raised in the DAS-1626 close report; recorded by the orchestrator in the same run.
Not fixed there — `scripts/` was outside that ticket's zone lock and was concurrently
held by the DAS-1618 review. Reported rather than papered over: the ticket text's
stated schema and the repository's actual state disagreed, and the disagreement is
itself the finding.

### 2026-07-25 — QA Lead

**DECISION: (a) NORMALIZE.** `config` (the linked `docs/06-maintenance/` runbook)
is now REQUIRED on every recurring run. Standard adopted: *every scheduled
maintenance run has a runbook a human can read* — no by-name exemption.

**Grounded in what the two config-less entries actually are:**
- `golden-eval` (kind `ws6-eval`, `command = ["python3", "scripts/agent_eval.py"]`)
  — a real script invocation whose `command[1]` already resolves. It is the WS6
  golden-eval harness: the eval scorecard the QA-Lead/GATE-6 owns, the single most
  consequential recurring run for eval-threshold judgment. Nothing about it is
  doc-averse; it merely predates the `ws-*-health` runbook convention (an original
  DAS-1494/DAS-1487 entry). It clearly warrants — and now has — a runbook.
- `memory-hygiene` (kind `ws4-scheduled`, `command = ["prune_memory"]`) — an
  ArcRift **MCP tool call**, structurally NOT a `python3 <script>` invocation, so
  there is no `command[1]` to resolve. But "no script path" is orthogonal to "no
  runbook": the weekly ArcRift prune has real operational semantics (project-scoped
  pruning, never a blind wipe, ties to the Persistent Memory Law, human-gated on
  governance-bearing facts) that warrant a doc exactly like the others.

So `config` can be universal without contradiction; the `command[1]` script-path
rule stays a SEPARATE, shape-keyed rule (`command[0] == "python3"`), never keyed on
a name.

**Why (a) over (b):** option (b)'s allow-list is a closed by-name set
`{golden-eval, memory-hygiene}` — the exact by-name special case the ticket warns
rots: if `golden-eval` later gains a config, someone must remember to shrink the
frozenset or the equality assertion goes RED for the *right* change. (a) removes the
exemption entirely — `config` universal, zero names anywhere — leaving only the
shape-keyed `command[1]` rule, which cannot rot. Cleaner invariant, no standing
liability, and both entries genuinely warrant a runbook.

**Changes (zone: `scripts/stage_gate.py` + `tests/test_stage_gate.py` +
`docs/06-maintenance/`):**
- Authored `docs/06-maintenance/golden-eval.md` and
  `docs/06-maintenance/memory-hygiene.md` (the latter documents structurally why an
  MCP-call command has no `command[1]`).
- Added `config:` to both entries in `maintenance_schedule()`; recorded the
  NORMALIZE decision + the shape-keyed `command[1]` rule in that function's
  docstring.
- Tightened `test_stage_gate.py`: `config` moved into `_MAINTENANCE_BASE_KEYS`
  (required on all); schema factored into `_assert_entry_conforms()`; added
  `test_new_config_less_entry_fails_schema` — a scratch copy (real schedule never
  mutated) proving a hypothetical 11th config-less entry fails RED.

**Verification (observed output):**
- Load-bearing property — config-less entry on a scratch copy:
  `RED as required — AssertionError: ws-z-future-health: missing required key(s)
  ['config']`; and NOT a tautology — `With config present, the same 11-entry
  schedule conforms (GREEN).`
- `pytest tests/test_stage_gate.py -q` → `26 passed in 0.78s`.
- Full suite `pytest -q` → `2578 passed, 25 skipped in 21.27s`.
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`.
- `python3 scripts/board_lint.py` → `OK — 198 ticket(s) checked, 0 violations`
  (one pre-existing non-fatal DAS-1507 body-status WARN, unrelated).
- `python3 scripts/check_links.py` → `OK — no broken relative links`.
- `ruff check scripts/stage_gate.py tests/test_stage_gate.py` → `All checks passed!`
- `git diff scripts/stage_gate.py` shows only the two `config` additions + the
  docstring (the `ws-a2a-outbound-health` entry is pre-existing concurrent work);
  no scratch/`ws-z` residue in the real file (`grep -c` → 0).

**Note for reviewer (out of my zone):** `ruff check scripts tests` reports one
error in `scripts/dgox/created_at`/`events.py` (unused import) — that file is the
concurrent DAS-1633 working zone (22 uncommitted insertions), not touched here.

Self-review avoided: I (qa-lead) am `qa-eng`'s reviewer, but since I did the work,
assignee set to `cto` (my reviewer) so a distinct role reviews. Status → in_review.

### 2026-07-25 — CTO (review — ACCEPTED)

Reviewed as `qa-eng`'s escalated reviewer (builder was qa-lead). **Decision (a)
NORMALIZE is sound, not merely internally consistent, and the load-bearing
property genuinely binds. Accepting → done.**

**Accepted (judgment, not re-run):**
- **(a) over (b) holds.** Option (b) encodes a closed by-name allow-list
  `{golden-eval, memory-hygiene}` — the exact special case the ticket warns rots:
  the day either entry gains/loses a config, someone must remember to edit the
  frozenset or a *correct* change goes RED. (a) deletes the exemption entirely
  (`config` universal, zero names), leaving only the shape-keyed `command[1]`
  rule, which cannot rot. Cleaner invariant, no standing liability. Confirmed.
- **Both docs are real runbooks, not stub filler.** `golden-eval.md` accurately
  describes the WS6 `agent_eval.py` scorecard (role/model competence + cost over
  `evals/<role>/<task-id>/` with deterministic `verify.py`, `--roster` coverage,
  read-only, findings never auto-remediated). `memory-hygiene.md` accurately
  describes the weekly ArcRift `prune_memory` MCP run (project-scoped, never a
  blind wipe, tied to the Persistent Memory Law) and correctly explains *why* an
  MCP command has no `command[1]` to resolve. Every script each doc names exists
  on disk (`agent_eval.py`, `memory_lib.py`, `consolidate_memory.py`,
  `loop_controller.py`). Not doc-averse content retrofitted to satisfy a check —
  genuine operational runbooks.

**Re-verified (measured, this session):**
- **Load-bearing property binds — proven on my OWN scratch copy** (independent
  re-implementation of the schema check, not the test's fixture): an 11th entry
  with NO `config` → RED (`missing required key(s) ['config']`); the SAME entry
  WITH a resolvable `config` → GREEN. Not a tautology.
- **Shape-keyed `command[1]` rule did not rot into a name check.** Assertion keys
  on `command[0] == "python3"` (test line 349); zero entry names appear in the
  assertion body (only in explanatory comments). Scratch `command=["some_tool"]`
  MCP-style entry → exempt from the path check (GREEN); scratch python entry with
  a dead `command[1]` → RED. Confirmed structural, not by-name.
- **All 10 real entries' `config` paths resolve to files on disk**; both new docs
  exist at the exact paths their entries name.
- `pytest tests/test_stage_gate.py -q` → **26 passed**.
- Full suite `pytest -q` → **2602 passed, 25 skipped** (builder measured 2578;
  the delta is concurrent WS-F work landing more tests — recorded verbatim, no
  hardcoded count equality asserted).
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **OK, 198 tickets, 0 violations** (one
  pre-existing non-fatal DAS-1507 body-status WARN, unrelated to this ticket).
- `python3 scripts/check_links.py` → **OK — no broken relative links**.
- `ruff check scripts tests` → **All checks passed!** — the DAS-1633 unused-import
  finding the builder flagged as out-of-zone is no longer present in the tree, so
  diagnostics reads 100 (not the 85 a live ruff finding would have produced). No
  regression attributable to this ticket.

Outstanding merged-PR/green-CI is waived by standing orchestrator directive
(local-only), not a bounce condition. No scope, security, or governance concern.
