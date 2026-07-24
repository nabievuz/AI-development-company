---
id: DAS-1554
title: WS-B Design — daslab_sdk call shape, admission gateway, run_wave boundary
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-002, FR-003, FR-004]
labels: [security]
zone: docs/design
depends_on: [DAS-1553]
created: 2026-07-24
updated: 2026-07-25 # GATE-2 closed
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-B).** Design the runner contract
the Development tickets implement. No code beyond schemas/interface
signatures.

- **Load boundary (SR-1):** the `daslab_sdk` call shape — `cwd` = repo root,
  `setting_sources=["project"]` — that loads the existing `.claude/agents`,
  skills, `CLAUDE.md`, hooks, and `.mcp.json` (ArcRift included) unmodified;
  the explicit invariant that porting the 32 roles to another agent
  abstraction is forbidden.
- **Explicit-model + admission contract (SR-2):** how every dispatch pulls
  `model` from `governance/policies/model-allocation.md` (never trusting
  frontmatter alone); how the runner becomes the ADR-0009 admission
  gateway — what it governs (which model, under which per-dispatch budget,
  ADR-0027 SI-5) and what it does not (no routing/selection decision).
- **`run_wave` boundary (SR-3):** the exact function boundary calling
  `scripts/wave_runner.py:run_wave(plan, results)` with orchestrator-supplied
  data, preserving the ADR-0025 dispatch-equivalence guarantee; how the
  standard `run_start`/`run_end`/`span`/checkpoint/attestation stream
  (ADR-0023/0024/0031/0032) is reused, not forked by a second producer.
- **Board/git-law boundary (SR-4):** confirm the runner reads/writes
  `board/tickets/*.md` exactly as `/daslab-cycle` does; a code-touching ticket
  still requires a worktree/branch/PR; the runner must not merge its own PR.
- **Auth + budget/credit design:** the Claude-account/OAuth authentication
  path (Q9, distinct from an API-key path); how the monthly subscription
  credit composes with the `mustaqil:` per-run/per-day caps already landed in
  `config/budgets.yaml` (DAS-1543); the sanctioned-pause behaviour on credit
  exhaustion (idle + alert, resume on refresh, never a crash or false-green).
- **Isolation note:** the SDK reads host-level config regardless of
  `setting_sources` (ADR-0034's own accepted risk) — design the explicit
  `env`/`cwd` isolation the runner sets so a headless dispatch cannot leak or
  inherit host-level state across concurrent runs.

Security Lead consulted (accountable stage owner = CTO; responsible =
backend-em) — the same posture ADR-0034 itself calls for on this "second
runtime surface to maintain and secure."

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering the SDK call shape, the explicit-model + admission-gateway contract, the `run_wave` call boundary + event/attestation reuse, the board/git-law boundary, and the auth/budget/credit-ceiling integration — each traced to its FR and ADR-0034 SR invariant.
- [ ] Explicit `env`/`cwd` isolation design so concurrent headless dispatches cannot leak host-level state (ADR-0034 accepted risk).
- [ ] Negative-path behaviour specified for SC-002 (missing-model dispatch rejected before the model call) and SC-004 (budget-breach / credit-exhaustion → idle+alert / sanctioned pause) so DAS-1557 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Design). SR-1..SR-4 call-shape + admission +
run_wave-boundary + auth/budget design, per ADR-0034 and SPEC-003.

### 2026-07-25 — Backend EM
**AADL Stage-2 (GATE-2) design delivered → `docs/design/ws-b-agent-sdk-runner.md`**
(no runtime code; schemas/contracts only; touched only `docs/design/` + this
ticket). Mirrors the WS-A design-doc style; every section traced to its FR +
ADR-0034 SR:

- **§1 Call-shape (SR-1/FR-001):** `daslab_sdk` wraps the Claude Agent SDK
  `query(prompt, options)` with `cwd`=repo root, `setting_sources=["project"]` —
  loads the 32 `.claude/agents` shims + skills + `CLAUDE.md` + hooks + `.mcp.json`
  (ArcRift) unmodified. Structural invariant: no `create_agent`/other-abstraction
  role path exists, so a ported role is unreachable by construction.
- **§2 Admission gateway (SR-2/FR-002 + ADR-0009):** every dispatch carries an
  EXPLICIT `model` (required arg, resolved from `governance/policies/model-
  allocation.md`, frontmatter never the trusted source — LAW 3); the runner IS
  the ADR-0009 admission gateway under the SDK — a single fail-closed `admit()`
  governing model + SI-5 budget + swappable auth, making NO routing/selection/
  re-tier decision (that stays in `plan`).
- **§3 run_wave boundary (SR-3/FR-003):** the runner assembles orchestrator-
  supplied `(plan, results)` and calls `scripts/wave_runner.py:run_wave` — the
  SAME single post-decision seam, never a second producer of the
  run_start/run_end/span/checkpoint/attestation/wave-ledger stream. Dispatch-
  equivalence (ADR-0025/0031) holds at a function boundary.
- **§4 Auth+budget+credit (FR-006/007/008, Q9):** Claude-account/OAuth profile
  auth (subscription), NOT a metered API key (env drops `ANTHROPIC_API_KEY`);
  `config/budgets.yaml` `mustaqil:` per-run/per-day = SI-5 hard ceiling; monthly
  credit = outer ceiling; breach/exhaustion → idle+alert / sanctioned pause
  (never false-green/crash); `metered_overflow` stays OFF. Flip-time re-verify of
  live plan terms bound as an explicit Deployment precondition on **DAS-1558**.
- **§5 Board/Git law (SR-4/FR-004):** board canonical (C2), no routing-field
  writes (C3), worktree/branch/PR still required for code (ADR-0005), runner never
  self-merges (C4).
- **§6 Flag + isolation (SR-5/FR-005 + ADR-0034 accepted risk):**
  `ws_b_agent_sdk_runner` OFF ⇒ inert + byte-identical interactive waves; absent
  SDK ⇒ unavailable not broken; explicit constructed `env` (no host-cred
  passthrough) + `cwd` + per-dispatch worktree isolation so concurrent headless
  dispatches can't leak host state.

**Negative-path spec handed to DAS-1557 (§7):** SC-001 dispatch-equivalence
(flag-on==flag-off decisions + one-producer) · SC-002 missing-explicit-model
rejection before the model call (+ frontmatter-not-trusted) · SC-003 flag-off
no-op / byte-identical interactive wave (+ absent-SDK unavailable) · SC-004
budget-breach → idle+alert and credit-exhaustion → sanctioned pause, both
distinct from false-green/crash, idempotent resume.

**Validators (all exit 0):** `python3 scripts/board_lint.py` → OK, 0 violations
(the DAS-1507 body-status WARN is pre-existing, unrelated); `python3
scripts/check_links.py` → OK; `python3 scripts/check_spec_consistency.py` → OK,
10 SPEC.md checked.

Set `status: in_review`, `assignee: cto` (GATE-2 accountable per ROUTING —
Backend EM's manager), bumped `updated`. Security Lead review of §4.1 subscription-
auth + §6.2 host-state isolation is consulted-only and noted for the reviewer.
⛔ LOCAL-ONLY — no commit/push/PR.

### 2026-07-25 — CTO — GATE-2 CLOSURE (design ratified)
**AADL Stage-2 / GATE-2 (Design) CLOSED for WS-B RUNNER.** As accountable stage
owner I reviewed `docs/design/ws-b-agent-sdk-runner.md` against ADR-0034
(SR-1..SR-5, Accepted 2026-07-24), SPEC-003 (FR-001..008 / SC-001..005), ADR-0009
(admission ceiling), ADR-0027 SI-5, and the live `run_wave` boundary. Every
section traces one-to-one to its SR invariant and FR, and each claim was verified
against ground truth, not just the prose:

- **§1 call-shape (SR-1/FR-001):** `cwd`=repo-root + `setting_sources=["project"]`
  loads the canonical 32 `.claude/agents` shims + skills + `CLAUDE.md` + hooks +
  `.mcp.json` unmodified; the structural no-`create_agent`/no-other-abstraction
  invariant makes a ported role unreachable by construction. Sound.
- **§3 run_wave boundary (SR-3/FR-003):** VERIFIED against
  `scripts/wave_runner.py:759` — the design's boundary
  `run_wave(plan, results, *, created_at, …, organism_emit=True)` matches the real
  signature exactly. The runner is a NEW CALLER of the one post-decision seam
  (immutable `(plan,results)`, caller-supplied `created_at`, "reads no clock /
  makes no routing decision"), never a second producer of the
  run_start/run_end/span/checkpoint/attestation/wave-ledger stream. Dispatch-
  equivalence (ADR-0025/0031) holds at a function boundary; flag-on == flag-off.
- **§2 admission (SR-2/FR-002 + ADR-0009):** the runner IS the ADR-0009 gateway
  the ADR deferred to "a future SDK-based runner" — one fail-closed `admit()`
  governs explicit-model (LAW 3, required arg resolved from
  `governance/policies/model-allocation.md`, frontmatter never trusted) + SI-5
  budget + swappable auth, and makes NO routing/selection/re-tier decision. The
  LAW 8 ceiling is honored, not re-opened. Sound.
- **§4 auth/budget (FR-006/007/008 + Q9):** VERIFIED against `config/features.yaml`
  (`ws_b_agent_sdk_runner: false`) and `config/budgets.yaml` (`mustaqil:` caps
  `per_run`/`per_day` `on_breach: idle_and_alert`; `monthly_credit_ceiling`
  `on_exhaustion: sanctioned_pause`; `metered_overflow: false`; the
  `[NEEDS VERIFICATION at WS-B go-live]` marker). Auth-budget matches the Q9
  subscription stance and the SI-5 ceiling; the flip-time re-verify is correctly
  bound as a Deployment precondition on DAS-1558, not a build-time blocker.
- **§5 board/Git law (SR-4/FR-004):** board canonical (C2), no routing-field
  writes (C3), worktree/branch/PR still required for code (ADR-0005), runner never
  self-merges (C4). Sound.
- **§6 flag + isolation (SR-5/FR-005):** flag OFF ⇒ inert + byte-identical
  interactive waves; absent SDK ⇒ unavailable not broken. Sound.

**Security-Lead-consulted review carried by the accountable owner — both flagged
sections judged SOUND, no gap:**
- **§4.1 (Claude-account subscription auth, no metered API key):** the design
  correctly captures the SDK credential precedence (`ANTHROPIC_API_KEY` →
  `ANTHROPIC_AUTH_TOKEN` → OAuth profile, first match wins) and the non-obvious
  gotcha that an empty `ANTHROPIC_API_KEY=""` still WINS its slot and would shadow
  the subscription profile — so the isolation DROPS the key vars entirely rather
  than blanking them, letting the account OAuth profile resolve. Subscription-only
  intent is enforced by env construction, and auth stays swappable behind the one
  §2.2 gateway. No metered-$ leak path. Sound.
- **§6.2 (per-dispatch worktree + constructed env/cwd host-state isolation):**
  directly mitigates ADR-0034's accepted host-leak risk (the SDK reads host-level
  config regardless of `setting_sources`). `cwd`=repo-root pins settings
  resolution; the child env is CONSTRUCTED (allow-set only, no `os.environ`
  passthrough) and omits host `ANTHROPIC_*`/cloud/session vars; per-dispatch env +
  per-dispatch worktree give two isolation surfaces so concurrent dispatches
  (no parallel cap, Model Allocation Law) cannot leak or corrupt one another's
  host state. Least-host-state-by-default posture, correctly bounded by the OFF
  flag. Sound.

**Negative-path spec (§7) ACCEPTED for DAS-1557:** SC-001 dispatch-equivalence +
one-producer, SC-002 missing-explicit-model rejection before the model call
(+ frontmatter-not-trusted), SC-003 flag-off no-op / byte-identical + absent-SDK
unavailable, SC-004 budget-breach → idle+alert and credit-exhaustion → sanctioned
pause (both distinct from false-green/crash, idempotent resume). Each assertion is
expressible against the `daslab_sdk` surface DAS-1555/1556 build plus the existing
`run_wave`/`verify_wave_ledger` primitives.

**Validators (all exit 0):** `python3 scripts/board_lint.py` → OK, 180 tickets, 0
violations (the DAS-1507 body-status WARN is pre-existing, unrelated); `python3
scripts/check_links.py` → OK; `python3 scripts/check_spec_consistency.py` → OK,
10 SPEC.md checked.

**DECISION: GATE-2 CLOSED.** Design ratified. `status: done`. Disposition is
LOCAL-ONLY (docs-only ticket, `zone: docs/design`; no PR/CI on this branch),
accepted on local green — the merged-PR/green-CI acceptance line applies to the
code tickets, not this design deliverable. This UNBLOCKS the two WS-B Development
tickets, which are distinct zones and dispatchable in parallel: **DAS-1555**
(`daslab_sdk` core runner, `zone: daslab_sdk`) + **DAS-1556** (admission/auth/
budget wiring, `zone: scripts`).
⛔ LOCAL-ONLY — no commit/push/PR.
