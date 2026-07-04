# ADR 0003 — Self-locating repository root (no hardcoded paths)

- **Status:** Accepted
- **Date:** 2026-06-18
- **Deciders:** CTO, Backend EM, SRE Lead

## Context

The repository must boot on any machine, any user, and any clone path with zero
edits (LAW A / LAW B). Historically scripts and generated agent shims embedded
an absolute path (`/Users/<name>/projects/daslab`), which crashed a fresh clone
(`gen_subagents.py` → `FileNotFoundError`) and made the org non-portable.

## Decision

The repository root is **resolved at runtime, never written down**.

- A single helper, `scripts/_paths.py`, resolves the root in priority order:
  1. the `DASLAB_ROOT` environment variable (explicit override for CI/containers);
  2. `git rev-parse --show-toplevel` (the enclosing work-tree);
  3. the directory two levels up from the helper (file-relative fallback).
- Scripts import `ROOT` from `_paths`; none defines its own absolute root.
- `gen_subagents.py` emits repo-root-relative wording in every agent shim
  ("Work from the repository root — your current working directory …") and only
  relative cross-file references.
- `.mcp.json` uses `${HOME}` for the ArcRift backend and a relative `projects`
  path — no machine-specific literal.

## Enforcement

`scripts/check_no_hardcoded_paths.py` scans every tracked file for a
`/Users/<name>` or `/home/<name>` literal and fails CI on any hit
(`board/tickets/` and the scanners themselves are allowlisted — they quote the
pattern as data). It is wired into `.github/workflows/ci.yml` and the
`diagnostics.py` Portability dimension. A hermetic pytest suite proves detection.

## Consequences

- A fresh clone at any path boots and self-scores 100/100; the `DASLAB_ROOT`
  override supports sandboxed/containerized runs.
- New scripts must `from _paths import ROOT` rather than computing their own root.
