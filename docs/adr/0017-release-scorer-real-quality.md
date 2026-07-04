# ADR 0017 — Release scorer measures real quality (ruff gate), not just artifact completeness

- **Status:** Accepted (2026-06-27; **CTO ratify**; additive, no binding-policy text changed)
- **Date:** 2026-06-27
- **Scope:** `scripts/diagnostics.py` — the Code-quality dimension.
- **Deciders:** **CTO (ratify);** Founder (directed the remediation).
- **Relates:** ADR-0002 (enforcement-as-code); finding: scorer gameable by stub files.

## Context

`diagnostics.py`'s **Code-quality** dimension scored only **artifact completeness** —
"validator files present" + "validator tests present" — which a stub or empty file passes.
The audit flagged this as **gameable**: `SCORE` could read 100/100 over hollow files. A
release scorer must measure real quality, not file presence.

## Decision

Add a **real lint gate** to the Code-quality dimension: run `ruff check scripts tests` and
**fail the dimension on any finding**. Ruff is already the repo's linter (`ci.yml`), installed
in CI and locally, and is not gameable by a stub (a stub that lints dirty fails). The
completeness checks remain as a floor.

**Deferred (needs a dependency):** a `pytest --cov --cov-fail-under=<floor>` gate — `pytest-cov`
is not in `requirements-dev.txt`, and adding a dependency + network install unattended was out of
scope. Tracked as a follow-up. The pytest **suite itself already gates separately in CI** (706
tests), so functional regressions are caught; this ADR closes the *gameable-completeness* hole.

## Consequences

**Positive.** The scorer now reflects real lint quality; a stub-only change that lints dirty drops
the dimension. **Negative / accepted.** Ruff must be on PATH where diagnostics runs (it is, in CI
+ local); if absent the check **degrades to a skip** rather than failing the build. The coverage
floor is a follow-up (needs `pytest-cov`). **Law check.** ADR-0002 (gate is code + currently
green); no binding-policy text changed.
