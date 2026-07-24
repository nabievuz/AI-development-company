---
id: DAS-1570
title: MUSTAQIL WS-D LENS — self-host observability and governed-tool admission (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent:
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**EPIC — MUSTAQIL v3.0 WS-D LENS.** Self-host **Langfuse** observability via an
**OTLP export of the ADR-0024 spans DasLab already emits** — explicitly **NOT
LangSmith**, self-host only, in-tenant (ADR-0038 TN-1). **Plus governed-tool
admission** of the eval/guardrail tool shortlist — **promptfoo, AgentShield,
Presidio** — each admitted through the existing **ADR-0033 governed MCP edge**
(WS-A), never as a bulk toolkit import and never as a second admission path.
Redaction on export per ADR-0012. Behind feature flag `ws_d_langfuse_lens`
(scaffolded OFF by DAS-1543).

**Contract of record:** ADR-0036 (OB-1…OB-4), ADR-0024 (span-event schema),
ADR-0012 (redaction), ADR-0033 (the governed MCP edge WS-D's tool admission
reuses), `docs/specs/005-mustaqil-ws-d-lens/SPEC.md` (FR-001…FR-006,
SC-001…SC-005), master prompt row D + Part 2
(`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`), discovery
answers Q5/Q9/Q11.

**Sequence note:** WS-D runs **PARALLEL from WS-A** — it does not wait on WS-A's
full epic closure, only on the **ADR-0033 edge existing** (the FastMCP sidecar
mechanism built in WS-A Development). The tool-admission Development ticket
(DAS-1574) carries that cross-workstream dependency explicitly; every other
WS-D ticket proceeds independently.

**AADL — six-stage closure (children DAS-1571..DAS-1577):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1571 | Planning | Author + ratify ADR-0036, review SPEC-005, confirm the `ws_d_langfuse_lens` feature key OFF | cto |
| DAS-1572 | Design | OTLP exporter design (self-host Langfuse target, ADR-0012 redaction mapping) + tool-admission design for promptfoo/AgentShield/Presidio via the 0033 edge | backend-em |
| DAS-1573 | Development | OTLP exporter — export ADR-0024 spans to self-host Langfuse, flag OFF | backend-em |
| DAS-1574 | Development | Admit promptfoo, AgentShield, Presidio through the ADR-0033 governed MCP edge | backend-eng-1 |
| DAS-1575 | Testing | Redaction-on-export verified; tool-admission negative tests; in-tenant-only target proven | qa-eng |
| DAS-1576 | Deployment | Runbook + self-host Langfuse deployment note; flag stays OFF on merge | sre-eng |
| DAS-1577 | Maintenance | Scheduled health/eval of the Langfuse lens and the tool-admission edge | product-analyst |

## Acceptance criteria
- [ ] All seven children (DAS-1571..DAS-1577) closed, each through its own AADL stage gate.
- [ ] **FR-001:** the OTLP exporter ships ADR-0024 spans to a self-hosted Langfuse instance only — never LangSmith or any hosted endpoint.
- [ ] **FR-002/SC-002:** every exported span/attribute is ADR-0012 classified + redacted before it leaves the process; a redaction probe passes.
- [ ] **FR-003:** `board/.events.jsonl` + committed attestations stay canonical; disabling/losing the Langfuse lens changes no board/dispatch outcome.
- [ ] **FR-004/SC-001:** the exporter is feature-flagged OFF by default; with the flag OFF, dispatch and event emission are byte-identical to pre-merge.
- [ ] **FR-005/SC-003:** promptfoo, AgentShield, and Presidio each enter only through the ADR-0033 edge (overlay allow-list + PreToolUse audit/deny + redaction); a negative test proves a non-allow-listed role is refused.
- [ ] **FR-006:** publishing the self-host Langfuse endpoint, or pointing the exporter at any hosted project, is an explicit Founder act — never automated.
- [ ] **SC-004:** a check proves the exporter target resolves to an in-tenant/self-hosted endpoint only (TN-1); a hosted-endpoint config fails the check.
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/`check_dependency_graph` green; no `project:` field on any WS-D ticket (R9); committed wave attestation (ADR-0031/0032).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-D**, each gate logged in the stage-board.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (WS-D LENS,
ADR-0036). Contract = ADR-0036 (OB-1..OB-4) + SPEC-005 + reuse of the ADR-0033
edge for tool admission. Children DAS-1571..DAS-1577 (one per AADL stage, 2
Development — exporter vs tool-admission, distinct repo zones). Org-engine epic —
no `project:` field (board_lint R9). Depends on the prep bootstrap (DAS-1543) for
the feature-flag scaffold (`ws_d_langfuse_lens` already landed `false`). Runs
parallel from WS-A per the master-prompt sequence; only DAS-1574 (tool-admission
Development) carries a hard dependency on the WS-A tool-bridge sidecar
(DAS-1547) since that ticket builds the 0033 edge mechanism it reuses.
