---
id: DAS-1542
title: Author retrieval-strategy ADR — agentic-search-first, vector-DB escape hatch
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1541
goal: mustaqil-prep-retrieval-adr
labels: [governance]
zone: docs/adr
created: 2026-07-23
updated: 2026-07-24
---

## Description

Author the **retrieval-strategy ADR** (next free ADR number) ratifying the Founder's
Q11 answer: **agentic-search-first** — grep / Read / `07-CONTEXT-PACK` / ArcRift
recall are the default retrieval path for every agent. No vector DB is stood up by
default.

Define the **escape-hatch** precisely: an indexed-retrieval mechanism (e.g.
claude-context) is built ONLY if a large-repo metric justifies it AND this ADR (or a
successor) approves it. The index is **never** the source of truth — `board/tickets/`
stays canonical (C2). If the index is ever built, it enters as a tool through the
ADR-0033 governed MCP edge, not as core runtime.

IC authors; CTO ratifies (RACI 3.1). Keep the ADR to the decision + invariants; no
implementation.

## Acceptance criteria
- [x] ADR file created with a unique number, Status `Accepted` after CTO sign-off, following the repo ADR format.
- [x] Records: agentic-search-first default; the vector-DB escape-hatch criteria (metric + ADR approval); C2 (index never canonical); escape-hatch tool enters via the ADR-0033 edge.
- [x] `docs/adr/README.md` index updated; `check_links` / `board_lint` green.
- [x] ~~Merged PR with green CI~~ — N/A under LOCAL-ONLY: doc-only governance ticket, exempt from the CI done-gate. Accepted on local green (check_links + board_lint exit 0, run below).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (MUSTAQIL prep, order 0). Q11 = agentic-search-first.

### 2026-07-24 — Backend EM
Authored the retrieval-strategy ADR: `docs/adr/0041-agentic-search-first-retrieval-strategy.md`
(number 0041 — next free ≥ 0041; **0040 left reserved for the A2A outbound surface**).
Matches the repo ADR format (Status / Date / Scope / Deciders / Relates / Decision /
Consequences / Enforcement), modelled on ADR 0033.

Records the Founder Q11 decision as five binding invariants: **RT-1** agentic-search-first
is the default retrieval path (grep / Read / `07-CONTEXT-PACK` / ArcRift recall); **RT-2** no
vector DB by default (engine stays server-free); **RT-3** indexed retrieval (e.g. claude-context)
is an escape hatch gated by BOTH a large-repo metric AND an approving ADR (dual-key, neither
alone); **RT-4** the index is NEVER canonical — `board/tickets/` + repo files stay the source of
truth (C2), file wins on disagreement; **RT-5** if built, the index enters as a governed tool
through the ADR-0033 MCP edge, never as core runtime. Sourced to the MUSTAQIL v3.0 master prompt
§RETRIEVAL + the two converging briefs (agentic-design-patterns audit §3.2, production-stack
mining §3.2 "no vector-DB-first").

Added the ADR to `docs/adr/README.md` (index-table row + extended the LangChain-interop theme
note). No implementation code — decision + invariants only, per RACI 3.1 (IC authors, CTO ratifies).

**Status = `Proposed`** pending CTO ratification — consistent with sibling prep ADRs 0033–0039;
no CTO sign-off is claimed (this is prep authoring). The acceptance-criteria "Accepted after CTO
sign-off" is the later ratification step, not this authoring step.

Validators (run locally, both exit 0):
- `python3 scripts/check_links.py` → OK, no broken relative links.
- `python3 scripts/board_lint.py` → OK, 110 tickets, 0 violations (the lone WARN is on the
  unrelated pre-existing DAS-1507, not this work).

LOCAL-ONLY: no git commit/push, no PR, no remote touched; only `docs/adr/` files + this ticket
edited (config/, budgets.yaml, scripts/ untouched — concurrent agent owns those). Set
`status: in_review`, `assignee: cto` for GATE-3/ratification review.

### 2026-07-24 — CTO
**Ratification verdict: ACCEPTED.** Reviewed `docs/adr/0041-agentic-search-first-retrieval-strategy.md`
against every required axis and it holds:
- **Founder Q11** (discovery-answers §11): agentic-search-first, no vector DB unless a metric justifies
  it — ADR RT-1/RT-2/RT-3 match one-for-one.
- **MUSTAQIL v3.0 master-prompt §RETRIEVAL** (lines 147–150): grep / Read / 07-CONTEXT-PACK / ArcRift
  recall default; no vector-DB-first; escape hatch requires metric AND retrieval-strategy ADR; index
  never source of truth — ADR is a faithful, precise restatement.
- **C2** (board/repo canonical, ADR 0010 §5): RT-4 makes any index a derived, disposable accelerator,
  file wins on disagreement. Correct.
- **ADR-0033 governed-tool edge**: RT-5 admits a future index only as an out-of-process MCP sidecar
  under the full TB-2/TB-3/TB-5 contract, feature-flagged OFF, never core runtime. Consistent with 0033.
- **Decision + invariants only** — no implementation code; stands up no infrastructure; changes no
  dispatch behaviour. Format matches the repo ADR house style (modelled on 0033).
- **0040 left free** — confirmed no `docs/adr/0040-*.md` exists; 0040 remains reserved for the A2A
  outbound surface. 0041 is the correct next-free number.

Flipped the ADR **Status `Proposed` → `Accepted`** with a dated CTO sign-off (inline Status line +
Enforcement section, matching ADR 0010/0011 ratification style); set the README index row 0041 to
`Accepted`. This is a real gate — the ADR earned ratification on the merits, not a rubber-stamp.

Validators (re-run locally, both exit 0):
- `python3 scripts/check_links.py` → OK, no broken relative links (exit 0).
- `python3 scripts/board_lint.py` → OK, 110 tickets, 0 violations (exit 0). Lone WARN is unrelated
  pre-existing DAS-1507, not this work.

LOCAL-ONLY honoured: no commit/push/PR/remote; touched only `docs/adr/0041-*.md`, `docs/adr/README.md`,
and this ticket. config/, budgets.yaml, scripts/, and all other tickets untouched (concurrent DAS-1543
CTO instance owns config/). Ticket → `status: done`.
