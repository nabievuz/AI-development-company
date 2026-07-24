---
id: DAS-1549
title: WS-A Testing — negative tests for grant refusal, audit-skip denial, egress block, redaction
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [SC-001, SC-002]
labels: [security]
zone: tests
depends_on: [DAS-1547, DAS-1548]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-A).** Prove the governance holds with
adversarial negative tests. Security Engineer (red team) consulted.

Cover:
- **SC-001:** a globally-granted tool (no overlay allow-list) is refused (TB-2); a call
  that skips the `PreToolUse` audit is denied (TB-3).
- **SC-002:** browser egress to a non-allow-listed domain is blocked (TB-4/Q5); a
  tool-event redaction probe passes (ADR-0012).
- **SC-003 guard:** with the flag OFF, dispatch is byte-identical to pre-merge.
- Fold in and extend `tests/test_ws_a_tool_bridge.py`.

## Acceptance criteria
- [x] Negative tests exist and PASS in CI for SC-001 (grant refusal + audit-skip denial) and SC-002 (egress block + redaction probe).
- [x] Flag-off no-op behaviour asserted (SC-003).
- [x] `tests/test_ws_a_tool_bridge.py` folded in and green; overall pytest green (local — CI deferred, WS-A LOCAL-ONLY).
- [x] Security Engineer red-team review recorded (GATE-3, DAS-1546/1547). Merged PR + green CI deferred per WS-A LOCAL-ONLY disposition.

## Security conditions (GATE-2)

Bound by the CTO at GATE-2 closure of DAS-1546 (Security Lead audit). **Beyond** the
doc's §4 SC-001/SC-002, these five negative tests are **MUST-PASS** — GATE-4 for this
ticket **cannot be signed** unless all pass. Each proves a binding condition on
DAS-1547/1548 (C1–C8).

- **T1 (C3):** a hook-exec failure (crash / non-zero exit / malformed stdout) ⇒ tool
  **DENIED** (fail-closed on both CLI and Agent SDK).
- **T2 (C4):** an allow-listed host that 302→a non-allow-listed host ⇒ **denied**, and
  the redirect target is **never fetched**.
- **T3 (C5):** a URL host / redirect resolving to 169.254.169.254 / 127.0.0.1 /
  10.0.0.0-8 ⇒ **denied** unless a profile explicitly and narrowly scopes it.
- **T4 (C2):** a `"*"` roles value in the compiled allow-list map does **NOT** grant
  any-role.
- **T5 (C1):** the drift guard **fails CI** on a tampered/stale compiled allow-list
  (meaningful only once the file is tracked per C1).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Testing). SC-001/SC-002 negative tests; red-team consulted.

### 2026-07-24 — CTO
GATE-2 closed on DAS-1546. Attached binding negative-test conditions **T1–T5** (above)
from the Security Lead audit — MUST-PASS for GATE-4, in addition to §4 SC-001/SC-002.

### 2026-07-24 — QA Engineer
**AADL Stage 4 — Testing.** Folded the formal T1–T5/SC negative-test suite into the two
existing test files (no duplication — extended what was already there, added only what
was missing). LOCAL-ONLY honored: only `tests/*` files + this ticket touched; no
implementation/config/ADR file edited.

**Files touched:**
- `tests/test_ws_a_tool_bridge.py` — extended 31 → 43 tests.
- `tests/test_ws_a_browser_tool_egress.py` — extended 24 → 26 tests.

**T1–T5 / SC → proving test function(s):**
- **SC-001** (globally-granted/no-overlay tool refused; audit-skip still denies) —
  `test_denies_unlisted_external_tool` (pre-existing) +
  `test_sc001_no_overlay_entry_refused`, `test_sc001_audit_write_failure_still_denies` (new).
- **SC-002** (browser egress block + tool-event redaction probe) —
  `test_c5_browser_check_egress_blocks_ssrf_via_profile`,
  `test_egress_profile_deny_all_ships_by_default` (pre-existing, egress block) +
  `test_sc002_tool_event_redaction_probe` (new — proves the AUDIT INTEGRATION point:
  `main()`'s call to `redact_then_truncate` on `reason`, not just the standalone scrubber).
- **SC-003** (flag-OFF byte-identical no-op) — `test_c3_flag_off_is_inert` (pre-existing) +
  `test_sc003_flag_off_no_op_even_for_a_would_be_denied_tool` (new, stronger: uses a tool
  that WOULD be denied if the flag were on).
- **T1 (C3)** hook-exec crash ⇒ fail-closed deny (exit 2) —
  `test_c3_wrapper_denies_on_spawn_failure` (pre-existing, spawn failure) +
  `test_t1_internal_crash_denies_and_exits_2` (new — forces an internal exception inside
  `main()` and asserts the exact `__main__` fail-closed wrapper denies + exits 2).
  **Malformed-event-with-flag-ON residual** — `test_t1_malformed_event_with_flag_on_must_deny_not_allow`
  (new). **This test is `xfail(strict=True)` — it FAILS against current code.** Verified
  directly: flag ON + malformed stdin (`"{not valid json"`) → `audit_external_tool.main()`
  catches the `json.loads` `ValueError`, sets `event = {}` → `tool_name = ""` → `decide()`
  takes the "not an external tool" branch → **allow** (`{}`), audited as `decision: allow`.
  This is the exact DAS-1547 red-team residual, which the CTO's GATE-2 binding upgraded
  from a non-blocking hardening note to a **MUST-PASS T1 condition**. **Genuine unresolved
  gap, not a test-authoring issue** — confirmed via manual repro (`printf '{not valid json'
  | DASLAB_WS_A_FLAG=on ... audit_external_tool.py` → rc 0, stdout `{}`, audit line
  `"decision": "allow"`). Per this ticket's constraints I did NOT patch
  `tools/mcp_bridges/audit_external_tool.py` (tests-only footprint, LOCAL-ONLY, "never
  silently patch impl"). **Escalating the fix to backend-em/backend-eng-1** (owners of
  DAS-1547/`audit_external_tool.py`): `main()` must explicitly deny (not fall through to
  the not-an-external-tool allow branch) when the flag is ON and the incoming event fails
  to parse as JSON. **QA Lead: GATE-4 cannot be signed as fully MUST-PASS until this fix
  lands and the xfail is removed/flipped to a passing assertion** — routing per ROUTING.md
  (qa-eng → qa-lead is my only escalation route; the implementation fix itself routes to
  backend-em/backend-eng-1 via the orchestrator).
- **T2 (C4)** allow-listed host 302→disallowed host ⇒ denied, redirect target never
  fetched — mcp_bridges layer: `test_c4_web_fetch_egress_gate_before_network` (pre-existing,
  gate-ordering) + `test_t2_allowlisted_host_redirect_to_disallowed_host_is_denied_and_never_fetched`
  (new — real local HTTP server issuing a 302, asserts exactly one request hit the origin,
  the redirect target was never fetched). Browser layer: `test_c4_browser_navigate_denies_before_any_network_call`
  (pre-existing) + `test_t2_browser_allowlisted_host_redirect_to_disallowed_host_denied_never_fetched`
  (new, same real-HTTP-server proof at the browser layer).
- **T3 (C5)** internal-range/DNS-rebinding-style resolution blocked at resolve time —
  `test_c5_blocks_loopback_linklocal_rfc1918` (pre-existing, basic set) +
  `test_t3_dns_rebinding_style_resolution_is_blocked_at_resolve_time`,
  `test_t3_ipv6_mapped_and_unique_local_also_blocked` (new, mcp_bridges layer) +
  `test_t3_browser_dns_rebinding_style_resolution_blocked_at_resolve_time` (new, browser
  layer, via the exact imported `check_egress`). Per the DAS-1547 red-team note, the
  resolve-time block HOLDS; the TOCTOU between this resolution and urllib's own later
  connect-time resolution remains a **documented future-hardening item** (pinning the
  vetted IP into the actual connection) — NOT asserted as fixed by these tests, consistent
  with the ticket's own instruction ("at minimum assert the resolve-time block holds").
- **T4 (C2)** `"*"` roles value never grants any-role — `test_c2_decide_denies_wildcard_roles_value`,
  `test_c2_load_allowlist_rejects_wildcard` (pre-existing; no new test needed, already
  MUST-PASS-complete).
- **T5 (C1)** drift guard detects a tampered/stale compiled allow-list —
  `test_c1_allowlist_matches_overlays_no_drift` (pre-existing, proves TODAY'S committed
  file has zero drift) + `test_t5_tampered_allowlist_is_detected_as_drift` (new — a
  hand-edited copy diverges from a fresh recompile) + `test_t5_stale_allowlist_missing_a_real_grant_is_detected_as_drift`
  (new — an overlay grant added but not recompiled also diverges).
- **C8** (browser write/submit/upload/clipboard/local-control denied under default grant) —
  `test_c8_bridge_functions_enforce_the_gate_before_backend` (pre-existing, covers all
  eight privileged actions in one assertion; no new test needed).

**Validators run (exact results):**
- `python3 -m pytest tests/test_ws_a_tool_bridge.py tests/test_ws_a_browser_tool_egress.py -q`
  → **66 passed, 2 skipped (mcp absent, expected), 1 xfailed (the T1 residual above)**.
- `python3 -m pytest -q` (full suite) → **1942 passed, 4 skipped, 1 xfailed** — no
  collateral breakage anywhere in the repo.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (all 7 categories PASS).
- `python3 scripts/board_lint.py` → **OK — 180 ticket(s) checked, 0 violations** (the
  DAS-1507 body-status WARN is pre-existing/unrelated, non-fatal).
- `ruff check tests/test_ws_a_tool_bridge.py tests/test_ws_a_browser_tool_egress.py` →
  **All checks passed!**

**Disposition:** all acceptance criteria are met EXCEPT the T1 malformed-event-with-flag-ON
MUST-PASS condition, which is written, verified to genuinely fail against current code, and
`xfail(strict=True)`-marked (so it shows up honestly in every CI run rather than being
silently green or silently omitted) rather than patched by me. Everything else (SC-001,
SC-002, SC-003, T2, T3, T4, T5, C8) is written and PASSING. Setting `status: in_review`,
`assignee: qa-lead` for the GATE-4 review + disposition call on the one open T1 finding
(hold GATE-4 open pending a backend-em/backend-eng-1 fix + xfail removal, or accept as a
tracked residual — QA Lead's call, above my charter authority to decide unilaterally).

### 2026-07-24 — QA Lead
**GATE-4 (Testing) CLOSED for WS-A REACH. Decision: PASS.** Independently re-verified — no
rubber-stamp; re-ran every gate command myself and confirmed the single open T1 finding is
now remediated.

**T1 fail-open residual — REMEDIATED and now PASSING.** The DAS-1547 red-team residual (flag
ON + malformed/unparseable PreToolUse event fell through to the not-an-external-tool **allow**
branch) has been fixed **fail-closed** in `tools/mcp_bridges/audit_external_tool.py` (per the
DAS-1547 `## Log` remediation entry). Verified directly at the impl:
- `main()` now catches the `json.loads` `ValueError` and calls `_deny_unidentified("unparseable
  PreToolUse event")` (C3 fail-CLOSED), plus a matching deny when the event is not an object.
- Manual repro (the exact prior fail-open case):
  `printf '{not valid json' | DASLAB_WS_A_FLAG=on python3 tools/mcp_bridges/audit_external_tool.py`
  → emits `permissionDecision: deny` ("unparseable PreToolUse event with the WS-A flag ON …
  fail-closed deny (C3)"), **rc=2**. Previously rc=0 + `{}` + audited `allow`.
- The proving test `test_t1_malformed_event_with_flag_on_must_deny_not_allow` is **un-xfail'd**
  (grep confirms **zero** `xfail` markers remain in either WS-A test file) and **PASSES** on its
  own and in-suite.

**MUST-PASS conditions (CTO GATE-2 binding, T1–T5) — ALL GREEN.** T1 (C3 hook-exec crash +
malformed-event fail-closed), T2 (C4 allow-listed→disallowed 302 denied, redirect never
fetched, both mcp_bridges + browser layers), T3 (C5 internal-range / DNS-rebinding-style
resolve-time block, incl. IPv6-mapped/ULA), T4 (C2 `"*"` roles never grants any-role), T5 (C1
drift guard fails on tampered/stale compiled allow-list) — each maps to a real, passing test
function per the QA Engineer mapping above; spot-verified the mapping holds against the current
files. SC-001/SC-002/SC-003 coverage present and passing; C8 (eight privileged browser actions
gated before backend) present and passing. Security Engineer red-team was consulted at GATE-3
(recorded on DAS-1546/1547).

**Gate evidence (re-run 2026-07-24, exact):**
- `python3 -m pytest tests/test_ws_a_tool_bridge.py tests/test_ws_a_browser_tool_egress.py -q`
  → **67 passed, 2 skipped** (mcp absent, expected). **No xfail remaining** (was 1 xfailed on T1
  before the fix).
- `python3 -m pytest -q` (full suite) → **1943 passed, 4 skipped, 0 xfailed** — no collateral
  breakage.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (all 7 categories PASS).
- `python3 scripts/board_lint.py` → **exit 0 — 180 ticket(s) checked, 0 violations** (the DAS-1507
  body-status WARN is pre-existing/unrelated, non-fatal).

**Disposition:** all acceptance criteria + all five MUST-PASS T-conditions are met and green.
Setting `status: done`. Per prior WS-A ticket disposition, this WS is **LOCAL-ONLY** — the
"merged PR + green CI" clause of the engineering DoD is deferred and this gate is accepted on
local green (same treatment as the earlier WS-A tickets). No files other than this ticket were
edited; tests/impl/config untouched by QA Lead.

**Closing GATE-4 unblocks DAS-1550 (AADL Stage 5 — Deployment).**
