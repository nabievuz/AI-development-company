---
id: DAS-1547
title: WS-A Development — FastMCP tool-bridge sidecar under tools, fold in the spike, flag OFF
status: in_review
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-001, FR-002, FR-003, FR-004]
labels: [security]
zone: tools/mcp_bridges
depends_on: [DAS-1546]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-A, part 1).** Build the governed
tool-bridge MCP sidecar per the DAS-1546 design.

- **TB-1:** an out-of-process FastMCP sidecar under `tools/` (same shape as `ArcRift`),
  wired in `.mcp.json`; the engine stays server-free (`check_no_dead_runtime` holds);
  absence of the sidecar means the tool does not exist.
- **Fold in the on-branch spikes** — `tools/mcp_bridges/langchain_tool_bridge.py`,
  `tools/mcp_bridges/audit_external_tool.py`, `tools/mcp_bridges/mcp.snippet.json`,
  `requirements-tools.txt` — harden to the design; do not rewrite from scratch.
- **TB-2/TB-3:** enforce the overlay allow-list and the `PreToolUse` audit/deny path;
  emit tool transcripts as ADR-0012-redactable events.
- **TB-5/FR-004:** guarded by the WS-A feature flag (OFF); with the flag OFF the
  sidecar is inert and dispatch is unchanged.

## Acceptance criteria
- [ ] FastMCP sidecar under `tools/mcp_bridges/` wired in `.mcp.json`; `check_no_dead_runtime` / `diagnostics.py` still 100/100.
- [ ] On-branch spike files folded in and passing (not left untracked); allow-list + PreToolUse audit/deny enforced per design.
- [ ] Tool-event redaction path present (ADR-0012); tool never writes routing fields (C3) / never bypasses a gate (C4).
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge. Merged PR, green CI.

## Security conditions (GATE-2)

Bound by the CTO at GATE-2 closure of DAS-1546 (Security Lead audit, findings F1–F7).
These are **MUST-satisfy** — GATE-3 for this ticket **cannot be signed** unless all are
met. Hand the matching tests (T1–T5) to DAS-1549.

- **C1 (F1):** Make `board/.tool-allowlist.json` a **tracked, reviewed** artifact (it is
  a security *input* to the request path, not a runtime log) so generate-and-diff has a
  committed baseline and a hand-edit is a real red build — OR replace §1.3's CI-diff
  drift claim with a mechanism that actually works on a gitignored file. Resolve the
  tracked-vs-gitignored contradiction before wiring; do not ship the false claim.
- **C2 (F2):** The compiler MUST NEVER emit `"*"` as a **roles-list value**; AND harden
  `decide()` so a `"*"` roles value is not treated as any-role (remove/guard the
  `roles == "*"` branch, or add a load/schema check rejecting any `"*"` value in the
  compiled map). Keep the legitimate server-wide `tools: ["*"]` overlay grant compiling
  to an **explicit role list**.
- **C3 (F3):** Pin the harness fail-mode — a PreToolUse hook that **fails to execute**
  (spawn error / non-zero / crash / unparseable stdout) MUST fail **CLOSED** (tool
  denied) on both the CLI and the Agent SDK. Verify actual semantics; if either fails
  open, add a wrapper that guarantees closed. Hand DAS-1549 the T1 test.
- **C4 (F5):** Egress enforcement MUST **disable redirect-following** OR re-check **every**
  3xx hop against the invoking profile before following it.
- **C5 (F6):** The egress check MUST resolve the target and **block** loopback,
  link-local (169.254.0.0/16, incl. cloud-metadata 169.254.169.254), and RFC-1918 ranges
  unless a profile narrowly and explicitly scopes them; never trust the URL host string
  alone. Re-justify or drop the bare-`localhost` example grant.
- **C6 (F7):** Domain matching MUST anchor on a **label boundary** (exact base or
  `.`-prefixed suffix: `host == base or host.endswith("." + base)`), never a bare
  substring/suffix match.
- **C7 (F4):** Deliver the ADR-0012 §2 extended scrubber pattern set (Bearer/JWT, DSN,
  GitHub-token family, high-entropy fallback, PII) **with tests**, redact-then-truncate
  ordered, high-entropy `{32,}` tuned to not over-redact Tier-M digests; preserve the
  structural primary control (raw payload Tier-F, no-secrets-by-default). Do not let the
  doc imply regex completeness the scrubber does not have.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Development, part 1). TB-1/TB-2/TB-3; folds in the branch spike.

### 2026-07-24 — CTO
GATE-2 closed on DAS-1546. Attached binding security conditions **C1–C7** (above) from
the Security Lead audit — MUST-satisfy for GATE-3. Everything stays behind
`ws_a_tool_bridge` OFF until DAS-1549 proves them.

### 2026-07-24 — Backend EM
Development done (TB-1/TB-2/TB-3), spikes hardened (not rewritten), all behind
`ws_a_tool_bridge` OFF. Ready for CTO review + the security-eng red-team/GATE-3 pass.

**Files created:**
- `tools/mcp_bridges/redaction.py` — ADR-0012 §2 extended scrubber (C7).
- `tools/mcp_bridges/egress_guard.py` — deny-all egress + SSRF/label-boundary (C4/C5/C6).
- `config/egress-allowlist.yaml` — tracked deny-all-by-default profiles (no localhost; no browser profile — DAS-1548's).
- `board/.tool-allowlist.json` — TRACKED compiled allow-list baseline (`{}`; C1).
- `.claude/settings.json` — PreToolUse `mcp__.*` hook with C3 fail-closed wrapper (TB-3).

**Files hardened/edited:**
- `tools/mcp_bridges/audit_external_tool.py` — C2 decide()/load hardening; flag-gated inertness; ADR-0012 scrub of audit `reason`; C3 exit-2 fail-closed guard.
- `tools/mcp_bridges/langchain_tool_bridge.py` — no-redirect opener (C4) + egress gate before any network syscall.
- `scripts/gen_subagents.py` — TB-2 compiler: overlay `## External tools` → `board/.tool-allowlist.json` (extended, not forked; ADR-0029). Never emits `"*"` (C2).
- `.mcp.json` — merged the `langchain-tools` FastMCP sidecar (portable `${workspaceFolder}`; playwright/browser left to DAS-1548).
- `tools/mcp_bridges/mcp.snippet.json` — corrected stale hook path + merge-state note.
- `.github/CODEOWNERS` — regenerated (adds `/tools/` area this workstream introduces; generated file, `gen_codeowners.py`).
- `tests/test_ws_a_tool_bridge.py` — folded-in + expanded to 31 tests (positive + negative) covering C1–C7.

**C1–C7 → satisfied by (file + test):**
- **C1** tracked generate-and-diff allow-list — `board/.tool-allowlist.json` (tracked, NOT gitignored) compiled by `scripts/gen_subagents.py::compile_tool_allowlist`; drift = red build via `test_c1_allowlist_matches_overlays_no_drift` + `test_c1_tool_allowlist_is_tracked`. (Resolves the F1 tracked-vs-gitignored contradiction: the design's §1.3 gitignore line is superseded — the file is a security INPUT, so it is committed.)
- **C2** no `"*"` roles value — compiler emits only explicit sorted role-key lists (`compile_tool_allowlist`); `decide()`/`load_allowlist()` reject any `"*"` value/list-member. Tests: `test_c2_server_wide_grant_compiles_to_explicit_roles`, `test_c2_decide_denies_wildcard_roles_value`, `test_c2_load_allowlist_rejects_wildcard`.
- **C3** hook fails CLOSED — `.claude/settings.json` command `sh -c 'python3 …/audit_external_tool.py || exit 2'` (spawn/crash → exit 2 = PreToolUse block) + in-script exit-2 guard on internal error; malformed event/empty allow-list → deny. Tests: `test_c3_settings_binding_present_and_failclosed`, `test_c3_decode_failclosed`, `test_c3_wrapper_denies_on_spawn_failure`, `test_c3_flag_on_enforces_and_audits`. (Relies on the documented CLI+SDK PreToolUse exit-code-2 = deny contract.)
- **C4** no unchecked redirect — `langchain_tool_bridge._NoRedirect` refuses every 3xx; the egress gate runs before any network call. Tests: `test_c4_no_redirect_handler_refuses`, `test_c4_web_fetch_egress_gate_before_network`.
- **C5** resolve + block internal ranges — `egress_guard.check_egress` resolves the host and blocks loopback/link-local(169.254/16 incl .169.254)/RFC-1918 unless a profile lists the exact IP literal (fixed a bug where any allow-listed domain waived the block). Tests: `test_c5_blocks_loopback_linklocal_rfc1918`, `test_c5_allows_public_resolved_host`, `test_c5_deny_by_default_empty_or_absent_profile`, `test_c5_unresolvable_host_denied`.
- **C6** label-boundary match — `egress_guard.host_matches` (`host == base or host.endswith("." + base)`; `*.base` = sub-domains only). Tests: `test_c6_plain_entry_label_boundary`, `test_c6_wildcard_entry_subdomains_only`, `test_c6_full_check_rejects_lookalike_suffix`.
- **C7** ADR-0012 §2 scrubber — `redaction.py` (Bearer/JWT, DSN, sk-ant/AKIA/GitHub family, PII email+phone, high-entropy `{32,}` fallback tuned to skip pure-hex/numeric Tier-M digests), redact-then-truncate, fail-closed `safe_scrub`. Structural primary control preserved (raw payload Tier-F, never stored). Tests: `test_c7_redacts_all_classes`, `test_c7_no_over_redaction_of_tier_m_digests`, `test_c7_redact_then_truncate_ordering`, `test_c7_safe_scrub_fail_closed`, `test_c7_high_entropy_fallback_catches_mixed_secret`, `test_c7_no_raw_secret_substring_survives`.

**Flag-OFF no-op:** `_flag_on()` fail-safes to OFF; `main()` short-circuits to allow with NO audit write when OFF — verified: `mcp__ArcRift__store_memory` → `{}` (allow), rc 0, no audit file (byte-identical to pre-merge; ArcRift/obsidian never denied). Sidecar is absent-by-default (`mcp` not in core `requirements.txt`), so absent ⇒ tool doesn't exist.

**Validators:** `diagnostics.py` = **100/100**; `board_lint.py` OK (110 tickets, 0 violations; the DAS-1507 WARN is pre-existing, unrelated); `check_agents_sync.py` OK (32 shims in sync); `ruff check` clean on all touched files; `pytest tests/test_ws_a_tool_bridge.py` = 31 passed, 1 skipped (`mcp` absent).

**Routed / notes for reviewer:**
- Handed to DAS-1549: adversarial tests T1–T5 (map to my SC-001/SC-002 negative coverage).
- ⚠️ Pre-existing suite red (NOT mine, out of footprint): `tests/test_feature_flags.py` (3 fails) — its hardcoded `DEFAULTS` expectation predates the MUSTAQIL `ws_*` flag expansion (DAS-1543) in `scripts/feature_flags.py`; needs a one-line dict refresh by that owner. I did not touch `feature_flags.py`/`features.yaml`/`test_feature_flags.py`.
- Footprint note: regenerated `.github/CODEOWNERS` (generated file) to add the `/tools/` area — required to land the tracked spike + reach diagnostics 100/100; trivial to revert if the reviewer prefers it split out.
- LOCAL-ONLY honored: no commit/push/PR/branch — files edited in place on `docs/governed-devin-langchain-direction`. `in_review` here is a board-state handoff, not a pushed PR (per dispatch instruction).
