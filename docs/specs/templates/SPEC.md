<!--
  SPEC.md — per-epic executable intent (ADR-0015, spec-kit Phase 2).
  WRITE ONLY for a goal that decomposes to >= ~15 tickets OR any AI-agent goal.
  Smaller goals skip this file. WHAT/WHY only — no tech stack (that lives in the
  AADL Stage-2 design docs). Copy to docs/specs/<NNN>-<slug>/SPEC.md (org-engine)
  or projects/<slug>/specs/<NNN>-<feat>/SPEC.md (project). Keep ids unique.
  Use [NEEDS CLARIFICATION: <question>] inline (max 3) for unresolved scope (ADR-0014).
-->
# SPEC <NNN> — <epic / feature name>

- **Goal:** <kebab-goal-slug>
- **Owner:** <role>
- **Status:** draft | reviewed | implementing | done

## User Scenarios

> Given / When / Then, ordered by priority (P1 first). Behavioural, not technical.

- **P1 —** Given <context>, when <action>, then <observable outcome>.
- **P2 —** Given <context>, when <action>, then <observable outcome>.

## Functional Requirements

> One testable requirement per line. `FR-NNN` ids, unique. Child tickets bind to
> these via `implements: [FR-001, ...]`.

- **FR-001** — The system MUST <requirement>.
- **FR-002** — The system MUST <requirement>.

## Success Criteria

> Measurable. `SC-NNN` ids, unique.

- **SC-001** — <metric / threshold that proves the spec is met>.
