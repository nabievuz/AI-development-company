#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "metrics" / "registry.yaml"
GATE_METRICS = REPO_ROOT / "metrics" / "gate_metrics.json"


MIN_SAMPLES = 30
MAX_FP_RATE = 0.10
MAX_OVERRIDE_RATE = 0.05

SKIPPED, WARN, ENFORCE = "skipped", "warn", "enforce"


def classify(samples: int, fp_rate: float | None, override_rate: float | None) -> str:
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


EXIT_OK = 0
EXIT_NO_DATA = 3


def main(argv: list[str] | None = None) -> int:
    st = statuses()
    if not st:
        print(
            "gate_promotion: NO DATA — no metric registry found; zero gates were "
            "classified and nothing is promoted.",
            file=sys.stderr,
        )
        return EXIT_NO_DATA
    counts = {SKIPPED: 0, WARN: 0, ENFORCE: 0}
    print("Gate promotion status (ADR-0020) — skipped is NOT a pass:")
    for gate, status in st.items():
        counts[status] += 1
        print(f"  {status.upper():8} {gate}")
    print(f"\nskipped {counts[SKIPPED]} · warn {counts[WARN]} · enforce {counts[ENFORCE]} "
          f"(criteria: >= {MIN_SAMPLES} samples, fp <= {MAX_FP_RATE:.0%}, override <= {MAX_OVERRIDE_RATE:.0%})")
    if counts[SKIPPED] == len(st):
        print(
            f"gate_promotion: NO DATA — all {len(st)} gate(s) are SKIPPED for want of "
            "samples; no gate is measured, so none is enforced.",
            file=sys.stderr,
        )
        return EXIT_NO_DATA
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
