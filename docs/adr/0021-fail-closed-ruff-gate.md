# ADR 0021 — The lint gate is fail-closed: an unmeasured lint never scores 100

**Status:** Accepted
**Date:** 2026-06-27

## Context

[ADR 0002](0002-enforcement-as-code.md) makes the release gate
([`scripts/diagnostics.py`](../../scripts/diagnostics.py)) the single source of
truth, and [ADR 0017](0017-release-scorer-real-quality.md) added a real lint
check — `ruff check scripts tests` — to the Code-quality dimension so a hollow
stub file can no longer earn full marks.

That lint check had a fail-**open** hole: when the `ruff` executable was absent it
caught `FileNotFoundError` and reported the check as **passed** ("degraded"). On a
machine or CI image without `ruff` installed, the Code-quality dimension still
earned its full weight and the scorer could print `SCORE = 100/100` even though
no lint had actually run. An enforcement gate that silently passes when it cannot
measure is the false-green failure mode [ADR 0020](0020-gate-promotion-no-false-green.md)
exists to prevent — applied here to the lint gate itself.

## Decision

**Make the lint gate fail-closed.** If `ruff` cannot run (not installed), the
`ruff-clean` check **fails**, so the Code-quality dimension does not earn its
weight and the total cannot reach 100/100. The gate passes only when `ruff`
actually runs and reports zero findings. `ruff` is a required tool of the engine
(it is wired into [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml));
treating its absence as a pass contradicted that requirement.

A failing-case test in [`tests/test_diagnostics.py`](../../tests/test_diagnostics.py)
proves the property: with `ruff` simulated absent, the Code-quality dimension
scores 0 (so the total is below 100).

## Consequences

**Positive:** the 100/100 release gate now means lint genuinely ran and was
clean — it can no longer be reached by an environment that simply lacks the
linter. The gate's guarantee matches its claim.

**Negative / accepted:** running the gate now hard-requires `ruff` on the PATH.
That is intentional and already true in CI; local operators install it from
`requirements-dev.txt`. The cost of a missing tool is a visible failure, not a
silent pass.
