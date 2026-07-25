---
id: DAS-1625
title: Adjudicate whether config features.yaml belongs in the never-auto-approve governance matcher
status: done
assignee: security-lead
author: sre-lead
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-006]
labels: [governance, security]
zone: config
depends_on: [DAS-1617]
created: 2026-07-24
updated: 2026-07-24
---

> **STANDING DECISION (DAS-1625, Security Lead, 2026-07-24): `**/features.yaml`
> IS a `governance_or_policy` never-auto-approve path.** Adjudicated, applied,
> proven. Do not re-escalate this question per workstream — see the Log for the
> probe, the reasoning, and the over-reach analysis.

## Description

**Escalated by SRE Lead from DAS-1617 (WS-F GATE-2 Design) for Security Lead
adjudication.** `config/risk_taxonomy.yaml`'s `governance_or_policy` matcher lists
`**/loop.yaml` but **not** `**/features.yaml` (line 52).

`config/features.yaml` is where every Founder-only flip point lives —
`heartbeat_enabled` (ADR-0027 SI-7), `a2a_outbound` (ADR-0040 FR-003),
`organism_emit`, and the whole MUSTAQIL `ws_*` family. Its sibling governance SSOT
`config/loop.yaml` IS matched.

**Verified latent, NOT live** (probed against the live matcher by the escalating
SRE Lead — re-verify independently, do not take it on trust): a synthetic ticket
carrying `approval: auto` plus `paths: ["config/features.yaml"]` matches **zero**
never-auto-approve categories, whereas the same ticket with `config/loop.yaml`
matches `governance_or_policy`. It is not currently exploitable because a flip is
structurally unreachable by other means and every WS-F ticket — DAS-1622 included —
carries `stage: GATE-5` + `labels: [security]`, which resolves to two categories
independently. The defence-in-depth layer is what is missing, not the flip guard
itself.

**The question to adjudicate — this is a judgement call, not a foregone
conclusion.** Decide, as Security Lead, whether adding `**/features.yaml` to
`governance_or_policy` is correct, and record the reasoning either way:
- If YES — make the minimal edit and prove it closes the gap. Then check for
  over-reach: `**/features.yaml` is a glob, so confirm it does not sweep in
  unrelated files elsewhere in the tree, and confirm no legitimate routine flow
  (a test fixture, a scratch copy, a generated file) is broken by the new match.
- If NO — say precisely why the existing `labels: [security]` / `stage: GATE-5`
  coverage is sufficient and record that as the standing decision so this is not
  re-escalated every workstream.

⛔ You MUST NOT flip any flag in `config/features.yaml`. This ticket changes the
*matcher* that governs approval of edits to that file, never the file's values.
`git diff config/features.yaml` must be empty at the end.

## Acceptance criteria
- [x] The gap independently re-verified (or refuted) against the live matcher, with the probe and its verbatim output recorded — not accepted from the escalation report.
- [x] An explicit Security Lead decision recorded with reasoning, in either direction.
- [x] If the decision is to add the matcher — the edit applied, the gap proven closed by re-running the probe, and the absence of glob over-reach demonstrated.
- [x] `check_never_auto_approve.py` green; `diagnostics.py` 100/100; `board_lint`/validators green.
- [x] `git diff config/features.yaml` empty; no flag flipped; no `project:` field (R9).

## Log
### 2026-07-24 — SRE / DevOps Lead
Escalated from DAS-1617's GATE-2 close (recorded by the orchestrator in the same
run). Not fixed in DAS-1617 because the fix edits a `governance_or_policy` path,
sits outside that ticket's `zone: docs/design`, and is a Security Lead / CTO call
rather than an SRE one. Non-blocking for WS-F: GATE-2 closed on its own merits and
DAS-1618 is unblocked independently of this ticket.

### 2026-07-24 — Security Lead

**DECISION: YES — `**/features.yaml` added to `governance_or_policy`.** The
escalation is **CONFIRMED, not overstated**, and its "latent, not live"
characterisation is **correct**. One line changed in `config/risk_taxonomy.yaml`.
No flag flipped. Adjudication is recorded above as a **STANDING DECISION** so it
is not re-litigated each workstream.

#### 1. Independent re-verification (escalation NOT taken on trust)

I did not reuse the SRE Lead's probe. I wrote my own
(`probe_das1625.py`, scratchpad — not committed; it is reproducible from this
log) which drives the live matcher two independent ways against the **real**
`config/risk_taxonomy.yaml`: (a) in-process `check_never_auto_approve.matches_category`
looped over every never-auto-approve category, and (b) the real CLI end-to-end on
an isolated temp board, one synthetic ticket per case. Cases A/E/F are the *worst
realistic* shape — `approval: auto` + `paths:` only, with **no** `labels:`, **no**
`stage:`, **no** `ticket_type:`, i.e. a ticket authored without the WS-F conventions.

**Verbatim, BEFORE the edit:**

```
PART 1 — in-process matcher (matches_category) vs REAL taxonomy
A_features_bare       paths=['config/features.yaml']            -> *** NO CATEGORY — auto-approve ALLOWED ***
B_loop_bare           paths=['config/loop.yaml']                -> BLOCKED by governance_or_policy
C_risktax_bare        paths=['config/risk_taxonomy.yaml']       -> BLOCKED by governance_or_policy
D_features_wsf_conv   paths=['config/features.yaml']            -> BLOCKED by gate5_deployment,security_sensitive
E_features_nested     paths=['projects/x/config/features.yaml'] -> *** NO CATEGORY — auto-approve ALLOWED ***
F_features_bare_name  paths=['features.yaml']                   -> *** NO CATEGORY — auto-approve ALLOWED ***

PART 2 — real CLI end-to-end on an isolated temp board
A_features_bare       exit=0  OK: 1 tickets checked, no never-auto-approve violations.
B_loop_bare           exit=1  FAIL: never-auto-approve violations (QONUN-5): |   - PROBE-B: auto-approved but category 'governance_or_policy' requires human approval
C_risktax_bare        exit=1  FAIL: ... 'governance_or_policy' requires human approval
D_features_wsf_conv   exit=1  FAIL: ... 'gate5_deployment' ... | ... 'security_sensitive' ...
E_features_nested     exit=0  OK: 1 tickets checked, no never-auto-approve violations.
F_features_bare_name  exit=0  OK: 1 tickets checked, no never-auto-approve violations.
```

The claim in the escalation is exactly reproduced: a bare `approval: auto` +
`paths: ["config/features.yaml"]` ticket matched **zero** categories and exited
**0**, while the identical ticket naming `config/loop.yaml` was blocked by
`governance_or_policy`. Case D independently confirms the escalation's own
mitigating claim: with `stage: GATE-5` + `labels: [security]` the same ticket was
blocked by **two** categories (`gate5_deployment`, `security_sensitive`) even with
the glob absent.

#### 2. Exposure characterisation — LATENT confirmed, and weaker than a live hole

I checked the escalation's reasoning rather than restating it, and the exposure is
**narrower** than the escalation implies, for two reasons it did not name:

- **The path selector currently binds nothing on the live board.** `approval:` and
  `paths:` are OPTIONAL frontmatter (board/README.md). Measured: `grep -rl '^approval:' board/` → **0** of 182 tickets; `grep -rl '^paths:' board/` → **0**. The
  never-auto-approve gate only ever fires on a ticket that *declares* it was
  auto-approved. Nothing on the board does. So this was never a live bypass — it is
  a declaration-consistency layer with a hole, not an open door.
- **The path selector is self-declared, therefore advisory by construction.** It
  matches strings a ticket writes about itself, never a real diff. A ticket that
  edits `config/features.yaml` and simply omits `paths:` is unmatched today and
  would remain unmatched after my edit. This layer can only ever be
  defence-in-depth; treating it as the flip guard would be the actual error.

**Is there ANY path where an `approval: auto` ticket touching `config/features.yaml`
reaches an agent?** Yes — *as a declaration*. Nothing forces a ticket to carry
`labels: [security]` or `stage: GATE-5`; those are authoring convention. A future
ticket under a different goal, authored by any role, touching the feature-flag SSOT
and following the optional declaration convention, would have passed CI clean. That
is a real defect in the layer, and is why I decided YES.

**But it is not a live hole**, because a CI pass never authorises a flip. The
actuation controls, all verified today and all independent of this matcher:

| Layer | Control | Verified |
|---|---|---|
| Identity/RBAC | `config.edit.security` (scoped in `config/rbac.yaml` L77 to "rbac.yaml / tenant_boundary.yaml / egress-allowlist.yaml / **features.yaml**") is founder-only; `scripts/rbac.py` `FOUNDER_ONLY` refuses to LOAD a grants file that gives it to a non-founder kind | probe: `agent → ('deny', "agent is not granted 'config.edit.security' (default-deny)")`; same deny for `orchestrator` and `audit-team`; `founder → ('allow', ...)` |
| Human review | `.github/CODEOWNERS` `/config/ @nabievuz` — any PR touching `config/features.yaml` requests Founder review | read |
| Evidence | `scripts/check_heartbeat_readiness.py` — `heartbeat_enabled` flip needs a ≥3-day clean shadow window (today: **NOT READY, 0/3**) | unchanged by this ticket |
| Declaration | `check_never_auto_approve.py` ← **the layer repaired here** | this ticket |

DAS-1622 re-read directly: it carries `stage: GATE-5`, `labels: [governance, security]`,
no `approval:`, no `paths:`, `status: blocked`. The gate never fires on it either way;
its Founder-only character rests on the layers above, not on this matcher. **Nothing
in this ticket changes heartbeat readiness, and no flag was flipped.**

#### 3. Why YES rather than NO

- **Symmetry.** `loop.yaml` (loop-mode SSOT) and `features.yaml` (feature-flag SSOT)
  are the same class of Founder-only governance SSOT; ADR-0027 cites both in the same
  breath and `rbac.yaml` scopes both under one founder-only permission. The absence
  was an accident of drafting, not a design distinction. I could find no reasoning
  that would justify covering one and not the other.
- **Convention is not structure.** The alternative (NO) would rest the coverage of a
  QONUN-5 *floor* category on tickets happening to be labelled `security`. The
  hard-coded `_QONUN5_FLOOR` in three separate modules exists precisely because these
  categories must not depend on anything a ticket author can forget.
- **Asymmetric error cost.** A false positive costs one human approval on a
  feature-flag ticket — which the CODEOWNERS layer already requires anyway, so the
  marginal cost is ~zero. A false negative lets an auto-approved edit to the
  Founder-only flip SSOT pass CI clean. The matcher's own docstring commits to
  erring toward catching more.

#### 4. Gap proven closed — verbatim, AFTER the edit

```
A_features_bare       paths=['config/features.yaml']            -> BLOCKED by governance_or_policy
D_features_wsf_conv   paths=['config/features.yaml']            -> BLOCKED by gate5_deployment,governance_or_policy,security_sensitive
E_features_nested     paths=['projects/x/config/features.yaml'] -> BLOCKED by governance_or_policy
F_features_bare_name  paths=['features.yaml']                   -> BLOCKED by governance_or_policy

PART 2 — real CLI:
A_features_bare  exit=1  FAIL: ... - PROBE-A: auto-approved but category 'governance_or_policy' requires human approval
E_features_nested exit=1 FAIL: ... 'governance_or_policy' requires human approval
F_features_bare_name exit=1 FAIL: ... 'governance_or_policy' requires human approval
```

#### 5. Over-reach analysis — the glob sweeps in nothing

This was checked, not assumed. An over-broad security glob that blocks ordinary work
gets disabled by the next person, which is worse than the gap.

- **What the glob can match in this tree.** `git ls-files | grep '(^|/)features\.yaml$'`
  → exactly **one**: `config/features.yaml`. Untracked (`--others --exclude-standard`)
  → **none**. Untracked *including* gitignored → **none**. Filesystem sweep found only
  `./config/features.yaml` plus three `.claude/worktrees/*/config/features.yaml` — the
  same tracked file in sibling checkouts of this repo, not distinct artifacts.
- **Structurally it cannot break a filesystem flow at all.** The matcher compares
  against strings in a ticket's `paths:` frontmatter, never against files on disk.
  So a test fixture, a generated file, or a scratch copy cannot be "newly blocked".
  Concrete case: `scripts/kill_switch_drill.py:169` writes a temp `features.yaml`
  into a work dir every drill run — unaffected, because no ticket declares that path.
- **Zero regressions on the live board.** 0 of 182 tickets declare `paths:`, so the
  new glob changes the classification of exactly **zero** existing tickets.
- **Blast radius of a future match.** The only behaviour change is: a ticket that
  declares it edits a `features.yaml` may no longer *also* declare `approval: auto`.
  It is not blocked from being worked — it is required to record a human approver.
  That is the intended, minimal outcome.
- **Deliberately NOT broadened.** The glob matches `features.yaml` only — not
  `features.yml`, not `feature_flags.*`, not `config/**`. Minimal edit, exactly
  mirroring the `loop.yaml` precedent. Broadening is what invites the over-reach
  failure mode.
- CI scans `--board board` only; project boards live under gitignored `projects/`
  and are not swept, so no project flow is touched.

#### 6. Verification — verbatim

```
$ python3 scripts/check_never_auto_approve.py --board board --config config/risk_taxonomy.yaml
OK: 184 tickets checked, no never-auto-approve violations.
exit=0

$ python3 scripts/check_org_drift.py
OK: org constants in sync with the schema; never_auto_approve consistent across schema + config.

$ python3 scripts/board_lint.py
board_lint: 1 body-status warning(s) (non-fatal ...):
  WARN  DAS-1507: a 'status: <status>' line appears in the ticket BODY ...
board_lint: OK — 182 ticket(s) checked, 0 violations.
(pre-existing WARN on DAS-1507, unrelated to this ticket)

$ python3 -m pytest tests/test_check_never_auto_approve.py tests/test_org_schema.py \
    tests/test_intent_preview.py tests/test_p4_affordances.py \
    tests/test_adaptive_taxonomy.py tests/test_stage_gate.py -q
124 passed in 0.83s

$ python3 scripts/diagnostics.py
[PASS] Security       10/10
SCORE = 100/100

$ git diff config/features.yaml
(empty — no output)
$ grep -nE "heartbeat_enabled|a2a_outbound" config/features.yaml
12:heartbeat_enabled: false  ...
29:a2a_outbound: false       ...
```

`git diff config/risk_taxonomy.yaml` shows one changed `paths:` line plus the
rationale comment above it, and nothing else.

Note for the committer: `git diff HEAD -- config/features.yaml` is **not** empty —
it shows a `+a2a_outbound: false` line that was **already staged in the index before
this run began** (the concurrent A2A workstream). That change is not mine; my
working-tree diff against the index is empty and I made no edit to that file. The
added flag is `false`.

#### 7. Findings routed onward (NOT fixed here — out of this ticket's remit)

- **ESCALATION → CTO (ratification).** This edit lands *inside* a
  `governance_or_policy` never-auto-approve path (`config/risk_taxonomy.yaml` matches
  its own glob). Per QONUN-5 that class is human-approval-only, so I am explicitly
  **not** self-approving it: the change needs Founder/CTO ratification at commit/PR
  time (CODEOWNERS `/config/ @nabievuz` is the enforcing layer). Flagged, not assumed.
- **ADJACENT GAP (new work, needs a ticket).** The same probe shows the *other three*
  files scoped by the founder-only `config.edit.security` permission are likewise
  unmatched by any never-auto-approve path glob:
  `config/rbac.yaml` → NO CATEGORY, `config/tenant_boundary.yaml` → NO CATEGORY,
  `config/egress-allowlist.yaml` → NO CATEGORY (`config/budgets.yaml` too).
  `rbac.yaml` is reachable only via the `permission_change` `labels: [permissions, rbac]`
  convention — the *same* convention-dependence this ticket just rejected for
  `features.yaml`. Same latency argument applies (declaration layer only, RBAC and
  CODEOWNERS still closed), so this is **not** a live hole either. I deliberately did
  **not** widen the glob set beyond what this ticket sanctions: an unreviewed
  broadening of a governance SSOT is exactly the failure mode this gate exists to
  prevent. Recommend a follow-on ticket for Security Lead / CTO.

Nothing here changes WS-F: heartbeat readiness remains honestly **NOT READY (0/3
clean days)** and DAS-1622 remains `blocked` by design as a Founder-only act.
