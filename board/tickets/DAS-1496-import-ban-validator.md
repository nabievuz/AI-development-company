---
id: DAS-1496
title: Donor import-ban validator
status: done
assignee: security-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1491
goal: organism-ws7-gateway
zone: import-ban
created: 2026-07-03
updated: 2026-07-04
---

## Description

**What / why.** ORGANISM WS7 GATEWAY establishes a clean-room boundary (GATE-4,
§2.3): the DasLab engine must NOT depend on or import any of the five banned
"donor" agent-framework libraries. Today nothing mechanically enforces this — a
future dependency bump or a copy-pasted snippet could silently reintroduce a
banned lib and violate the clean-room provenance. This ticket adds a CI
validator that fails the build the moment any banned donor library appears in a
dependency manifest or as an import in `scripts/`.

**Banned donor libraries (5):**
1. `langgraph`
2. `agent-framework` (microsoft)
3. `crewai`
4. `agency-swarm`
5. `superagi`

**Embedded context.** The current baseline was verified clean earlier in the
ORGANISM program, so this validator runs green against `main` on day one — it is
a fail-closed guardrail against regressions, not a remediation. It matches both
distribution/package names (in manifests) and import module names (in Python
source), since some libs ship under a package name that differs from their
import path (e.g. `agent-framework` distribution vs. its import module).

**Extend vs. new.** NEW standalone validator: `scripts/check_import_ban.py`.
Follow the shape of the other `scripts/check_*.py` validators so it composes
cleanly. Do NOT fold this into an existing validator — the WS7 gate wants it as
its own named check. Then EXTEND `scripts/diagnostics.py` by wiring the new
validator into its required-validator list so a banned lib drops the 100/100
score and fails CI.

**Key files + paths.**
- `scripts/check_import_ban.py` — NEW validator (scanner + CLI, exit non-zero on any hit).
- `scripts/diagnostics.py` — EXTEND: register `check_import_ban` in the required-validator list.
- `requirements.in`, `requirements.txt`, `requirements-dev.txt` — dependency manifests scanned.
- `scripts/` — Python source tree scanned for banned imports.
- Test file alongside the existing validator tests (mirror their location/naming) — clean-baseline-passes + synthetic-banned-fails cases.

## Acceptance criteria

- [x] `check_import_ban.py` fails (non-zero exit) on any of the 5 donor libs appearing in `requirements*.txt` / dependency manifests OR as an import in `scripts/`
- [x] Validator matches both package/distribution names in manifests and import module names in Python source
- [x] `check_import_ban` wired into `diagnostics.py`'s required-validator list (banned lib → diagnostics fails, not 100/100)
- [x] Test: clean baseline passes; a synthetic banned entry (manifest and/or import) fails
- [x] Full test suite: 0 failed
- [x] Diagnostics: 100/100 on the clean baseline

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS7 GATEWAY decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.
READ: requirements.in, requirements.txt, requirements-dev.txt, scripts/diagnostics.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-4 (cross-cutting, §2.3 clean-room). Add scripts/check_import_ban.py that FAILS CI if any of the 5 banned donor libraries — langgraph, agent-framework (microsoft), crewai, agency-swarm, superagi — appears in requirements*.txt or any dependency manifest (or as an import in scripts/). Run against the CURRENT baseline (verified clean earlier). Wire it into diagnostics.py's required-validator list. Tests: clean baseline passes; a synthetic banned entry fails.
Acceptance: [ ] check_import_ban.py fails on any of the 5 donor libs in manifests/imports; [ ] wired into diagnostics required list; [ ] clean baseline passes, synthetic banned fails (test); [ ] full suite 0 failed, diagnostics 100/100.
Constraints: org-engine ticket (this WS7 machinery), NO project: field.

### 2026-07-03 — Security Engineer
Implemented GATE-4 import-ban validator.

**Created** `scripts/check_import_ban.py`:
- Scans `requirements*.txt` and `requirements*.in` for banned distribution names
- Scans `scripts/*.py` for banned Python import statements
- Word-boundary-safe matching via Python `re` with `\b` (not git grep -E)
- PEP 508 name normalisation: hyphens == underscores, case-insensitive
- Supports `--root` for hermetic testing
- Exits 0 (clean) or 1 (violation) or 2 (usage error)

**Extended** `scripts/diagnostics.py`:
- `check_code_quality`: added `check_import_ban.py` to `required_scripts` and `test_check_import_ban.py` to `required_tests` (presence gate)
- `check_security`: added `no-banned-donor-libs` check that runs `check_import_ban.py` as a subprocess; a violation drops the security dimension (10 pts) and the 100/100 score

**Created** `tests/test_check_import_ban.py`: 19 tests covering clean baseline, all 5 banned libs in manifests, hyphen/underscore normalisation, case-insensitivity, comment-line skipping, bare/from/submodule import forms, word-boundary correctness, and CLI exit codes.

**Verification**:
- `python3 scripts/check_import_ban.py` → OK (clean baseline)
- `python3 -m pytest -q` → 1553 passed, 1 skipped, 0 failed
- `python3 scripts/diagnostics.py` → SCORE = 100/100
- `python3 scripts/board_lint.py` → 0 violations
- `ruff check scripts tests` → All checks passed

Committed to `feat/das-1496-import-ban` (local only, per GIT STRICT LOCAL-ONLY directive).
Branch ready for review by security-lead.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite green; check_import_ban.py (word-boundary-safe, 19 tests) wired into diagnostics; clean baseline (§2.3 — no donor imports).

### 2026-07-04 — Security Engineer (FIX-C audit remediation)
Self-audit found two scope holes in the original DAS-1496 implementation:

**Hole 1 — scan_imports was top-level only.** `scripts/cache/`, `scripts/cost/`,
`scripts/dgox/` (8 Python files) and the entire `tests/` tree were not scanned.
Fix: replaced `scripts_dir.glob("*.py")` with `rglob("*.py")` and added a second
scan root (`tests/`) so both trees are covered recursively.

**Hole 2 — scan_manifests missed pyproject.toml.** A banned lib declared under
`[project.dependencies]` (PEP 621) or `[tool.poetry.dependencies]` (Poetry) would
have been invisible to CI. Fix: added `_scan_pyproject()` using stdlib `tomllib`
(Python 3.11+) to extract and check both dependency tables.

Added 10 new tests (29 total): nested-dir-import caught; all-5-banned-via-subdirs
caught; tests/-dir import caught; nested-clean passes; pyproject PEP-621 hit;
pyproject Poetry hit; all-5-via-pyproject; clean-pyproject passes; hyphen/underscore
normalised in pyproject; real-repo pyproject clean.

Verification (worktree feat/fix-c-importban-scope):
- `python3 scripts/check_import_ban.py` → OK (clean baseline, now covers subdirs + pyproject)
- `python3 -m pytest -q` → 1616 passed, 1 skipped, 0 failed
- `python3 scripts/diagnostics.py` → SCORE = 100/100
- `python3 scripts/board_lint.py` → 0 violations
- `ruff check scripts tests` → All checks passed

Commit 918b1db on branch `feat/fix-c-importban-scope` (LOCAL only — GIT STRICT LOCAL-ONLY directive).
Status set to `in_review`; assignee remains `security-lead`.
