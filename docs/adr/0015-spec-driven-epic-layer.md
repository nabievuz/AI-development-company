# ADR 0015 — Phase 2: size-gated per-epic SPEC.md + FR/SC traceability (spec-kit graft)

- **Status:** Accepted (2026-06-26, Founder-directed debt paydown; **CTO ratify — RACI 3.1 A**; additive, no binding-policy text changed)
- **Date:** 2026-06-26
- **Scope:** Planning layer — a new `docs/specs/templates/SPEC.md`, `scripts/check_spec_consistency.py`
  (+`diagnostics.py`/`ci.yml` registration), `.claude/skills/daslab-plan/SKILL.md`. Optional
  `spec:` / `implements:` ticket frontmatter.
- **Deciders:** **CTO (ratify);** Founder (directed the build).
- **Relates:** ADR-0014 (clarify gate — this is its deferred **Phase 2**); ADR-0002 (enforcement-as-code);
  ADR-0004 (project-agnostic engine); QONUN-1 (Project Placement).

## Context

ADR-0014 grafted GitHub Spec Kit's clarify gate and deferred the per-feature **executable spec**
(spec-kit's `spec.md` + `FR-NNN`/`SC-NNN` traceability). The spec-kit diagnostic flagged this layer as
**over-engineering if made mandatory** ("waterfall reborn", ~10× overhead) and **largely redundant for
design-driven projects** that already carry a behavioural spec (e.g. `.pen` screens 1:1 with tickets).

So this ADR adds the capability **size-gated and opt-in**, not mandatory: the value is a real
executable-intent artifact for large/AI-agent goals, without taxing the common small goal.

## Decision

1. **SPEC.md is per-EPIC and size-gated.** A `SPEC.md` is written **only** for a goal that decomposes
   to **≥ ~15 tickets** OR **any AI-agent goal** (AADL applies). Smaller goals keep today's direct
   queue→ticket path. The gate is a `/daslab-plan`-time judgement, not a CI gate — CI never forces a SPEC.

2. **Template** (`docs/specs/templates/SPEC.md`), tech-stack-free: `## User Scenarios` (Given/When/Then
   per priority), `## Functional Requirements` (`FR-001…`), `## Success Criteria` (`SC-001…`, measurable).
   The *technical* plan stays in the AADL Stage-2 design docs — SPEC.md is WHAT/WHY only.

3. **Location (QONUN-1):** org-engine specs at `docs/specs/<NNN>-<slug>/SPEC.md`; project specs at
   `projects/<slug>/specs/<NNN>-<feat>/SPEC.md` (gitignored, local). No repo-root `specs/` proliferation.

4. **Ticket linkage (optional fields):** a child ticket may carry `spec: <NNN-slug>` and
   `implements: [FR-001, SC-002]` to bind it to its spec.

5. **Enforcement (`scripts/check_spec_consistency.py`, ADR-0002):**
   - **Structure:** every `SPEC.md` that exists has the three sections, ≥1 `FR-NNN`, and unique FR/SC ids.
   - **No dangling refs:** any ticket whose `implements:` names an id must reference an id that EXISTS in
     the `spec:` it declares — catches typos / drift between spec and tickets.
   - **CI-safe / structural limit:** passes when no `SPEC.md` exists (the state today and on a fresh CI
     runner). Project specs under gitignored `projects/` are validated only locally, like ADR-0014's
     `check_approved_goal_queue.py`. The *reverse* "every FR covered by a ticket" check is deliberately
     **left to the planner/reviewer**, not a hard gate — it would false-fail a freshly-authored spec.

## Consequences

**Positive.** A large/AI-agent goal gets a reviewable executable-intent artifact with FR/SC traceability;
dangling refs are caught in CI; the engine stays project-agnostic (ADR-0004 — generic examples only).
Dormant and zero-cost until a qualifying goal opts in.

**Negative / accepted.** One more validator on the 100/100 gate. The size-gate is a human judgement
(not code-enforced) — intentional, to avoid the mandatory-pipeline over-engineering the diagnostic warned
of. Redundant for `.pen`-spec projects — those simply don't write a SPEC.md.

**Law check.** QONUN-1 (specs live under `docs/specs/` or `projects/<slug>/`, never repo root). ADR-0004
(no project name in the engine; template uses generic ids). ADR-0002 (validator + failing-case pytest +
diagnostics registration). No binding-policy text changed.

## Enforcement / acceptance

- `docs/specs/templates/SPEC.md` + `scripts/check_spec_consistency.py` + failing-case pytest.
- Registered in `diagnostics.py` (consistency) and `ci.yml`; `SCORE = 100/100` preserved.
- `/daslab-plan` size-gate note. README ADR index row on ratification.
