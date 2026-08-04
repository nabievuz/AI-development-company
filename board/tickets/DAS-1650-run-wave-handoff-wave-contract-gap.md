---
id: DAS-1650
title: run_wave cannot record a handoff wave — guardrails mutate the board and terminality always fails
status: todo
assignee: sre-lead
author: cto
dept: engineering
priority: p1
parent: 
goal: platform-hardening
labels: [correctness, governance]
zone: scripts
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Hit live during the 2026-08-04 `/daslab-cycle` wave with `organism_emit: true`.**
Two independent defects, both reproduced, both reverted rather than committed. Neither
is theoretical — together they took `diagnostics.py` from 100/100 to 80/100 and
silently overwrote two subagents' recorded determinations.

### 1. `run_wave` mutates board state from guardrail screening of the `output` field

`run_wave(..., run_guardrails=True)` — **the default** — screens each
`TicketResult.output` through the role's OUTPUT guardrail and, after the two bounded
retries, escalates by **writing to the ticket file**: status → `in_review`, assignee →
the role's reviewer, plus appended `origin: output_guardrail` log entries.

Observed on `main`:

| Ticket | Subagent's own determination | What `run_wave` wrote |
|---|---|---|
| DAS-1628 | `interrupted`, `security-lead`, Founder interrupt card raised | `in_review`, `cto` |
| DAS-1645 | `in_review`, `ceo` (ROUTING escalation — author is the reviewer's manager) | `in_review`, `security-lead` |

The DAS-1628 case is the serious one: a deliberately parked ticket with a blocking
Founder question was converted into an ordinary review handoff. The parking decision
and its card survived only because the agent had committed them to its own branch.

The orchestrator's contribution to this was passing condensed summaries where the
skill's snippet says `output=agent_output` — a real fix should make that harder to get
wrong, because the failure is **silent and destructive**:

- The guardrail cannot distinguish "the agent produced bad output" from "the caller
  passed a summary instead of the output". Both escalate identically.
- An observational call documented as producing artifacts also rewrites the board, and
  nothing in the call site says so. `run_guardrails` defaults to `True`.
- The escalation overwrote a status the *accountable role* had reasoned about at
  length, with no conflict detection and no signal that anything was overridden.

### 2. Terminality (ADR-0032 arm 3) cannot hold for any handoff wave

Independent of the above. `check_wave_reconciliation.TERMINAL_STATUSES` is
`frozenset({"done", "blocked"})`, and arm 3 requires every ticket a ledger entry names
to be terminal on the board. But `/daslab-cycle` is instructed to record **every
dispatched ticket**, and a perfectly normal wave ends with tickets in `in_review`
(handed to a reviewer) or `interrupted` (parked on a Founder gate — a status the board
model explicitly defines).

So a wave that hands off rather than completes produces a committed ledger entry that
**can never reconcile**:

```
FAIL: wave-reconciliation gate (GATE-4 / ADR-0032)
  - ledger run_id '01KZ60...': recorded ticket DAS-1628 is 'in_review', not terminal (done/blocked)
  - ledger run_id '01KZ60...': recorded ticket DAS-1645 is 'in_review', not terminal (done/blocked)
[FAIL] Architecture 0/20 → SCORE = 80/100
```

Fixing defect 1 does not fix this. The contract needs a decision: either a handoff wave
is not ledger-recordable, or non-terminal recorded tickets are legitimate and arm 3
must express that (e.g. terminal-for-this-run vs terminal-on-the-board). Whichever way
it goes, `/daslab-cycle`'s "call `run_wave` once per wave" instruction and arm 3 must
stop contradicting each other.

### 3. Minor, same call site: the skill's snippet references a function that does not exist

`.claude/skills/daslab-cycle/SKILL.md` step 6 shows `created_at=dispatch_emitter.utcnow()`.
`dispatch_emitter` does not export `utcnow` — it lives in `dgox.events`, which the same
step tells the caller not to import. Any operator following the snippet gets
`AttributeError` on the first call.

## Acceptance criteria
- [ ] Decide and record whether `run_wave` should mutate board state at all from an
      observational collect-time call; if it should, the call site must make that
      explicit rather than defaulting to it.
- [ ] A caller passing a non-agent-output string cannot silently trigger a destructive
      escalation — detect, refuse, or require the output be marked as such.
- [ ] Guardrail escalation refuses to overwrite a status the assigned role set
      deliberately (at minimum `interrupted`, which encodes a blocking Founder gate),
      or surfaces the conflict instead of resolving it silently.
- [ ] Arm-3 terminality reconciled with handoff waves — with the reasoning recorded, since
      this is a governance-contract decision, not a lint tweak.
- [ ] A regression test covers a full handoff wave end to end (tickets ending
      `in_review` / `interrupted`) and asserts the gate outcome the decision above chose.
- [ ] SKILL.md step 6 snippet corrected to a call that actually runs.
- [ ] `diagnostics.py` 100/100 with the handoff-wave test fixture present.

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Found by hitting it, not by reading. All side effects were reverted before commit:
board mutations to DAS-1628/DAS-1645 restored via `git checkout`, the
`board/wave-ledger.jsonl` entry reverted, and the uncommitted
`metrics/attestations/01KZ60BQMQR3DBMVN5KSTA6Y48.json`,
`metrics/evidence/01KZ60BQMQR3DBMVN5KSTA6Y48.json` and `board/runs/01KZ60.../`
artifacts deleted. `diagnostics.py` back to 100/100 and both the reconciliation and
attestation gates green after the revert.

Consequence for this wave: it produced **no attested ledger record**. That is the
honest outcome — no ticket reached a terminal state, so under the current contract there
is nothing for the ledger to attest. The wave's real outputs live on the two subagent
branches and in the follow-up tickets DAS-1646..DAS-1649.
