# ADR 0022 — Semantic versioning & release policy

**Status:** Accepted
**Date:** 2026-06-29

## Context

DasLab is published as a single clean, history-free public baseline. With the
repository public, consumers need a predictable, machine-checkable way to track
what changed between releases. The engine already enforces its laws as code
([ADR 0002](0002-enforcement-as-code.md)), so the versioning contract should be
enforced the same way rather than left to convention.

## Decision

**Adopt Semantic Versioning (`MAJOR.MINOR.PATCH`).**

- **`VERSION`** holds the current version string and is the machine-readable
  source of truth.
- **`CHANGELOG.md`** records every release in [Keep a Changelog](https://keepachangelog.com/)
  format.
- **Each release** is an annotated git tag `vX.Y.Z` on `main` plus a matching
  GitHub Release.
- **The release gate enforces it:** the git-hygiene dimension of
  [`scripts/diagnostics.py`](../../scripts/diagnostics.py) fails unless `VERSION`
  is present and well-formed (`\d+\.\d+\.\d+`) and `CHANGELOG.md` exists — so a
  release cannot ship without both.
- **Increments:** MAJOR for an incompatible engine/contract change, MINOR for a
  backward-compatible capability, PATCH for a fix.

The first public release under this policy is **1.0.0**.

## Consequences

**Positive:** consumers get a stable version contract; the release gate makes the
`VERSION` + `CHANGELOG` discipline non-optional rather than advisory.

**Negative / accepted:** every release now requires a `VERSION` bump, a
`CHANGELOG` entry, and an annotated tag — the deliberate cost of a disciplined
public cadence.
