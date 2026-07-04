---
id: DAS-1448
title: Merge-policies (append-only / owner-exclusive / aggregate) + reducers (P4)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1446]
zone: scripts/board_lint
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What & why.** Today the `/daslab-cycle` orchestrator enforces a hard
correctness guard: *never two tickets touching the same repo zone in one wave*
(`.claude/skills/daslab-cycle/SKILL.md`, step 3 — the "Correctness guard
(keep)" using the declared `zone:` field per ADR-0016). That guard trades
throughput for merge-conflict safety: the second same-zone ticket always waits
for the next wave. For zones whose parallel outputs are *mechanically
mergeable* (append-only logs, owner-partitioned files, aggregatable counters),
this is a needless brake — the ORGANISM program-plan (WS1 "pulse") calls for a
declarative escape hatch that lets two same-zone tickets run in one wave
**when, and only when, the zone opts in with a merge policy** and a reducer
that deterministically combines the parallel outputs.

This ticket adds that opt-in. It introduces an **optional** ticket frontmatter
field `merge_policy:` on a per-declared-zone basis, a small library of Python
**reducers** that merge parallel same-zone outputs, and extends
`board_lint.py` so the correctness guard is relaxed for a same-zone *pair*
**only** when the zone declares a permitting policy. With no policy declared,
the default behavior is unchanged: a same-zone pair is still forbidden
(fail-closed).

**Embedded context — the exact mechanics that already exist:**

- `scripts/board_lint.py` parses YAML frontmatter with a lightweight regex
  (`_FM_RE` / `_KV_RE`, no external YAML dep) into a flat `dict[str, str]`.
  Every value is a string; list-valued fields (like `depends_on: [DAS-1446]`)
  are captured as the raw string `"[DAS-1446]"`. `REQUIRED_FIELDS` lists the
  nine mandatory keys; rules R1–R9 are applied in `lint_tickets()`. **R9** is
  the platform-only guard: a ticket on `board/tickets/` must NOT carry a
  `project:` field — so this new field must NOT be `project:` and must not
  reintroduce a project concept. `board_lint` currently does **not** do any
  same-zone / same-wave reasoning at all — that logic lives only in the
  `/daslab-cycle` skill prose. This ticket is where the *lint layer* gains
  awareness of `merge_policy` and validates it.
- `scripts/check_dependency_graph.py` already reads the OPTIONAL `zone:` field
  (`_fm_field`, a separate tolerant line-based reader) and flags a
  present-but-empty `zone:` as a defect. It does NOT read `merge_policy`. The
  `zone:` field is the anchor that `merge_policy` attaches to.
- `.claude/skills/daslab-cycle/SKILL.md` step 3 is the runtime consumer of
  `zone:`. Its correctness guard is prose, enforced at dispatch time by the
  orchestrator, and (per the file's own note) guarded in CI "by a skill-token
  test, not here." This ticket does **not** rewrite the orchestrator's live
  dispatch behavior — it delivers the *validation + reducer library* that a
  later WS1 ticket wires into dispatch. Keep the SKILL prose truthful: if you
  reference the new policy, add it as an explicit opt-in that widens the guard,
  never as a change to the default.

**Extend-vs-new posture.** EXTEND the existing scripts; do not fork them.
- Extend `scripts/board_lint.py` in place: add `merge_policy` parsing +
  validation as a new rule (e.g. R10), keeping the existing regex parser
  working. The `depends_on: [DAS-1446]` style shows list values arrive as raw
  strings — if `merge_policy` ever needs multi-value or per-zone-map form,
  add a **tolerant reader** helper rather than swapping the whole parser.
- Add the reducers as a NEW, self-contained, dependency-free module under
  `scripts/` (e.g. `scripts/merge_reducers.py`) so it is unit-testable in
  isolation and importable by both the lint layer and a future dispatch hook.
- Add tests alongside the existing test suite (mirror where
  `board_lint` / `check_dependency_graph` are tested — search
  `tests/` for `board_lint` and place the new tests in the same location).

**Key existing files this touches:**
- `scripts/board_lint.py` — extend the frontmatter validation (new rule +
  optional tolerant reader).
- `scripts/merge_reducers.py` — NEW module: the three reducers.
- `scripts/check_dependency_graph.py` — READ-ONLY reference for the tolerant
  `_fm_field` reader pattern and the existing `zone:` handling; do not change
  its behavior unless a `merge_policy`-adjacent defect must be flagged there.
- `.claude/skills/daslab-cycle/SKILL.md` — step 3 correctness-guard prose;
  update ONLY to document the opt-in widening, keeping the default forbidden.
- `tests/` — new unit tests for the parser/validator and the reducers.

**Field grammar (implement exactly):** `merge_policy:` is optional. When
present, its value is one of:
- `append-only` — parallel outputs are concatenated in a deterministic
  (e.g. lexical-by-ticket-id) order; no line is dropped or reordered within a
  contributor's block.
- `owner-exclusive` — each parallel output owns a disjoint sub-region
  (e.g. distinct files / keys); the reducer verifies disjointness and unions
  them, FAILING if two outputs touch the same owned unit.
- `aggregate:<reducer>` — a named aggregation (e.g. `aggregate:sum`,
  `aggregate:union`); the reducer combines values by the named operation.
  An unknown `<reducer>` name is a validation error.

A `merge_policy` present with an empty or unrecognized value is a defect
(mirror the `check_dependency_graph.py` present-but-empty `zone:` treatment).
A `merge_policy` declared WITHOUT a `zone:` is a defect (the policy has no
anchor to attach to).

**AADL stage: GATE-3 Development.** This is org-engine (DasLab-platform) work.
Per QONUN Project Placement Law + board_lint R9, the frontmatter carries **no**
`project:` field.

## Acceptance criteria

- [ ] `merge_policy` frontmatter field is PARSED by `board_lint.py` (regex
      parser still works for all existing tickets) and VALIDATED: allowed forms
      are `append-only`, `owner-exclusive`, `aggregate:<reducer>`; empty /
      unrecognized value is a violation; `merge_policy` without a `zone:` is a
      violation.
- [ ] A new dependency-free `scripts/merge_reducers.py` module implements three
      reducers — `append-only`, `owner-exclusive`, and `aggregate:<reducer>`
      (at least `sum` and `union`) — each deterministically merging a list of
      parallel same-zone outputs, with `owner-exclusive` FAILING on overlap and
      `aggregate` FAILING on an unknown reducer name.
- [ ] `board_lint.py` permits a same-zone ticket **pair** in the schema ONLY
      when that zone declares a permitting `merge_policy`; the correctness
      guard's default (no policy) still forbids a same-zone pair.
- [ ] A merge test runs each reducer on representative parallel outputs and
      asserts the merged result is correct and deterministic (stable across
      input ordering where the policy promises order-independence; stable
      concat order for `append-only`).
- [ ] Default path proven: a same-zone pair with NO `merge_policy` declared is
      still rejected (fail-closed) — regression test asserts this.
- [ ] `python3 scripts/board_lint.py` and
      `python3 scripts/check_dependency_graph.py` both still exit 0 on the
      current board (no false positives introduced); new tests pass.
- [ ] `.claude/skills/daslab-cycle/SKILL.md` step-3 guard prose documents the
      opt-in widening (same-zone pair allowed only under a declared policy) and
      never weakens the no-policy default; the SKILL cache-prefix invariant is
      not disturbed (change lives in the mutable body, not the stable prefix).
- [ ] No `project:` field is added anywhere (board_lint R9 stays green); no new
      file is created outside `scripts/` and `tests/`.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend EM
Built P4 (merge-policies + reducers). Local-only, branch `feat/das-1448-merge-policies`.

**New module `scripts/merge_reducers.py`** (dependency-free, stdlib only):
- Grammar authority (single source of truth): `KNOWN_AGGREGATORS={sum,union}`,
  `parse_policy`, `is_valid_policy`, `MergeError`.
- Three reducers over `(ticket_id, payload)` contributions:
  - `append_only` — concat blocks in lexical ticket-id order; within-block order
    preserved; input-order-independent.
  - `owner_exclusive` — disjoint union of owned units (mapping or iterable);
    RAISES `MergeError` on overlap; order-independent.
  - `aggregate(reducer_name)` — `sum` (numeric) / `union` (set); RAISES on an
    unknown reducer name.
  - `merge(policy, contribs)` dispatch.

**`scripts/board_lint.py` extended (EXTEND-in-place, regex parser untouched):**
- Imports `is_valid_policy` from `merge_reducers` (no grammar duplication).
- Tolerant readers `_zone_of` / `_merge_policy_of` (strip quotes/whitespace),
  mirroring `check_dependency_graph._fm_field`.
- **R10** (per-ticket grammar, additive): validates `merge_policy` when present —
  allowed forms only; empty/unrecognized = violation; `merge_policy` without a
  `zone:` anchor = violation. Tickets without the field lint exactly as before.
- **Wave correctness guard (SAFETY, exported, fail-closed):**
  `same_zone_pair_allowed(fm_a, fm_b)` and `zone_wave_conflicts(wave)`. These are
  the schema-level decision helpers `/daslab-cycle` (and tests) call over a
  *candidate wave*. **Default = FORBID:** a same-zone pair is rejected unless
  BOTH tickets declare the SAME valid, permitting `merge_policy`. No policy /
  mismatched / empty / invalid → forbidden. Deliberately NOT run over the whole
  board in `main()` — the board legitimately holds many same-zone tickets across
  different waves (e.g. four `daslab-cycle` tickets today), so a whole-board rule
  would false-positive; this matches `check_dependency_graph`'s own note that the
  same-zone/wave rule is a runtime property, not repo state.

**`.claude/skills/daslab-cycle/SKILL.md`** step-3 guard prose: added an
"Opt-in widening (default stays closed)" note pointing at the exported predicate;
no volatile tokens in the stable prefix; bumped `CACHE_PREFIX_VERSION`
v11-fanout-deferred → v12-merge-policies and re-fixed `scripts/.cache_prefix_baseline`
(same protocol DAS-1449 used for its step-3 prose change).

**`check_dependency_graph.py`** left unchanged (read-only reference; empty-`zone:`
already covered; `merge_policy`-without-zone is covered by board_lint R10).

**Tests:** `tests/test_merge_reducers.py` (16 — each reducer, determinism /
input-order-independence, owner-exclusive overlap fail, aggregate unknown-reducer
fail, grammar accept/reject, `merge` dispatch). `tests/test_board_lint.py` +13
(R10 grammar + zone-anchor; wave-guard: same-zone pair FORBIDDEN without policy,
PERMITTED with a shared valid policy, forbidden on mismatch/invalid,
`zone_wave_conflicts` accept/reject/ignore-singletons).

**VERIFY (all green):** pytest 839 passed / 1 skipped; `board_lint` 0;
`check_dependency_graph` clean; `check_never_auto_approve` clean;
`diagnostics` 100/100; `check_cache_prefix` OK. ruff clean.

**Default-still-forbids guarantee:** `same_zone_pair_allowed` returns `False`
for any same-zone pair lacking a shared valid permitting policy — proven by
`test_same_zone_pair_forbidden_without_policy` and
`test_zone_wave_conflicts_rejects_unpermitted_pair`.

→ `status: in_review`, assignee `cto` (ROUTING; never self-review).
SAFETY FLAG for reviewer: this widens the wave-correctness guard — scrutinize the
fail-closed default and the exported predicate. Note: no WS1 dispatch ticket yet
wires `same_zone_pair_allowed`/`zone_wave_conflicts` into live dispatch (SKILL
step 3 remains prose); that wiring is a follow-up per the ticket's own scoping.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 945 pass + all validators green + combined-merge verification (events.py/SKILL union resolved). merge_reducers.py + board_lint R10 + same_zone_pair_allowed (fail-closed default proven). SAFETY: widens wave-correctness guard but INERT (not yet wired into live dispatch) — follow-up ticket must wire the predicate.
