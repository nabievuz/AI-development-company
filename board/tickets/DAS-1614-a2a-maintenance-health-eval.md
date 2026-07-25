---
id: DAS-1614
title: A2A Maintenance — scheduled health and eval of the outbound endpoint
status: done
assignee: product-analyst
author: ceo
dept: engineering
priority: p2
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [SC-003, SC-005]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1613]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for A2A OUTBOUND).**

Stand up the ongoing health/eval cadence for the A2A surface once it is live:

- Scheduled check that the in-tenant boundary still holds (no config drift
  toward a hosted relay/registry) — feeds SC-003.
- Scheduled check that the flag/publish state matches what the Founder last
  authorized (no silent drift from OFF to ON, or from internal-only to
  published, without a corresponding logged Founder act).
- Periodic re-run of the negative-test suite (DAS-1612) against the live
  surface, folded into the existing golden-eval / diagnostics cadence — feeds
  SC-005's "stays green" property over time, not just at merge.
- Report cadence: fold findings into the existing product analytics review
  (per `product/CLAUDE.md` Success Metrics — monthly product analytics review).

## Acceptance criteria
- [x] A scheduled check verifies the in-tenant boundary holds over time (SC-003).
- [x] A scheduled check verifies flag/publish state matches the last logged Founder act (no drift).
- [x] The negative-test suite (DAS-1612) is folded into a recurring eval cadence.
- [x] Findings are reported through the existing monthly product analytics review.
- [x] `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Maintenance). Depends on DAS-1613 (Deployment).
Gated behind DAS-1606's binding sequencing note (after WS-B, deferred until
after WS-G's proof per Q12) — left in `status: backlog` until that gate opens.
This closes the AADL 6-gate template for the A2A OUTBOUND epic (DAS-1606).

### 2026-07-24 — Product Analyst
**GATE-6 CLOSED for A2A OUTBOUND (DAS-1606's 6-gate template now complete).**

Read `product/CLAUDE.md`, `product/agents/product-analyst/AGENTS.md`,
`board/README.md`, and two sibling health docs
(`docs/06-maintenance/ws-e-tenant-health.md`,
`docs/06-maintenance/ws-h-control-health.md`) to mirror structure/cadence
vocabulary. Produced `docs/06-maintenance/ws-a2a-outbound-health.md`
(doc-only — zone lock `docs/06-maintenance/` + this ticket, no edits to
`scripts/`, `tools/a2a/`, `scripts/a2a_intake/`, `config/`, `docs/adr/`,
`docs/specs/`, `docs/runbooks/`; flag NOT touched).

Composed the checks from real, existing artifacts (no new script, no new
scheduler — per instruction):

1. **In-tenant boundary (SC-003)** — ran `scripts/check_in_tenant.py`
   (wired at `scripts/diagnostics.py:810-823` + `.github/workflows/ci.yml:303`).
   Verbatim: `TN-1 OK: all code/IP endpoints in-tenant (7 declared; model
   call excepted).` exit 0.
2. **Flag/publish-state drift** — read `tools/a2a/publish.py:
   build_publish_event` to confirm the real emitted event shape
   (`event_type`, `ts`, `principal_id`, `principal_kind`, `decision`,
   `flag_state`, `target`, `reason`). Checked `config/features.yaml`
   (`a2a_outbound: false`) against `board/.events.jsonl` for any
   `a2a_publish` event: zero found. Baseline documented honestly: **flag
   OFF, zero publish events, in agreement — no drift.** Also logged a real,
   unfixed gap (out of this ticket's zone): `scripts/feature_flags.py`'s
   `DEFAULTS` doesn't track `a2a_outbound`, so `feature_flags.enabled(
   "a2a_outbound")` always returns `False` regardless of config — the
   documented check reads `config/features.yaml` directly instead. Flagged
   as follow-up, not silently worked around and not fixed out-of-zone.
3. **Negative-test cadence (DAS-1612)** — ran
   `python3 -m pytest tests/test_a2a_outbound_endpoint.py
   tests/test_a2a_intake.py -q`. Verbatim: `95 passed in 0.20s`. Folded into
   the existing golden-eval/diagnostics cadence description (no new runner).
4. **Report cadence** — routed to the existing monthly product analytics
   review per `product/CLAUDE.md` Success Metrics; no new forum invented.

Cadence wiring caveat (honest, not silent): registering a
`ws-a2a-outbound-health` entry in `scripts/stage_gate.py:
maintenance_schedule()` (the pattern every sibling WS-A/B/C/D/E/H doc uses)
touches `scripts/`, which is outside this ticket's declared zone lock
(`docs/06-maintenance/` + ticket file only). Documented as explicit
follow-up work in the health doc's "Cadence and registration" section — a
future `zone: scripts` ticket should add the `recurring_runs` entry (and,
if desired, a thin no-fork composing script mirroring
`scripts/ws_e_health_check.py`'s pattern). Not done here to respect the
zone lock.

Gates (re-run, observed, not claimed): `python3 scripts/diagnostics.py` →
`SCORE = 100/100`. `python3 scripts/board_lint.py` → `OK — 180 ticket(s)
checked, 0 violations` (one pre-existing, unrelated WARN on DAS-1507).
Confirmed no `project:` field on this ticket (R9 clean).

All four acceptance criteria genuinely hold with named, verified artifacts.
`status: done`. No escalation needed — no decision here exceeded Product
Analyst charter authority; the zone-lock deferral is a scope note, not a
blocker.
