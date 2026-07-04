# ADR 0018 — Role-overlay contract: every overlay carries Mission / Scope / Definition of Done / Escalation

- **Status:** Accepted (2026-06-27; CTO ratify; additive, no binding-policy text changed)
- **Date:** 2026-06-27
- **Scope:** `<dept>/agents/<role>/AGENTS.md` overlays; `scripts/check_overlay_sections.py` (+ ci.yml).
- **Deciders:** **CTO (ratify);** Founder (directed the remediation).
- **Relates:** ADR-0002 (enforcement-as-code); RACI 2.5 (overlay approval).

## Context

Most of the 32 role overlays carried only `## Identity` + `## When to escalate` — they shipped
without saying what the role exists to do, what it owns, or when its work is complete.
A role definition that is a stub is not a definition.

## Decision

Every role overlay MUST carry four contract sections, each non-trivial (>= 40 chars of body):

- `## Mission` — what the role exists to do.
- `## Scope` — what it owns and what it does NOT own.
- `## Definition of Done` — when its work is complete.
- `## Escalation` — when/how to escalate (`## When to escalate` is accepted).

Enforced by `scripts/check_overlay_sections.py` (ADR-0002). **Rollout:** ships **warn-only**, the
32 overlays are filled (role-specific Mission/Scope/DoD derived from the model-allocation rationale
+ dept charter + RACI), then the gate flips to **--strict** (fail-closed) so a hollow overlay can
never ship again.

## Consequences

**Positive.** Every shipped role is actually defined; the generator-filled baselines are consistent
and role-specific, and the strict gate prevents regression to stubs. **Negative / accepted.** The
generated Mission/Scope/DoD are solid baselines, not hand-bespoke prose — per-role refinement by the
owning CXO (RACI 2.5) is a welcome follow-up; the gate only enforces presence + substance, not style.
**Law check.** ADR-0002 (validator + failing-case pytest + ci wiring). RACI 2.5 (CXO accountable for
overlays — CTO ratifies this contract). No binding-policy text changed.
