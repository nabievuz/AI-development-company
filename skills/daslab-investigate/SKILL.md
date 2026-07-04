---
name: daslab-investigate
description: >
  DasLab autonomous root-cause debugging for engineering agents (CTO, EMs,
  Backend/Frontend/SRE/Security/QA Engineers, Developer). Enforces the Iron Law —
  no fix without root-cause investigation first — through a five-phase method:
  investigate, pattern-match, test the hypothesis, fix the root cause with a
  regression test, verify. ALWAYS use this skill when debugging a bug, test
  failure, production incident, or any unexpected behavior, when a ticket reports
  an error/stack trace, or when tempted to patch a symptom. Includes a 3-strike
  escalation rule so the agent never loops forever. Emits a structured debug
  report + the DasLab finding format and a terminal STATUS (§5.5/§6). Runs as
  an autonomous root-cause method in each work wave.
---

# DasLab Investigate — autonomous root-cause debugging

You are an engineer chasing a bug. This is the **diagnostic process** for the fleet: find
why it breaks before changing anything.

## Iron Law
**NO FIXES WITHOUT ROOT-CAUSE INVESTIGATION FIRST.** Fixing symptoms creates whack-a-mole
debugging — every non-root fix makes the next bug harder to find. Find the cause, then fix it.

## Phase 1 — Root-cause investigation
Gather context before forming any hypothesis.
1. **Collect symptoms** — read the error/stack trace/repro steps from the ticket. If context is
   missing, ask the requester **one** precise question (comment + `NEEDS_CONTEXT`), don't guess.
2. **Read the code** — trace the path from symptom back to causes. Grep for all references, Read the logic.
3. **Check recent changes** — was it working before? A regression means the root cause is in the
   diff. `git log`/`git diff` the suspect area.
4. **Reproduce** — can you trigger it deterministically? If not, gather more evidence first.
5. **Check history** — search prior learnings / `git log` for past fixes in the same files.
   **Recurring bugs in the same area are an architectural smell, not a coincidence.**

Output: `Root-cause hypothesis: …` — a specific, testable claim about what is wrong and why.

## Scope lock (autonomous)
After naming the hypothesis, **declare the narrowest affected module** in a ticket comment and
restrict your edits to it — prevents scope creep. Work in a git worktree off fresh `origin/main`
(orchestrator §6.5) so concurrent agents don't collide. If the bug genuinely spans the repo,
say so and skip the lock.

## Phase 2 — Pattern analysis
Match the bug against known shapes before testing:

| Pattern | Signature | Where to look |
|---|---|---|
| Race condition | intermittent, timing-dependent | concurrent access to shared state |
| Nil/null propagation | NoMethodError/TypeError | missing guards on optional values |
| State corruption | inconsistent/partial data | transactions, callbacks, hooks |
| Integration failure | timeout/unexpected response | external API / service boundaries |
| Configuration drift | works locally, fails in staging/prod | env vars, feature flags, DB state |
| Stale cache | old data, fixes on cache clear | Redis, CDN, browser, Turbo |

Also check `TODOS.md` and `git log` for prior fixes in the same area. If it matches none, **WebSearch**
the *sanitized* generic error (strip hostnames/IPs/paths/SQL/customer data — search the category,
not the raw message). A documented known-issue becomes a candidate hypothesis.

## Phase 3 — Hypothesis testing (before writing ANY fix)
1. **Confirm** — add a temporary log/assertion at the suspected root cause, run the repro. Does the
   evidence match?
2. **If wrong** — return to Phase 1, gather more evidence. Do not guess.
3. **3-strike rule** — if 3 hypotheses fail, **STOP and escalate**: set the ticket `blocked`,
   `@`-mention your manager with the evidence and the 3 ruled-out hypotheses, `STATUS: BLOCKED`.
   This may be architectural, not a simple bug (matches orchestrator escalation: ≥3 fails on a ticket).

**Red flags — slow down if you catch yourself:** "quick fix for now" (there is no for-now);
proposing a fix before tracing data flow (you're guessing); each fix reveals a new problem
elsewhere (wrong layer, not wrong code).

## Phase 4 — Implementation (only after the root cause is confirmed)
1. **Fix the root cause, not the symptom** — the smallest change that eliminates the actual problem.
2. **Minimal diff** — fewest files/lines; resist refactoring adjacent code.
3. **Regression test** that **fails without** the fix and **passes with** it (proves both).
4. **Run the full suite**, paste the output — no regressions.
5. **Blast radius >5 files:** default to fix the critical path now and open a follow-up issue with
   an owner for the rest (`DONE_WITH_CONCERNS`); escalate (`BLOCKED`) instead if the spread means the
   root cause is architectural.

## Phase 5 — Verification & report
Reproduce the original scenario and confirm it's fixed (not optional). Post a structured report:
```
DEBUG REPORT
Symptom:         <what was observed>
Root cause:      <what was actually wrong>
Fix:             <what changed, with file:line>
Evidence:        <test output / repro showing the fix works>
Regression test: <file:line of the new test>
Related:         <TODOS items, prior bugs in same area, architectural notes>
```
Findings that surface but are out of scope use the DasLab line format
`[SEVERITY] (confidence: N/10) path:line — summary`. Then end with a terminal STATUS (§5.5):
- Fixed + verified + regression test green → `STATUS: DONE — root cause fixed, regression test added`
- Fixed, but related risks remain → open follow-up issue → `STATUS: DONE_WITH_CONCERNS — DAS-<id>`
- 3 hypotheses failed / architectural → `STATUS: BLOCKED — <one-line>` + escalate
- Missing repro/context → `STATUS: NEEDS_CONTEXT — <what's needed>`

## Capture learnings
If you found a non-obvious pattern/pitfall/architectural insight, record one durable learning
(affected files included) so future investigations on the same area find it (Reflect, orchestrator §2.9.5).

## Hard rules
- Iron Law is absolute: no fix lands before the root cause is named and confirmed.
- A bug fix ships with a regression test, or it isn't done.
- Never loop past 3 failed hypotheses — escalate with evidence.
- Cite `file:line` everywhere. Obey git/PR discipline (§6.5); CI green is the gate.
