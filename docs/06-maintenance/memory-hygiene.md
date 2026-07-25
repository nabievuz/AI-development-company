# Memory-hygiene — AADL Stage 6 Maintenance (GATE-6)

> The weekly ArcRift prune run. Accountable: QA Lead (Maintenance-stage eval
> owner). Consulted: CTO. Basis: Persistent Memory Law (`CLAUDE.md`).
> Runbook authored: DAS-1631.

## What this is

A **recurring** memory-hygiene run that prunes stale or incorrect facts from
DasLab's long-term memory (ArcRift), wired into the **existing**
Maintenance-stage cadence (`scripts/stage_gate.py:maintenance_schedule()`)
rather than a new daemon or scheduler. Per the AI-agent-lifecycle policy §3
(Stage 6), the schedule descriptor is **data, not an installer** — cadence lives
in the Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here deploys or
auto-runs itself.

Command: `prune_memory` (an **ArcRift MCP tool call**, not a `python3 <script>`
invocation).
Registered as the `memory-hygiene` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6), and
the per-workstream `ws-*-health` checks.

## What it does

The Persistent Memory Law (`CLAUDE.md`) requires that a wrong or stale memory is
never kept: "Delete a stale/incorrect fact with `prune_memory` — keeping a wrong
memory is FORBIDDEN." This weekly run applies that hygiene across the ArcRift
knowledge graph so that recall quality does not silently degrade as facts age or
are superseded. The DasLab-side wrapper is `scripts/memory_lib.py` (which issues
the actual `prune_memory` calls); the read-only inventory helper
`scripts/consolidate_memory.py` never prunes or stores on its own.

## Why its command is structurally not a script path

`memory-hygiene`'s `command` is `["prune_memory"]` — a single element naming an
**ArcRift MCP tool**, with no `command[1]` argument to resolve to a file on disk.
It is therefore correctly **exempt from the `command[1]`-resolves rule**, which
applies only to a `python3 <script>` invocation (keyed on the command **shape**,
`command[0] == "python3"` — never on this entry's name). This distinction is a
structural property of the command, not a special case: any MCP-tool-call entry
is exempt for the same reason, and any script-invocation entry is not.

This is orthogonal to the `config` (runbook) link: an MCP-backed run has no
script path, but it still has real operational semantics worth documenting —
which is exactly what this doc is, so `config` can be universal across the
schedule (DAS-1631).

## Cadence and registration

- **Cadence:** weekly (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `memory-hygiene`).
- **Command:** `prune_memory` (ArcRift MCP).
- **Scope discipline:** pruning is project-scoped (STRICT project isolation per
  the Persistent Memory Law); a prune in one project's memory must never touch
  another's.
- Same registration point every other Maintenance-stage run uses — no second
  scheduling mechanism was introduced.

## Alerting — a prune is never blind

- A prune is applied against a **specific stale/incorrect fact** the run
  identifies — never a blanket wipe, and never an auto-decision that a live
  fact is wrong. A borderline case is a **finding** routed to a human, not an
  autonomous deletion.
- Any change with governance weight (e.g. deciding a policy-bearing memory is
  stale) is `governance_or_policy` / never-auto-approve
  (`config/risk_taxonomy.yaml`) and waits for a human (QONUN-5 / ADR-0027 SI-7).

## Verification

```
python3 -m pytest tests/test_memory_governance.py tests/test_consolidate_memory.py -q
```
