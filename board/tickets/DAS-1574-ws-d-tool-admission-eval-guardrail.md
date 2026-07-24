---
id: DAS-1574
title: WS-D Development — admit promptfoo, AgentShield, and Presidio through the ADR-0033 governed MCP edge
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-005, FR-006]
labels: [security]
zone: tools/mcp_bridges
depends_on: [DAS-1572, DAS-1547]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-D, part 2).** Admit the
eval/guardrail tool shortlist — **promptfoo, AgentShield, Presidio** — per the
DAS-1572 design, reusing the ADR-0033 edge WS-A built rather than opening a
second admission path.

**Cross-workstream dependency:** this ticket needs the ADR-0033 edge mechanism
to already exist — the FastMCP sidecar convention, the compiled
`board/.tool-allowlist.json`, and the `PreToolUse` audit/deny hook — all built
in **DAS-1547** (WS-A Development). It does NOT need WS-A's browser tool
(DAS-1548) or WS-A's epic to be fully closed; only the tool-bridge sidecar
mechanism.

- **FR-005:** each of the three tools enters as an out-of-process MCP sidecar
  under `tools/`, wired in `.mcp.json`, reachable only through a role's overlay
  allow-list (least privilege — no blanket grants); every call passes the
  existing `PreToolUse` audit/deny path.
- **FR-006:** publishing/enabling is bounded by the same fail-closed defaults
  as the base 0033 edge — no WS-D-specific bypass, no global grant, no new
  admission surface.
- Do not fork `audit_external_tool.py`, the allow-list compiler, or
  `egress_guard.py` — import/reuse them (ADR-0029 extend-vs-new), matching how
  DAS-1548 reused DAS-1547's egress guard.
- Feature-gated by `ws_d_langfuse_lens` OR the shared `ws_a_tool_bridge` key
  per the DAS-1572 design's decision on which flag governs admission of these
  three tools; record the choice in the log.

## Acceptance criteria
- [ ] promptfoo, AgentShield, and Presidio each exposed as a governed MCP sidecar under `tools/`, wired in `.mcp.json`.
- [ ] Each reachable only via an explicit overlay allow-list entry; a role without the entry is refused (no blanket/global grant).
- [ ] Every call passes the existing `PreToolUse` audit/deny + ADR-0012 redaction path, reused (not reimplemented) from DAS-1547.
- [ ] Feature-flagged OFF by default; flag-off dispatch unchanged. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Development, part 2). Admits promptfoo,
AgentShield, Presidio through the existing ADR-0033 edge. Depends on DAS-1572
(this workstream's design) AND DAS-1547 (the WS-A ticket that built the 0033
edge mechanism being reused) — the concrete instance of the master-prompt's
"D runs parallel from A, needs the 0033 edge" sequencing note. Distinct repo
zone from DAS-1573 (tools/mcp_bridges vs tools/observability) so the two
Development tickets can proceed without a same-zone wave collision.

### 2026-07-24 — Backend Engineer 1

Implemented per `docs/design/ws-d-langfuse-lens.md` §5. **No second admission
path** was created — the three tools are admitted through the *identical*
ADR-0033/WS-A chain (`overlay ## External tools` → `gen_subagents.py` compile
→ `board/.tool-allowlist.json` → `audit_external_tool.decide()` PreToolUse →
`redaction.py`), reusing `audit_external_tool.py`, the allow-list compiler,
and `egress_guard.py` verbatim (none forked, none edited).

**Flag decision (logged per ticket instruction):** the PreToolUse
audit/deny gate that governs *reachability* of these tools continues to be
governed by the existing, unmodified `ws_a_tool_bridge` flag inside
`audit_external_tool.py` (`_FLAG = "ws_a_tool_bridge"`, unchanged) — this is
the literal mechanism DAS-1547 built and this ticket reuses verbatim, so it
is not re-pointed at `ws_d_langfuse_lens`. `ws_d_langfuse_lens` remains the
flag for the separate WS-D exporter/lens surface (DAS-1573). Both flags are
`false` by default in `config/features.yaml`, so today's admission
posture is: flag OFF → hook inert (allow-through, no audit line, per the
existing TB-5 behaviour) → structurally no behaviour change from this
ticket regardless of which flag a future flip targets.

**FR-005 → file + test map:**
- Sidecars (TB-1, out-of-process, FastMCP, `tools/` shape): `tools/mcp_bridges/promptfoo_tool_bridge.py` (`run_eval`, local-fixture eval), `tools/mcp_bridges/agentshield_tool_bridge.py` (`scan_action`, heuristic guardrail), `tools/mcp_bridges/presidio_tool_bridge.py` (`analyze_text`, PII detection with I/O redaction) — wired in `.mcp.json` (`promptfoo`, `agentshield`, `presidio` stdio servers). Test: `test_mcp_json_wires_all_three_sidecars`, `test_promptfoo_run_eval_against_local_fixture`, `test_promptfoo_missing_fixture_reports_error_not_crash`, `test_agentshield_flags_destructive_action`, `test_agentshield_safe_action_passes`.
- Least-privilege overlay grants (TB-2), compiled by `scripts/gen_subagents.py` into `board/.tool-allowlist.json`:
  - `mcp__promptfoo__run_eval` → `["qa-eng", "qa-lead"]` (`engineering/agents/qa-eng/AGENTS.md`, `engineering/agents/qa-lead/AGENTS.md` `## External tools` blocks; design §5.2 "qa-eng (also QA Lead)").
  - `mcp__agentshield__scan_action` → `["security-lead"]` (`engineering/agents/security-lead/AGENTS.md`).
  - `mcp__presidio__analyze_text` → `["security-lead"]` (`engineering/agents/security-lead/AGENTS.md`; design §5.2 "the redaction/PII layer").
  - No blanket/global grant; no `"*"` anywhere. Test: `test_compiled_allowlist_grants_only_designed_roles`, `test_compiled_allowlist_matches_overlays_no_drift`, `test_compiled_allowlist_has_no_wildcard_roles`.
- PreToolUse audit/deny + no bypass (TB-3): a role without the overlay entry is refused by the *same* `decide()` as any other external tool; a tool wired in `.mcp.json` but declared by no overlay compiles to no key and denies for every role; every decision (allow AND deny) is audited; a malformed/unparseable event with the flag ON still fails closed and is still audited (not skipped). Test: `test_non_allowlisted_eval_tool_refused_by_same_decide`, `test_tool_present_in_mcp_json_but_no_overlay_denies_every_role`, `test_every_decision_is_audited_allow_and_deny`, `test_audit_skip_denied_malformed_event`, `test_settings_binding_present_covers_these_tools_too` (confirms `.claude/settings.json`'s existing `mcp__.*` binding — untouched — already covers all three via its wildcard matcher).
- Egress (TB-4): new deny-all `eval-guardrail-deny-all: []` profile added to `config/egress-allowlist.yaml` (mirrors the existing `browser-deny-all` pattern) and referenced by all three overlay grants — no production credentials, no network by default. Test: `test_egress_profile_for_eval_tools_is_deny_all`.
- Presidio-own-I/O redaction caveat (ADR-0012, design §5.1): `presidio_tool_bridge.analyze_text` never echoes a raw detected value — it returns entity TYPES + a count plus the input run through the *same* `redaction.scrub`/`redact_then_truncate` pass any other tool transcript gets. Test: `test_presidio_never_echoes_raw_pii`, `test_presidio_never_echoes_raw_secret`, `test_presidio_output_passes_through_redact_then_truncate_cap`, `test_presidio_no_findings_reports_zero_entities`.

**FR-006 → file + test map:** no WS-D-specific bypass/global grant was
introduced anywhere in this change (verified by the wildcard/drift tests
above); flag-off inertness for all three tools is asserted directly:
`test_flag_off_is_inert_for_all_three_tools`, `test_features_yaml_ws_d_flag_default_off`.

**Verification (run in the git-add -A STAGED state, per ticket instruction):**
- `python3 scripts/diagnostics.py` → **100/100** (all 7 categories PASS, incl. `tn1-in-tenant-boundary`, `no-committed-secrets`).
- `python3 scripts/check_agents_sync.py` → `OK — 32 shim(s) in sync with ROUTING.md` (exit 0; overlays were recompiled via `gen_subagents.py` after the two grant edits).
- `python3 scripts/board_lint.py` → `OK — 180 ticket(s) checked, 0 violations` (exit 0; one pre-existing non-fatal WARN on an unrelated ticket, DAS-1507).
- `python3 -m pytest` (full suite) → **2034 passed, 4 skipped** (20 new in `tests/test_ws_d_tool_admission.py`, all green; no regressions).
- `ruff check tools/mcp_bridges tests scripts` → **All checks passed!**
- Confirmed `tools/observability/` (DAS-1573's concurrent zone) and `.claude/settings.json` (the `mcp__.*` hook binding) were **not modified** — only read/asserted-against in a test.
- A test-run side effect that appended a line to the tracked `board/.tool-audit.jsonl` was reverted (`git checkout -- board/.tool-audit.jsonl`) so the staged diff carries no incidental audit-log noise.

**Status:** `in_review`, assignee → `backend-em` (per `board/ROUTING.md`; never
self-review). Branch: `docs/governed-devin-langchain-direction` (the shared
working checkout this whole MUSTAQIL program is staged on, per the
orchestrator's dispatch — **no commit, no push, no PR** made, per the
ticket's LOCAL-ONLY constraint). All changes remain staged/uncommitted in
the working tree for the reviewer/Founder to commit.

### 2026-07-24 — Security Engineer
**GATE-3 blocking security red-team (adversarial, in-code — not doc review).**
Ran `pytest tests/test_ws_d_tool_admission.py` (20 passed) plus my own ephemeral
`decide()` / presidio probes (deleted; no permanent test added — DAS-1575 owns that).

| # | Item | Verdict |
|---|------|---------|
| 1 | Least-privilege grants — only the designed roles, no over-grant | **HOLDS** — compiled `board/.tool-allowlist.json` = `promptfoo.run_eval → [qa-eng, qa-lead]`, `agentshield.scan_action → [security-lead]`, `presidio.analyze_text → [security-lead]`. No blanket, no `"*"`. |
| 2 | Non-granted role refused by `decide()` | **HOLDS** — `backend-eng-1→run_eval` DENY, `qa-eng→scan_action` DENY, `backend-em→analyze_text` DENY; granted roles ALLOW. An undeclared tool on a granted server (`mcp__promptfoo__some_other_tool`) also DENIES (allowlist keyed by full tool name, no server-level over-grant). |
| 3 | No `"*"` roles value honoured | **HOLDS** — `decide()` denies both a `"*"` string value and a `"*"` list member; `load_allowlist`/`_reject_wildcard` treat any `"*"`-bearing map as deny-all. |
| 4 | Every decision audited; audit-skip denied | **HOLDS** — `main()` writes a scrubbed audit line for allow AND deny before emitting; `_deny_unidentified` (flag ON + unparseable/non-object event) fails closed, audits, and exits 2 — no ungoverned `mcp__.*` fall-through. |
| 5 | Presidio own-I/O redaction (never echoes raw PII) | **HOLDS** — `analyze_text("…victim@example.com … sk-ant-api03-… +1 415 555 0199")` → `presidio: 3 entities [EMAIL, PHONE, API_KEY] | redacted: … [REDACTED:pii] … [REDACTED:api_key] … [REDACTED:pii]`; no raw value survives; return also passes `redact_then_truncate`. |
| 6 | Single ADR-0033 edge; no second admission path; egress deny-all | **HOLDS** — `.claude/settings.json` has exactly ONE `PreToolUse` `mcp__.*` matcher → `audit_external_tool.py`. Grants originate ONLY from the 3 role overlays (`qa-eng`, `qa-lead`, `security-lead` `## External tools`). No second hook, no bypass. All three carry the `eval-guardrail-deny-all: []` egress profile (deny-all-by-default). |
| 7 | Flag OFF ⇒ inert; dispatch unchanged | **HOLDS** — both `ws_a_tool_bridge` (governs reachability) and `ws_d_langfuse_lens` default `false`; with the flag OFF the hook `main()` is inert allow-through (TB-5), writing no audit line and changing no dispatch outcome. Sidecars are absent-by-default consumers. |

**No REAL hole found. Residual (NON-blocking → DAS-1575):** the reference sidecars
ship dependency-light stand-in backends; the ticket's own note that production
swaps in the real promptfoo/AgentShield/Presidio engines must preserve the same
I/O-redaction + `eval-guardrail-deny-all` egress posture — recommend DAS-1575 add
a contract test asserting any real-backend swap keeps output through `redaction`
and the deny-all profile.

**Overall: GATE-3 red-team PASSED — cleared for CTO ratification.** Status stays
`in_review`; assignee moved `backend-em → cto` for ratification.

### 2026-07-24 — CTO
**AADL Stage-3 / GATE-3 (Development) CLOSED for WS-D LENS part 2 (eval/guardrail
tool admission).** Ratified after independent re-verification in STAGED state
(`git add -A` first, to catch tracked-file + overlay-sync checks):

- `python3 scripts/diagnostics.py` = **100/100** (exit 0) — TRACKED.
- `python3 scripts/check_agents_sync.py` = exit **0** (32 shims in sync with
  ROUTING.md) — confirms this ticket's overlay recompile (`gen_subagents.py` after the
  qa-eng/qa-lead/security-lead `## External tools` grant edits) left no drift.
- `python3 -m pytest tests/test_ws_d_otlp_exporter.py tests/test_ws_d_tool_admission.py -q`
  = **39 passed** (20 admission + 19 exporter), exit 0.
- `python3 -m pytest -q` (full suite) = **2053 passed, 4 skipped**, exit 0 — no regressions.
- `python3 scripts/board_lint.py` = exit **0** (180 tickets, 0 violations; lone WARN =
  pre-existing DAS-1507, unrelated).

**Security GATE-3 red-team is on record above (Security Engineer, PASSED — no real
hole):** least-privilege grants exact (`promptfoo.run_eval → [qa-eng, qa-lead]`,
`agentshield.scan_action → [security-lead]`, `presidio.analyze_text → [security-lead]`;
no blanket, no `"*"`), non-granted / undeclared-tool-on-granted-server refused by the
same `decide()`, every decision audited + audit-skip denied via `_deny_unidentified`,
Presidio never echoes raw PII (returns entity types + count through the same
`redact_then_truncate`), a single ADR-0033 `PreToolUse` `mcp__.*` edge in
`.claude/settings.json` → `audit_external_tool.py` (no second admission path, no
bypass), `eval-guardrail-deny-all` egress, both `ws_a_tool_bridge` and
`ws_d_langfuse_lens` default `false` ⇒ flag OFF inert (allow-through, dispatch
unchanged). Flag-governance choice logged above (reachability stays on the unmodified
`ws_a_tool_bridge` DAS-1547 mechanism). Acceptance criteria met.

**Residual → DAS-1575 (Testing), NON-blocking:** the reference sidecars ship
dependency-light stand-in backends; a production swap to the real
promptfoo/AgentShield/Presidio engines must preserve the same I/O-redaction +
`eval-guardrail-deny-all` egress posture — DAS-1575 adds a contract test asserting any
real-backend swap keeps output through `redaction` and the deny-all profile. This is
DAS-1575's formal test to add, not a GATE-3 blocker.

Everything remains behind flags OFF. **LOCAL-ONLY** — accepted on local green; no
commit/push/PR made. **GATE-3 part 2 CLOSED → status `done`. Unblocks DAS-1575 (Testing).**
