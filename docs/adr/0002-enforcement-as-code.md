# ADR 0002 — Enforcement-as-code: advisory laws become CI-gating validators

**Status:** Accepted
**Date:** 2026-06-18
**Scope:** Platform / enforcement
**Relates:** [ADR 0001 — completion status protocol](0001-status-handoff-protocol.md).

## Context

DasLab governs itself with **laws** — `CLAUDE.md` QONUNlar (project placement,
AI-agent lifecycle, model allocation, persistent memory), the board rules in
`board/README.md`, the git rules in `engineering/AGENTS.md` §6, and the
gate/lifecycle policy in `governance/policies/`. Until this decision every one of these
was **advisory prose**: enforced only by an agent or operator remembering to
follow it. Prose laws drift. We saw the failure mode directly — `in_review`
self-review deadlocks and orphaned follow-ups (ADR 0001) were *written down* as
rules long before they stopped happening, because nothing **checked**.

Once the repo is self-contained (ADR 0003), the targets these laws describe —
relative links, agent-definition sync, gate ordering, board schema — all exist
in-tree on any checkout. That makes them **machine-checkable for the first
time**. The release gate is also defined as a hard number (`diagnostics.py`
must read `SCORE = 100/100`), which only means something if the dimensions
feeding that score are computed by code, not asserted by a human.

## Decision

**Turn each load-bearing law into a typed Python validator with a module
docstring, an `argparse` CLI, and a `pytest` failing-case test that proves the
validator actually catches a violation. Run the whole suite in CI as a merge
gate.**

The validators:

- `scripts/board_lint.py` — board ticket schema, status/assignee/parent rules.
- `scripts/check_links.py` — every tracked `.md` relative `[..](path)` link
  resolves; no dangling targets.
- `scripts/check_agents_sync.py` — generated agent definitions match their
  source (the `gen_subagents.py` contract).
- `scripts/check_gates.py` — AI-agent lifecycle gate ordering; no GATE-5-open →
  production.
- `scripts/diagnostics.py` — the **weighted 7-dimension 100/100 scorer**, the
  single source of truth for the release gate. `--check` / `--json`; exits
  non-zero unless the score is exactly `100`.

Two non-negotiable properties make this "enforcement-as-code" rather than "more
scripts":

1. **Every validator ships with a test that fails on a *known violation*.** A
   validator that can't demonstrate it catches a bad input is not trusted. The
   test is the proof the gate has teeth.
2. **CI runs the suite as a gate** on every PR and push to
   the default branch — `ruff` + `py_compile`, all four validators, `pytest`,
   `gitleaks` (honoring `.gitleaks.toml`), a **fresh-clone reproducibility job**
   (`git clone . /tmp/c && gen_subagents.py && git diff --exit-code`), and
   `diagnostics.py` as the final gate that must print `SCORE = 100/100`.

A law that is not encoded as a validator remains advisory **by definition** — the
intent is that load-bearing laws migrate into this suite over time, not that the
suite is frozen at five scripts.

## Consequences

**Positive:** the laws stop drifting silently — a violation fails CI instead of
surviving until someone notices. `diagnostics.py` gives the release a single,
auditable go/no-go number that the release tag gates on. The
fresh-clone job makes ADR 0003's self-containment a *tested* property, not a
claim. New contributors get fast, deterministic feedback locally (each validator
runs standalone) and in CI.

**Negative / accepted:** validators are themselves code that must be maintained
and kept honest — a false-negative validator is worse than none, which is why the
failing-case test is mandatory. The 100/100 release bar is intentionally strict:
any single failing dimension blocks the release, so the cost of a flaky check is
high and flakiness must be fixed, not tolerated. CI gains a fresh-clone job that
adds wall-clock time to every run; accepted as the price of guaranteed
reproducibility.

## Revisit triggers

- If a binding law lands in `CLAUDE.md` / `AGENTS.md` / `governance/` with no
  corresponding validator → add one (with its failing-case test) or explicitly
  record why it stays advisory.
- If `diagnostics.py` 100/100 starts being routinely overridden to ship → the
  scorer's weights or dimensions are wrong; recalibrate the scorer, do not lower
  the bar.
- If CI wall-clock from the validator + fresh-clone suite becomes a bottleneck →
  parallelize jobs or cache, but the fresh-clone repro and the final
  `diagnostics.py` gate stay mandatory.
