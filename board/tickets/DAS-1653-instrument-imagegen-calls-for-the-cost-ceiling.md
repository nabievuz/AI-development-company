---
id: DAS-1653
title: The imagegen cost ceiling exists but nothing invokes it at call time — instrument the bridge
status: todo
assignee: backend-eng-1
author: finance-analyst
dept: engineering
priority: p1
parent: 
goal: platform-hardening
labels: [governance, cost]
zone: tools/mcp_bridges
depends_on: [DAS-1647]
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Routed by `finance-analyst` at DAS-1647 hand-off, which deliberately delivered
partial work rather than claiming a ceiling it could not make load-bearing.**

DAS-1647 built the mechanism and proved it in both directions:
`config/budgets.yaml` gained a `third_party_tools.imagegen` section with dated
per-image pricing and a `caps.per_day` ceiling (`max_calls: 40`,
`max_cost_usd: 6.00`, `on_breach: deny`), and `scripts/check_cost.py --check-imagegen`
denies on breach — verified by direct probe and by reading real `span` events.

**But nothing calls it when a real image is generated.** Two gaps, both outside
DAS-1647's `config` zone, which is why the widening block in
`governance/policies/third-party-model-tools.md` §5 was deliberately **left in place**:

1. `tools/mcp_bridges/imagegen_tool_bridge.py` neither calls
   `check_cost.py --check-imagegen` pre-flight nor emits a `span` event after a call.
2. `--check-imagegen` is not wired into any automatic gate; a human or CI step must
   invoke it.

The consequence is precise and worth stating plainly: **real traffic can never breach
the ceiling, because no span is ever emitted for an imagegen call.** The deny path is
exercised only by probe mode and hand-built event files. The pricing and the deny logic
are real; they are not yet load-bearing at the moment money is spent.

This is the ticket that makes the ceiling mean something. Until it lands, the bound on
`mcp__imagegen` spend remains **social** (the grant names three design roles), not
mechanical — which is exactly what `security-lead` refused to accept at DAS-1645.

## Acceptance criteria
- [ ] The bridge emits a `span` event per successful generation carrying at minimum the
      model id and a call count, so `--check-imagegen`'s real-event mode sees actual
      traffic. Use the existing `dgox.events` builders — do not invent a second event
      shape.
- [ ] Decide between pre-flight check and post-hoc metering **and record why**. A
      pre-flight `deny` prevents the spend; post-hoc metering only reports it after the
      account is billed. They are not equivalent and the ticket should not treat them as
      interchangeable.
- [ ] A breach actually denies at call time — proven end to end with the ceiling
      temporarily lowered, not by unit test alone. Both directions.
- [ ] Failure of the metering path must not silently disable the ceiling. Decide whether
      an unwritable event store fails open or closed, and justify it — a ceiling that
      quietly stops applying when logging breaks is not a ceiling.
- [ ] `--check-imagegen` wired into an automatic gate, or an explicit recorded decision
      that it stays manual and why.
- [ ] Only then: §5's widening block lifted, in the same change that makes it true.
- [ ] `tests/test_imagegen_tool_bridge.py` green (its 53 cases assert the module never
      raises and never leaks the credential — new I/O must not break either);
      `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on `finance-analyst`'s explicit routing request. `depends_on: [DAS-1647]` because
this instruments the ceiling that ticket built — DAS-1647 is `in_review` with `coo`, so
this is correctly dep-blocked until it closes.

Zone `tools/mcp_bridges`, which it shares with DAS-1644 and DAS-1648. Those three cannot
run in the same wave under the zone guard unless they declare a matching `merge_policy:`
— expect them to serialise across waves.
