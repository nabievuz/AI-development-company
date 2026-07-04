---
id: DAS-1466
title: Compile allowed routes into agents and add check_comm_flows validator
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1463
goal: organism-ws2-loom
depends_on: [DAS-1465]
zone: gen-subagents
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** This is the GATE-3 Development ticket for §5 row 9 of the ORGANISM
program — the "LOOM" (communication fabric) work stream. The org's allowed
message routes are declared once in `governance/communication-flows.yaml` (the
sender→receiver adjacency, authored/validated by the upstream ticket **DAS-1465**).
Today that declaration is inert: it lives in a YAML file but nothing compiles it
into the agents themselves, and nothing rejects a ticket/dispatch that references
a route no agent is allowed to use. Two gaps to close:

1. **Structural (make the illegal unrepresentable).** Extend
   `scripts/gen_subagents.py` so each generated `.claude/agents/<role>.md`
   definition **carries its own allowed OUTBOUND routes**, read from
   `governance/communication-flows.yaml`. After this change an agent's definition
   literally enumerates who it may message; a route the agent is not granted has
   no place in its definition — structurally unrepresentable.
2. **Enforcement (catch the illegal).** Add `scripts/check_comm_flows.py`, a
   validator that **FAILS (exit 1)** any ticket/dispatch referencing an
   undeclared `(sender, receiver)` route — i.e. a pair not present in
   `governance/communication-flows.yaml`. It parses the flows file as the single
   source of truth and reports the offending pair(s).

**Extend vs. new.**
- **Extend** `scripts/gen_subagents.py` — the existing generator that already
  emits `.claude/agents/<role>.md` + `board/ROUTING.md` from the dept overlays and
  the model-allocation policy. Add a flows-loader and weave each role's allowed
  outbound routes into the generated body (a new section in the shim). Do NOT
  fork a second generator — the shim is fully regenerated on every run, so the
  route block must be produced inline here.
- **New file** `scripts/check_comm_flows.py` — mirror the structure/CLI/exit-code
  conventions of `scripts/check_agents_sync.py` (argparse, `from _paths import
  ROOT`, exit 0 = OK / 1 = violation / 2 = usage/IO). Reuse its frontmatter and
  table-parsing idioms rather than inventing new ones.

**Key files (paths).**
- `scripts/gen_subagents.py` — generator to extend; emits `.claude/agents/*.md` +
  `board/ROUTING.md`. The per-role body is the `body = f"""---..."""` block
  (~lines 85–126); add the allowed-routes section there.
- `scripts/check_agents_sync.py` — the regenerate-and-diff invariant guard and the
  reference implementation for the new validator's shape (argparse/exit codes).
- `governance/communication-flows.yaml` — source of truth for allowed routes,
  authored by **DAS-1465** (this ticket's `depends_on`); do not proceed until it
  exists in-tree.
- `scripts/check_comm_flows.py` — NEW validator to create.
- `.claude/agents/<role>.md` (32 shims) + `board/ROUTING.md` — regenerated
  outputs; must be regenerated and committed, and stay green under
  `scripts/check_agents_sync.py`.
- `scripts/_paths.py` — provides `ROOT`; import it, do not hardcode paths.

Because `gen_subagents.py` regenerates ALL of `.claude/agents/*` and `board/ROUTING.md`,
run the FULL diagnostics suite and `scripts/check_agents_sync.py` after
regenerating (regenerate-and-diff must be clean — no unexplained drift).

## Acceptance criteria

- [ ] Each generated `.claude/agents/<role>.md` def carries its allowed outbound
      routes, compiled from `governance/communication-flows.yaml`.
- [ ] `scripts/check_comm_flows.py` exists and FAILS (exit 1) a ticket/dispatch
      that references an undeclared `(sender, receiver)` route; exits 0 when all
      referenced routes are declared.
- [ ] `scripts/gen_subagents.py` re-run regenerates the shims + `board/ROUTING.md`;
      `scripts/check_agents_sync.py` stays green (regenerate-and-diff clean).
- [ ] An undeclared route is both structurally unrepresentable (not in any agent
      def) AND validator-caught by `check_comm_flows.py` (§5 row 9 satisfied).
- [ ] Diagnostics 100/100, full suite 0 failed.
- [ ] Org-engine ticket — no `project:` field (board_lint R9). No other files
      created beyond `scripts/check_comm_flows.py` + regenerated outputs.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS2 LOOM decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
Read scripts/gen_subagents.py, scripts/check_agents_sync.py, and .claude/agents to write the criteria + paths below. Note: `governance/communication-flows.yaml` does not yet exist in-tree — it is produced by the dependency **DAS-1465**, so this ticket is correctly gated on it (`depends_on: [DAS-1465]`). The per-role route block goes into the `body` f-string of gen_subagents.py (~lines 85–126); the new validator should mirror check_agents_sync.py's argparse/`_paths.ROOT`/exit-code shape. GATE-3 Development (P9) — the §5 row-9 headline.

### 2026-07-03 — Backend EM
Implemented both halves of §5 row 9 (LOOM enforcement). DAS-1465's
`governance/communication-flows.yaml` (60 edges) is now in-tree, so the gate is
satisfied. Branch `feat/das-1466-gen-routes` (local only).

**Structural (routes compiled into agents).** Extended `scripts/gen_subagents.py`:
new `load_outbound_routes()` reads the flows YAML into `{sender: [(kind, receiver)]}`
(de-duplicated, sorted `(kind, receiver)` for byte-stable regeneration), and
`format_routes_block(key, routes)` renders each role's allowed outbound routes. A new
`## Allowed outbound routes (compiled from governance/communication-flows.yaml)`
section is woven into the per-role `body` f-string. Regenerated all 32
`.claude/agents/*.md` + `board/ROUTING.md`. Example — `backend-em` now enumerates
`delegation → backend-eng-1/2`, `escalation → cto`; `board-member` (a leaf with no
reports/manager edges) renders "none". A route a role is not granted has no place in
its definition → structurally unrepresentable. Absent-flows path degrades gracefully
(no crash) for sparse worktrees.

**Enforcement (undeclared route caught).** New `scripts/check_comm_flows.py` mirrors
`check_agents_sync.py` (argparse, `from _paths import ROOT`, exit 0/1/2). It loads the
declared `(sender, receiver)` set from the flows file (the SSOT — its absence is exit
2, not a tolerated skip) and FAILS (exit 1) any referenced route not in that set.
Two reference sources: (a) **ticket mode** (default) scans `board/tickets/*.md` for a
`routes:` frontmatter field (tolerant single/bracketed-list grammar, `>`/`->`/`→`
separators); (b) **dispatch mode** validates `--route sender>receiver` (repeatable)
and/or `--dispatch FILE.json`. Deliberately keyed off *explicit* route references, not
`(author, assignee)` — on the current board every ticket is `author: ceo` assigned to
the eventual worker (e.g. `ceo→backend-em`, `ceo→sre-lead`), which are work
assignments, not comm routes; keying off them would false-positive. Today no ticket
declares `routes:`, so the whole board passes (exit 0).

**Tests** (`tests/test_check_comm_flows.py`, 33 cases): declared route passes / an
undeclared route (`ceo→backend-em`) is caught in ticket, `--route`, and `--dispatch`
modes; missing flows → exit 2; token grammar + tolerant list parsing; plus TWO
integration tests on the real regenerated tree proving every route compiled into a
shim is a declared route AND the known-undeclared `ceo→backend-em` pair appears in no
shim (unrepresentable). Registered the validator + test in `scripts/diagnostics.py`
required-suite lists.

**Verify (FULL, all green):** `pytest -q` = 1234 passed / 1 skipped; `diagnostics.py`
= 100/100; `board_lint.py` = 0 violations; `check_agents_sync.py` = OK, 32 shims in
sync (regenerate-and-diff clean); `check_comm_flows.py` = exit 0 on the clean board,
exit 1 on an undeclared dispatch; `ruff check scripts/ tests/` = clean. Committed
locally (no push per strict local-only). All acceptance criteria met. Reviewer: CTO
(per ROUTING.md). → `in_review`.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done. allowed routes compiled into all 32 agent shims (undeclared route unrepresentable) + check_comm_flows.py; check_agents_sync green. §5 contract row 9 DELIVERED.
