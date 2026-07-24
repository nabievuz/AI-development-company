---
id: DAS-1595
title: WS-G Deployment — ship the proof to the tenant VM (BLOCKED external)
status: blocked
assignee: sre-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1588
goal: mustaqil-ws-g-proof
spec: 007-mustaqil-ws-g-proof
implements: [FR-006]
stage: GATE-5
labels: [governance]
zone: docs/runbooks
depends_on: [DAS-1594]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for WS-G).** Deliver the "shipped" bar for
the proof (Q7). SRE Lead accountable; Security Lead + Legal consulted.

- **FR-006/Q7:** "shipped" = merged to `main` + green CI + **deployed to the tenant VM**
  (one Linux VM, discovery Q2). Record the deploy runbook and the deploy evidence.
- The completed proof deploy is the final dimension of the 0→100 evidence trail —
  committed + hash-chained (DAS-1592).
- Record the deploy decision + evidence; a committed wave attestation (ADR-0031/0032).

**BLOCKED — external dependency.** There is **no provisioned tenant VM in this session**
(Q2 self-host infra is not stood up here). The deploy-to-VM step MUST NOT be skipped,
faked, or reported green (FR-006 / ADR-0020) — it is carried as `blocked` with this
precise reason until a tenant Linux VM is provisioned. Unblock condition: a reachable
in-tenant Linux VM + the Founder's go-ahead to deploy.

## Acceptance criteria
- [ ] Deploy runbook complete (`docs/runbooks/`): build, deploy-to-VM, health-check, rollback.
- [ ] Proof deployed to the tenant VM; deploy evidence recorded; final 0→100 evidence dimension committed + attested.
- [ ] "Shipped" bar met = merged + green CI + deployed to the VM (FR-006).
- [ ] Committed wave attestation; `diagnostics.py` 100/100; merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-G Deployment, GATE-5). status: **blocked** — external
dependency: no provisioned tenant VM in this session (Q2). Per FR-006 / ADR-0020 the
deploy-to-VM step is never faked or skipped; it waits as `blocked` with this reason
until a tenant Linux VM exists + the Founder approves the deploy. Not auto-dispatched
(external-dependency block).

## Blocking conditions (GATE-3 residual — CTO, DAS-1592)

**MUST-DO before a real 0→100 delivery can certify `verdict: complete`.** The WS-G evidence
gate (`scripts/check_evidence_gate.py`, DAS-1592) is intentionally **fail-closed** on three of
its six ED-1 dimensions. As of the GATE-3 re-closure (CTO, 2026-07-24) it can reject every known
forgery but cannot yet ACCEPT a true delivery: D1 `aadl_gates_closed`, D4 `diagnostics_100`, and
D5 `golden_eval` are re-measured only from the delivery's self-authored `fixtures/` directory,
for which no independently-committed, hash-chained anchor exists — so a re-measured `pass` for
these three is downgraded to `skipped` (ADR-0020: unattested is never green), making
`verdict: complete` UNREACHABLE via this gate until this condition is met.

This is genuinely part of THIS deploy (the first real receipt this ticket writes). Before the
proof can report a genuine `complete`:

1. **Extend the attested evidence chain to record the three facts.** Extend the wave attestation
   / `scripts/snapshot_evidence.py` (`build_run_evidence`) — which today carry only
   counted-completion + chain-integrity data — to also record and attest the proof delivery's
   real **diagnostics score**, **AADL gate-closure state**, and **golden-eval result** into the
   tamper-evident `metrics/evidence/<run_id>.json` + `WaveAttestation` chain. This is a
   `wave_runner.py`/`snapshot_evidence.py` change (out of DAS-1592's file scope, by design).
2. **Corroborate D1/D4/D5 against that anchor (Option A).** Update `check_evidence_gate.py` to
   corroborate D1/D4/D5 against the committed, attested facts from (1) instead of downgrading a
   fixtures-only `pass` to `skipped` — remove/retire the `_UNCORROBORATED_CLAIM_DIMENSIONS`
   downgrade once, and only once, a trustworthy anchor exists to check the positive claim against.
3. **Regression:** a genuine all-pass delivery backed by the attested anchor MUST reach
   `verdict: complete` (rc 0); a delivery whose `fixtures/` claim disagrees with the attested
   anchor MUST still be rejected. Both forges DAS-1592 killed (self-report; plausible-but-
   unattested fixtures) MUST stay dead.

Until (1)+(2) land, the gate stays fail-closed — this is the accepted honest-empty trade
(ADR-0020), not a regression: `ws_g_proof` is OFF by default and this deploy is itself
infra-gated, so nothing depends on reaching `complete` before this condition is satisfied.
