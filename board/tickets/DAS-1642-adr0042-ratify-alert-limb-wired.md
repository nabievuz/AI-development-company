---
id: DAS-1642
title: Update ADR-0042 to record the SI-5 alert limb as wired now that DAS-1634 landed
status: done
assignee: ceo
verified_by: ceo
author: sre-lead
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: docs/adr
depends_on: [DAS-1634]
created: 2026-07-25
updated: 2026-07-25
---

<!-- REVIEW CLOSED — CEO (governance/ADR-accuracy review). ADR-0042 now matches the shipped code in both directions: not overstated (in-band emission, sink deferred to DAS-1643), not understated (severity info / metric SI-5 / byte-identical dispatch / closed decision alphabet). See the CEO log entry below. -->


## Description

**Routed by the SRE Lead from the DAS-1634 review. A doc-vs-code drift — the exact
class this run has spent itself closing.**

ADR-0042 (`docs/adr/0042-adr0027-addendum-monthly-credit-ceiling.md`) was written when
the SI-5 alert limb did not exist. Its §Reconciliation row 3 and its §Consequences
record the "idle + alert" contract with the **alert half as an OPEN RESIDUAL** —
"the shipped code idles but does not alert." DAS-1634 has now wired that limb
(`alerting.sanctioned_pause_alert`, emitted from `loop_controller.tick()`, severity
`info`/metric `SI-5`, byte-identical dispatch, reviewed and `done`).

So the ADR now understates the code: it says a limb is missing that is present. Left
alone, a future reader treats a closed residual as open — and worse, the whole point
of ADR-0042 was to make the contract match the code, so an ADR that trails its own
subject is self-defeating.

**Ratify the limb as wired.** Update the Reconciliation row and the Consequences note
to record that both halves of SI-5's "idle + alert" now exist and are verified, citing
DAS-1634. This is a CTO act (ADR ratifier).

**Verify against the shipped code, not this ticket text** — read
`scripts/alerting.py::sanctioned_pause_alert` and the `tick()` call site, confirm the
severity/metric and the byte-identical-dispatch property hold as described, and record
what you checked. If DAS-1634's implementation differs from what you are about to write,
the ADR records the SHIPPED behavior, or the discrepancy is routed back — the ADR never
documents an intent the code does not implement (the same discipline that governed the
original DAS-1630 ratification).

**Do NOT overstate it either.** The persistence residual (nothing routes the alert to a
monitored sink outside `tick()`) is REAL and separately ticketed as DAS-1643 — the ADR
should note the alert is emitted in-band on the tick surface and that a persistent sink
is deferred (DAS-1643), not claim end-to-end delivery. Accuracy in both directions.

Preserve ADR-0042's `Accepted` status and its SI-5.1…SI-5.6 clause numbering; do not
renumber or supersede.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT edit `scripts/` or `config/` — this is a
`docs/adr` prose update only. **No git state mutation.**

## Acceptance criteria
- [x] ADR-0042 Reconciliation row 3 + Consequences updated to record the SI-5 alert limb as wired and verified, citing DAS-1634.
- [x] The claim verified against `scripts/alerting.py` + the `tick()` call site (severity/metric + byte-identical dispatch), with what was checked recorded — not restated from this ticket.
- [x] The persistence residual (DAS-1643) noted as deferred rather than the ADR claiming end-to-end delivery.
- [x] `Accepted` status + SI-5.1…SI-5.6 numbering preserved; no supersession.
- [x] `check_links.py`, `check_spec_consistency.py`, `board_lint` green; `diagnostics.py` 100/100; no `project:` field (R9).

## Log
### 2026-07-25 — SRE / DevOps Lead
Routed from the DAS-1634 review close: with the alert limb wired, ADR-0042's
"open residual" record for SI-5's alert half is now stale. Recorded by the
orchestrator in the same run. A `docs/adr` edit and an ADR-ratification act, so
routed to the CTO rather than resolved by SRE.

**Reviewer note (ROUTING):** author is `sre-lead`; at `in_review` this must route to
the CTO's reviewer, NOT back to `sre-lead`. (Since the CTO is the natural author of an
ADR edit, if the CTO ends up doing the work, the reviewer is the CEO per ROUTING —
whoever the orchestrator dispatches, keep author ≠ reviewer to avoid the self-review lint.)

### 2026-07-25 — CTO
Ratified the SI-5 alert limb as WIRED against the SHIPPED code (not this ticket text
or DAS-1634's report), then updated ADR-0042 to close the stale open-residual record.

**What I checked the ADR text against (verbatim, shipped code):**
- `scripts/alerting.py::sanctioned_pause_alert` (line 219) — signature
  `(per_day_budget_exceeded, monthly_credit_exhausted) -> dict | None`; returns
  `None` when neither rail is tripped; on a trip returns `{"severity": "info",
  "metric": "SI-5", "message": …}`. Severity `info` sits OUTSIDE `ANOMALY =
  {warning, critical}`, so `filter_quiet` / `--fail-on-critical` never see it. Uses
  the same `severity`/`metric`/`message` dict shape as `evaluate_alerts` — no second
  notifier schema. Confirmed severity=`info`, metric=`SI-5`.
- `scripts/loop_controller.py::tick()` — `decision` is computed at lines ~484–498
  (`route_from_store(...)`); the alert is computed AFTER, lines ~516–520, via a lazy
  `import alerting` then `alerting.sanctioned_pause_alert(budget_exceeded,
  credit_exhausted)`, wrapped in `try/except → alert = None` (failure-isolated). It
  is added to the result dict as `result["alert"]` ONLY (line 532). It reads the same
  two booleans `route_from_store` already consumed and never feeds back into
  `decision` — observation-only; the dispatch decision is byte-identical with or
  without the alert. It covers BOTH rails (per-day cap + monthly ceiling).
- `scripts/flow_router.py` — `DECISIONS = frozenset({DISPATCH, VALIDATE, IDLE})`
  (line 93) = exactly `{dispatch, validate, idle}`. The alert added NO fourth
  decision; §SI-5.3's closed alphabet is intact.
- `_print_tick` (line 572–574) prints `result["alert"]` in-band on the tick surface.
  Confirmed there is NO routing to a monitored sink outside `tick()` — the persistence
  residual is REAL and is recorded as deferred to DAS-1643, NOT claimed as end-to-end
  delivery.

No discrepancy found → nothing routed back to DAS-1634; the ADR records the shipped
behavior. Edits (docs-only, zone `docs/adr`): (1) Reconciliation row 3 rewritten from
"open residual" to "limb WIRED and verified (DAS-1634), recorded by DAS-1642", in-band
emission stated, persistent sink deferred (DAS-1643); (2) Consequences "Negative /
accepted" residuals bullet updated the same way; (3) `docs/adr/README.md` ledger row 51
residual list updated (the README explicitly listed the unwired limb, so keeping it
accurate is required, not an invented change). `Accepted` status and SI-5.1…SI-5.6
numbering preserved; nothing superseded or renumbered; no clause rewritten.

**Verification (verbatim):** `check_links.py` → `OK — no broken relative links`;
`check_spec_consistency.py` → `OK: 10 SPEC.md file(s) checked … consistent`;
`board_lint.py` → `OK — 200 ticket(s) checked, 0 violations` (one pre-existing non-fatal
WARN on DAS-1507, unrelated); `diagnostics.py` → `SCORE = 100/100`. My change is
docs-only; the concurrent DAS-1641 edit in `scripts/` did not perturb the score at
measurement time.

Set `status: in_review`; assigned to `ceo` per ROUTING (author is `sre-lead`, and the
CTO did the work — author ≠ reviewer, avoids the self-review lint).

### 2026-07-25 — CEO
Governance/ADR-accuracy review as reviewer (CTO authored the edit; not self-review).
The review question: does ADR-0042 now state exactly what the shipped code does — no
more, no less. Verdict: **APPROVED → done.** ADR-0042 matches the shipped code.

**Re-verified against the source myself (did NOT take the CTO log at face value):**
- `scripts/alerting.py::sanctioned_pause_alert` (l.219) — signature `(per_day_budget_exceeded,
  monthly_credit_exhausted) -> dict | None`; `None` when neither rail trips; on a trip returns
  `{"severity": "info", "metric": "SI-5", "message": …}`, same `severity`/`metric`/`message`
  shape as `evaluate_alerts` (no second notifier). `ANOMALY = {"warning","critical"}` (l.68) —
  `info` is outside it, so `filter_quiet`/`--fail-on-critical` never see it. Covers BOTH rails.
  Confirms the ADR's severity `info` / metric `SI-5` claim.
- `scripts/flow_router.py` — `DECISIONS = frozenset({DISPATCH, VALIDATE, IDLE})` (l.93) = exactly
  `{dispatch, validate, idle}`. No fourth action added; §SI-5.3's closed alphabet intact.
- `scripts/loop_controller.py::tick()` — `decision = route_from_store(...)` computed first
  (~l.501-513), THEN `alert = alerting.sanctioned_pause_alert(budget_exceeded, credit_exhausted)`
  (l.536), reading the SAME two booleans `route_from_store` consumed, wrapped `try/except → alert
  = None` (failure-isolated). Byte-identical dispatch holds — alert never feeds back into
  `decision`. Added to the result dict as `result["alert"]` ONLY (l.550). `_print_tick` prints it
  in-band on the tick surface (l.590-592).
- **Overstatement check (the one the ticket exists to prevent):** a repo-wide grep for the alert
  (`sanctioned_pause_alert` / `result["alert"]`) returns exactly TWO consumers — the compute site
  (l.536) and the print site (l.590). NOTHING routes it to a sink outside `tick()`. The ADR's
  "emitted in-band, persistent sink deferred (DAS-1643), NOT end-to-end delivery" is therefore
  exactly true — no "delivered" / "operators are alerted" language anywhere in the edited text.
- `board/tickets/DAS-1643-*.md` exists, `status: backlog`, and the ADR cites it in Reconciliation
  row 3, the Consequences residuals bullet, and README row 51. Residual honestly carried, not dropped.
- ADR integrity: `Accepted` intact (l.3, l.301); SI-5.1…SI-5.6 all present and unrenumbered;
  "supersedes nothing"; only Reconciliation row 3 + Consequences + README row 51/theme prose changed.
  (ADR-0042 is an untracked new file, so there is no committed baseline to `git diff`; verified by
  reading the full file. The README `git diff` also shows the concurrent DAS-1607+ A2A row 0040 /
  theme-range edits — not this ticket's, additive, no bearing on ADR-0042 accuracy.)

**Accepted without independent re-derivation (recorded honestly):** the AADL/RACI framing of the
CTO's ratification act itself, and the correctness of the SI-5.1/SI-5.2/SI-5.5/SI-5.6 clauses that
DAS-1642 did not touch (out of scope for this alert-limb review; owned by the DAS-1618 ratification).

**Validators (verbatim, re-run):** `check_links.py` → `OK — no broken relative links`;
`check_spec_consistency.py` → `OK: 10 SPEC.md file(s) checked … consistent`; `board_lint.py` →
`OK — 200 ticket(s) checked, 0 violations` (1 pre-existing non-fatal WARN on DAS-1507, unrelated);
`diagnostics.py` → `SCORE = 100/100`. Docs-only ticket (zone `docs/adr`) — no bearing on the
ruff/scripts dimension, so the concurrent DAS-1641 scripts edit could not regress it.

Set `status: done`, added `verified_by: ceo`. ADR-0042 now matches the shipped code.
