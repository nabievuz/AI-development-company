---
id: DAS-1628
title: Adjudicate never-auto-approve path coverage for the remaining founder-only config SSOTs
status: interrupted
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
updated: 2026-08-04
---

> **STANDING DECISION (DAS-1628, Security Lead, 2026-08-04): the presence of
> DAS-1625's edit on `main` is NOT ratification of it.** Founder git authorship
> and a CODEOWNERS-pinned path are not evidence of Founder review in this repo —
> see the Log for why. This ticket is PARKED at its own acceptance criterion 1
> pending an explicit Founder signal (interrupt card `DAS-1628-1`). Do not
> re-derive this; do not proceed on the four config files until the card is
> answered `ratified`.

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

### 2026-08-04 — Security Lead

**GATE ADJUDICATION: acceptance criterion 1 is NOT satisfied. Ticket PARKED
(`todo` → `in_progress` → `interrupted`), interrupt card `DAS-1628-1` raised.**
I did **not** proceed to the four-file adjudication. No config file was edited,
no flag flipped, no glob widened.

The orchestrator explicitly declined to decide this gate and offered evidence for
me to adjudicate rather than re-derive. I verified each item independently and
reached the **opposite** conclusion from the one the evidence superficially
suggests. Recorded above as a **STANDING DECISION** so it is not re-litigated.

#### 1. What was actually asked

Criterion 1 asks whether DAS-1625's `risk_taxonomy.yaml` edit is **ratified** —
not whether it is *present*. Those are different claims, and all the offered
evidence bears only on the second. The edit is indeed present
(`config/risk_taxonomy.yaml:60` carries `**/features.yaml`, verified). That was
never in doubt and is not what the gate tests.

#### 2. Why "Founder-authored commit through a CODEOWNERS-pinned path" is NOT ratification

Four independent findings, each verified in this worktree:

- **Founder git authorship has zero discriminating power here.** Every commit in
  this repository is authored *and* committed as
  `Akmaljon Nabiev <androidakmalbek@gmail.com>` — 53 under that address plus 4
  under the GitHub noreply alias, i.e. **57 of 57**. Of those, **50 carry a
  `Co-Authored-By: Claude ...` trailer**, meaning they are agent-produced work
  committed under the Founder's identity by the harness. The Founder's identity is
  the *default* for agent output in this repo, not a signal of Founder review.
  Commit `5ecd46d` itself carries
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. It is an
  agent commit.

- **CODEOWNERS never fired, and does not distinguish `/config/` anyway.**
  CODEOWNERS is a GitHub *pull-request review-request* mechanism. `5ecd46d` has a
  **single parent** (`892082d`) — it is not a merge commit, so no PR existed, no
  review was requested, and none was approved. Separately, `.github/CODEOWNERS:4`
  is `*  @nabievuz` — **every path in the repo** is pinned to the Founder, so
  "landed through a CODEOWNERS-pinned path" is true of every file ever committed
  here and carries no information specific to `/config/`.

- **The commit never mentions the change.** `5ecd46d` is **91 files, +18823/-206**,
  and its message covers A2A OUTBOUND, WS-F TEMPO GATE-1..4, budget-rail hardening,
  ADR-0040/0042 — with **no** mention of DAS-1625, `features.yaml`, the risk
  taxonomy, or the never-auto-approve matcher. Ratification means a human
  considered *this* change. Riding along unmentioned inside an omnibus commit is
  the opposite of that.

- **No ratification record exists anywhere.** This repo *has* a canonical channel
  for explicit Founder decisions — the interrupt card + `resume:<value>` contract
  (`board/interrupts/README.md`). I read all nine existing cards
  (`FINALE-D0..D8`). **None** concerns the risk-taxonomy matcher. The two nearest
  standing instructions point the other way: **FINALE-D3** carves
  security-sensitive zone diffs *out* of anything auto-approvable, and **FINALE-D4**
  instructs that any NEW founder-grade question should **park that ticket and
  surface it**. All nine cards expired `2026-08-01` (today is 2026-08-04), so none
  is live in any case.

#### 3. DAS-1625's `status: done` does not import ratification

I re-read DAS-1625 directly. Its own log, §7, states: *"I am explicitly **not**
self-approving it: the change needs Founder/CTO ratification at commit/PR time."*
That escalation has **no recorded answer** anywhere in the ticket, the board, or
the interrupt store. `done` was set on the *work*; an unanswered escalation inside
a closed ticket is still unanswered. Treating ticket closure as an answer would let
any escalation be discharged by closing the ticket that raised it.

#### 4. The structural argument that settles it

If "the edit is on `main` under the Founder's git identity" counted as
ratification, then **DAS-1628 could ratify itself by that same route** the moment
it committed — and so could every future governance-SSOT edit. A ratification test
that the agent seeking ratification can satisfy unilaterally, by doing the very
thing needing ratification, is not a test. It would make the QONUN-5
never-auto-approve gate vacuous for exactly the category it most needs to bind.

This is also precisely the compounding this ticket's own Description names: *"Stacking
a second, larger unratified governance-SSOT edit on top of an unratified first one
is precisely the compounding this gate is designed to stop."* Proceeding here would
add **four** more paths to the same matcher on the strength of a ratification that
does not exist.

#### 5. Why `interrupted` and not `blocked`

`blocked` is defined for external-dependency stalls and is never auto-dispatched.
`board/interrupts/README.md` draws exactly this distinction: the interrupt card
exists because `blocked` mischaracterises *"I need a human choice to keep going."*
One explicit Founder answer unparks this ticket, so the card is the right
instrument. Card `board/interrupts/DAS-1628-1.json` (schema-valid against
`board/interrupts/schema.json`) offers three options: `ratified` /
`not-ratified-hold` / `not-ratified-revert`. Per the README, `interrupted` has **no
reviewer semantics**, so `assignee` stays `security-lead` (the resuming agent) and
no reviewer routing applies.

**Idempotency (DAS-1447): re-dispatch is safe to re-run.** Nothing was applied
before the interrupt — no config edit, no commit of a matcher change, no flag
flip, no branch pushed, no dispatch or merge performed. The ticket resumes from a
clean state with no guard needed; there is no side effect to double-apply.

#### 6. Verification — verbatim (state unchanged by me)

```
$ python3 scripts/check_never_auto_approve.py --board board --config config/risk_taxonomy.yaml
OK: 204 tickets checked, no never-auto-approve violations.

$ python3 scripts/board_lint.py
board_lint: OK — 202 ticket(s) checked, 0 violations.
(1 pre-existing non-fatal WARN on DAS-1507, unrelated — same WARN recorded in DAS-1625)

$ python3 scripts/check_org_drift.py
OK: org constants in sync with the schema; never_auto_approve consistent across schema + config.

$ python3 scripts/check_dependency_graph.py
OK: dependency graph acyclic, no dangling deps (138 ticket(s) declare depends_on).

$ python3 scripts/check_comm_flows.py
check_comm_flows: OK — 0 referenced route(s) ... all declared (60 routes).

$ python3 -c "import jsonschema, json; jsonschema.validate(
      json.load(open('board/interrupts/DAS-1628-1.json')),
      json.load(open('board/interrupts/schema.json')))"
card OK against schema.json

$ git diff --stat config/
(empty — no config file touched)
```

#### 6a. BUG FOUND — `diagnostics.py` rejects a validly-formed `interrupted` ticket

**The acceptance criterion "diagnostics.py 100/100" is not reachable in this
environment, and was not before I touched anything.** Reporting both numbers
honestly rather than a green one:

```
$ python3 scripts/diagnostics.py          # on the main checkout, BASELINE
[FAIL] Code-quality    0/15
        XX ruff-clean: ruff unavailable — lint gate cannot run (fail-closed, ADR-0021)
SCORE = 85/100                            # <- pre-existing, tooling absence, not mine

$ python3 scripts/diagnostics.py          # this worktree, after my status change
[FAIL] Code-quality    0/15   (same pre-existing ruff gap)
[FAIL] Consistency     0/15
        XX status-enum: bad status: ["DAS-1628-...md='interrupted'"]
SCORE = 70/100
```

The 15-point Consistency drop is **a defect in `diagnostics.py`, not a defect in
this ticket**. `scripts/diagnostics.py:68` hard-codes a **stale duplicate** of the
status enum:

```python
VALID_STATUS = {"backlog", "todo", "in_progress", "blocked", "in_review", "done"}
```

`interrupted` is missing. The SSOT — `scripts/board_lint.py:111` `VALID_STATUSES`,
mirrored in `board/README.md` — has carried `interrupted` since DAS-1446, and
`board_lint` passes my ticket clean. So the two validators disagree about what a
legal status is.

This directly violates the binding invariant in
`board/interrupts/README.md` §"Consumer sweep": *"no consumer may reject or
strand a validly-formed `interrupted` ticket or silently drop it."* That sweep
enumerates four consumers (board_lint R2, board_lint R8, `/daslab-cycle` triage,
ROUTING.md) and **missed `diagnostics.py`**. DAS-1446's consumer sweep was
incomplete; mine is the first validly-formed `interrupted` ticket to hit it.

**I deliberately did NOT fix it here.** `scripts/` is outside this ticket's
`zone: config`, this ticket is parked at its own gate, and a one-line edit to a
scoring validator should carry its own ticket and its own reviewer rather than
ride along inside a parked governance ticket — that is the same discipline
DAS-1625 applied when it declined to widen the glob set by analogy. The fix is
one word: add `"interrupted"` to `VALID_STATUS`, or better, import
`VALID_STATUSES` from `board_lint` so the duplicate cannot drift again. Routed
below.

**I also did NOT downgrade this ticket to `blocked` to keep the score green.**
`interrupted` is the correct status per the design-of-record; picking a wrong
status to dodge a validator bug is the "disable the gate rather than fix it"
failure mode I argued against in DAS-1625 §5. The score is honest as it stands.

#### 7. Routed onward (NOT decided here)

- **FOUNDER (via card `DAS-1628-1`)** — the ratification question itself. This is
  above my charter: I cannot ratify a governance-SSOT edit, and I especially cannot
  ratify one whose ratification gates my own ticket.
- **NEW WORK → CTO to route (needs a ticket, zone `scripts`).** `diagnostics.py:68`
  `VALID_STATUS` is missing `interrupted` and disagrees with the `board_lint.py`
  SSOT — see §6a. It costs 15 diagnostics points for every `interrupted` ticket on
  the board and breaches the DAS-1446 consumer-sweep invariant. One-line fix;
  preferably de-duplicate against `board_lint.VALID_STATUSES` so it cannot drift
  again. Not fixed here (out of zone, parked ticket).
- **ESCALATION → CTO.** Two structural findings worth a decision beyond this ticket:
  (a) there is **no mechanism in this repo by which a governance-SSOT edit can be
  distinguished as Founder-ratified** — git identity is shared with all agent
  output and CODEOWNERS cannot fire on direct-to-`main` commits, so DAS-1625's
  nominated enforcement layer is structurally incapable of enforcing. (b) All nine
  `FINALE-D*` pre-authorization cards **expired 2026-08-01**; the board still
  contains them with no expiry check. Both are new work, not fixed here.
- **NOTE (no action taken).** `config/egress-allowlist.yaml` — one of the four
  files this ticket would have adjudicated — now carries the `imagegen-openrouter`
  profile admitted by DAS-1645 (`in_review`, zone `tools/mcp_bridges`). I did not
  read into or touch that zone. Had this ticket proceeded, adding
  `egress-allowlist.yaml` to the matcher would have had no retroactive effect on
  that grant (the matcher binds ticket frontmatter, never a diff), so there is no
  interaction to resolve and nothing is owed to DAS-1645.
