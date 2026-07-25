---
id: DAS-1641
title: Correct the remaining cap label-vs-source mismatches and the fail-open rail docstring
status: done
assignee: sre-lead
author: cto
verified_by: sre-lead
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1639]
created: 2026-07-25
updated: 2026-07-25
---

## Description

**Four residuals found by the CTO while reviewing DAS-1639. All pre-existing, none
blocking, all in the same "what the label says vs what the code reads" family that
DAS-1639 just closed for the per-day rail.**

### R1 — another label-vs-source mismatch (the same defect, one file over)

`scripts/kill_switch_drill.py:395-401` reads the **informational** top-level
`caps.per_run` / `caps.per_day` under a comment describing it as "a hard dispatch
ceiling (ADR-0027 SI-5)". That is precisely the mismatch DAS-1639 fixed in
`loop_controller._per_day_budget_exceeded` — a comment naming SI-5 above code reading
the shared informational gate. It enforces nothing today, which is why it is p2 rather
than p1, but a drill that *claims* to check the SI-5 ceiling and reads a different
number is exactly the kind of thing that later gets trusted.

Point it at `mustaqil.caps` (the authority established in DAS-1639: `budgets.yaml:40`
calls the top-level block informational; ADR-0027 SI-5 at `docs/adr/0027-scheduler-safety.md:157-160`
says the heartbeat treats its own caps as the hard ceiling **regardless of the org-wide
gate promotion state**, being by definition *stricter than the shared gate*), or, if
the drill genuinely means to check the shared gate, correct the comment to say so. Do
not leave the label and the source disagreeing.

### R2 — a safety rail whose docstring contradicts its behaviour

`loop_controller._per_day_budget_exceeded`'s docstring says "if in doubt, idle", but
the rail **fails open**: it returns `False` (dispatch NOT withheld) on a missing file,
unparseable YAML, absent `mustaqil:`, absent `caps`, or absent `per_day`.

The fail-open behaviour itself was reviewed and **accepted** in DAS-1639 — the
compensating control is fail-CLOSED (`ws_b_health_check.check_budget_ceiling_drift`
returns `ok=False` on all five of those inputs, and is composed into
`heartbeat_go_no_go`'s FR-004 gate). **Do not change the behaviour here.** Correct the
docstring so a future reader does not rely on a guarantee the function does not make,
and name the compensating control so the layering is discoverable rather than looking
like an oversight.

### R3 — decorative fixture pricing

That helper calls `aggregate_spans(events_path, since=...)` without `budgets_path`, so
tier pricing always resolves from the real config — meaning the `tiers:` block in every
test fixture is decorative and silently ignored. Pre-existing and inert in production,
but a fixture that appears to control pricing and does not will mislead the next person
writing a budget test. Either thread `budgets_path` or drop the misleading `tiers:`
from the fixtures.

### R5 — naming nit

The go/no-go helper is `_si5_cap_note`, not `_si5_line`; earlier tickets and logs cite
the wrong name. Correct where it appears in code comments (board tickets are historical
record — leave those).

**R4 was recorded as a scope note, not work:** the rail no longer binds if the org
block were ever tightened below $15. That is correct as built (SI-5 is the runner's
own stricter ceiling) and is recorded against `docs/design/ws-f-tempo-verification.md:72`.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT change any cap VALUE or widen SI-5/SI-6. Do
NOT change the fail-open behaviour of `_per_day_budget_exceeded` — R2 is a docstring
correction, and altering a reviewed-and-accepted safety-rail behaviour in a p2 cleanup
ticket is exactly the kind of drive-by change this board's review discipline exists to
prevent.

## Acceptance criteria
- [x] R1: `kill_switch_drill.py:395-401` reads the block its comment claims, or the comment is corrected to match what it reads — label and source agree either way, with the choice reasoned in the log.
- [x] R2: the docstring matches actual behaviour (fails open) and names the fail-closed compensating control. Behaviour unchanged — demonstrated, not asserted.
- [x] R3: fixture `tiers:` either made effective (thread `budgets_path`) or removed as misleading.
- [x] R5: `_si5_cap_note` named correctly in code comments.
- [x] `check_heartbeat_readiness.py` still NOT READY (0/3, `active_plan is undeclared`); `kill_switch_drill --smoke` 6 rails green; `DECISIONS` unchanged; no cap value changed.
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-25 — CTO
Found while reviewing DAS-1639 by checking whether the label-vs-source defect it fixed
survived anywhere else — R1 shows it does. Recorded by the orchestrator in the same
run. All four are non-blocking; none was a bounce condition on DAS-1639, which was
accepted.

**Reviewer note (ROUTING):** author is `cto`; at `in_review` this ticket must NOT be
assigned back to `cto`. Route to `sre-lead` (the builder's manager) instead — assigning
to the author trips the no-self-review lint.

### 2026-07-25 — SRE Engineer

Worked all four residuals, local checkout (no worktree per dispatch instructions),
zone-locked to `scripts/` + `tests/` + this ticket. No config/docs touched.

**R1 (`scripts/kill_switch_drill.py::drill_budget_caps`, ~L555-563 in current file —
line numbers shifted from the ticket's 395-401 due to intervening uncommitted work).**
Decision: repointed the read at `mustaqil.caps` rather than just fixing the comment,
because the drill's own intent (per its function docstring, "per-run cap is a hard
ceiling") is unambiguously to check the SI-5 hard ceiling, not the informational
org-wide gate — checking the informational block would make the assertion vacuously
about a number the ADR itself says binds nothing. Changed:
```
real = yaml.safe_load(_REAL_BUDGETS.read_text(...)) or {}
_real_mustaqil_caps = (real.get("mustaqil") or {}).get("caps") or {}
per_run = (_real_mustaqil_caps.get("per_run") or {})
per_day = (_real_mustaqil_caps.get("per_day") or {})
```
(was `real.get("caps")...`), with the comment rewritten to name DAS-1641/R1 and cite
`budgets.yaml:40`'s informational label + ADR-0027 SI-5's "regardless of org-gate
promotion state" language as the authority. Label and source now agree.
Verified: `python3 scripts/kill_switch_drill.py --smoke` →
`pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok` /
`kill-switch-drill: OK — every safety rail held on every pass`, exit 0. Grepped
`tests/` for a pinned `$50`/`$500` on `per_run_ceiling_ok`: none — the only
assertion is `assert r["per_run_ceiling_ok"] is True` (`tests/test_kill_switch_drill.py:359`),
which still holds under the new source ($5/$15 mustaqil values, same
`per_day >= per_run` shape as before).

**R2 (`scripts/loop_controller.py::_per_day_budget_exceeded` docstring).** Rewrote the
"if in doubt, idle" line to state the actual fail-open behaviour verbatim (missing
file / unparseable YAML / absent `mustaqil:`/`caps`/`per_day` / any read-path
exception → returns `False`, dispatch NOT withheld) and named the fail-closed
compensating control `ws_b_health_check.check_budget_ceiling_drift`, composed into
`heartbeat_go_no_go.py`'s FR-004 gate. Zero logic changed — the `try/except` bodies
are byte-identical to before this ticket. `git diff` on this hunk is prose-only (the
one non-docstring line changed in this function is the separate R3 edit below).
Verified: `python3 -m pytest tests/test_loop_controller.py -q -k per_day` → the exact
DAS-1639 per-day suite (`test_per_day_budget_resolves_from_mustaqil_key_not_org_informational_block`,
`test_per_day_budget_reproduces_defect_before_fix_would_have_been_true`,
`test_per_day_budget_true_when_spend_is_today`,
`test_per_day_budget_mixed_days_only_today_counts`,
`test_per_day_budget_boundary_instant_is_included`,
`test_tick_threads_now_once_into_per_day_budget`,
`test_tick_emits_alert_on_per_day_trip`) → `7 passed`, identical to pre-change.

**R3 (`scripts/loop_controller.py::_per_day_budget_exceeded`).** Chose to thread
`budgets_path` through (`aggregate_spans(events_path, budgets_path, since=day_start)`,
was `aggregate_spans(events_path, since=day_start)`) rather than strip `tiers:` from
fixtures — smaller and more correct: it makes `_per_day_budget_exceeded` consistent
with its sibling `_monthly_credit_exhausted`, which already threads `budgets_path`
into its own `aggregate_spans` call two functions below; the asymmetry was itself a
latent inconsistency, and stripping `tiers:` from three fixture files would have
left that asymmetry in place. Confirmed every existing `_per_day_budget_exceeded`
caller in `tests/test_loop_controller.py` already carries a `tiers:` block whose
values mirror real `config/budgets.yaml` pricing, so no test changed outcome — but
`scripts/kill_switch_drill.py::_write_budgets` (used by `drill_budget_caps`, a
production script, not a test) did NOT carry a `tiers:` block and broke on first run
(`SI-5 budget_caps: ok=False, per_day_action='dispatch'` — spend priced at $0 with no
tiers to resolve pricing from). Fixed by adding a `tiers:` block to `_write_budgets`
mirroring real config pricing (opus/sonnet/haiku), with a docstring note explaining
why R3 made this necessary. Re-verified after the fix: `--smoke` green (see R1
evidence above) and the full suite green (below).

**R5.** Grepped `scripts/` and `tests/` for `_si5_line`: zero occurrences. The only
hits repo-wide are in `board/tickets/DAS-1639-*.md` and this ticket's own body — both
historical record, explicitly out of scope per the ticket text. No code comment
needed correction; `_si5_cap_note` (`scripts/heartbeat_go_no_go.py:227`) is already
named correctly everywhere in code.

**Verification (verbatim, all run from repo root):**
- `python3 scripts/kill_switch_drill.py --smoke` → exit 0, 6/6 rails ok (shown above).
- `python3 scripts/check_heartbeat_readiness.py` → exit 1, `VERDICT: NOT READY`,
  `0/3 consecutive clean day(s)`, `mustaqil.monthly_credit_ceiling.active_plan is
  undeclared` — unchanged blockers, no cap value touched.
- `python3 scripts/heartbeat_go_no_go.py` → exit 1, `VERDICT: NO-GO`.
- `python3 -m pytest -q` (full repo suite) → `2612 passed, 25 skipped`, 0 failed.
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`.
- `python3 scripts/board_lint.py` → `OK — 200 ticket(s) checked, 0 violations` (1
  pre-existing non-fatal WARN on DAS-1507, unrelated to this ticket).
- `ruff check scripts tests` → `All checks passed!`.
- `git diff config/*.yaml` — non-empty, but every line in it predates this ticket
  (pre-existing uncommitted DAS-1607..1626 A2A/WS-F work already in the working
  tree per `git status` at session start); I made zero edits under `config/`.
- `board/.events.jsonl` and `board/.metrics-history.jsonl`: both absent (`ls`
  confirms `No such file or directory` for both) — untouched.
- No hardcoded suite-count equality added anywhere in my edits.

Files touched: `scripts/loop_controller.py` (`_per_day_budget_exceeded`: docstring
rewrite for R2 + `budgets_path` threaded into `aggregate_spans` for R3),
`scripts/kill_switch_drill.py` (`drill_budget_caps` read-source + comment for R1;
`_write_budgets` fixture gained a `tiers:` block as a consequence of R3). No new
files, no worktree, no commit (local-only, per dispatch constraints).

Setting `status: in_review`, `assignee: sre-lead` (my reviewer per ROUTING; author
`cto` excluded per the reviewer note above).

### 2026-07-25 — SRE / DevOps Lead (review)

ACCEPT. Reviewed as builder's manager (author `cto`, so no-self-review routed the
review to me). All four residuals hold; no bounce condition. Local checkout, read-only
git, zero edits outside this ticket file + the ArcRift outbox.

**Re-verified independently (not merely re-read the builder's claims):**

- **R1 — read-source repointed to `mustaqil.caps`, and the assertion is NOT vacuous.**
  `drill_budget_caps` now reads `real["mustaqil"]["caps"]` and the comment agrees with
  the source. Seeded three violating cases against a scratch-loaded copy of the real
  config using the exact `per_run_ok` expression from the drill:
  `mustaqil.caps.per_run` removed → `per_run_ok=False`; `per_day.max_cost_usd < per_run`
  → `False`; whole `mustaqil:` block absent → `False` — **whereas the OLD top-level
  read (`caps.per_run`) would have returned True on that same input**. So the drill now
  fails red exactly when the SI-5 ceiling is absent/malformed, which is precisely the
  defect the top-level read masked. Real config → `True`. `--smoke` = 6 rails green,
  exit 0. The pinned assertion `assert r["per_run_ceiling_ok"] is True`
  (`tests/test_kill_switch_drill.py:359`) is backed by all four real `mustaqil.caps`
  fields (per_run 2M/400K/$5, per_day $15), not a hardcoded number.

- **R2 — docstring truthful, behaviour unchanged, no control-flow byte smuggled in.**
  The fail-open limbs (`except Exception: return False` on the cap read and on the
  ledger read, plus `if cap_usd <= 0: return False`) are intact; the only executable
  delta attributable to this ticket in `_per_day_budget_exceeded` is the R3
  `budgets_path` argument (below) — everything else in the function is accepted
  DAS-1639/DAS-1632 windowing work already in the working tree. The docstring's named
  compensating control is REAL and WIRED, not a plausible-sounding reference: verified
  `ws_b_health_check.check_budget_ceiling_drift` returns `ok=False` on a missing file,
  YAML parse error, absent `mustaqil:`, and missing `caps`/window/field
  (`scripts/ws_b_health_check.py:171-195`), and `heartbeat_go_no_go.py` composes it into
  the FR-004 gate (go/no-go output attributes the credit-ceiling gate to
  `ws_b_health_check.py :: check_budget_ceiling_drift`). Per-day suite `7 passed`,
  identical to the builder's run.

- **R3 — correction, not mask; fixture NOT tuned-to-pass.** Compared the `_write_budgets`
  `tiers:` block against real `config/budgets.yaml` line-for-line: opus 5.00/0.50/25.00,
  sonnet 3.00/0.30/15.00, haiku 1.00/0.10/5.00 — an EXACT mirror of the real SSOT
  pricing (only the irrelevant `model_id` is omitted). Not fitted to force a green.
  Threading `budgets_path` into `aggregate_spans` is a pure production no-op:
  `budgets_path` is a pricing-only param (`since` windowing is separate), and in
  production the rail is passed the real `config/budgets.yaml`, which is exactly
  `aggregate_spans`' default `_BUDGETS_PATH` — so tier resolution is byte-identical to
  before. It only gives a caller-supplied fixture path a say it silently lacked, and
  matches the sibling `_monthly_credit_exhausted` which already threaded it.

- **R5 — no code change needed and none made.** `_si5_cap_note` is correct everywhere
  in code (`heartbeat_go_no_go.py:227`); `_si5_line` survives only in historical ticket
  bodies, correctly left as record.

**Accepted (builder judgement I concur with, not independently re-derived):** the choice
to repoint the R1 read (vs correct the comment) and to thread `budgets_path` (vs strip
`tiers:`) — both are the more-correct, lower-asymmetry option and align the rail with
`config/budgets.yaml:40`'s informational label + ADR-0027 SI-5's "stricter than the
shared gate, regardless of org-gate promotion" authority. R4 correctly left as a scope
note.

**Verification battery (verbatim, repo root, read-only):**
- `kill_switch_drill.py --smoke` → exit 0, `SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok`.
- `check_heartbeat_readiness.py` → exit 1, `VERDICT: NOT READY`, `0/3 consecutive clean
  day(s)`, `mustaqil.monthly_credit_ceiling.active_plan is undeclared` — blockers
  unchanged, no cap value touched.
- `heartbeat_go_no_go.py` → exit 1 (read directly), `VERDICT: NO-GO`.
- per-day subset (`-k per_day`) → `7 passed, 37 deselected`.
- `test_kill_switch_drill.py` → `62 passed`.
- WS-F composite (`test_heartbeat_go_no_go` + `test_check_heartbeat_readiness` +
  `test_loop_controller` + `test_kill_switch_drill` + `test_ws_b_health_check`) →
  `185 passed`.
- full repo suite (`pytest -q`) → `2612 passed, 25 skipped`, 0 failed.
- `diagnostics.py` → `SCORE = 100/100`.
- `board_lint.py` → `OK — 200 ticket(s) checked, 0 violations` (1 pre-existing non-fatal
  WARN on DAS-1507, unrelated).
- `ruff check scripts tests` → `All checks passed!`.
- `git diff --stat config/budgets.yaml` → empty; the four modified `config/*.yaml`
  (features/rbac/risk_taxonomy/tenant_boundary) are all pre-existing A2A/WS-F working-tree
  work, none touched by this `zone: scripts` ticket. No cap VALUE changed; SI-5/SI-6
  not widened; `heartbeat_enabled` not flipped.
- No hardcoded suite-count equality in any edited file.

**Outstanding by orchestrator directive (NOT a bounce):** merged-PR / green-CI is
waived for this local-only run — no `git push`/PR was made or expected. Moving to
`status: done`, `verified_by: sre-lead`. Acceptance criteria confirmed (all boxes hold
against re-verified evidence above).
