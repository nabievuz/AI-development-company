---
id: DAS-1565
title: WS-C Development — E2B and OpenHands per-task sandbox adapter, isolation boundary, stub backend
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [FR-006]
labels: [security]
zone: tools/sandbox
depends_on: [DAS-1563]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-C, part 2).** Build the per-task
**sandbox adapter** a worker node uses to run untrusted code/commands in isolation, per the
DAS-1563 isolation contract. Security Lead consulted.

- **FR-006:** an isolation boundary (E2B / OpenHands, Docker-based per Q2) — untrusted
  execution cannot reach the host, the repo, another task, or a credential it was not
  explicitly scoped (fail-closed default: no host mounts, no network, no creds).
- **Stub/reference backend (buildable without a live host):** follow the WS-A pattern —
  the real Docker/E2B driver is an **optional, absent-by-default** dependency
  (`tools/sandbox/requirements-sandbox.txt`, kept out of core `requirements.txt`); the
  adapter is importable/testable with zero optional deps installed against a stub backend.
  The sandbox therefore *does not exist* until the optional backend is installed.
- Feature-flagged OFF (the shared `ws_c_langgraph_loop` key) — with the flag OFF the
  adapter is inert and dispatch is unchanged.
- **Actually running a live sandbox/VM is OUT of scope here** — that is DAS-1566 (blocked
  on a live host). This ticket delivers the adapter + isolation policy + tests against the
  stub, which are fully buildable in-repo.

Distinct repo zone (`tools/sandbox/`) from the LangGraph substrate (DAS-1564) so the two
Development tickets don't collide in one wave.

## Acceptance criteria
- [ ] Per-task sandbox adapter under `tools/sandbox/` with a fail-closed isolation policy (no host mount / no network / no creds by default); real driver is an optional absent-by-default dep.
- [ ] Adapter importable + unit-testable against the stub backend with zero optional deps installed; the sandbox does not exist unless the optional backend is installed.
- [ ] Isolation-policy tests pass against the stub (host/repo/other-task/credential unreachable by default); live-host isolation smoke deferred to DAS-1566.
- [ ] Feature flag OFF by default; flag-off dispatch unchanged; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Development, part 2). FR-006 per-task sandbox adapter
(E2B/OpenHands), stub-backend buildable like the WS-A tool bridge; behind
`ws_c_langgraph_loop` OFF. Live-host execution split out to DAS-1566 (external dependency).
Security Lead consulted on the isolation boundary.

### 2026-07-24 — Backend Engineer 1
Built the `SandboxBackend` contract + host-free `LocalStubSandbox` per
`docs/design/ws-c-langgraph-loop.md` §5, under `tools/sandbox/` (new zone,
distinct from concurrent DAS-1564's `scripts/dgox/` — untouched).

**Files:**
- `tools/sandbox/contract.py` — stdlib-only `SandboxBackend` Protocol +
  `SandboxScope`/`Mount`/`ScopedSecret`/`ResourceLimits`/`SandboxHandle`/
  `ExecResult`/`SandboxEscapeError`. `ScopedSecret.to_event_fields()` is the
  Tier-M-safe projection (name/scope/ttl only, never `.value`).
- `tools/sandbox/local_stub.py` — `LocalStubSandbox`: per-task temp workdir,
  in-process deny-by-default checks; a small internal verb set
  (`read`/`write`/`exists`/`net`/`cred`/`sleep`) rather than a generic
  subprocess passthrough (a subprocess's `cwd` alone does not stop an
  absolute/`..` escape from touching the real host — the path check has to
  happen before dispatch, not rely on OS cwd confinement).
- `tools/sandbox/flag.py` — `flag_on()` reads `ws_c_langgraph_loop` from
  `config/features.yaml` (env override `DASLAB_WS_C_FLAG`), fail-safe to OFF —
  WS-A pattern.
- `tools/sandbox/requirements-sandbox.txt` — live backend deps (docker/e2b),
  commented out, absent by default; `DockerSandbox` itself is NOT built here
  (blocked DAS-1566) — this file only reserves the extension point.
- `tests/test_ws_c_sandbox_adapter.py` — 24 tests, all green.

**Four walls + escape-prevention → file : test map:**
1. **Host** — `local_stub._resolve_within()` rejects absolute paths and any
   `..` component before touching a path → `test_host_wall_rejects_dotdot_traversal`,
   `test_host_wall_rejects_absolute_path`, `test_host_wall_allows_confined_write_and_read`.
2. **Repo** — only `scope.workdir_mounts` (the task's own worktree) resolves;
   `.git`/board/other-ticket paths outside it are refused the same way →
   `test_repo_wall_rejects_escape_into_sibling_repo_area`,
   `test_repo_wall_only_own_worktree_mounted`.
3. **Other-task** — `LocalStubSandbox.open()` raises `SandboxEscapeError` if
   `scope.task_id` != the requested `task_id`; `exec()` denies a closed/foreign/
   forged handle; no mount is ever shared across `task_id`s →
   `test_other_task_wall_open_rejects_scope_task_id_mismatch`,
   `test_other_task_wall_stale_handle_denied_after_close`,
   `test_other_task_wall_foreign_token_denied`,
   `test_other_task_wall_no_shared_mount_across_tasks`.
4. **Unscoped-credential** — `scope.credentials` empty by default (ADR-0012);
   `open()` raises if a credential's `.scope` != the task; egress is
   deny-all except an explicit `egress_allowlist` →
   `test_credentials_empty_by_default`, `test_scoped_credential_grant_is_usable`,
   `test_open_rejects_credential_scoped_to_a_different_task`,
   `test_credential_value_never_lands_in_an_event` (asserts `to_event_fields()`
   carries no `value`, and the raw secret string never appears in the
   serialized event dict), `test_egress_denies_non_allowlisted_host`,
   `test_egress_deny_all_when_no_profile_configured`,
   `test_egress_allows_explicit_allowlist_match`.
5. **Escape-prevention** — every denial above returns `ExecResult(ok=False, ...)`
   with **no side effect** (no file written/leaked) →
   `test_escape_attempt_denied_result_has_no_side_effect`,
   `test_escape_via_unknown_verb_denied_fail_closed` (unknown verb ⇒ fail-closed,
   not best-effort), `test_resource_limit_denies_over_cap_sleep`,
   `test_resource_limit_denies_oversized_write`.
6. **Flag-off inert** — `flag_on()` defaults `False` reading the tracked
   `config/features.yaml` (`ws_c_langgraph_loop: false`); the adapter itself
   stays usable as a library regardless (it doesn't gate itself — the WS-C
   loop that will call it is separately flagged off) →
   `test_flag_off_by_default`, `test_flag_reads_tracked_features_file_as_off`,
   `test_flag_env_override_can_flip_on`, `test_adapter_usable_regardless_of_flag_state`.

**Verify (STAGED, `git add -A` first):**
- `ruff check tools/sandbox tests/test_ws_c_sandbox_adapter.py` → clean.
- `python3 -m pytest tests/test_ws_c_sandbox_adapter.py -q` → 24 passed.
- `python3 -m pytest -q` (full suite) → 2098 passed, 4 skipped, **1 pre-existing
  failure** (`test_check_import_ban.py::test_real_repo_clean_baseline`,
  banned `langgraph` import in `scripts/dgox/langgraph_loop.py`) — this is
  concurrent DAS-1564's zone, explicitly out of my footprint; not caused by
  and not fixed by this ticket.
- `python3 scripts/board_lint.py` → exit 0 (180 tickets, 0 violations; the
  1 WARN is pre-existing DAS-1507 body-status prose, unrelated).
- `python3 scripts/diagnostics.py` (staged) → SCORE 75/100: **Code-quality**
  and **Security** both fail solely on `scripts/dgox/langgraph_loop.py`
  (ruff findings + the banned-donor-lib check firing on its `from langgraph`
  import) — same DAS-1564 concurrent-work cause, confirmed via
  `ruff check scripts tests` isolating the hits to
  `scripts/dgox/langgraph_loop.py` / `tests/test_ws_c_langgraph_substrate.py`.
  `codeowners-complete` stayed green — `/tools/` (whole-dir CODEOWNERS entry,
  `@nabievuz`) already covers the new `tools/sandbox/` subdir, no CODEOWNERS
  regen needed for this ticket.

No `/Users/owner`/hardcoded-home literals (all paths via `tmp_path`); secret-shaped
test strings fragmented with `+` (`"sk-fake" + "-scoped" + ...`).

⛔ LOCAL-ONLY: no git push/PR/commit/remote. Footprint: `tools/sandbox/` (new) +
`tests/test_ws_c_sandbox_adapter.py` (new) + this ticket. `scripts/dgox/`, ADRs,
config, and other tickets untouched.

**Status → in_review, assignee → backend-em** (per ROUTING; never self-review).
Flagging for the orchestrator: the `test_check_import_ban` failure and the
diagnostics Code-quality/Security drop both trace to DAS-1564's concurrent
`scripts/dgox/langgraph_loop.py` work, not this ticket — route that finding to
whoever owns DAS-1564, not to this ticket's reviewer.

### 2026-07-24 — Security Engineer
**GATE-3 blocking red-team (adversarial, in-code) — DAS-1565 sandbox isolation boundary.**
Read `tools/sandbox/contract.py` + `local_stub.py` + `flag.py`, ran the 24-test suite
(green), and crafted ephemeral out-of-tree exploit probes (deleted; no permanent test
files — SC-005 escape suite stays DAS-1567's). Verdict per wall — HOLDS unless noted.

| Wall / control | Probe | Verdict |
|---|---|---|
| **Host wall** | `..`, `../../etc/passwd`, `foo/../../bar`, absolute `/etc/passwd`, absolute host-tmp path | **HOLDS** — all denied `ok=False`, `_resolve_within` rejects absolute + any `..` component before any I/O |
| **Host wall — symlink** | symlink inside mount → host dir; read+write through it | **HOLDS** — `.resolve()` follows the link, `relative_to(root)` fails → denied; **no host file created** (verified) |
| **Repo wall** | only `workdir_mounts` resolves; `.git`/board/sibling paths outside mount | **HOLDS** — paths outside the granted mount refused identically |
| **Other-task wall** | forged handle (task B's token on task A), fully fabricated token, stale handle after `close()`, `scope.task_id`≠`task_id` at `open()` | **HOLDS** — token-mismatch + closed-reg denied `ok=False`; scope mismatch raises `SandboxEscapeError`; no shared mount across task_ids |
| **Unscoped-credential wall** | cross-scoped cred at `open()`, ungranted `cred`, empty-by-default, Tier-M `to_event_fields()` | **HOLDS** — cross-scope grant raises at `open()`; empty by default; `to_event_fields()` carries only name/scope/ttl, secret **value never present** (asserted raw string absent from serialized dict) |
| **Egress** | deny-all no profile; allowlist match; `api.github.com.evil.com`; userinfo `api.github.com@evil.com` | **HOLDS** — deny-all default; both suffix-confusion and userinfo bypass tricks denied (urlparse `.hostname` + exact/`.`-suffix match) |
| **Escape-prevention** | oversized write, over-cap sleep, unknown verbs (`exec`/`subprocess`), empty argv | **HOLDS** — all `ok=False`; **no side effect** (oversized write left no file); unknown verb fail-closed; resource caps enforced before act |

**LOW residual (fail-closed, NOT an escape — hand to DAS-1567):** a path containing an
embedded NUL byte and *no* `..` (e.g. `read "foo\x00bar"`) reaches `_resolve_within`'s
`(mount_root / rel).resolve()`, which raises an **uncaught `ValueError` ("embedded null
character")** instead of returning the contract-promised `ExecResult(ok=False, exit_code=-1)`.
This is a robustness/contract-conformance defect, **not an isolation breach**: it fails
CLOSED — no host/repo path is reached, no file is read or written, and any NUL path that
*also* carries `..` is caught cleanly by the `..` guard first. Isolation HOLDS; only the
denial *shape* deviates (raise vs clean deny). Fix for DAS-1567: wrap the `_resolve_within`
body so any `OSError`/`ValueError` from path construction returns `None` (clean deny), and
add a NUL-byte case to the SC-005 escape suite.

**Note handed to DAS-1567 (residuals):** (1) the NUL-byte hardening above; (2) `cred` returns
the secret value in `ExecResult.stdout` by design (the in-sandbox task is the intended
consumer) — the Tier-M guarantee rests on callers building events via `to_event_fields()` and
never serializing raw `stdout`; a caller-side lint/assertion belongs in the SC-005 suite;
(3) the stub is explicitly NOT a kernel boundary (documented) — real host/namespace isolation
smoke is DAS-1566's live `DockerSandbox`.

**Import-ban policy note (for CTO, GATE-4 — informational, not this ticket's blocker):** the
prior `test_check_import_ban` red on this branch is now GREEN (DAS-1564's dynamic-import
resolution); the concurrent-work noise this log flagged is cleared. The unreconciled *policy*
question lives in DAS-1564's log.

**Overall: GATE-3 red-team PASSED for DAS-1565** — all four isolation walls + escape-prevention
HOLD; the single residual is fail-closed and non-escaping. Kept `in_review`, `assignee → cto`.
Cleared for CTO ratification. Edited only this ticket file (no impl/test/config change).

### 2026-07-24 — CTO
**GATE-3 (Development) CLOSED — DAS-1565 RATIFIED (`in_review` → `done`).** As GATE-3-accountable
and GATE-4 clean-room owner, I ratify the per-task sandbox adapter. Basis:

1. **Red-team PASSED (Security Engineer, blocking) — no sandbox escape.** All four walls +
   escape-prevention HOLD fail-closed: **Host** (`_resolve_within` rejects absolute paths and any
   `..` component before I/O; symlink-to-host followed by `.resolve()` then `relative_to` fails →
   denied, no host file created), **Repo** (only the task's own `workdir_mounts` resolves; `.git`/board/
   sibling paths refused), **Other-task** (forged/fabricated/stale handles denied; `scope.task_id`
   mismatch raises `SandboxEscapeError`; no shared mount across task_ids), **Unscoped-credential +
   egress** (creds empty by default, cross-scope grant raises at `open()`, `to_event_fields()` never
   carries `.value`, egress deny-all with suffix-confusion + userinfo bypass tricks both denied). Every
   denial returns `ExecResult(ok=False)` with no side effect; unknown verb fail-closed; resource caps
   enforced before act. The stub is explicitly NOT a kernel boundary (documented) — live namespace
   isolation smoke is DAS-1566.

2. **ADR-0035 import-ban reconciliation (done under DAS-1564) clears this ticket's noise.** The
   earlier `test_check_import_ban` red / diagnostics 75/100 this log flagged traced to concurrent
   DAS-1564 `scripts/dgox/` work, not `tools/sandbox/`. With the scoped GATE-4 carve-out now applied
   (`SANCTIONED_IMPORT_PATHS` in `check_import_ban.py` — langgraph allowed ONLY in `scripts/dgox/`,
   other four donor libs fully banned), that concurrent noise is fully resolved: diagnostics is
   **100/100** and the full suite green. The sandbox adapter itself carries no banned import (stdlib-only
   contract + host-free stub; the live docker/e2b driver stays the absent-by-default extra
   `tools/sandbox/requirements-sandbox.txt`).

3. **Verification (STAGED, `git add -A`):** `check_import_ban.py` exit **0**; `diagnostics.py`
   **100/100** (no-banned-donor-libs OK, codeowners-complete OK — `/tools/` already covers
   `tools/sandbox/`); `pytest tests/test_ws_c_sandbox_adapter.py` **24 passed**; full suite
   **2119 passed, 4 skipped**; `board_lint.py` exit **0** (180 tickets; lone WARN pre-existing DAS-1507).

**Residuals → DAS-1567 (Testing, now UNBLOCKED):** (1) the **LOW NUL-byte denial-shape hardening** —
an embedded-NUL path with no `..` reaches `(mount_root / rel).resolve()` and raises `ValueError`
instead of the contract's clean `ExecResult(ok=False)`; this **fails CLOSED** (no host/repo path
reached, isolation HOLDS — only the denial *shape* deviates) → wrap `_resolve_within` to return a
clean deny on any `OSError`/`ValueError` and add a NUL case to the SC-005 escape suite; (2) the
caller-side raw-`stdout` Tier-M assertion (`cred` returns the value by design for the in-sandbox
consumer; the guarantee rests on callers using `to_event_fields()`); (3) live-host `DockerSandbox`
isolation smoke is DAS-1566 (external dependency). All behind `ws_c_langgraph_loop` OFF (inert).
⛔ LOCAL-ONLY: no commit/branch/push/PR. WS-C impl (`tools/sandbox/*`) untouched this run.
</content>
