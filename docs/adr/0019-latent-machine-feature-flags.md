# ADR 0019 — Latent-machine feature flags: DGO-X shadow + T4/T7 governors default OFF

- **Status:** Accepted (2026-06-27; **CTO ratify — RACI 3.1 A**; additive)
- **Date:** 2026-06-27
- **Scope:** `config/features.yaml`, `scripts/feature_flags.py`; the /daslab-cycle step-5d emission gate.
- **Deciders:** **CTO (ratify);** Founder (directed the remediation).
- **Relates:** ADR-0010/0011 (DGO-X, Phase-1 shadow-only); audit finding: idle machinery burns tokens with no consumer.

## Context

DGO-X Phase-1 emits `routing_decision` shadow events with **no Phase-2 consumer** (ADR-0011),
and the T4 (cost/model-mix) + T7 (quality) governors run each wave. The audit (P10) flagged
this as **consumerless machinery that burns tokens** every wave for no current benefit.

## Decision

Introduce a single feature-flag file `config/features.yaml`, read via `scripts/feature_flags.py`
(`enabled("<flag>")`), with the consumerless machinery **defaulting OFF**:

- `dgox_emit: false` — /daslab-cycle step-5d shadow `routing_decision` emission stays off until a
  Phase-2 consumer exists. The DGO-X library + tests are unchanged; only the wave-time emission is gated.
- `t4_t7_governors: false` — the T4/T7 governor invocations during a wave stay off until they gate
  something real.

Flags fall back to the same OFF defaults if the file is absent/empty (fail-safe). Flipping a flag to
`true` re-enables its machinery once its consumer is live.

## Consequences

**Positive.** The idle DGO-X shadow + governors no longer burn tokens every wave; re-enabling is a
one-line flag flip. The library/validators stay intact (CI unaffected — CI does not run waves).
**Negative / accepted.** The wave-time gate is honoured by the /daslab-cycle orchestrator reading the
flag (soft, like other runtime directives); the `feature_flags.py` reader is the canonical API for any
code path. Turning DGO-X emission off changes wave behaviour by design (shadow events stop). **Law
check.** ADR-0002 (reader + failing-case pytest). No binding-policy text changed; ADR-0011's shadow rule
is honoured (still no dispatch effect either way).
