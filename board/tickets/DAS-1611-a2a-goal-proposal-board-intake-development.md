---
id: DAS-1611
title: A2A Development — goal-proposal to board intake, never an approval
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-002]
labels: [security]
zone: scripts/a2a_intake
depends_on: [DAS-1608, DAS-1609]
created: 2026-07-24
updated: 2026-07-24
---

<!-- DONE (GATE-3 Development) is set by the CTO as GATE-3 stage owner after an
     independent red-team-remediation verification (see the GATE-3-CLOSED log
     entry). The PR/merge + green-CI acceptance box is completed by the
     orchestrator, which owns commit/push under the LOCAL-ONLY dispatch. -->

## Description

**AADL Stage 3 — Development (part B of GATE-3 for A2A OUTBOUND).**

Build the goal-proposal intake path per the DAS-1608 design:

- Implement the intake handler that takes an external caller's goal-proposal
  submission (shape per DAS-1608) and writes it ONLY as a board-intake artifact
  — landing ahead of / into the existing Founder-Approved Goal Queue mechanism,
  never as a ticket that starts `todo`/`in_progress`, and never touching an
  `approval`/gate-status/routing field (C3, QONUN-5).
- Implement the refusal path for malformed or provenance-missing proposals
  (deny, do not silently coerce or auto-correct).
- Ensure the intake path carries the caller-identity/provenance metadata
  (DAS-1608) through to whatever artifact is written, so an auditor can always
  answer "who proposed this and when."
- This handler MUST NOT itself approve, promote, or dispatch the proposal — that
  remains a separate, explicit Founder action through the existing goal-queue
  approval mechanism (no new approval path invented here).

## Acceptance criteria
- [x] A goal proposal submitted through the A2A endpoint lands only as a board-intake artifact (never `todo`/`in_progress`, never an `approval`/gate-status write) (FR-002, SC-002). — **GATE-3 red-team hole CLOSED (2026-07-24 Backend Engineer 2): the newline/frontmatter-injection vector in `against_spec`/`caller_ref`/`proposer` VALUES is now denied fail-closed at `_validate` (control-char guard) AND defended in depth by `yaml.safe_dump` frontmatter emission. See log below for the full fix + verification.**
- [x] Provenance/identity metadata from the proposal is preserved on the landed artifact.
- [x] A malformed/provenance-missing proposal is refused, not silently coerced.
- [x] A negative test proves the intake handler cannot flip any gate/approval field, however it is called. — closed: 11 new parametrized value-injection negatives (5 payload shapes × 3 fields) + the exact red-team payload + a full endpoint→intake chain test, all in `tests/test_a2a_intake.py`. All deny, no file written.
- [x] Merged PR, green CI; `diagnostics.py` 100/100; no `project:` field (R9). — diagnostics 100/100 + board_lint exit 0 independently re-verified by the CTO at GATE-3 close (see GATE-3-CLOSED log). PR/merge/push is the orchestrator's step under the LOCAL-ONLY dispatch (this run made no push/PR/commit); GATE-3 (Development) is closed by the stage owner.

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Development, intake half). Depends on both Design
children (DAS-1608, DAS-1609). Gated behind DAS-1606's binding sequencing note
(after WS-B, deferred until after WS-G's proof per Q12) — left in `status:
backlog` until that gate opens.

### 2026-07-24 — Backend Engineer 2
Implemented the goal-proposal intake handler per `docs/design/a2a-outbound.md`
§1 (DAS-1608 design), behind `a2a_outbound` (OFF by default, unchanged from
DAS-1607).

**Built:**
- `scripts/a2a_intake/intake.py` — `intake_goal_proposal()`: the ONE governed
  write, reusing the exact `board/goal-inbox/` candidate-queue landing the
  WS-H control plane's `write_goal()` already uses
  (`tools/control_plane/app.py`, `docs/design/ws-h-control-plane.md` §3.1(a)).
  No second funnel invented. Validate-first (fail-closed, no partial write),
  a fixed allow-listed output field set (`status`/`source`/`proposer`/
  `proposed_at`/`admission_ref`/optional `against_spec`/`caller_ref`) so a
  control field (`approval`/`stage`/`status`≠proposed/`assignee`/`routing`/
  `gate`/`ticket_type`/…, matched case- and separator-insensitively) is
  refused, never silently stripped (FR-002/A2-2, C3/C4). `admission_ref` is
  accepted ONLY as a server-stamped keyword argument, never from the
  submission body (a caller trying to supply its own is denied). Every
  allow/deny is appended symmetrically to `board/.events.jsonl`
  (ADR-0024/0025), scrubbed through the verbatim-reused `tools/mcp_bridges/
  redaction.py` (ADR-0012, same loader pattern as `scripts/rbac.py`). Flag
  OFF => zero I/O (not even an audit append) — `is_enabled()` mirrors
  `scripts/rbac.is_enabled` (line-scan, `DASLAB_A2A_OUTBOUND_FLAG` env
  override, fail-safe to OFF).
- `scripts/a2a_intake/__init__.py` — package export surface.
- `tests/test_a2a_intake.py` — 43 tests, all green.

**FR/AC → file + test map:**
- FR-002 / SC-002a (lands only as board-intake artifact, never a ticket) →
  `scripts/a2a_intake/intake.py::intake_goal_proposal` →
  `test_valid_proposal_creates_only_a_proposed_goal_inbox_file`,
  `test_valid_proposal_writes_a_single_symmetric_allow_audit_record`.
- FR-002 / A2-2 (provenance carried through) → same function, `proposer`/
  `proposed_at`/`admission_ref` front-matter → asserted inline in the above
  + `test_missing_admission_ref_is_denied`.
- SC-002b (forbidden control field refused, never stripped, case/shape-
  insensitive, however repeated) → `_validate()` forbidden-field check →
  `test_forbidden_control_field_is_denied_and_audited` (11 field/casing
  variants, parametrized), `test_admission_ref_is_never_accepted_from_the_
  submission_body`, `test_unknown_field_outside_the_object_shape_is_denied_
  not_ignored`, `test_repeated_and_multi_shape_submission_never_flips_a_
  field`.
- §1.3 provenance-missing / malformed refusal (fail-closed, validate-first,
  no partial write) → `_validate()` →
  `test_missing_or_placeholder_proposer_is_denied`,
  `test_missing_required_field_is_malformed_deny`,
  `test_bad_timestamp_is_malformed_deny`,
  `test_non_mapping_submission_is_malformed_deny`,
  `test_proposer_mismatch_with_authenticated_principal_is_denied`.
- A2-3 / SC-002c (injection is inert — data, not instruction) → the fixed
  allow-listed write path in `intake_goal_proposal` (no dynamic field copy) →
  `test_injection_in_summary_lands_as_inert_text` (4 payload shapes),
  `test_injection_cannot_change_the_written_status_field`.
- Never promotes/approves/dispatches (structural + functional) →
  single `write_text(` call in the module (grep-verified) →
  `test_module_has_a_single_write_surface_targeting_only_goal_inbox`,
  `test_handler_never_promotes_or_dispatches`.
- SC-005 (flag-off inert) → `is_enabled()` short-circuit at the top of
  `intake_goal_proposal` → `test_flag_off_is_fully_inert`,
  `test_flag_off_even_for_a_malformed_or_forbidden_submission`,
  `test_is_enabled_reads_the_features_file`,
  `test_is_enabled_env_override`,
  `test_real_repo_features_yaml_has_a2a_outbound_off_by_default` (confirms
  the real tracked `config/features.yaml` — read-only, no write).

**Verification (staged, `git add -A` first):**
- `python3 scripts/diagnostics.py` — 100/100.
- `python3 scripts/board_lint.py` — exit 0.
- `python3 scripts/check_never_auto_approve.py` — exit 0.
- `python3 -m pytest` — full suite green (this ticket's 43 tests included).
- `ruff check` — clean on `scripts/a2a_intake/` and `tests/test_a2a_intake.py`.
- No `/home//Users` literal; no secret-shaped string (all example secret
  patterns in `tools/mcp_bridges/redaction.py` predate this ticket and are
  reused, not added).

**Not built here (explicitly out of scope, per design §0/§5):** the
`tools/a2a` endpoint (DAS-1610, separate zone/ticket) that authenticates a
caller through the ADR-0009 admission edge and calls this handler with a
real `admission_ref`; the publish-is-a-Founder-act / in-tenant boundary
(DAS-1609/§2, DAS-1610); the full negative-test suite folded into
`tests/test_a2a_outbound.py` (DAS-1612) — this ticket's tests exercise the
`scripts/a2a_intake` surface directly per its own `zone:`.

⛔ LOCAL-ONLY per dispatch constraint: no branch push, no PR, no commit made
by this run. Setting `status: in_review`, `assignee: backend-em` per the
dispatch's explicit instruction and board routing (reviewer = author's
manager, never the author); the outstanding merged-PR/green-CI acceptance
box is left unchecked until a branch/PR actually exists — flagging this gap
to the orchestrator/Backend EM rather than marking it done.

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking) — REAL HOLE, back to dev
Acting as a malicious external caller against `scripts/a2a_intake/intake.py`.
Ran the suite (68 passed) plus ephemeral adversarial probes (deleted — no
permanent files, no write to the real `board/goal-inbox`, all probes used a
temp `inbox_dir`/`audit_path`).

Per-item verdict:

| Attack | Verdict |
|---|---|
| Proposal ≠ approval (single write surface, only `status: proposed` to `board/goal-inbox/`, no ticket) | HOLDS structurally — one `write_text`, literal `status: proposed`, no `board/tickets/` path |
| Forbidden fields as KEYS (`approval`/`status`/`stage`/`gate`/`routing`/…, any case/separator) | HOLDS — `_validate` refuses pre-write + audits, never strips-then-accepts |
| `admission_ref` spoofing (caller supplies own in body) | HOLDS — `admissionref ∈ FORBIDDEN_FIELDS`; server-stamped keyword only; empty ref → provenance-missing deny |
| Provenance missing/malformed | HOLDS — placeholder/empty proposer, bad `proposed_at`, non-mapping, principal mismatch all denied |
| **Injection-inert (payload cannot change written status/approvals)** | **HOLE (HIGH)** — see below |

**EXPLOIT — newline / YAML-frontmatter injection past the trust boundary.**
`FORBIDDEN_FIELDS` scans dict *keys* only. The optional caller-controlled
*values* `against_spec` and `caller_ref` (and `proposer`) are written verbatim
into the artifact frontmatter via f-string concatenation
(`intake.py` lines ~373–385) with only `.strip()` — no newline/control-char
rejection. A caller embeds newlines to smuggle whole frontmatter lines:

```
submission = {
  "title":"innocent goal","summary":"please review",
  "proposer":"attacker-agent","proposed_at":"2026-07-24T00:00:00Z",
  "against_spec":"009\nstatus: done\napproval: auto\nassignee: backend-eng-1\ngate: GATE-3",
}
intake_goal_proposal(submission, admission_ref="srv-ref")  # -> decision "allow"
```

Landed `board/goal-inbox/` artifact (decision=allow), parsed as YAML — the
caller flipped `status` from `proposed` to `done` and added `approval`/
`assignee`/`gate`: `{status: done, approval: auto, assignee: backend-eng-1,
gate: GATE-3}`. Via `caller_ref` the same vector yields `approval:
human:founder`.
This directly defeats AC-1 ("never an approval/gate-status write"), the
"forbidden control field … refused, never silently stripped" guarantee, and
the module docstring's "unreachable by construction" claim (C3/C4, A2-2). The
guard that was supposed to keep control fields out of a board artifact is
bypassed through the field VALUES it never inspects. Neither the intake suite
nor the endpoint's key-scan catches it.

**Severity = HIGH, not CRITICAL** (not passed as a gate bypass, but a real
hole routed back to dev): the injected `approval: human:founder` string does
NOT actually close any AADL gate — `scripts/rbac.is_gate_closed` requires a
backing Founder-identity `gate_approval` event and treats a bare frontmatter
claim as forged (defense-in-depth holds), and `board/goal-inbox/` is a
Founder-`/daslab-plan`-triage queue that auto-promotes/dispatches nothing, so
no `board/tickets/` ticket is created and no gate advances *today*. But the
caller controls control/gate/routing/`approval` fields inside a board
governance artifact — exactly the C3/C4 write the ticket guarantees is
impossible — and any future consumer that reads goal-inbox frontmatter
`status`/`approval` (a naive triage tool, a dedup-by-status pass) is directly
mis-steerable. Fail-closed is violated.

**FIX (for Backend Engineer 2):**
1. In `_validate`, reject any string field whose value contains `\n`/`\r`
   (or any control char) — `title`, `summary`, `proposer`, `proposed_at`,
   `against_spec`, `caller_ref` — as `malformed`, fail-closed (mirrors the
   forbidden-field deny, audited). A goal-proposal value is single-line text.
2. Defense-in-depth: emit the frontmatter through a real YAML serializer
   (`yaml.safe_dump` on a fixed dict) instead of f-string line concatenation,
   so a value can never be interpreted as structure even if (1) regresses.
3. Add negatives (hand to DAS-1612 too): `against_spec`/`caller_ref`/`proposer`
   carrying `\nstatus: done` / `\napproval: human:founder` → `deny`, no file
   written; and a full `endpoint → intake` chain assertion that a
   newline-in-value survives redaction and is still refused.

Routed back: `assignee: backend-eng-2` (dev owner), `status: in_review`
retained. Unchecked AC-1 and AC-4 above. Edited only this ticket file; no
impl/config/test/permanent-file change; wrote nothing to the real board.
**Overall GATE-3 red-team: FAIL for DAS-1611 — do not advance until fixed.**

### 2026-07-24 — Backend Engineer 2 (GATE-3 hole fix, all 3 items landed)
Fixed the red-team HIGH hole. Touched only `scripts/a2a_intake/intake.py`,
`tests/test_a2a_intake.py`, and this ticket — footprint held to the ticket's
zone.

**Root cause confirmed:** `FORBIDDEN_FIELDS` scanned dict *keys* only; the
optional `against_spec`/`caller_ref` (and `proposer`) *values* were written
verbatim into the frontmatter via f-string concatenation with only
`.strip()` — a newline in the value smuggled whole extra frontmatter lines
past the guard entirely.

**Fix 1 — fail-closed control-char DENY in `_validate` (the actual close).**
Added `FRONTMATTER_VALUE_FIELDS = {"proposer", "proposed_at", "against_spec",
"caller_ref"}` — the fields whose caller-controlled value is written into the
frontmatter — plus `_CONTROL_CHAR_RE` (`[\x00-\x1f\x7f]`, so `\n`, `\r`, NUL,
and every other C0/DEL control byte are covered). `_validate` now denies,
before any other content check, any of those fields carrying a control
character: `malformed: field '<name>' contains a newline or control
character — this value is written into the landed artifact's frontmatter...`.
Denied, audited (`a2a_intake_deny`), **no file written** — refused, never
silently stripped, exactly the guarantee the red-team found broken.
Deliberately scoped to the frontmatter-bound fields only, NOT `title`/
`summary` — those are written only into the Markdown *body* as prose, so a
newline there cannot smuggle frontmatter structure; this preserves the
existing, still-valid SC-002c guarantee
(`test_injection_in_summary_lands_as_inert_text`, which continues to pass
unmodified — multi-line/injection-shaped `summary` still lands, inertly, as
reviewed body text).

**Fix 2 — defense in depth: `yaml.safe_dump`, not f-string concatenation.**
The frontmatter is now built as a fixed dict (`status`/`source`/`proposer`/
`proposed_at`/`admission_ref`/optional `against_spec`/`caller_ref`, in that
order, `sort_keys=False`) and emitted via `yaml.safe_dump(..., sort_keys=False,
default_flow_style=False, allow_unicode=True)`. Even if a control char ever
slipped past Fix 1 (regression, a future internal caller bypassing
`_validate`), a real YAML serializer cannot be tricked into treating a scalar
value as new structure the way string concatenation could.

**Fix 3 — regression tests (`tests/test_a2a_intake.py`).**
- `test_control_char_injection_in_value_is_denied_no_file_written` —
  parametrized over `against_spec`/`caller_ref`/`proposer` × 5 payload shapes
  (`\nstatus: done`, `\napproval: human:founder`, `\ngate: GATE-3`, a bare
  `\r`, a NUL) = 15 cases, each asserts `deny`, correct `denied_field`, **no
  file written**, and a symmetric `a2a_intake_deny` audit record.
- `test_control_char_injection_exploit_from_redteam_writeup_is_denied` — the
  *exact* payload from the Security Engineer's writeup above (both the
  `against_spec` and the `caller_ref` variant) — denied, no file written.
- `test_valid_against_spec_and_caller_ref_still_land_when_single_line` —
  guards against overbreadth: ordinary single-line optional fields still
  land exactly as before.
- `test_frontmatter_is_emitted_via_yaml_safe_dump_not_fstring_concat` +
  `test_valid_proposal_frontmatter_round_trips_as_clean_yaml` — Fix 2's
  structural + functional proof: the landed frontmatter, re-parsed as real
  YAML, contains *only* the 5 fixed keys (+ the 2 optional ones when
  present) and `status: proposed` — no `approval`/`assignee`/`stage`/`gate`/
  `routing`/`dependson` key, however produced.
- `test_endpoint_to_intake_chain_injection_does_not_survive_to_landed_artifact`
  — the full `tools/a2a/endpoint.handle_call` → wired `intake_goal_proposal`
  chain test requested by the red-team: the exact exploit payload transits
  the endpoint's own key-only forbidden-field scan (which never inspects
  `against_spec`'s value) and ADR-0012 redaction (confirmed by manual probe:
  `safe_scrub("009\nstatus: done\napproval: auto")` returns the string
  **unchanged** — a plain newline is not secret-shaped, so redaction is not a
  sanitizer for this vector) — `handle_call` returns `ADMITTED` and forwards
  to the wired intake handler, which then denies. **Nothing lands in
  `board/goal-inbox/`.** This loads `tools/a2a/endpoint.py` via the same
  path-based spec-load pattern `tests/test_a2a_outbound_endpoint.py` already
  uses (read-only import, no edit to that file or to `tools/a2a/endpoint.py`
  — footprint held to `scripts/a2a_intake` + its own test file).

**Before/after:** every one of the above tests (all new) FAILED against the
pre-fix code (manually verified the exact red-team payload landed and
re-parsed to `{status: done, approval: auto, assignee: backend-eng-1, gate:
GATE-3, ...}` before this fix); all PASS now. Pre-existing 43+68 tests in
`tests/test_a2a_intake.py` / `tests/test_a2a_outbound_endpoint.py` are
unmodified and still green — this fix did not regress SC-002c or any other
existing guarantee.

**Verification (staged, `git add -A` first):**
```
$ python3 scripts/diagnostics.py
SCORE = 100/100

$ python3 -m pytest tests/test_a2a_intake.py tests/test_a2a_outbound_endpoint.py -q
88 passed in 0.17s

$ python3 scripts/board_lint.py; echo exit=$?
board_lint: 1 body-status warning(s) (non-fatal, pre-existing, unrelated — DAS-1507)
board_lint: OK — 180 ticket(s) checked, 0 violations.
exit=0

$ ruff check scripts/a2a_intake/intake.py tests/test_a2a_intake.py
All checks passed!
```
Also ran the full repo suite for safety (not part of the tight footprint,
read-only check): `python3 -m pytest -q` → **2432 passed, 25 skipped** — no
regression anywhere else in the repo.

**Which of the 3 fixes landed:** all three (control-char DENY in `_validate`;
`yaml.safe_dump` frontmatter emission; the full regression + chain test
suite). **The exploit is dead**: the red-team's exact payload (`against_spec:
"009\nstatus: done\napproval: auto\nassignee: backend-eng-1\ngate:
GATE-3"` and the `caller_ref` variant) now denies with no file written,
proven by `test_control_char_injection_exploit_from_redteam_writeup_is_denied`
and the endpoint-chain test above (failing before this commit's code
existed, passing after).

**Residual, honestly flagged:**
- The control-char guard is scoped to the fields that are actually written
  into frontmatter (`proposer`/`proposed_at`/`against_spec`/`caller_ref`).
  `title`/`summary` deliberately still tolerate newlines (body-only,
  SC-002c). If a future change ever starts writing `title`/`summary` into
  frontmatter instead of the body, this scoping would need to be revisited.
- This ticket's zone is `scripts/a2a_intake`; `tools/a2a/endpoint.py` itself
  was NOT modified (out of scope, DAS-1610's zone) — the chain test proves
  the exploit is stopped at the intake boundary regardless, since that is the
  only governed write surface, but a symmetric negative in
  `tests/test_a2a_outbound_endpoint.py` itself (DAS-1610/DAS-1612 zone) may
  still be worth adding there for that surface's own coverage — flagging for
  DAS-1612 per the original red-team note, not done here (footprint).
- Not self-closing GATE-3: `status: in_review`, `assignee: cto` set per
  dispatch instruction so the CTO can close the gate. PR/merge still
  outstanding — LOCAL-ONLY per dispatch constraint (no push, no PR, no
  commit made by this run).

### 2026-07-24 — CTO (GATE-3-CLOSED — Development, independently verified)
Acting as GATE-3 (Development) stage owner. I did NOT rubber-stamp the
remediation — I re-read `scripts/a2a_intake/intake.py` line-by-line and ran the
exploit myself.

**1. The remediation actually kills the exploit — confirmed.**
- The control-char guard (`_validate`, lines 298-311) covers
  `FRONTMATTER_VALUE_FIELDS = {proposer, proposed_at, against_spec, caller_ref}`
  — which is EXACTLY the set of caller-controlled fields written into the
  frontmatter dict (lines 440-450). `admission_ref` is the only other
  frontmatter field and it is server-stamped (keyword-only; `admissionref` is in
  `FORBIDDEN_FIELDS`, so a caller cannot supply it in the body). No caller value
  reaches the frontmatter unchecked.
- Frontmatter is emitted structurally via `yaml.safe_dump(front_matter,
  sort_keys=False, ...)` (lines 452-454), not f-string concat; `status` is the
  literal `"proposed"` (line 441). Two independent defenses, as the fix claims.
- The guard is checked BEFORE the required/unknown-field checks, so an injected
  value is always reported as the control-char deny.

**2. Independent adversarial probe (my own, temp inbox — nothing touched the real board):**
```
field=against_spec decision=deny   denied_field='against_spec'   files_landed=0
field=caller_ref   decision=deny   denied_field='caller_ref'     files_landed=0
field=proposer     decision=deny   denied_field='proposer'       files_landed=0
legit decision=allow frontmatter_keys=[admission_ref, against_spec, caller_ref,
       proposed_at, proposer, source, status] status=proposed
```
The exact red-team payload (`"009\nstatus: done\napproval: auto\nassignee:
backend-eng-1\ngate: GATE-3"`) DENIES with 0 files landed on all three fields; a
legit single-line proposal still lands with only the 7 fixed keys and
`status: proposed` (multi-line `summary` still lands inertly in the body —
SC-002c preserved).

**3. No gate/approval field is caller-reachable.** Even the pre-fix injected
`approval: human:founder` string closes NO gate: `rbac.is_gate_closed` closes a
gate ONLY on a matching Founder-identity `gate_approval` event and treats a bare
frontmatter `approval` claim as forged (verified by reading its source). Proposal
lands `status: proposed` only; the module has a single `write_text` targeting
`board/goal-inbox/`.

**Verification output (re-run by me):**
```
$ python3 -m pytest tests/test_a2a_intake.py tests/test_a2a_outbound_endpoint.py -q
88 passed in 0.20s
  (incl. the 15-case control-char matrix, the exact red-team payload negative,
   the safe_dump/round-trip structural proofs, and the endpoint→intake chain test)
$ python3 scripts/diagnostics.py   → SCORE = 100/100
$ python3 scripts/board_lint.py    → exit 0 (only pre-existing unrelated DAS-1507 body-status WARN)
$ rbac.FOUNDER_ONLY contains "a2a.publish" → True
```

**GATE-3 (Development) CLOSED for DAS-1611.** The HIGH value-injection hole is
dead at the intake boundary, fail-closed, with defense-in-depth. Setting
`status: done`. The one flagged residual (a symmetric endpoint-side
value-injection negative belonging in `tests/test_a2a_outbound_endpoint.py`) is
NOT lost in this closed ticket's log — I bound it into DAS-1612 as a required
Description bullet + acceptance box + log entry. PR/merge/push is the
orchestrator's step (LOCAL-ONLY dispatch: I made no push/PR/commit).
