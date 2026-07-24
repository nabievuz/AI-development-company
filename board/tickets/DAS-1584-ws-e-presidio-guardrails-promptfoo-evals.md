---
id: DAS-1584
title: WS-E Development — Presidio classifier policy guardrails plus promptfoo golden-set evals
status: todo
assignee: backend-eng-2
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-006, FR-007]
labels: [security]
zone: tools/guardrails
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 3).** Wire the guardrail chain
and the golden-set evals per the DAS-1581 design. Distinct repo zone from DAS-1582/1583
so the Development tickets proceed without a same-zone wave collision. Security Lead
consulted (guardrails); Product Analyst consulted (evals).

- **TN-5 / FR-006 (guardrails):** a layered **Presidio (PII) + classifier + policy**
  guardrail chain wired into the ADR-0012 redaction / guardrail path, **admitted through
  the ADR-0033 governed MCP edge** (least-privilege, PreToolUse audit) — never a bulk
  import. Presidio (and any model/classifier weights) resolve in-tenant (TN-1); reuse the
  WS-A redaction posture, do not fork ADR-0012.
- **FR-007 (evals):** **promptfoo** + a **hand-labeled golden set** wired into the
  existing `evals/` CI path, checked **BEFORE any LLM-judge**, WITH an anti-gaming probe
  (golden-set-before-dashboard, ADR-0017/0020) — no golden-set pass ⇒ not green.
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); flag-off ⇒ the chain is inert,
  the eval path unchanged, dispatch unchanged.

Hand the matching probe tests (SC-004) to DAS-1585.

## Acceptance criteria
- [ ] Presidio+classifier+policy guardrail chain wired to the ADR-0012 redaction path and admitted via the ADR-0033 edge (least-privilege, PreToolUse audit); a probe detects + redacts planted PII/secrets (SC-004).
- [ ] promptfoo golden set runs in the `evals/` CI path before any LLM-judge, with an anti-gaming probe; a false-green cannot pass (SC-004).
- [ ] Guardrail components resolve in-tenant (TN-1); no fork of ADR-0012 redaction; no bulk toolkit import.
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 3). TN-5/FR-006 Presidio+classifier+policy guardrails via the 0033 edge + FR-007 promptfoo golden-set evals (golden-set-before-LLM-judge + anti-gaming probe). All behind `ws_e_tenant_hardening` OFF.
