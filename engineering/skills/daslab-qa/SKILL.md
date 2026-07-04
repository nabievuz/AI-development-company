---
name: daslab-qa
description: >
  DasLab autonomous QA for web applications — browser-agnostic with graceful
  degradation. Builds a test plan (diff-aware or full), exercises the app with
  whatever capability is available (claude-in-chrome MCP if present, else
  HTTP-level checks + Dokploy MCP), finds bugs, fixes the root cause, and
  generates a regression test for each. ALWAYS use this skill when asked to "QA",
  "test this site", "find bugs", "test and fix", before the Test gate of the
  sprint (orchestrator §3.5), or when a feature branch needs verification beyond
  unit tests. Emits the DasLab finding format and a terminal STATUS (§5.5/§6).
  Drives a real browser via the claude-in-chrome MCP when present, degrading to
  HTTP-level checks otherwise.
---

# DasLab QA — browser-agnostic web testing

You verify a web app works, then fix what doesn't and lock it with a regression test. This is
the **Test** phase of the sprint (orchestrator §3.5). The highest-value output is **runtime-free**:
the regression tests you write. The browser is optional and degrades gracefully.

## Step 0 — Capability detection (run first; no silent caps)
Detect what you can drive, and **state it**:
- **Browser available** — `mcp__claude-in-chrome__*` tools present (Chrome
  connected). Full interaction + visual checks possible.
- **HTTP only** — no browser MCP. You can `curl` status codes, headers, response bodies, redirects,
  and key-content presence, and read server logs via **Dokploy MCP** (`mcp__dokploy__*`).
  You **cannot** do clicks/visual/JS-state testing — say which checks you're skipping and why.
- Either way, **unit/integration/E2E test generation is always available** — that is the core deliverable.

## Step 1 — Test plan
- **Diff-aware** (feature branch, no URL): from `git diff origin/main`, list the changed user flows,
  endpoints, and states to verify. Trace each codepath (reuse `daslab-plan-review` §3 test logic).
- **Full** (URL given): discover key pages/flows (`/`, auth, the feature surface) and map the journeys.
- For each item: the action, the expected result, and the test that would cover it.

## Step 2 — Exercise (best-effort, by capability)
- **Browser:** walk each journey via the browser MCP — happy path, then interaction edge cases
  (unexpected input, double-submit, back-button), error states, and empty/boundary states.
- **HTTP:** assert status/redirect/headers/content for each endpoint; check auth-required routes
  reject anonymous access; scan Dokploy logs for errors/stack traces during the run.
- Record each defect with concrete evidence (response, log line, or screenshot reference).

## Step 3 — Fix the root cause (not the symptom)
For each real bug, hand to `daslab-investigate` discipline: find the root cause, apply the minimal
fix on the branch, commit atomically. Do not patch symptoms.

## Step 4 — Regression test (mandatory per bug)
Write a test that **fails before** the fix and **passes after** (proves both). If the repo has no
test framework, bootstrap the standard one for the stack (detect runtime → pick the conventional
framework → minimal config → a TESTING.md note), then add the test. Run the **full suite**, paste output.

## Step 5 — Report + status (§5.5/§6)
Emit each finding one per line: `[SEVERITY] (confidence: N/10) path-or-url:loc — summary`. Then a
ship-readiness summary:
```
DasLab QA — <scope> — capability: <browser|http-only>
Tested: <journeys/endpoints n>   Bugs: <n> (fixed <n>, open <n>)
Regression tests added: <n>   Suite: <pass/fail with counts>
Not covered (capability gap): <list, or "none">
```
Terminal status:
- App verified, bugs fixed, suite green → `STATUS: DONE — N bugs fixed, N regression tests added`
- Bugs found that must not ship → set ticket `blocked` → `STATUS: BLOCKED — <one-line>`
- Verified but coverage-limited by capability → open follow-up → `STATUS: DONE_WITH_CONCERNS — DAS-<id> (browser QA pending)`
- No URL/branch/repro to test → `STATUS: NEEDS_CONTEXT — <what's needed>`

## Hard rules
- **Declare the capability and what you could not test** — never let HTTP-only QA read as full QA.
- Every fixed bug ships with a regression test, or it isn't fixed.
- Obey git/PR discipline (§6.5); the Test gate feeds Ship, CI green is the gate.
- Capture durable site quirks via `daslab-learn` (scoped to the project — boundary applies).
