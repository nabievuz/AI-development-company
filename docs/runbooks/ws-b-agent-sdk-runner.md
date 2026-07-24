# Runbook — WS-B: headless Agent SDK runner (`daslab_sdk`, ADR-0034)

**AADL Stage 5 — Deployment (GATE-5 for WS-B).** SRE Lead accountable; Security
Lead + Legal consulted. This runbook does **not** flip anything — it is the
ordered procedure for a future, explicit Founder-authorized flip, plus the
rollback and the deploy evidence for *this* merge (flag OFF).

## What ships (this merge)

| File | Role |
| --- | --- |
| `daslab_sdk/runner.py`, `daslab_sdk/contracts.py` | headless `dispatch_ticket`/`dispatch_wave` core (DAS-1555) — flag-gated, no live SDK call in this session |
| `scripts/ws_b_admission.py` | admission gateway, Claude-subscription auth-env isolation, budget/credit ceiling (DAS-1556) |
| `daslab_sdk/requirements-sdk.txt` | the **opt-in** SDK extra — kept out of core `requirements.txt` |
| `tests/test_ws_b_daslab_sdk_runner.py`, `tests/test_ws_b_admission.py`, `tests/test_ws_b_negative_paths.py` | GATE-4 test-scoped adapter + SC-001…SC-004 coverage (DAS-1557) |
| `config/features.yaml:ws_b_agent_sdk_runner` | the flag — **`false`** at merge and after this ticket |

**No production deploy happens here.** The runner ships feature-flagged
**OFF**; the Founder production-deploy gate is not triggered by this merge.
The runner also does not make a live headless Claude call in this session —
that requires subscription auth wired in a real environment and the flag ON,
neither of which this ticket does.

---

## 1. The flip procedure (documented, NOT executed)

Ordered steps to turn `ws_b_agent_sdk_runner` **ON** in production. Every step
below is a future action; **none is performed by this ticket**.

### Step 1 — promote the production admission adapter

DAS-1557 built a **test-scoped** adapter (`tests/test_ws_b_negative_paths.py::
ws_b_admission_adapter`) that maps the 5-outcome `ws_b_admission.
AdmissionOutcome` (`ADMIT` / `REJECTED` / `IDLE_AND_ALERT` /
`SANCTIONED_PAUSE` / `UNAVAILABLE`) onto the runner's 2-outcome
`daslab_sdk.contracts.AdmissionOutcome` (`ADMIT` / `HOLD`), translating the
dataclass shape (`ws_b_admission.AdmissionDecision{outcome,ticket_id,role,
model,reason,alert}` → `contracts.AdmissionDecision{outcome,ticket_id,model,
reason}`).

The CTO bound the **production** adapter to this flip-time wiring (GATE-3
closure, DAS-1556 log; GATE-4 closure, DAS-1557 log): before any live drive,
promote that same 5→2 mapping out of the test file into a real, importable
module (e.g. `daslab_sdk/ws_b_admission_adapter.py` or equivalent — the exact
path is an implementation choice for whoever performs the flip, not decided
here) that `daslab_sdk.dispatch_ticket`/`dispatch_wave` inject as the
`Admitter` the design's §2.2 gateway describes. The mapping to reuse (do not
re-derive it from scratch — the test file is the reference implementation):

- `ADMIT` → `contracts.AdmissionOutcome.ADMIT`
- every non-`ADMIT` outcome (`REJECTED`, `IDLE_AND_ALERT`,
  `SANCTIONED_PAUSE`, `UNAVAILABLE`) → `contracts.AdmissionOutcome.HOLD`,
  preserving `reason`
- dataclass shape translated to `AdmissionDecision{ticket_id, model, outcome,
  reason}`

This is a code change (`daslab_sdk` zone) — it needs its own worktree, branch,
and PR per ADR-0005/the board's git law; it is **out of scope** for this
ticket, which only documents that it must happen before Step 5.

### Step 2 — re-verify the flip-time precondition (from DAS-1553)

**Binding precondition, carried from DAS-1553's GATE-1 closure and the
design's §4.4:** before `ws_b_agent_sdk_runner` is ever flipped ON, re-verify
the *current* Claude plan's Agent-SDK terms, per-plan monthly credit, and
headless-use policy against Anthropic's **live** documentation — not the
`config/budgets.yaml` placeholder numbers (`pro: 20`, `max_5x: 100`,
`max_20x: 200`), which are keyed to the active plan and re-confirmed at this
gate.

**Re-verification performed in this session:** the credit-based subscription
model referenced by `config/budgets.yaml`'s `[NEEDS VERIFICATION at WS-B
go-live]` marker was announced 2026-06-15 and then paused; this session did
not have live network access to Anthropic's current documentation to confirm
whether the per-plan credit ceiling / headless Agent-SDK-use policy is now in
force, still paused, or superseded. **Outcome: unresolved.** Per the ticket's
own instruction and DAS-1553's binding — do not flip on an unverified
assumption — the flag **stays OFF** on that basis alone, independent of any
other precondition below. Whoever performs a future flip must re-run this
check against Anthropic's live docs at that time and record the outcome
before proceeding to Step 5.

### Step 3 — install the opt-in SDK extra

```bash
pip install -r daslab_sdk/requirements-sdk.txt
```

This is a separate, optional-dependency install — never folded into the
core `requirements.txt` (design §6.1: absent SDK ⇒ the runner is simply
unavailable, dispatch unchanged). Verify the import resolves:

```bash
python3 -c "import claude_agent_sdk" 2>&1 | head -5
```

### Step 4 — set Claude-account/subscription auth (never a metered API key)

Authenticate the host running the flip via the Claude-account/OAuth profile
(`ant auth login`), the same resolution order the Agent SDK, `ant` CLI, and
Claude Code all use. Confirm the flip environment does **not** carry
`ANTHROPIC_API_KEY` (including an empty `ANTHROPIC_API_KEY=""`, which still
wins its precedence slot per design §4.1):

```bash
env | grep -i ANTHROPIC_API_KEY || echo "ANTHROPIC_API_KEY absent — correct"
```

A present key (even empty) shadows the subscription OAuth profile and routes
spend onto a metered key — the exact violation `build_subscription_env()`
(`scripts/ws_b_admission.py`) is built to prevent. If this check fails, do
not proceed — fix the environment before Step 5.

### Step 5 — flip `ws_b_agent_sdk_runner` ON (Founder governance act)

Only after Steps 1–4 are each independently confirmed:

```yaml
# config/features.yaml
ws_b_agent_sdk_runner: true
```

This is a `security_sensitive` + `governance_or_policy` change (never
`approval: auto*`, QONUN-5) — a Founder-only act, not something any
engineering role performs unilaterally. It is not performed by this ticket.

---

## 2. Budget/credit at go-live

- **Monthly credit = the SI-5 outer ceiling.** `config/budgets.yaml
  mustaqil.monthly_credit_ceiling` (Q9): the subscription's monthly credit is
  the hard dispatch ceiling for the runner, stricter than the per-run/per-day
  caps above it.
- **Breach → idle + alert.** A wave whose estimated usage would breach
  `mustaqil.caps.per_run`/`per_day` evaluates to idle + alert
  (`on_breach: idle_and_alert`, `scripts/alerting.py`) — zero dispatch, never
  a partial or false-green wave.
- **Credit exhaustion → sanctioned pause.** Monthly-credit depletion
  (`on_exhaustion: sanctioned_pause`) is an expected, resumable halt — not a
  crash or silent stop — and resumes normally once the credit refreshes
  (idempotent re-entry, DAS-1447 guard-before-act).
- **Metered overflow stays OFF.** `metered_overflow: false` is a structural
  invariant (`admit()` has no overflow parameter at all) — spend can never
  exceed the subscription. Flipping it ON is a separate Founder-only budget
  decision, out of scope for both this runbook and the runner's own
  authority.

---

## 3. Rollback

Rollback is a **flag flip**, never a code removal (ADR-0019):

```yaml
# config/features.yaml
ws_b_agent_sdk_runner: false
```

With the flag OFF: `gated_admit()` short-circuits to `UNAVAILABLE` before any
`admit()` logic runs, the `daslab_sdk` dispatch path does not run, and
interactive `/daslab-cycle` dispatch is byte-identical to the runner never
having existed (SC-003). Optionally, also remove the opt-in SDK extra
(`pip uninstall claude-agent-sdk` or equivalent per the packaging in use) —
not required for rollback to take effect, since absent-SDK is itself an
inert, non-broken state (design §6.1), but tidies the host.

No database migration, no data backfill, and no board-schema change is
associated with either direction of this flip — rollback is single-step and
immediate.

---

## 4. Deploy evidence — flag OFF at merge = no live drive

Flag-off state confirmed on this checkout:

```bash
grep -n "ws_b_agent_sdk_runner" config/features.yaml
# 21:ws_b_agent_sdk_runner: false # WS-B headless Agent SDK runner (ADR-0034, daslab_sdk). ...
```

The flag-off no-op tests (SC-003, TB/SR-5) assert an interactive wave driven
with the flag OFF is unaffected by the runner's presence — the evidence this
merge introduces no live-drive behavior change:

```bash
python3 -m pytest tests/test_ws_b_daslab_sdk_runner.py -k flag_off -q
```

---

## 5. Deferred / not this ticket

- Promoting the production admission adapter (Step 1) — a future, separate
  code change with its own worktree/branch/PR.
- Re-verifying Anthropic's live Agent-SDK terms (Step 2) with actual network
  access — this session recorded the check as **unresolved**, which alone
  keeps the flag OFF regardless of any other precondition.
- Installing the SDK extra, wiring subscription auth, and flipping the flag
  (Steps 3–5) — a Founder-authorized act performed at a real go-live, not in
  this session.
