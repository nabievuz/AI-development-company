---
name: daslab-canary
description: >
  DasLab autonomous post-deploy canary monitoring for SRE/DevOps and CTO. After a
  deploy, watches the live app for errors, health regressions, and page failures —
  primarily via the Dokploy MCP (container status, logs, app monitoring) plus
  HTTP health checks, and browser/visual checks when claude-in-chrome MCP is
  available. Compares against a pre-deploy baseline and recommends rollback on
  regression. ALWAYS use this skill at the Ship phase of the sprint (orchestrator
  §3.5) right after a deploy, when asked to "monitor deploy / canary / post-deploy
  check", or to verify production health. Emits a health report + terminal STATUS
  (§5.5/§6). Drives post-deploy health checks through the Dokploy MCP.
---

# DasLab Canary — post-deploy health verification

You are the safety net between "shipped" and "verified." Deploy is not done until the canary is
green. Primary instrument: the **Dokploy MCP** (`mcp__dokploy__*`) — you already have it.

## Step 0 — Capability + target
Identify the app + Dokploy application/compose id and its public URL. Confirm Dokploy MCP is
reachable. Note whether `mcp__claude-in-chrome__*` is available for visual checks (optional).

## Step 1 — Baseline (capture BEFORE deploy, if not already)
Record the pre-deploy reference: HTTP status + latency on key routes, container running/healthy
state (`mcp__dokploy__application-one` / `docker-getContainers...`), and a recent clean log window.
If no baseline exists, capture the current state as the reference and say so.

## Step 2 — Continuous monitoring loop (default ~10 min, `--quick` = single pass)
On a short interval, check:
- **Container health** — running + not restarting/crash-looping (`application-readAppMonitoring`,
  `docker-getContainers...`). A restart loop is a deploy failure.
- **Logs** — scan `application-readLogs` / `compose-readLogs` for new errors, stack traces, or
  fatal lines that weren't in the baseline window. Redact secrets (Dokploy MCP already redacts env).
- **HTTP health** — status code, latency vs baseline, and key-content presence on the main routes;
  auth-required routes still reject anonymous.
- **Visual (optional)** — if browser MCP present, screenshot key pages and compare to baseline for
  blank/broken renders.

## Step 3 — Health report
```
DasLab Canary — <app> — <duration> — instrument: dokploy-mcp[+browser]
Container: <healthy | restarting Nx> · HTTP: <routes ok/total, p50 latency vs baseline>
New errors in logs: <n> (<top line, sanitized>)
Visual: <ok | regressions | skipped (no browser)>
Verdict: <HEALTHY | DEGRADED | FAILED>
```

## Step 4 — Status + rollback (§5.5/§6)
- All green vs baseline → `STATUS: DONE — canary healthy over <duration>`
- Regression detected (crash loop, error spike, latency blowout, broken page) → **recommend
  rollback now** (Dokploy `application-redeploy` to the previous image / `rollback`), set ticket
  `blocked`, `@`-mention SRE/CTO → `STATUS: BLOCKED — <regression>, rollback recommended`
- Healthy but with a minor non-blocking anomaly → open follow-up →
  `STATUS: DONE_WITH_CONCERNS — DAS-<id> (<anomaly>)`
- Can't reach Dokploy MCP or the app → `STATUS: NEEDS_CONTEXT — <what's needed>`

## Hard rules
- A deploy is not `done` until the canary is HEALTHY (the Ship gate, §3.5/§6.5).
- Compare against a baseline, not vibes — a number vs the pre-deploy number.
- On a clear regression, recommend rollback **first**, diagnose second (`daslab-investigate`).
- Never paste raw secrets from logs; reference the location.
