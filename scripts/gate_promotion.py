#!/usr/bin/env python3
"""gate_promotion.py — warn-only → enforce promotion controller (ADR-0020, remediation P1b).

A gate must EARN enforcement with data discipline. This module classifies each metric gate
(from `metrics/registry.yaml`) into one of three honest states, so an unmeasured gate is never
reported as a false green:

  - **skipped** — no data (samples == 0). The gate is NOT measured; it does NOT count as a pass.
  - **warn**    — measuring: some data, but not yet enough samples, or the safety metrics
                  (false-positive rate, override rate) are missing or out of band → never enforced.
  - **enforce** — earned: samples >= MIN_SAMPLES AND fp_rate <= MAX_FP_RATE AND
                  override_rate <= MAX_OVERRIDE_RATE.

Like `loop_controller.py`, this EVALUATES and REPORTS — it never auto-applies a promotion
(QONUN-5: enforcing a gate is governance). The classification is a pure, adversarially-tested
function: there is NO input for which `samples == 0` yields anything but `skipped`, and NO input
that reaches `enforce` without meeting ALL three criteria.

Usage:
    python scripts/gate_promotion.py            # status table for the registry gates

Exit 0 always (a reporter; it never fails the build — that is the gate's own job once enforced).
"""
from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "metrics" / "registry.yaml"
GATE_METRICS = REPO_ROOT / "metrics" / "gate_metrics.json"  # optional measured snapshot

# Promotion criteria (ADR-0020). A gate enforces only when it clears ALL of these.
MIN_SAMPLES = 30
MAX_FP_RATE = 0.10
MAX_OVERRIDE_RATE = 0.05

SKIPPED, WARN, ENFORCE = "skipped", "warn", "enforce"


def classify(samples: int, fp_rate: float | None, override_rate: float | None) -> str:
    """Pure classifier. Invariants (adversarially tested):

    * samples <= 0 (or invalid) -> SKIPPED, always — an unmeasured gate is never a green.
    * ENFORCE requires samples >= MIN_SAMPLES AND both rates present AND within band.
    * anything measured-but-not-yet-qualified -> WARN (never silently enforced).
    """
    if not isinstance(samples, int) or samples <= 0:
        return SKIPPED
    if samples < MIN_SAMPLES:
        return WARN
    if fp_rate is None or override_rate is None:
        return WARN
    if fp_rate < 0 or override_rate < 0:
        return WARN
    if fp_rate <= MAX_FP_RATE and override_rate <= MAX_OVERRIDE_RATE:
        return ENFORCE
    return WARN


def _registry_gates() -> list[str]:
    if yaml is None or not REGISTRY.exists():
        return []
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    return sorted((data.get("metrics") or {}).keys())


def _measured() -> dict[str, dict]:
    """Optional per-gate metrics snapshot {gate: {samples, fp_rate, override_rate}}; {} if absent."""
    if not GATE_METRICS.exists():
        return {}
    import json
    try:
        data = json.loads(GATE_METRICS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def statuses() -> dict[str, str]:
    measured = _measured()
    out: dict[str, str] = {}
    for gate in _registry_gates():
        m = measured.get(gate, {})
        out[gate] = classify(int(m.get("samples", 0) or 0), m.get("fp_rate"), m.get("override_rate"))
    return out


def main(argv: list[str] | None = None) -> int:
    st = statuses()
    if not st:
        print("gate_promotion: no metric registry found — nothing to classify.")
        return 0
    counts = {SKIPPED: 0, WARN: 0, ENFORCE: 0}
    print("Gate promotion status (ADR-0020) — skipped is NOT a pass:")
    for gate, status in st.items():
        counts[status] += 1
        print(f"  {status.upper():8} {gate}")
    print(f"\nskipped {counts[SKIPPED]} · warn {counts[WARN]} · enforce {counts[ENFORCE]} "
          f"(criteria: >= {MIN_SAMPLES} samples, fp <= {MAX_FP_RATE:.0%}, override <= {MAX_OVERRIDE_RATE:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
