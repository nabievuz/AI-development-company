---
id: DAS-1546
title: WS-A Design — tool-admission model (overlay allow-list, PreToolUse audit, redaction, egress)
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-002, FR-003, FR-005, FR-006]
labels: [security]
zone: docs/design
depends_on: [DAS-1545]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-A).** Design the governed admission
model the Development tickets implement. No code beyond schemas/specs.

- **Least-privilege allow-list (TB-2):** how a role's `<dept>/agents/<role>/AGENTS.md`
  overlay declares an allowed external tool, and how that compiles (ADR-0018/0029) so a
  non-declared tool is unreachable. No blanket grants.
- **PreToolUse audit/deny (TB-3):** the `.claude/settings.json` `PreToolUse` hook shape
  (honored identically by the Claude Code CLI and the Agent SDK) that can audit or DENY
  each external-tool call; how tool transcripts map to ADR-0012 event classification +
  redaction; the invariant that a tool never writes routing fields (C3) or bypasses a
  gate (C4).
- **Egress policy (TB-4/Q5):** deny-all except an explicit domain allow-list; where the
  allow-list lives; how browser egress is treated as untrusted input (FR-006).

Security Lead consulted (accountable stage owner = CTO; responsible = backend-em).

## Acceptance criteria
- [ ] Design doc under `docs/` covering the allow-list schema, the PreToolUse audit/deny contract, the ADR-0012 redaction mapping, and the deny-all + domain allow-list egress policy — each traced to its FR and TB invariant.
- [ ] Negative-path behaviour specified for SC-001/SC-002 (global grant refused, audit-skip denied, non-allow-listed egress blocked) so DAS-1549 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Design). TB-2/TB-3/TB-4 admission model.
