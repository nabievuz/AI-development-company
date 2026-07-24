---
id: DAS-1583
title: WS-E Development — in-tenant LiteLLM model gateway plus deferred vLLM SGLang eject-path adapter
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-004, FR-005]
labels: [security]
zone: tools/model_gateway
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 2).** Build the in-tenant
model gateway per the DAS-1581 design. Distinct repo zone from DAS-1582 so the two
Development tickets proceed without a same-zone wave collision.

- **TN-1 / FR-004 (gateway):** a **LiteLLM** in-tenant model gateway config that realizes
  the ADR-0009 admission layer — every model call resolves to an **in-tenant endpoint**;
  the near-term default is the Claude subscription via account auth (Q9, NOT a metered
  API key); the auth path stays swappable. A model call whose endpoint resolves to a
  hosted/external target that carries code/IP is a config error that **BLOCKS** the run
  (TN-1 precondition, built on DAS-1543). Budget/credit ceiling stays the outer bound
  (ADR-0027 SI-5) — not re-implemented here, only respected.
- **FR-005 (DEFERRED eject-path):** a vLLM / SGLang open-weight in-tenant serving
  **adapter behind its own feature flag DEFAULT OFF** — the eject-path for a tenant whose
  policy forbids any external model call. It is NOT the near-term build: the adapter +
  its **unit tests are buildable with NO live serving stack present** (mock/absent
  backend); the flag stays OFF until an explicit Founder decision opens the eject-path.
  Live vLLM/SGLang serving against a real GPU/VM is out of this ticket (see the BLOCKED
  Deployment ticket DAS-1586).
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); the eject-path additionally
  behind its own OFF sub-flag; flag-off ⇒ inert, dispatch unchanged.

Hand the matching negative tests (SC-003) to DAS-1585.

## Acceptance criteria
- [x] LiteLLM gateway config resolves every model call to an in-tenant endpoint; default = Claude subscription via account auth (Q9); the auth path is swappable via the admission layer.
- [x] An external/hosted code-IP-carrying endpoint evaluates to a BLOCKED config error (TN-1); a negative test proves it (SC-003).
- [x] vLLM/SGLang eject-path adapter present behind its own DEFERRED flag OFF; unit-tested with no live serving stack; inert until a Founder decision (SC-003).
- [x] Feature flag(s) OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. (Merged PR / green CI: NOT done — LOCAL-ONLY constraint on this run, see log.)

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 2). TN-1/FR-004 LiteLLM in-tenant gateway (Claude-subscription default, Q9) + FR-005 DEFERRED vLLM/SGLang eject-path adapter behind its own OFF flag — adapter + unit tests buildable without a live serving stack; live serving deferred to the BLOCKED DAS-1586. All behind `ws_e_tenant_hardening` OFF.

### 2026-07-25 — Backend Engineer 1

**AADL Stage-3 Development (GATE-3) built, part 2 — in-tenant LiteLLM gateway +
DEFERRED vLLM/SGLang eject-path.** New zone `tools/model_gateway/` (distinct from
DAS-1582's/DAS-1584's zones, no same-wave collision).

**FR -> file + test map:**
- **FR-004 (TN-1, LiteLLM in-tenant gateway):** `tools/model_gateway/gateway.py` —
  `LiteLLMGateway`/`ModelRoute`/`GatewayCall`/`enforce_boundary`/`GatewayConfigError`.
  Realizes the ADR-0009 admission layer by REUSING (not re-implementing)
  `scripts/ws_b_admission.admit()` for the admission decision and
  `scripts/check_in_tenant.is_in_tenant()` for the TN-1 boundary predicate
  (lazy path-based module load, mirrors `tools/observability/otlp_exporter.py`'s
  `_load_module` pattern — no parallel boundary check, no fork). Default route
  `DEFAULT_ROUTES` = `claude_subscription` (`https://api.anthropic.com`,
  `role=model`, `auth=account`) — the Q9 near-term default, the SOLE
  `accepted_external_roles` exception (matches `config/tenant_boundary.yaml`).
  Any other route registered under a non-`model` role that resolves external is
  BLOCKED at both registration time and call time (defense in depth) —
  `GatewayConfigError`, never a silent pass-through. Auth path is swappable by
  route name, not by rewriting a caller. Tests: `tests/test_ws_e_litellm_gateway.py`
  G1-G5 (default route in-tenant + admitted; external non-model endpoint blocked
  at registration AND at call time; in-tenant non-model endpoint accepted;
  `ws_b_admission`'s REJECTED outcome propagates unchanged for an empty model).
- **FR-005 (DEFERRED vLLM/SGLang eject-path):** `tools/model_gateway/ejectpath.py` —
  `OpenWeightBackend`, `build_route`, `register_ejectpath`, `mock_call`,
  `EjectPathInactiveError`. Route tagged `role="ejectpath"` (deliberately NOT
  `"model"`, so it does not ride the Claude route's external exception — the
  eject-path must independently prove in-tenant, which *strengthens* TN-1 per
  design §4.2). Buildable + unit-tested against a MOCK loopback endpoint
  (`DEFAULT_MOCK_URL = http://127.0.0.1:8000`); no live vLLM/SGLang serving stack
  stood up (that stays DAS-1586, blocked). Tests: E1 (sub-flag OFF ⇒
  `EjectPathInactiveError`, route never registered), E2 (sub-flag ON ⇒ a mock
  call succeeds, well-formed `GatewayCall`), E3 (an external eject-path target is
  BLOCKED even with the sub-flag ON), E4 (parent `ws_e_tenant_hardening` OFF
  keeps the eject-path inert even if only the sub-flag env-overrides ON —
  nested gating), E5 (eject-path call shape identical to the Claude-route call
  shape — swapping is config, not an agent rewrite).
- **New flag:** `ws_e_openweight_ejectpath` added to `config/features.yaml`
  (default `false`), nested under the parent `ws_e_tenant_hardening` — ADDED
  ONLY, no other key touched. Read by `tools/model_gateway/flag.py`
  (`tenant_hardening_on()`, `openweight_ejectpath_on()`) via its own
  fail-safe-to-OFF line-scan (mirrors `tools/sandbox/flag.py`'s pattern) —
  deliberately independent of `scripts/feature_flags.py`'s restricted
  `DEFAULTS` allow-list so that module did not need touching (footprint).
  `openweight_ejectpath_on()` enforces the parent+sub-flag nesting itself.
  Tests: F1/F1b (both flags OFF by default — repo `config/features.yaml` and
  no env override — gateway construction/import unaffected, a pure library
  call like `ws_b_admission.py`).

**Gotcha found + fixed:** an initial `import flag` / `import gateway` (bare
module-name imports) collided via `sys.modules` caching with
`tools/sandbox/flag.py` (also named `flag.py`) once the full suite ran in one
pytest process — whichever loaded first won for every later bare `import flag`
anywhere in the run. Fixed by importing this package fully-qualified
(`from tools.model_gateway.flag import ...`) throughout
`ejectpath.py`/`__init__.py`/the test file instead of `sys.path.insert` +
bare import; `tools/` is a namespace package (no `__init__.py`) so this
resolves cleanly once the repo root is on `sys.path` (true for
`python3 -m pytest` from the repo root, as VERIFY requires).

**TN-1 evidence:** `python3 scripts/check_in_tenant.py` → `TN-1 OK: all
code/IP endpoints in-tenant (6 declared; model call excepted).` exit 0 — the
gateway/eject-path modules declare NO new entries in the shared
`config/tenant_boundary.yaml` SSOT (not touched, out of footprint); they reuse
its guard function directly against their own in-code route table instead
(design §4, "no BOM element adds a parallel boundary check").

**VERIFY (staged, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **100/100** (all 8 categories PASS,
  including `tn1-in-tenant-boundary`).
- `python3 scripts/check_in_tenant.py` → exit 0 (above).
- `python3 -m pytest` → **2158 passed, 4 skipped**, 0 failed (full suite,
  including this ticket's 12 new tests in `tests/test_ws_e_litellm_gateway.py`).
- `python3 scripts/board_lint.py` → exit 0, 180 tickets checked, 0 violations
  (1 pre-existing non-fatal WARN on DAS-1507, unrelated to this ticket).
- `ruff check tools/model_gateway tests/test_ws_e_litellm_gateway.py` → clean.
- No `/Users/owner`/`/home/` literals in new files (grepped); no secret-shaped
  strings introduced.

**Footprint respected:** only `tools/model_gateway/{__init__.py,flag.py,
gateway.py,ejectpath.py}`, `config/features.yaml` (one line added), and
`tests/test_ws_e_litellm_gateway.py` were authored by this ticket, plus this
file. Did not touch `config/rbac.yaml`/`scripts/rbac.py` (DAS-1582),
`tools/guardrails/` (DAS-1584), `config/tenant_boundary.yaml`, or
`scripts/feature_flags.py` — those either belong to a sibling ticket or were
deliberately left alone per the flag-reader design choice above. (Note: the
working tree also carries other, already-present uncommitted changes from
sibling WS-E tickets — `config/rbac.yaml`, `scripts/rbac.py`,
`tools/guardrails/`, `evals/ws-e-guardrails/` — none of which this ticket
created or edited; `git add -A` was required by VERIFY to reach 100/100 and
necessarily stages them too, but no line inside them originates here.)

**Constraint:** ⛔ LOCAL-ONLY — no git push / PR / commit / remote made this
run (per explicit dispatch instruction), matching the established DAS-1581
pattern for this workstream. No branch/worktree was created for the same
reason; all work is uncommitted in the working tree, staged.

**Status → `in_review`; assignee → `backend-em`** (GATE-3 reviewer per
`board/ROUTING.md`). Escalation: none within charter. Routing note for the
orchestrator: because no branch/PR exists (LOCAL-ONLY constraint), the normal
"in_review requires a pushed branch/PR" DoD is not literally satisfiable this
run — Backend EM review should be of the staged working-tree diff; the
merged-PR/green-CI acceptance-criterion line is intentionally left unchecked
above pending an explicit Founder/CTO decision on how to land LOCAL-ONLY WS-E
work (same open question implicitly carried by DAS-1581/DAS-1582/DAS-1584).

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking)

Adversarial in-code verification of `tools/model_gateway/`. Ran the WS-E gateway suite (12 tests) AND ephemeral exploit probes (deleted).

**Per-item verdicts:**
| Item | Verdict | Evidence (ephemeral probe) |
|---|---|---|
| TN-1: hosted/external code-IP endpoint refused fail-closed, reuses `check_in_tenant`, no hosted fallback | **HOLD** | Every external non-`model` role (`tool`,`code`,`ejectpath`,`sandbox`,`observability`,`embeddings`) → `GatewayConfigError` at REGISTRATION (and re-checked at call time); in-tenant `127.0.0.1` non-model accepted; `enforce_boundary` reuses `check_in_tenant.is_in_tenant` verbatim; `resolve_target` has no hosted default/fallback branch. |
| Eject-path inert while `ws_e_openweight_ejectpath` OFF; admission reused not bypassed | **HOLD** | Sub-flag OFF → `register_ejectpath`/`mock_call`→`EjectPathInactiveError`, route never registered, un-callable; route tagged `role="ejectpath"` (NOT `model`) so it must independently prove in-tenant; external eject-path URL blocked even with sub-flag ON; `call()` runs through the reused `ws_b_admission.admit()` (no parallel admission). |

**Overall: PASS — no code/IP endpoint leak. The Claude model call is the sole external exception (matches `config/tenant_boundary.yaml accepted_external_roles: [model]`).**

**Residual handed to DAS-1585 (NOT a GATE-3 blocker):** `enforce_boundary` accepts ANY external URL tagged `role="model"` — it checks role membership, not that the URL equals the declared `claude_model` host. A rogue `ModelRoute(url="https://evil-llm.example.com", role="model")` rides the exception. This is WITHIN the ratified `accepted_external_roles: [model]` policy (a model endpoint carries prompts/completions, not repo code/IP — the TN-1 concern is code/IP, which stays blocked), so it is not a boundary break. DAS-1585 should pin model-route URLs to the `config/tenant_boundary.yaml` declared model endpoint (host allow-list) + a negative test. Recorded, not blocking.

Verdict: keep `status: in_review`; `assignee: cto`. **GATE-3 red-team PASSED — cleared for CTO ratification.** LOCAL-ONLY: only this ticket file edited.

### 2026-07-24 — CTO (GATE-3 closure)

**AADL Stage-3 / GATE-3 (Development) CLOSED for WS-E part 2 (in-tenant LiteLLM gateway + DEFERRED vLLM/SGLang eject-path).** Ratified on the blocking Security-Engineer red-team (PASSED — no code/IP endpoint leak) plus my own independent staged verification (shared with DAS-1582/1584):
- `diagnostics.py` → 100/100 (incl. `tn1-in-tenant-boundary`); `check_in_tenant.py` clean (6 declared, model call excepted).
- WS-E 4 suites → 55 passed (12 gateway/eject-path here); full `pytest -q` → 2201 passed, 4 skipped.
- `check_never_auto_approve.py` exit 0; `board_lint.py` exit 0.

**Judgment:** TN-1 holds — `enforce_boundary` reuses `check_in_tenant.is_in_tenant` VERBATIM (no forked/parallel boundary check); every external non-`model` role is BLOCKED at registration AND call time (defense in depth); `resolve_target` has no hosted fallback branch. The Claude subscription route (`role=model`, account auth, Q9) is the SOLE external exception, matching `config/tenant_boundary.yaml accepted_external_roles: [model]` — a model endpoint carries prompts/completions, not repo code/IP, so it is within the ratified boundary, not a break. The DEFERRED eject-path is tagged `role="ejectpath"` (NOT `model`), so it must independently prove in-tenant (strengthens TN-1); inert while `ws_e_openweight_ejectpath` OFF and nested under `ws_e_tenant_hardening` OFF. Flag-off byte-identical.

**Residual bound to DAS-1585 (R2 — NOT a GATE-3 blocker):** `enforce_boundary` checks role membership, not that a `role="model"` URL equals the declared `claude_model` host — a rogue `ModelRoute(url=..., role="model")` rides the exception. This is WITHIN the ratified `accepted_external_roles: [model]` policy (model carries prompts, not code/IP), so not a boundary break. DAS-1585 to pin model routes to the `config/tenant_boundary.yaml` declared model host + a negative test. Bound into DAS-1585 `## Security conditions (GATE-3)`.

**Decision: GATE-3 CLOSED → `status: done`.** LOCAL-ONLY: only this ticket file edited (no commit/branch/PR/push). The staged-diff-to-merged-PR landing question remains the WS-E-wide open item (Founder/CTO). Unblocks DAS-1585 (Testing) alongside DAS-1582/1584.

### 2026-07-24 — Backend Engineer 1

R2 host-pin fix landed (found by DAS-1585's `test_r2_rogue_model_role_host_must_be_pinned_to_declared_claude_host`, `xfail(strict=True)`). `enforce_boundary()` in `tools/model_gateway/gateway.py` no longer returns unconditionally for `role="model"`: it now reads the SSOT-declared `claude_model` endpoint host from `config/tenant_boundary.yaml` (`_declared_claude_model_host()`), and REUSES `tools/mcp_bridges/egress_guard.host_matches` (label-boundary match) to confirm the route's URL host equals that declared host (`api.anthropic.com`). A `role="model"` route to any OTHER host (e.g. the rogue `https://evil-llm.example.com` in the test) now raises `GatewayConfigError` — fail-closed, same as a non-model external role. An empty/unreadable SSOT read also fails closed (refuses, never silently accepts). The legit Claude default route (`DEFAULT_ROUTES` / `default_gateway()`) is unaffected — same URL as the SSOT, still registers and resolves cleanly.

Removed `@pytest.mark.xfail(strict=True)` from the R2 test in `tests/test_ws_e_tenant_hardening.py` — it now PASSES for real (no longer xfail).

Verified: `pytest tests/test_ws_e_tenant_hardening.py tests/test_ws_e_litellm_gateway.py -q` → 20 passed (R2 passes, legit-route sanity test passes, all 12 prior gateway tests still green). Full `pytest -q` → 2209 passed, 4 skipped, 0 xfailed. `diagnostics.py` → 100/100 (incl. `tn1-in-tenant-boundary`). `check_in_tenant.py` → exit 0 (TN-1 OK, 6 declared, model call excepted). `ruff check tools/model_gateway/gateway.py tests/test_ws_e_tenant_hardening.py` → clean. `board_lint.py` → exit 0 (180 tickets checked, 0 violations; one pre-existing unrelated non-fatal WARN on DAS-1507 body prose).

Touched only `tools/model_gateway/gateway.py`, `tests/test_ws_e_tenant_hardening.py`, and this ticket's log. LOCAL-ONLY — no commit/branch/PR/push. `status` left `done` per instruction (this is a residual hardening note on an already-closed GATE-3 ticket, not a reopen). DAS-1585 status left untouched.
