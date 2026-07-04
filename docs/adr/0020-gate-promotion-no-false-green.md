# ADR 0020 — Gate promotion: warn-only → enforce only with data discipline; unmeasured is SKIPPED, not green

- **Status:** Accepted (2026-06-27; **CTO ratify — RACI 3.1 A**; high-risk → adversarially tested; additive, no binding-policy text changed)
- **Date:** 2026-06-27
- **Scope:** `scripts/gate_promotion.py` (+ ci.yml informational step); optional `metrics/gate_metrics.json` snapshot.
- **Deciders:** **CTO (ratify);** Founder (directed the remediation).
- **Relates:** `loop_controller.py` (loop-mode promotion — the sibling axis); `metrics/registry.yaml`; the audit's second-order finding (gates flip to enforce with no data discipline → false-green).

## Context

The audit's most insidious finding (second-order): a metric gate with **no data** can read as a
green pass (e.g. `check_model_mix` returns 0 — "unmeasured, inert" — which an aggregate reads as
green). Adding more gates without a **data-discipline promotion rule** strengthens *false confidence*.
A gate must EARN enforcement; until then it must be visibly **unmeasured**, not a silent pass.

## Decision

A pure, adversarially-tested classifier (`gate_promotion.classify`) puts every metric gate
(`metrics/registry.yaml`) into one honest state:

- **skipped** — `samples <= 0`: no data. **Never counts as a pass.** This is the load-bearing rule.
- **warn** — measuring: some data but `samples < MIN_SAMPLES`, or the safety metrics (false-positive
  rate, override rate) are missing / out of band. Never enforced.
- **enforce** — earned: `samples >= MIN_SAMPLES` (30) **AND** `fp_rate <= 10%` **AND**
  `override_rate <= 5%`.

Like `loop_controller.py`, the controller **evaluates and reports — it never auto-applies**
(promoting a gate to enforce is governance, QONUN-5). The "not gameable" property is enforced by
`tests/test_gate_promotion.py`: an adversarial grid proves **no** input reaches `enforce` without all
three criteria, and `samples == 0` is **always** `skipped`. Per-gate measurements come from an optional
`metrics/gate_metrics.json` snapshot; absent it (today), every gate is honestly `skipped`.

## Consequences

**Positive.** Unmeasured gates can no longer masquerade as green; a gate enforces only on real,
disciplined data; the invariant is a test, not a hope. **Negative / accepted.** Until `gate_metrics.json`
is populated from real waves, all gates show `skipped` — the honest current state (the audit's point).
Wiring each metric validator to *consume* this status (exit "skipped" vs pass) is a follow-up; the
controller + the policy + the invariant land now. **Law check.** ADR-0002 (module + adversarial pytest).
No auto-apply (QONUN-5). No binding-policy text changed.
