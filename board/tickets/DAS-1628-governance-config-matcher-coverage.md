---
id: DAS-1628
title: Adjudicate never-auto-approve path coverage for the remaining founder-only config SSOTs
status: todo
assignee: security-lead
author: security-lead
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [governance, security]
zone: config
depends_on: [DAS-1625]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Adjacent gap identified during DAS-1625's adjudication, deliberately left
unfixed there.** DAS-1625 added `**/features.yaml` to `config/risk_taxonomy.yaml`'s
`governance_or_policy` matcher. The same reasoning appears to extend to the other
config files sitting behind the founder-only `config.edit.security` permission,
which currently match **no** never-auto-approve category by path:

- `config/rbac.yaml` — reachable only via the `permission_change`
  `labels: ["permissions", "rbac"]` convention, i.e. exactly the
  convention-dependence DAS-1625's adjudication rejected as insufficient.
- `config/tenant_boundary.yaml` (ADR-0038 TN-1)
- `config/egress-allowlist.yaml`
- `config/budgets.yaml` (SI-5 caps)

**Why this was NOT folded into DAS-1625:** widening a governance SSOT beyond what
a single adjudication sanctioned is itself the failure mode the never-auto-approve
gate exists to prevent. Each file deserves its own reasoning, not a glob applied by
analogy.

**Why this ticket is gated on DAS-1625.** DAS-1625's own edit is itself
never-auto-approve (`config/risk_taxonomy.yaml` matches the very
`governance_or_policy` glob it defines) and is **awaiting Founder ratification**.
Stacking a second, larger unratified governance-SSOT edit on top of an unratified
first one is precisely the compounding this gate is designed to stop. Do not start
this ticket until DAS-1625's edit is ratified.

**Same latency argument applies — this is NOT a live hole.** As established in
DAS-1625: `approval:` and `paths:` are optional and **0 of 182 live tickets declare
either**, so the path-glob layer currently binds nothing on the real board; and the
selector matches self-declared frontmatter strings, never a real diff. Independently,
`rbac.decide()` returns deny for `agent`, `orchestrator`, and `audit-team` on
`config.edit.security` (founder-only, default-deny), and CODEOWNERS pins `/config/`.
A CI pass never authorises an edit. This is defence-in-depth, and should be reasoned
about as such rather than as an emergency.

## Acceptance criteria
- [ ] DAS-1625's `risk_taxonomy.yaml` edit confirmed ratified before any work starts (else this ticket stays parked).
- [ ] Each of the four files adjudicated on its own merits, with the decision and reasoning recorded per file — a single blanket glob is an acceptable outcome ONLY if argued explicitly, not assumed.
- [ ] For every file added: the gap proven closed by probe, and glob over-reach checked (tree sweep for other matching paths; no legitimate flow newly blocked).
- [ ] For every file NOT added: the reason recorded as a standing decision so it is not re-escalated.
- [ ] `check_never_auto_approve.py` green; `diagnostics.py` 100/100; `board_lint`/validators green; no flag flipped; no `project:` field (R9).

## Log
### 2026-07-24 — Security Lead
Raised in the DAS-1625 adjudication report as an explicit "new work, not fixed,
deliberately" item; recorded by the orchestrator in the same run. Left `todo` and
gated on DAS-1625 rather than dispatched immediately — the orchestrator declined to
stack a second unratified governance-SSOT edit in the same run.
