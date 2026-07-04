# ADR 0004 — Project-agnostic engine (one factory, any goal)

- **Status:** Accepted
- **Date:** 2026-06-18
- **Deciders:** CPO, CTO, CEO

## Context

DasLab grew up building one product (qaqnuz), and product-specific assumptions
risked leaking into the engine. The engine must be a **general-purpose software
factory** (LAW C): given any goal, it plans, builds, tests, reviews, secures,
documents, and ships an enterprise-quality deliverable through the six AADL gates
— for any project, not one.

## Decision

- **Projects are isolated.** All project material — code and its board tickets —
  lives under `projects/<slug>/` (its own git, gitignored, QONUN 1). The retired
  qaqnuz product and its 242 tickets were moved there; the engine's own release
  history is archived under `board/archive/`.
- **The public board starts empty.** A fresh clone has only a generic demo
  (`DAS-0001`) and `docs/EXAMPLE-RUN.md`. `/daslab-plan "<goal>"` seeds a new
  `projects/<slug>/` with the AADL skeleton and stage-gated tickets;
  `/daslab-cycle` executes them through the gates.
- **The engine is project-neutral.** No project-specific name appears in the
  engine's load-bearing files (generators, validators, skills, agent shims,
  routing, dept charters/overlays, umbrella specs).
- **Quality is a documented bar** (`governance/policies/quality-bar.md`) and
  performance is **measured** (`scripts/board_metrics.py`).

## Enforcement

`scripts/check_project_isolation.py` fails CI if a project name (default:
`qaqnuz`) appears in any engine file; historical/work-record areas
(`board/archive/`, `docs/`, `projects/`) and the scanner itself are out of scope.
It is wired into `.github/workflows/ci.yml` and the `diagnostics.py` Architecture
dimension.

## Consequences

- A new operator clones, bootstraps, and runs `/daslab-plan "<their goal>"` —
  DasLab asks Founder discovery questions, researches the project, creates
  `projects/<slug>/APPROVED-GOAL-QUEUE.md`, waits for approval, then serves any
  project at the enterprise quality bar.
- Adding a new long-lived product means a new `projects/<slug>/`, never edits to
  the engine; if a project name must be banned from the engine, add it to the
  `check_project_isolation.py` denylist.
