---
id: DAS-1450
title: Result-cache (P6) + fix check_cache_prefix _MIN_TOKENS threshold
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1442]
zone: scripts/cache
created: 2026-07-03
updated: 2026-07-03
---

## Description

Two related caching improvements to the DasLab engine, both GATE-3 (Development)
work under the ORGANISM program (spec-of-record:
`docs/research/ORGANISM-PROGRAM-PLAN.md`, program plank **P6 — result-cache**).

**(a) Result-cache for repeated dispatches.** Validator and research dispatches
in a wave are frequently identical across tickets and re-runs (same prompt, same
input digests). Today they re-execute every time, burning tokens and latency.
Add a content-addressed result cache: a hit short-circuits the dispatch and
returns the stored result instead of re-running it.

- **Cache key:** `sha256(prompt + input-digests)` — the prompt text plus a
  stable digest of every input the dispatch consumes, so any input change yields
  a new key.
- **Store:** one JSON file per entry at
  `board/.cache/<sha256(prompt+input-digests)>.json`. The `board/.cache/`
  directory is engine-internal wave state and must be gitignored (same posture
  as `board/.wave-log`, `board/.events.jsonl`, `board/.arcrift-outbox.jsonl` —
  see `.gitignore`). Create the directory on first write.
- **TTL:** each entry carries a written-at timestamp and a TTL; an entry older
  than its TTL is a miss (treated as absent / eligible for overwrite). Pick a
  conservative default TTL and make it configurable.
- **Observability:** a cache hit is logged as a `cached:true` event (append to
  the existing event store `board/.events.jsonl` via `scripts/dgox/events.py`,
  consistent with how `routing_decision` events are emitted in
  `.claude/skills/daslab-cycle/SKILL.md` step 5d). A miss/execute path is
  unchanged.

  **Extend, don't reinvent:** reuse the existing `scripts/dgox/events.py`
  `EventStore` for logging and follow the hashing/JSON conventions already in
  `scripts/`. New code lives under the `scripts/cache/` zone (this ticket's
  `zone:`). Do not couple the cache into `check_cache_prefix.py` — that script is
  about the *prompt-cache prefix invariant* (a different concern) and is only
  touched here for part (b).

**(b) Fix `check_cache_prefix.py` `_MIN_TOKENS`.** The minimum-length invariant
(check "c") asserts the stable-prefix region is at least `_MIN_TOKENS` tokens,
labelled "Opus 4.8 minimum cacheable prefix." The current value —
`_MIN_TOKENS = 1024` (`scripts/check_cache_prefix.py:83`) — is **wrong for Opus
4.8**. Per the claude-api reference (`shared/prompt-caching.md`, "Minimum
cacheable prefix" table):

> Opus 4.8, Opus 4.7, Opus 4.6, Opus 4.5, Haiku 4.5 → **4096 tokens**
> Fable 5, Sonnet 4.6, Haiku 3.5, Haiku 3 → 2048 tokens
> Sonnet 4.5, Sonnet 4.1, Sonnet 4, Sonnet 3.7 → 1024 tokens

`1024` is Sonnet-4.5-era; the correct **Opus 4.8** minimum is **4096 tokens**. A
breakpoint placed after fewer than 4096 tokens of stable content silently emits
a cache miss on every Opus 4.8 call — exactly the failure the check exists to
prevent — so `1024` under-enforces and lets a too-short prefix pass. Set
`_MIN_TOKENS = 4096` (or make it per-model with 4096 as the Opus-4.8 default).

**Verify before hardcoding:** load the `claude-api` skill and confirm the
current Opus 4.8 minimum against `shared/prompt-caching.md` at implementation
time; cite that source in the ticket log and in a code comment. Do not trust
this ticket's number blindly if the reference has since changed.

**Scope guard (do NOT do here):** the stable-prefix docs prose in
`.claude/skills/daslab-cycle/SKILL.md` ("Minimum cacheable prefix … **1024
tokens**", ~line 381–384) is also stale, but re-targeting the check from the
SKILL.md prose to the real preamble is a **deferred ADR-0006 amendment**
(approved §9 default) — out of scope for this ticket. Fix only the `_MIN_TOKENS`
constant and its tests. If the SKILL.md prose edit is required to keep the check
exit-0, coordinate it as the minimal necessary change and note it; otherwise
leave the ADR-0006 re-target for its own ticket.

**Key existing files touched:**
- `scripts/check_cache_prefix.py` — `_MIN_TOKENS` constant at line 83; the
  minimum-length check in `run_checks()` (~line 208–210, 267–272); docstring
  reference at line 17–20.
- `scripts/dgox/events.py` — `EventStore` reused for `cached:true` event logging.
- `board/.events.jsonl` — event sink (gitignored).
- `board/.cache/` — new cache directory (gitignored; add to `.gitignore`).
- `.claude/skills/daslab-cycle/SKILL.md` — read-only context for event-emission
  conventions; do NOT edit its prose (deferred, see scope guard).
- New code: `scripts/cache/` (this ticket's zone).

## Acceptance criteria

- [ ] Result-cache implemented: entries stored at
      `board/.cache/<sha256(prompt+input-digests)>.json` with a written-at
      timestamp and a configurable TTL; expired entries treated as a miss.
- [ ] `board/.cache/` is gitignored (added to `.gitignore`).
- [ ] A cache hit short-circuits the repeated validator/research dispatch
      (returns the stored result without re-executing) and logs a `cached:true`
      event to `board/.events.jsonl` via `scripts/dgox/events.py`.
- [ ] `_MIN_TOKENS` in `scripts/check_cache_prefix.py` corrected to the verified
      Opus 4.8 minimum (**4096 tokens** per `claude-api` skill
      `shared/prompt-caching.md`), or made per-model with 4096 as the Opus-4.8
      default; the claude-api source is cited in a code comment and the ticket log.
- [ ] The stale docstring/label in `check_cache_prefix.py` that says "1024" is
      updated to match the corrected value.
- [ ] `python3 scripts/check_cache_prefix.py` still exits 0 (the stable prefix
      remains long enough to satisfy the corrected, higher threshold; if it does
      not, that is a real finding — report it rather than lowering the threshold).
- [ ] Tests: unit tests cover (1) cache write → hit → TTL-expiry → miss, and
      (2) the `check_cache_prefix.py` length gate at the corrected threshold
      (passes at ≥ threshold, fails below it). All tests green.
- [ ] SKILL.md prose is NOT edited to re-target the check (deferred ADR-0006
      amendment); frontmatter carries no `project:` field (org-engine ticket,
      board_lint R9).

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend Engineer 1
Implemented both deliverables on branch `feat/das-1450-result-cache` (commit f853a19, LOCAL — not pushed; worktree /Users/owner/DasLab/.claude/worktrees/DAS-1450).

**(a) Result-cache (ORGANISM P6):**
- Created `scripts/cache/__init__.py` and `scripts/cache/result_cache.py`.
- `ResultCache` class: `get(prompt, input_digests, *, ticket_id, run_id)` → `dict|None`; `put(prompt, input_digests, result, *, ttl_seconds=86400)`.
- Cache key = `sha256(prompt + "".join(sorted(input_digests)))`.
- Store = `board/.cache/<sha256>.json` with `{key, result, written_at, ttl_seconds}` schema.
- Expiry: `(now - written_at).total_seconds() > ttl_seconds` → miss.
- Hit logging: `build_cache_hit` event via `EventStore` when `ticket_id` is provided; logging is best-effort (never breaks the dispatch path).
- Added `board/.cache/` to `.gitignore`.
- 20 unit tests in `tests/test_result_cache.py` covering write→hit, TTL-expiry→miss, corrupt file→miss, event logging, schema, key determinism/order-independence.

**(b) `_MIN_TOKENS` fix:**
- Source verified: `claude-api` skill `shared/prompt-caching.md` — Opus 4.8, 4.7, 4.6, 4.5 and Haiku 4.5 → **4096 tokens** minimum cacheable prefix. (1024 was Sonnet-4.5-era, under-enforced on Opus 4.8.)
- Changed `_MIN_TOKENS = 1024` → `_MIN_TOKENS = 4096` with citation comment in `scripts/check_cache_prefix.py:83`.
- Updated docstring (line 17) from "1024" to "4096".
- `python3 scripts/check_cache_prefix.py` exits 0: stable prefix measures ~5250 tokens, well above the corrected 4096 threshold.
- Updated boundary tests in `tests/test_check_cache_prefix.py` (boundary body now 16384 chars = 4096 tokens; `_LONG_CLEAN_PREFIX` now 16528 chars).

**Supporting changes:**
- `scripts/dgox/events.py`: added `"cache_hit"` to `_VALID_EVENT_TYPES`; added `build_cache_hit()` builder.
- `tests/test_dgox_phase1_shadow.py`: excluded `scripts/cache/` from dispatch-decision dgox-import scan (the cache module is an observability consumer of dgox, not a decision script — same rationale as the existing `scripts/dgox/` exclusion).

**Verification gates (all green):**
- `python3 scripts/diagnostics.py` → 100/100
- `python3 scripts/board_lint.py` → 0 errors (17 tickets)
- `python3 scripts/check_cache_prefix.py` → exit 0 (~5250 tokens ≥ 4096)
- `pytest` → 743 passed, 1 skipped, 0 failed

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: green diagnostics(100/100)/board_lint/pytest(810) + combined-merge verification (pure-code review collapsed into orchestrator+validator verification per local-only strategy). Result-cache module + _MIN_TOKENS 1024->4096 (claude-api verified). cache_hit event union-merged into events.py; merged to local main.
