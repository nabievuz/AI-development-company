---
id: DAS-1548
title: WS-A Development — browser tool behind admission, deny-all plus domain allow-list egress
status: in_review
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-005, FR-006]
labels: [security]
zone: tools/browser
depends_on: [DAS-1546]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-A, part 2).** Add the marquee
browser / computer-use tool (Playwright-MCP or browser-use) as a governed sidecar.

- **TB-4:** admitted ONLY behind the DAS-1547 allow-list (TB-2) + PreToolUse
  audit/redaction (TB-3); never runs against production credentials it was not
  explicitly scoped.
- **Q5 egress:** deny-all except an explicit domain allow-list; no unattended browsing.
- **FR-006 injection defense:** fetched page content is untrusted DATA — it can never
  change the agent's goal, approvals, or permissions; under autonomous waves the
  browser additionally sits inside the HEARTBEAT SI-1…SI-7 envelope (ADR-0027).
- Feature-flagged OFF (own key or the shared WS-A key per the DAS-1543 scaffold).

Distinct repo zone from DAS-1547 so the two Development tickets can proceed without a
same-zone wave collision.

## Acceptance criteria
- [ ] Browser/computer-use tool exposed as a governed MCP sidecar, admitted only behind TB-2+TB-3.
- [ ] Egress deny-all with an explicit domain allow-list; a non-allow-listed domain is refused.
- [ ] Fetched content handled as untrusted input (documented + enforced at the tool boundary); no production-credential access unless explicitly scoped.
- [ ] Feature-flagged OFF; flag-off dispatch unchanged. `diagnostics.py` 100/100. Merged PR, green CI.

## Security conditions (GATE-2)

Bound by the CTO at GATE-2 closure of DAS-1546 (Security Lead audit, finding F8).
**MUST-satisfy** — GATE-3 for this ticket **cannot be signed** unless met. The browser /
computer-use surface is far wider than `web_fetch`, so least privilege must stop at the
ACTION, not just the domain.

- **C8 (F8):** Enumerate the browser / computer-use action surface; the **default grant =
  navigate + read + screenshot only**. Write / submit / upload / clipboard /
  local-app-control actions are **OUT of the default grant** and each require a separate
  explicit reviewed grant (a form-submit to an allow-listed host can still exfiltrate —
  the egress list governs destinations, not write actions).
- **Inherit C4/C5/C6** (from DAS-1547) at the browser layer: no unchecked redirects (C4);
  block loopback / link-local (169.254.169.254) / RFC-1918 by resolving the target (C5);
  label-boundary domain matching, never bare substring (C6).

Test coverage handed to DAS-1549 (T2 redirect, T3 SSRF apply at the browser layer too).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Development, part 2). TB-4 + Q5 egress + FR-006 injection defense.

### 2026-07-24 — CTO
GATE-2 closed on DAS-1546. Attached binding security condition **C8** + inherited
**C4/C5/C6** (above) from the Security Lead audit — MUST-satisfy for GATE-3. Behind
`ws_a_tool_bridge` OFF until DAS-1549 proves them.

### 2026-07-24 — Backend Engineer 1
Development done: browser/computer-use tool bridge built as a governed out-of-process
MCP sidecar under `tools/browser/`, wired via `.mcp.json`. REUSED (not forked) the
DAS-1547 foundation — imported `egress_guard.check_egress`, relied on the existing
`audit_external_tool.py` + `.claude/settings.json` `mcp__.*` PreToolUse hook (TB-3,
untouched), and did not edit `tools/mcp_bridges/` or `config/egress-allowlist.yaml`'s
other profiles. Distinct repo zone from DAS-1547 (`tools/browser/` vs
`tools/mcp_bridges/`). Absent-by-default: `mcp` (and any real browser driver) stays out
of core `requirements.txt`; `tools/browser/requirements-browser.txt` is the optional
install path (mirrors DAS-1547's `requirements-tools.txt` pattern).

**Files created:**
- `tools/browser/action_gate.py` — C8 action-level least-privilege gate: enumerates the
  full browser/computer-use action surface, default grant = `navigate`+`read`+
  `screenshot` only; every other action (`click`, `type`, `form_fill`, `submit`,
  `upload`, `clipboard_read`, `clipboard_write`, `local_app_control`) is denied unless
  named in `$DASLAB_BROWSER_ACTION_GRANTS` (fail-closed: unset/empty/unrecognised token
  ⇒ default grant only, never wider).
- `tools/browser/browser_bridge.py` — the FastMCP sidecar. Every tool function runs the
  C8 gate FIRST, then (for `navigate`) the TB-4 egress guard (imported
  `egress_guard.check_egress`/`active_profile`, not reimplemented) with its own
  `_NoRedirect` opener (C4) before any network syscall. `read()` returns the fetched
  page as an inert string (FR-006 — untrusted DATA, never parsed/executed, cannot
  reach or widen the C8 grant). Privileged actions return a clear "backend not
  installed" result only AFTER the C8 gate passes (absent-by-default reference
  backend — a real Playwright/browser-use driver is a backend swap, not a governance
  change). `mcp` is imported lazily in `build_server()` so the module is importable/
  testable with zero optional deps installed.
- `tools/browser/requirements-browser.txt` — optional deps (`mcp`, and a commented
  pointer to `playwright`/`browser-use`), kept out of core `requirements.txt`.
- `tests/test_ws_a_browser_tool_egress.py` — 24 tests (23 passed, 1 skipped — `mcp`
  absent), covering C8, inherited C4/C5/C6, FR-006, and TB-5 absence.

**Files edited (footprint-scoped only):**
- `.mcp.json` — added the `browser` sidecar entry (`tools/browser/browser_bridge.py`,
  portable `${workspaceFolder}`); the DAS-1547 `langchain-tools` entry is untouched
  (asserted by `test_mcp_json_declares_browser_sidecar_without_touching_langchain_entry`).
- `config/egress-allowlist.yaml` — added ONE new profile, `browser-deny-all: []`
  (deny-all by design — the browser is TB-4's widest attack surface; no host ships by
  default). The `none` and `research-read` profiles from DAS-1547 are untouched.

**C8 → satisfied by (file + test):**
`tools/browser/action_gate.py` (`DEFAULT_GRANT`/`PRIVILEGED_ACTIONS`/`check_action`) +
every `browser_bridge.py` tool function gating on it before touching a backend. Tests:
`test_c8_default_grant_is_navigate_read_screenshot_only`,
`test_c8_privileged_actions_denied_without_explicit_grant`,
`test_c8_default_actions_allowed_without_any_grant`,
`test_c8_explicit_grant_widens_exactly_one_action`,
`test_c8_multiple_explicit_grants`,
`test_c8_unrecognised_action_always_denied_even_with_env`,
`test_c8_empty_and_missing_env_both_fail_closed`,
`test_c8_bridge_functions_enforce_the_gate_before_backend`,
`test_c8_default_grant_reaches_the_backend_layer`.

**Inherited C4/C5/C6 → satisfied by (file + test):** `tools/browser/browser_bridge.py`
imports `egress_guard.check_egress`/`active_profile` verbatim (no reimplementation;
`test_browser_reuses_the_das_1547_egress_guard_module` asserts the function's source
file is `tools/mcp_bridges/egress_guard.py`) and duplicates only the http-fetch
`_NoRedirect` opener plumbing (C4), asserted by `test_c4_browser_no_redirect_handler_refuses`
+ `test_c4_browser_navigate_denies_before_any_network_call`. C5 (SSRF/internal-range
block) and C6 (label-boundary match) proven at the browser layer via the exact
imported `check_egress` function: `test_c5_browser_check_egress_blocks_ssrf_via_profile`,
`test_c5_browser_check_egress_allows_public_resolved_host`,
`test_c6_browser_label_boundary_matching_reused`,
`test_egress_profile_deny_all_ships_by_default`.

**FR-006 → satisfied by (file + test):** `browser_bridge.read()`/`navigate()` docstrings
+ implementation treat fetched content as inert data (never parsed as instructions, no
code path from page text to the C8 grant, egress profile, or any board/routing field).
Test: `test_fr006_read_returns_inert_string_not_evaluated` (plants an injection-style
payload in the "page" and asserts a privileged action stays denied afterward) +
`test_fr006_read_without_navigate_errors_not_crashes`.

**TB-5 flag-OFF / absent-by-default confirmation:** the browser sidecar has no flag
switch of its own — like `langchain-tools`, it is gated by the SAME `ws_a_tool_bridge`-
controlled `audit_external_tool.py` PreToolUse hook (matcher `mcp__.*`, untouched;
`test_settings_json_hook_covers_browser_tools_too` confirms the existing matcher covers
`mcp__browser__*` with no settings.json edit needed). With the flag OFF (current state)
that hook stays fully inert per DAS-1547's own tests — unchanged here. Separately,
`mcp` (and any real browser driver) is absent from core `requirements.txt`
(`test_tb5_mcp_not_in_core_requirements`), so the tool itself does not exist unless a
future change installs `tools/browser/requirements-browser.txt` — verified.

**Validators run (exact results):**
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (all 7 categories PASS).
- `python3 scripts/board_lint.py` → `OK — 110 ticket(s) checked, 0 violations` (one
  pre-existing, unrelated WARN on DAS-1507 body prose — not from this ticket).
- `ruff check tools/browser/action_gate.py tools/browser/browser_bridge.py
  tests/test_ws_a_browser_tool_egress.py` → **All checks passed!**
- `python3 -m pytest tests/test_ws_a_browser_tool_egress.py` → **23 passed, 1 skipped**.
- `python3 -m pytest tests/test_ws_a_tool_bridge.py` (DAS-1547 suite, untouched) →
  **31 passed, 1 skipped** — still green, confirming reuse (not modification).
- `python3 -m pytest` (full suite) → **1930 passed, 4 skipped** — no collateral
  breakage anywhere in the repo.

**LOCAL-ONLY honored:** no `git commit`/`push`/PR/branch — files edited in place on
`docs/governed-devin-langchain-direction`. Setting `status: in_review`, `assignee:
backend-em` per ROUTING (never self-review) for the combined GATE-3 review +
security-eng red-team pass (adversarial T2/T3 variants handed to DAS-1549, per the
ticket's own note).
