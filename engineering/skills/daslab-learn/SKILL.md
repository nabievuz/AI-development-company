---
name: daslab-learn
description: >
  DasLab persistent learnings + memory-trust model for all agents. Captures
  durable cross-wave learnings (patterns, pitfalls, preferences,
  architecture, tooling) in a structured, append-only store, and recalls the
  relevant ones at the start of related work — WITHOUT leaking learnings across
  the workstream boundary. ALWAYS use this skill when capturing a learning during
  Reflect (orchestrator §2.9.5), at the end of an investigation/review/retro,
  when starting work where prior learnings on the same files/area would help, or
  when pruning stale/conflicting memory. Enforces per-project read-write /
  read-only / deny trust tiers so platform learnings never contaminate the
  product project and vice versa.
---

# DasLab Learn — persistent learnings with a memory-trust model

You are managing the org's long-term memory. The substrate is **the ArcRift persistent memory**
(DasLab's long-term memory store); this skill is the *discipline* on top:
a structured record, a recall-before-work habit, and — critically — a trust model that keeps
workstreams from poisoning each other's memory.

## The trust triad (maps to the workstream boundary)
Every learning is scoped to a **project/workstream**, and every project has a policy:

| Tier | Meaning | Default for |
|---|---|---|
| **read-write** | recall AND write learnings from this project's context | your own current project |
| **read-only** | recall org-wide learnings, but never write into this scope | the shared **org** tier (universal practices) |
| **deny** | invisible — never recalled or written | **the other workstream** |

**Hard rule (the boundary, [[two-workstreams-boundary]]):** the *platform / agent-improvement*
workstream (this `daslab` repo — orchestrator, agents, durability) and the **product**
project are mutually `deny`. A platform learning is never recalled while working a product ticket,
and a product learning is never recalled while working platform tickets. Only the **org tier**
(read-only, universal: git/PR discipline, status protocol, security basics) is shared by both.

Scope key = the project/workspace you are currently in (the ticket's `projectId` / workspace cwd).
When in doubt about a learning's scope, default to the **current project** (narrowest), never org.

## Learning record (append-only)
```
{ scope: <project|org>, type: pattern|pitfall|preference|architecture|tool,
  key: "<kebab-case 2-5 words>", insight: "<one sentence>",
  confidence: 1-10, source: observed|user-stated, files: ["path", …], date: <ISO> }
```
Append-only: to correct a learning, append a new entry with the fixed insight (history is
evidence). Never edit in place.

## Recall (do this at the START of related work)
Before building/reviewing/debugging in an area, recall learnings whose `scope` is the **current
project** plus the **org** read-only tier, filtered by the files/area you are touching. Never pull
from a `deny` scope. If a recalled learning applies, name it in one line:
`Prior learning applied: <key> (confidence N/10, <date>)` — this makes the org visibly compound.
Absence of a matching learning is itself useful signal (genuinely new ground).

## Capture (the Reflect step, §2.9.5)
Write a learning only if it is **durable** and would save 5+ minutes next time. The feeders:
`daslab-investigate` (Phase 5 — a non-obvious bug pattern/root-cause), `daslab-review` (a recurring
finding class), `daslab-retro` (a systemic blocker), or any agent that hit a project quirk / command
fix. **Skip** obvious facts, one-off transient errors, and anything already recorded. Scope it to the
current project unless it is a universal practice (then `org`, and only a manager writes to `org`).

## Maintain (prune — run periodically, e.g. in retro)
- **Stale check:** a learning whose `files` reference a deleted path → flag `STALE: <key> → <path>`.
- **Contradiction check:** two entries, same `key`, opposite `insight` → flag
  `CONFLICT: <key> — <A> vs <B>`; keep the higher-confidence/newer, mark the other superseded.
- Pruning is append-a-tombstone, not destructive delete — the trail stays auditable.

## Output + status (§5.5)
- Recalled/captured cleanly → `STATUS: DONE — N recalled, M captured (scope: <project|org>)`
- Found stale/conflicting memory needing a decision → open a follow-up →
  `STATUS: DONE_WITH_CONCERNS — DAS-<id> to reconcile <key>`
- Can't determine scope safely → `STATUS: NEEDS_CONTEXT — project scope unclear`

## Hard rules
- **Never cross the workstream boundary.** Platform and product memory are mutually `deny`; only the
  org read-only tier is shared. A leak here re-introduces exactly the coupling the boundary forbids.
- Append-only; corrections add entries, they don't overwrite.
- Scope narrow by default (current project), promote to `org` only for genuinely universal practice
  and only by a manager.
- One sentence per insight, kebab-case key, honest confidence. Recall before building, capture on reflect.
