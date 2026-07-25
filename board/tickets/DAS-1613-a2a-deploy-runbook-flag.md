---
id: DAS-1613
title: A2A Deployment — runbook, flag stays OFF on merge, publish is a Founder act
status: done
assignee: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-003, FR-006]
stage: GATE-5
labels: [security]
zone: docs/runbooks
depends_on: [DAS-1612]
created: 2026-07-24
updated: 2026-07-24
verified_by: sre-lead
---

## Description

**AADL Stage 5 — Deployment (closes GATE-5 for A2A OUTBOUND).**

- Write the A2A outbound runbook: how the endpoint is deployed, how the
  `a2a_outbound` flag is checked, how to roll back (disable the flag / remove
  the endpoint wiring — no residual dispatch-behavior change).
- Confirm on merge: `a2a_outbound` stays OFF (FR-006) — this deployment does NOT
  flip it. The endpoint existing in the codebase, flag OFF, changes no dispatch
  or board behavior (byte-identical, SC-005).
- Document the **publish-is-a-Founder-act** procedure explicitly (FR-003): what
  a Founder does to flip `a2a_outbound` ON, what gets logged to
  `board/.events.jsonl`, and that this runbook step is never executed by an
  agent on its own initiative.
- Confirm the in-tenant boundary check (DAS-1609/DAS-1610) is wired into CI/
  diagnostics so a future misconfiguration toward a hosted relay fails closed.

## Acceptance criteria
- [x] Runbook exists (`docs/runbooks/`) covering deploy, flag-check, and rollback for the A2A endpoint.
- [x] `a2a_outbound` confirmed OFF at merge time; dispatch/board behavior byte-identical to pre-merge (SC-005).
- [x] The publish-is-a-Founder-act procedure is documented, including the exact `board/.events.jsonl` log shape (FR-003).
- [x] The in-tenant boundary check is wired into CI/diagnostics.
- [x] `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9). Merge/CI leg = the orchestrator's commit at workstream close (LOCAL-ONLY run; no push/PR from this session).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Deployment). Depends on DAS-1612 (Testing).
Gated behind DAS-1606's binding sequencing note (after WS-B, deferred until
after WS-G's proof per Q12) — left in `status: backlog` until that gate opens.
`stage: GATE-5` set per board convention for the deployment-stage child.

### 2026-07-24 — SRE / DevOps Lead
**REVIEW of sre-eng's build → GATE-5 CLOSED for A2A OUTBOUND (flag OFF).** I am
the reviewer, not the builder. Every AC verified independently against the real
artifacts; all numbers below are observed output, not claims.

**AC1 — runbook.** `docs/runbooks/ws-a2a-outbound.md` present and substantive:
deploy (3-step Founder sequence, in-tenant bind first), flag-check, publish
procedure, TN-1/CI wiring, and rollback. Rollback is a genuine single reversible
step (flip `a2a_outbound: false`, already the default) plus an independent
structural lever (remove the module); `is_enabled()` fails safe to OFF, so a
broken config cannot turn the surface on.

**AC2 — flag OFF + SC-005 byte-identical.** `config/features.yaml:29` reads
`a2a_outbound: false`. **I did not touch it** (Founder-only act, QONUN-5/FR-003).
Verified byte-identity by reading the consumer call sites, not by assertion:
`grep -rn "tools/a2a\|tools\.a2a"` over the repo returns **no non-test importer**
— hits are only `tools/a2a/*` self-references and `tests/*`. The sole production
mention of "a2a" outside `tools/a2a` + `scripts/a2a_intake` is `scripts/rbac.py:65`,
where `a2a.publish` is a *permission-name string* in `FOUNDER_ONLY` — not a
dispatch path. No `/daslab-cycle` skill or workflow references the endpoint.
Independently, `handle_call`'s flag check (endpoint.py:288) returns `UNAVAILABLE`
*before* any TN-1 check, admission call, or `_append_event` — flag OFF appends
nothing to `board/.events.jsonl`.

**AC3 — publish-is-a-Founder-act + exact event shape.** Documented shape matches
the emitter exactly. Ran `publish()` live against a scratch ledger for two deny
paths; emitted keys were verbatim
`['decision','event_type','flag_state','principal_id','principal_kind','reason','target','ts']`
— identical to `build_publish_event` (publish.py:136-145) and to the runbook's
JSON block. Both fail-closed legs proven live:
- `decide("agent:sre-eng","a2a.publish")` -> `deny`; `decide("orchestrator",...)`
  -> `deny`; `decide("founder",...)` -> `allow`.
- Refuse-to-load lock: a tampered COPY granting `a2a.publish` under
  `grants.audit-team` raised `RbacConfigError: STRUCTURAL VIOLATION: founder-only
  permission 'a2a.publish' granted to non-founder kind 'audit-team' — refusing to
  load (fail-closed, QONUN-5)`. (First attempt at this tamper landed in the wrong
  YAML block and appeared to pass — re-ran correctly rather than report a false
  defect. Real `config/rbac.yaml` untouched: `git status` clean vs index.)
- TN-1 leg refuses a hosted target even for a genuine `founder` principal
  (`TN-1 BLOCK: publish target 'https://relay.example.com' resolves to an EXTERNAL host`).

**AC4 — TN-1 wired into CI/diagnostics, fails closed.** `scripts/diagnostics.py:810-823`
runs `check_in_tenant.py` unconditionally as the `tn1-in-tenant-boundary` gate;
`.github/workflows/ci.yml:303` runs `diagnostics.py`. Proven fail-closed on a
scratch COPY with the A2A bind repointed at a hosted relay:
`TN-1 FAIL: ... a2a_outbound (role=a2a) resolves to an EXTERNAL host:
https://a2a-relay.example.com`, **exit=1** — which forces the diagnostics gate
red (100/100 unreachable). Real `config/tenant_boundary.yaml` untouched.

**AC5 — gates re-run by me, verbatim:**
- `python3 scripts/diagnostics.py` -> `SCORE = 100/100`, `[PASS] Security 10/10`
  incl. `ok tn1-in-tenant-boundary`.
- `python3 scripts/check_in_tenant.py` -> `TN-1 OK: all code/IP endpoints in-tenant
  (7 declared; model call excepted).` exit=0
- `python3 scripts/board_lint.py` -> `OK — 180 ticket(s) checked, 0 violations.`
  (1 pre-existing non-fatal WARN on DAS-1507, unrelated to this ticket.)
- `python3 scripts/check_never_auto_approve.py` -> `OK: 182 tickets checked, no
  never-auto-approve violations.`
- `pytest tests/test_a2a_outbound_endpoint.py tests/test_a2a_intake.py -q` ->
  **95 passed in 0.20s** (matches QA Lead's GATE-4 count).

**AC6 — R9.** No `project:` field on this ticket; board_lint 0 violations confirms.

**One defect found and fixed (not papered over).** The runbook's FR-003 section
said the `a2a_call` type had "five possible outcomes" and then listed **six**,
wrongly including `unavailable`. Verified against the code: exactly **5**
`_append_event` call sites, and `unavailable` emits **no** event — so the list
directly contradicted the SC-005 guarantee stated two sections earlier in the
same file. Corrected the passage to name the five logged outcomes and to state
explicitly that `unavailable` emits nothing *by design*. Reviewer-side precision
fix to this ticket's own artifact; no GATE-1..GATE-4 work re-authored.

**GATE-5 semantics.** "Deployment" here = runbook + flag-OFF merge readiness
complete and the Founder flip procedure documented. **Nothing is exposed**; the
flag stays `false`. This is the same posture WS-C / WS-E / WS-H closed GATE-5
under, so closing it is not a never-auto-approve violation — and the ticket did
NOT ask me to perform the Founder act itself. I did not flip any flag.

Status `in_review` -> `done`. Merge/CI leg belongs to the orchestrator's
workstream-close commit (LOCAL-ONLY session: no commit, push, PR, or worktree).
