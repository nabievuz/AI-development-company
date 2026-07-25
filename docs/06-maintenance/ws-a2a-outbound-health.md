# A2A OUTBOUND health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for A2A OUTBOUND (ADR-0040 / `docs/design/a2a-outbound.md` /
> `docs/specs/009-mustaqil-a2a-outbound/SPEC.md`). Accountable: CPO.
> Responsible: Product Analyst. Consulted: Security Lead, SRE/DevOps Lead.
> Ticket: DAS-1614. Epic: DAS-1606.

## What this is

A **recurring, read-only** health/eval check for the A2A OUTBOUND surface —
the in-tenant boundary on the declared `a2a_outbound` endpoint, the
flag/publish-state drift lock, and the negative-test suite (DAS-1612) — that
composes the checks and artifacts DAS-1607..DAS-1613 already built. Per the
AI-agent-lifecycle policy §3 (Stage 6), the schedule is **data/documentation,
not an installer**: no new scheduler, no second diagnostics harness, no
parallel eval runner. This doc's zone is `docs/06-maintenance/` only — it does
not add or modify anything under `scripts/`, `tools/a2a/`,
`scripts/a2a_intake/`, `config/`, or `docs/adr/`.

**Honesty note on surface state (2026-07-24):** `a2a_outbound` is `false` in
`config/features.yaml` and the endpoint has never been published — DAS-1613
(GATE-5, closed earlier today) confirmed this and it is unchanged here. The
checks below are **armed and run now against the merged-but-dark surface**
(dead code path, no dispatch caller, SC-005 byte-identical). Nothing in this
document claims a live surface is being monitored in production. The
publish-state leg activates in substance only after a Founder flips the flag
via `tools/a2a/publish.py:publish()` (a Founder-only act, QONUN-5/FR-003) —
until then its correct, verified state is "armed, zero events, flag OFF."

## Check script

Check script: `scripts/ws_a2a_health_check.py`

Registered as the `ws-a2a-outbound-health` entry in `maintenance_schedule()`'s
`recurring_runs` list (line 529–543 of `scripts/stage_gate.py`), alongside
`health-tick` (WS4), `golden-eval` (WS6), `memory-hygiene` (ArcRift),
`ws-a-tool-edge-health` (WS-A), `ws-b-runner-health` (WS-B), `ws-d-lens-health`
(WS-D), `ws-c-loop-health` (WS-C), and `ws-e-tenant-health` (WS-E) — this is the
final workstream health entry, no second scheduling mechanism was introduced.

## What it checks

1. **In-tenant boundary drift (SC-003)** — reuses `scripts/check_in_tenant.py`
   (no fork; the SAME script wired at `scripts/diagnostics.py:810-823` as the
   unconditional `tn1-in-tenant-boundary` gate and at
   `.github/workflows/ci.yml:303`) over the tracked
   `config/tenant_boundary.yaml`, which already declares the `a2a_outbound`
   endpoint (`role: a2a`, `carries_code_ip: true`,
   `url: http://127.0.0.1:8765`, deliberately NOT in
   `accepted_external_roles`). A drift toward a hosted relay/registry bind —
   for the A2A endpoint or any other declared code/IP endpoint — is a finding.
   Verified this run:

   ```
   $ python3 scripts/check_in_tenant.py
   TN-1 OK: all code/IP endpoints in-tenant (7 declared; model call excepted).
   exit=0
   ```

2. **Flag/publish-state drift** — verifies `a2a_outbound`'s state in
   `config/features.yaml` matches the last logged Founder act in
   `board/.events.jsonl`. Grounded directly in `tools/a2a/publish.py`'s
   `build_publish_event` (read, not forked) — the emitted event keys are
   verbatim `['decision', 'event_type', 'flag_state', 'principal_id',
   'principal_kind', 'reason', 'target', 'ts']`, `event_type` always
   `"a2a_publish"`. The check is: read the newest `event_type == "a2a_publish"`
   line in `board/.events.jsonl` (if any), compare its `decision`/`flag_state`
   against the live `a2a_outbound:` value in `config/features.yaml` — a
   Founder `allow` event with `flag_state: true` that does not match a live
   `false` (or vice versa) is a finding; an unlogged flip of either is
   independently caught by `git diff`/CODEOWNERS review on
   `config/features.yaml` (a `security_sensitive` path).

   **Verified baseline this run (honest, not fabricated):**

   ```
   $ grep '^a2a_outbound:' config/features.yaml
   a2a_outbound: false          # A2A outbound surface (ADR-0040, ...)

   $ grep -c '"event_type":"a2a_publish"\|"event_type": "a2a_publish"' board/.events.jsonl 2>/dev/null || echo "0 (file absent or no match)"
   0 (file absent or no match)
   ```

   No `a2a_publish` event has ever been logged — expected, since the flag has
   never been flipped. The correct, current baseline is: **flag OFF, zero
   publish events, in agreement (no drift)**. A future finding would be either
   leg moving without the other: a flag flip with no corresponding logged
   Founder `allow` event, or a logged `allow` event with `flag_state: true`
   while the live config still reads `false` (a config rollback that outran
   the ledger, which is not itself a violation but must be visible as a
   reconciliation note, not silently dropped).

   `a2a_outbound` is now included in `scripts/feature_flags.py`'s `DEFAULTS`
   (line 42: `"a2a_outbound": False`), so `feature_flags.enabled("a2a_outbound",
   FEATURES_PATH)` resolves correctly. The check queries the flag via
   `feature_flags.enabled()` (line 133 of `scripts/ws_a2a_health_check.py`),
   not a side-band grep — the unified feature flag reader is now wired (DAS-1624).

3. **Recurring negative-test cadence (SC-005 "stays green" over time)** —
   folds `tests/test_a2a_outbound_endpoint.py` and `tests/test_a2a_intake.py`
   (DAS-1612's suite, 95 tests) into the same recurring
   golden-eval/diagnostics cadence the sibling WS-A/B/C/D/E/H health docs
   already reference (`scripts/agent_eval.py` "golden-eval" entry +
   `scripts/diagnostics.py`'s full-suite run) — not a new runner. Verified
   this run:

   ```
   $ python3 -m pytest tests/test_a2a_outbound_endpoint.py tests/test_a2a_intake.py -q
   ............................................................................................... [100%]
   95 passed in 0.20s
   ```

4. **Report cadence** — findings route into the existing **monthly product
   analytics review** (`product/CLAUDE.md` Success Metrics: "Product
   analytics review delivered monthly"). No new review forum is created. A
   finding from checks 1–3 is written up the same way any other Maintenance
   finding is: attached evidence, a follow-up `board/tickets/` ticket
   (`labels: [security]`, `dept: engineering`) if it is a drift, and a line
   item in the next monthly product analytics review either way (including a
   "no drift, flag still OFF, N tests still green" clean bill when there is
   nothing to escalate).

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-a2a-outbound-health`).
- **Command:** `python3 scripts/ws_a2a_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (in-tenant drift, flag/publish-state
  drift, and/or negative-test drift) — the caller MUST treat this as an alert,
  never swallow it, per the same discipline as every sibling WS-A/B/C/D/E/H entry.

## Alerting — a failure is never silent

A finding from any of the three checks above is treated the same way any
other Maintenance-cadence finding is treated on this program:

1. The verbatim command output is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope)
   with `labels: [security]`, `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE informed) — the
   same path DAS-1551/DAS-1559/DAS-1569/DAS-1577/DAS-1587/DAS-1605 used.
3. The ticket is **never** auto-remediated: fixing an in-tenant drift means
   correcting the drifted endpoint back to `config/tenant_boundary.yaml`'s
   in-tenant declaration (never a hosted target, TN-1/FR-004); fixing a
   flag/publish-state drift means reconciling `config/features.yaml` against
   the `board/.events.jsonl` record of the last genuine Founder act — never
   auto-flipping the flag either direction. `security_sensitive` +
   `governance_or_policy` categories per `config/risk_taxonomy.yaml` forbid
   `approval: auto*` on any of this (QONUN-5). The `a2a_outbound` flag itself
   is never touched by this check or by its remediation — publishing stays a
   Founder-only act.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding (e.g. the same drift class recurring, or a
flag/ledger mismatch found more than once) is a candidate lesson, not just a
one-off ticket. Per ADR-0029 §G5: the finding + accepted remediation is
logged in the relevant ticket (§Alerting above); `daslab-learn` distills only
**Founder-accepted** feedback into a role's `## Learned` section — this check
never writes to `## Learned` itself. Likely destination roles: `security-lead`
(RBAC/TN-1/publish-gate patterns) and `product-analyst` (report-cadence
patterns) per `governance/agent-templates/*.md` overlays.

## Verification

```
python3 scripts/ws_a2a_health_check.py            # human-readable
python3 scripts/ws_a2a_health_check.py --json     # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_a2a_health_check.py -q
```
