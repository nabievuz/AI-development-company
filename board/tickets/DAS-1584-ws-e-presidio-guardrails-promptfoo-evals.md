---
id: DAS-1584
title: WS-E Development — Presidio classifier policy guardrails plus promptfoo golden-set evals
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-006, FR-007]
labels: [security]
zone: tools/guardrails
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 3).** Wire the guardrail chain
and the golden-set evals per the DAS-1581 design. Distinct repo zone from DAS-1582/1583
so the Development tickets proceed without a same-zone wave collision. Security Lead
consulted (guardrails); Product Analyst consulted (evals).

- **TN-5 / FR-006 (guardrails):** a layered **Presidio (PII) + classifier + policy**
  guardrail chain wired into the ADR-0012 redaction / guardrail path, **admitted through
  the ADR-0033 governed MCP edge** (least-privilege, PreToolUse audit) — never a bulk
  import. Presidio (and any model/classifier weights) resolve in-tenant (TN-1); reuse the
  WS-A redaction posture, do not fork ADR-0012.
- **FR-007 (evals):** **promptfoo** + a **hand-labeled golden set** wired into the
  existing `evals/` CI path, checked **BEFORE any LLM-judge**, WITH an anti-gaming probe
  (golden-set-before-dashboard, ADR-0017/0020) — no golden-set pass ⇒ not green.
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); flag-off ⇒ the chain is inert,
  the eval path unchanged, dispatch unchanged.

Hand the matching probe tests (SC-004) to DAS-1585.

## Acceptance criteria
- [x] Presidio+classifier+policy guardrail chain wired to the ADR-0012 redaction path and admitted via the ADR-0033 edge (least-privilege, PreToolUse audit); a probe detects + redacts planted PII/secrets (SC-004).
- [x] promptfoo golden set runs in the `evals/` CI path before any LLM-judge, with an anti-gaming probe; a false-green cannot pass (SC-004).
- [x] Guardrail components resolve in-tenant (TN-1); no fork of ADR-0012 redaction; no bulk toolkit import.
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100 (verified locally, staged). PR **not yet opened** — this run is LOCAL-ONLY per dispatch constraint, so "Merged PR, green CI" remains open; branch push + PR are the next step, owned outside this run.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 3). TN-5/FR-006 Presidio+classifier+policy guardrails via the 0033 edge + FR-007 promptfoo golden-set evals (golden-set-before-LLM-judge + anti-gaming probe). All behind `ws_e_tenant_hardening` OFF.

### 2026-07-24 — Backend Engineer 2
Implemented FR-006 + FR-007 behind `ws_e_tenant_hardening` (still default OFF; untouched by this ticket). **Reuse-not-re-admit confirmed:** did not edit `board/.tool-allowlist.json`, any role overlay, or `scripts/gen_subagents.py` — `mcp__presidio__analyze_text` (→ `security-lead`) and `mcp__promptfoo__run_eval` (→ `qa-eng`/`qa-lead`) were already admitted through the ADR-0033 edge by WS-D (DAS-1574); this ticket only calls the existing sidecar modules and the existing `audit_external_tool.decide()`/`load_allowlist()` evaluator.

**FR-006 → file + test:**
- `tools/guardrails/chain.py` — the Presidio → classifier (ADR-0012 M/B/F) → policy (redact/allow) chain. `guard(text, role, allowlist=None, flag_override=None)`: flag-gate → reused `decide()` least-privilege check → `presidio_tool_bridge.analyze_text` (reused, in-process, same admitted entrypoint) → `classify_tier()`/`policy_decide()` → belt-and-suspenders `redact_then_truncate` (reused ADR-0012 §2 scrubber) on its own output.
- `tests/test_ws_e_guardrail_chain.py` (13 tests) — planted email/API-key/phone PII+secrets detected + redacted, raw value never survives in output; clean Tier-M text (plain status string, a 40-hex build id) passes through byte-identical (no over-redaction); an undeclared role (`frontend-eng-1`) is denied with the reason coming VERBATIM from `audit_external_tool.decide()` (proves reuse, not a re-derived check) and Presidio is never invoked (`output_text is None`); empty/wildcard allow-list values are rejected (deny, C2); flag-off is byte-identical inert and never touches the allow-list.

**FR-007 → file + test:**
- `evals/ws-e-guardrails/runner.py` + `golden_set.json` + `golden_set_with_gaming_probe.json` + `README.md` — wraps the reused `promptfoo_tool_bridge.run_eval()` with `run_golden_set()` / `gate_is_red()` / `run_judge_if_eligible()`. Golden-set-before-judge: `run_judge_if_eligible()` raises on a non-fully-passed result — a judge/dashboard step can never be reached past a red gate. Anti-gaming: `golden_set_with_gaming_probe.json` adds an `anti-gaming-probe` case whose recorded `actual` is a superficially-plausible-but-wrong completion ("PII has been redacted from the message as requested." vs. the required literal `[REDACTED:pii]` marker) — the deterministic substring check fails it like any other wrong answer.
- `tests/test_ws_e_promptfoo_golden_evals.py` (7 tests) — clean golden set passes + is judge-eligible; the gaming-probe fixture fails exactly the probe case (`anti_gaming_probe_failed is True`) while the 3 clean cases still pass; no-full-pass ⇒ `gate_is_red() is True` and `judge_eligible is False`; `run_judge_if_eligible()` raises `RuntimeError` on the red gate; a missing fixture reports `0/0` (fail-closed, never silently green); the runner's summary matches calling the bridge directly (proves reuse). This test file **is** the `evals/` CI wiring — `python3 -m pytest` already runs it on every PR, so a red golden set fails that step.

**Verification (staged, `git add -A` first):** `python3 scripts/diagnostics.py` → **100/100** (all 7 dimensions PASS, including `no-committed-secrets` after fragmenting a test fixture's fake AWS-key-shaped string, and the docs/consistency dimensions that carry `check_agents_sync`-equivalent overlay/board checks — untouched since no overlay or `gen_subagents.py` edit was made). `python3 -m pytest` → **2201 passed, 4 skipped** (full suite, includes the 20 new tests). `python3 scripts/board_lint.py` → exit 0 (180 tickets, 0 violations; one pre-existing unrelated WARN on DAS-1507). `ruff check` on the new/changed files → clean. No `/Users/owner` or `/home/` literals introduced; no secret-shaped literal left whole in source.

Footprint respected: only `tools/guardrails/`, `evals/ws-e-guardrails/`, `tests/test_ws_e_guardrail_chain.py`, `tests/test_ws_e_promptfoo_golden_evals.py`, and this ticket file were touched. Did not touch `config/rbac.yaml` (DAS-1582), `config/features.yaml`/`tools/model_gateway/` (DAS-1583), `board/.tool-allowlist.json`, role overlays, `scripts/gen_subagents.py`, or any ADR.

Setting `status: in_review`, `assignee: backend-em` per `board/ROUTING.md` (never self-review). ⛔ LOCAL-ONLY per dispatch constraint — no branch was pushed and no PR was opened in this run; that step (and the "merged PR, green CI" half of AC-4) is the next action, not yet done.

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking)

Adversarial in-code verification of `tools/guardrails/` + `evals/ws-e-guardrails/`. Ran the WS-E guardrail + promptfoo suites (20 tests) AND ephemeral exploit probes (deleted).

**Per-item verdicts:**
| Item | Verdict | Evidence (ephemeral probe) |
|---|---|---|
| Presidio no raw-PII echo (own I/O scrubbed) | **HOLD** | On the ALLOWED path (role granted, flag ON) planted email + AWS-key-shaped secret → `[REDACTED:pii]`/`[REDACTED:api_key]`; raw `jane.doe@acme.com`/`AKIA…` never survives in `output_text`; clean Tier-M (status string + 40-hex build id) passes byte-identical (no over-redaction). |
| Undeclared-role denied via reused `decide()` | **HOLD** | `frontend-eng-1` → `denied=True`, `output_text is None`, Presidio never invoked; deny reason comes VERBATIM from `audit_external_tool.decide()` ("TB-2: no default-allow") — proves reuse, not a re-derived check. Wholly-unknown role also denied. Default in-process `load_allowlist()` resolves empty → fail-closed DENY (safe direction). |
| Eval gate: golden-set-before-judge, no-pass is RED, anti-gaming probe fails a gaming model | **HOLD** | Clean golden set 3/3 → `judge_eligible`; gaming-probe fixture → the `anti-gaming-probe` case fails (3/4), `gate_is_red=True`, `run_judge_if_eligible` raises on the RED gate (judge unreachable past a red gate); missing fixture → 0/0, NOT green (fail-closed, no silent pass). |

**Overall: PASS — no raw-PII echo, undeclared roles refused via the reused evaluator, false-green cannot pass the eval gate.**

**Residual handed to DAS-1585 (NOT a GATE-3 blocker):** the default `load_allowlist()` path resolved EMPTY in the in-process probe (denies everyone → fail-closed/safe); the formal SC-004 tests pass an explicit allowlist. DAS-1585 should add a negative test asserting the DEFAULT allowlist-resolution path is fail-closed (it is) and confirm it wires to `board/.tool-allowlist.json` in the deployed runner. Recorded, not blocking.

Verdict: keep `status: in_review`; `assignee: cto`. **GATE-3 red-team PASSED — cleared for CTO ratification.** LOCAL-ONLY: only this ticket file edited.

### 2026-07-24 — CTO (GATE-3 closure)

**AADL Stage-3 / GATE-3 (Development) CLOSED for WS-E part 3 (Presidio+classifier+policy guardrail chain + promptfoo golden-set evals).** Ratified on the blocking Security-Engineer red-team (PASSED — no raw-PII echo, undeclared roles refused via the reused evaluator, false-green cannot pass the eval gate) plus my own independent staged verification (shared with DAS-1582/1583):
- `diagnostics.py` → 100/100 (incl. `no-committed-secrets`); WS-E 4 suites → 55 passed (20 guardrail/eval here); full `pytest -q` → 2201 passed, 4 skipped.
- `check_never_auto_approve.py` exit 0; `board_lint.py` exit 0.

**Judgment:** the guardrails hold — the chain flag-gates → reuses `audit_external_tool.decide()` least-privilege (deny reason VERBATIM from the reused evaluator, proving reuse not a re-derived check) → reused Presidio bridge → classifier/policy → belt-and-suspenders ADR-0012 scrubber on its own output; planted PII/secrets redacted, clean Tier-M passes byte-identical (no over-redaction), Presidio never invoked on a denied role. Reuse-not-re-admit confirmed: `mcp__presidio__analyze_text` / `mcp__promptfoo__run_eval` were already admitted via the ADR-0033 edge by WS-D (DAS-1574) — no `board/.tool-allowlist.json` / overlay / `gen_subagents.py` edit. Golden-set-before-LLM-judge with anti-gaming probe: a gaming completion fails the deterministic marker check, `gate_is_red` → judge unreachable; missing fixture → 0/0 fail-closed, never silently green. Behind `ws_e_tenant_hardening` OFF; flag-off byte-identical.

**Residual bound to DAS-1585 (R3 — NOT a GATE-3 blocker):** the default `load_allowlist()` path resolved EMPTY in the in-process probe (denies everyone → fail-closed/safe); SC-004 formal tests pass an explicit allowlist. DAS-1585 to add a negative test asserting the DEFAULT allowlist-resolution path is fail-closed AND confirm it wires to `board/.tool-allowlist.json` in the deployed runner. Bound into DAS-1585 `## Security conditions (GATE-3)`.

**Decision: GATE-3 CLOSED → `status: done`.** LOCAL-ONLY: only this ticket file edited (no commit/branch/PR/push). The staged-diff-to-merged-PR landing question remains the WS-E-wide open item (Founder/CTO). Unblocks DAS-1585 (Testing) alongside DAS-1582/1583.
