# ADR 0099 — Adopt a quarterly board-minutes cadence for cross-dept escalations

**Status:** Proposed
**Date:** 2026-07-04
**Scope:** Governance / board process
**Relates:** `governance/policies/raci.md`, `board/README.md`

## Context

Cross-department escalations (an issue above one C-suite's charter authority) currently
have no fixed cadence for board review — they are handled ad hoc whenever the Chairman
notices them in a ticket log. This has caused escalations to sit unacknowledged for
multiple waves with no visible SLA.

## Enforcement / acceptance

Once ratified, `/daslab-cycle` will refuse to leave an `status: blocked` escalation
ticket unresolved past one quarter without a board-minutes entry citing this ADR.
