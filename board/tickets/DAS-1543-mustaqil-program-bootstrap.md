---
id: DAS-1543
title: MUSTAQIL program bootstrap — budgets, feature-flag scaffold, TN-1 check
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1541
goal: mustaqil-prep-retrieval-adr
labels: [governance]
zone: config
created: 2026-07-23
updated: 2026-07-24
---

## Description

Lay the program scaffolding every workstream depends on.

1. **`budgets.yaml`** — conservative per-run / per-day caps (Q3). A wave that would
   breach a cap evaluates to **idle + alert** (ADR-0027 SI-5). Document that on the
   Claude subscription the **monthly credit is the outer ceiling** and credit
   exhaustion is a sanctioned pause, not a failure (Q9); keep metered overflow OFF.
2. **Feature-flag scaffold** — add the WS-A…H keys to `config/features.yaml`, all
   DEFAULT **OFF** (ADR-0019), read via `scripts/feature_flags.py`. Match the existing
   comment style (each key names its consumer and flip condition).
3. **TN-1 in-tenant precondition check** — a check (script + a diagnostics probe or
   CI hook) that fails a run if any configured endpoint that carries code/IP resolves
   to a hosted/external service. The Claude model call is the one accepted proprietary
   exception (Q9); code, sandbox, observability, and audit stay in-tenant.

Do NOT flip any flag ON. This ticket only creates the OFF scaffold + guards.

## Acceptance criteria
- [ ] `budgets.yaml` present with conservative caps and the monthly-credit ceiling documented; breach → idle + alert semantics wired or clearly specified for the runner to honor.
- [ ] `config/features.yaml` carries the WS-A…H keys, all `false`, each with a consumer/flip-condition comment; `scripts/feature_flags.py enabled("<key>")` resolves them.
- [ ] TN-1 check exists and BLOCKS on a hosted/external code/IP endpoint; passes when all such endpoints are in-tenant (Claude model call excepted).
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9). Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (MUSTAQIL prep, order 0). Q3/Q9 budget stance; ADR-0019 flags OFF; TN-1 in-tenant boundary.

### 2026-07-24 — Backend EM
Built the OFF scaffold + guards. LOCAL-ONLY (no commit/push/PR). Files created/edited:

- `config/budgets.yaml` — added a `mustaqil:` block: conservative per-run
  ($5 / 2M in / 400K out) and per-day ($15 / 20M in / 4M out) caps; `on_breach:
  idle_and_alert` (ADR-0027 SI-5, via scripts/alerting.py); `monthly_credit_ceiling`
  (Pro $20 / Max-5x $100 / Max-20x $200) documented as the OUTER ceiling with
  `on_exhaustion: sanctioned_pause` and `metered_overflow: false` (Q9). Left the
  existing ORGANISM `caps:` block untouched so WS3 cost-ledger is undisturbed.
- `config/features.yaml` — added the MUSTAQIL WS flags, all `false`, each with a
  consumer/flip-condition comment in the existing style. Keys: `ws_a_tool_bridge`,
  `ws_b_agent_sdk_runner`, `ws_c_langgraph_loop`, `ws_d_langfuse_lens`,
  `ws_e_tenant_hardening`, `ws_g_proof`, `ws_h_control_plane`, and a
  never-flipped placeholder `ws_f_heartbeat` (WS-F reuses the existing
  `heartbeat_enabled` — NOT duplicated).
- `scripts/feature_flags.py` — registered the 8 new keys in `DEFAULTS` (the loader
  filters unknown keys, so registration is required for `enabled(...)` to resolve
  them). Verified: `python3 scripts/feature_flags.py` and `enabled("<key>")` all
  resolve to False.
- `config/tenant_boundary.yaml` (new) — TN-1 SSOT: in-tenant endpoint inventory,
  `accepted_external_roles: [model]` (the Claude model call is the one accepted
  proprietary exception, Q9); sandbox/observability/audit/memory/embeddings all
  declared in-tenant.
- `scripts/check_in_tenant.py` (new) — TN-1 guard: FAILS (exit 1) if any
  `carries_code_ip` endpoint whose role is not accepted-external resolves to a
  public host; PASSES (exit 0) when all such endpoints are in-tenant; inert if the
  config is absent. Verified: passes on the current in-tenant config (6 endpoints),
  and a negative test (external sandbox URL) correctly fails with exit 1.
- `scripts/diagnostics.py` — wired a `tn1-in-tenant-boundary` probe into the
  Security dimension so a boundary breach fails a run.

No flag flipped ON — OFF scaffold + guards only. Did NOT touch `docs/adr/`
(concurrent editor). Validators: `diagnostics.py` = 100/100 (Security now 10/10);
`board_lint.py` = 0 violations (pre-existing DAS-1507 body-status WARN unrelated);
`ruff check` clean on all touched scripts; `pytest tests/test_scheduler.py
tests/test_alerting_cost.py` = 70 passed.

All acceptance criteria met except the last clause of AC-4 ("Merged PR, green CI")
— per the LOCAL-ONLY dispatch constraint no branch/PR was created; that step is
the reviewer/orchestrator's to carry out. Set `status: in_review`, `assignee: cto`
(ROUTING: Backend EM's manager; never self-review).

### 2026-07-24 — CTO (review + ratify)
ACCEPTED. Accountable owner for the framework/infra decision (RACI 3.6). Author is
CEO, so no self-review conflict. Reviewed the scaffold and independently re-ran the
gates (did not take the delivery log's word for green):

- `config/budgets.yaml` — the `mustaqil:` block is correct: conservative per-run
  ($5 / 2M in / 400K out) and per-day ($15 / 20M in / 4M out) caps; `on_breach:
  idle_and_alert` (ADR-0027 SI-5); `monthly_credit_ceiling` documented as the OUTER
  ceiling with `on_exhaustion: sanctioned_pause` and `metered_overflow: false` (Q9).
  Confirmed the existing ORGANISM `caps:` block (10M/2M/$50 per-run, 100M/20M/$500
  per-day) is UNTOUCHED — WS3 cost-ledger undisturbed. The `[NEEDS VERIFICATION at
  WS-B go-live]` note on the credit/Agent-SDK terms is the right posture; not a blocker
  for an OFF scaffold.
- `config/features.yaml` + `scripts/feature_flags.py` — 8 MUSTAQIL WS keys registered
  in DEFAULTS, all `false`, each with a consumer/flip-condition comment. `ws_f_heartbeat`
  is a never-flipped placeholder that does NOT duplicate the live `heartbeat_enabled`.
  Verified `feature_flags.py` resolves all 8 to off (heartbeat_enabled also off;
  organism_emit on as expected/pre-existing).
- `config/tenant_boundary.yaml` + `scripts/check_in_tenant.py` — `accepted_external_roles:
  [model]` (Claude model call = the sole accepted proprietary exception, Q9). Guard
  PASSES in-tenant (exit 0, 6 endpoints declared) and — independently confirmed via a
  negative test (hosted `https://sandbox.e2b.dev`, role=sandbox, carries_code_ip) —
  correctly BLOCKS an external code/IP endpoint (exit 1). TN-1 does what it claims.

Gates I ran: `diagnostics.py` = 100/100 (Security 10/10, new `tn1-in-tenant-boundary`
probe passing); `check_in_tenant.py` = exit 0 in-tenant, exit 1 on the negative test;
`feature_flags.py` = all 8 WS keys off. No defect found; nothing to send back.

AC status: AC-1/AC-2/AC-3 met; AC-4's `diagnostics 100/100 + validators green + no
`project:` field` met. The "Merged PR, green CI" clause of AC-4 is deferred by the
LOCAL-ONLY constraint (no branch/PR exists) — that branch→PR→merge step is a later
explicit orchestrator action, not part of this ratification. Accepting on local green
per the dispatch constraint. `status: done`.

No escalation. Downstream now unblocked: DAS-1545 (WS-A Planning / ratify ADR-0033)
depends on this feature scaffold — route it next.
