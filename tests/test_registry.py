#!/usr/bin/env python3
"""tests/test_registry.py — metrics/registry.yaml is a valid T1-T7 SSOT (R-1 / ADR-002).

Enforces: the registry parses, every metric carries the contract fields, the
targets match PRD-001 §1, and the P1 validators it names exist on disk. The
T2-T6 + anti-gaming validators are P2 — the registry must NAME them, but they
are intentionally not required to exist yet (no over-building in P1).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "metrics" / "registry.yaml"

EXPECTED_METRICS = [
    "T1_busy_fraction",
    "T2_idle_wave_rate",
    "T3_effective_concurrency",
    "T4_cost_model_mix",
    "T5_recovery_reliability",
    "T6_review_efficiency",
    "T7_quality",
]

# PRD-001 §1 targets (numeric/contractual goal per metric).
EXPECTED_TARGETS = {
    "T1_busy_fraction": 0.60,
    "T2_idle_wave_rate": 0.15,
    "T3_effective_concurrency": 6,
    "T4_cost_model_mix": 0.25,
    "T5_recovery_reliability": 0.99,
    "T6_review_efficiency": "downward trend",
    "T7_quality": "no degradation vs baseline",
}

CONTRACT_FIELDS = ("definition", "formula", "source", "target", "guardrail", "validator")


def _load() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def test_registry_parses():
    data = _load()
    assert isinstance(data, dict)
    assert isinstance(data.get("metrics"), dict)


def test_all_seven_metrics_present():
    assert list(_load()["metrics"].keys()) == EXPECTED_METRICS


def test_every_metric_has_contract_fields():
    for name, spec in _load()["metrics"].items():
        for field in CONTRACT_FIELDS:
            assert field in spec, f"{name} missing contract field {field!r}"


def test_every_metric_names_a_scripts_validator():
    for name, spec in _load()["metrics"].items():
        v = spec["validator"]
        assert isinstance(v, str) and v.startswith("scripts/") and v.endswith(".py"), (
            f"{name} validator must be a scripts/*.py path; got {v!r}"
        )


def test_targets_match_prd_section_1():
    metrics = _load()["metrics"]
    for name, want in EXPECTED_TARGETS.items():
        assert metrics[name]["target"] == want, (
            f"{name} target {metrics[name]['target']!r} != PRD §1 {want!r}"
        )


def test_all_validators_exist_on_disk():
    # After P2 every metric's validator + the anti-gaming validator is built.
    data = _load()
    for name, spec in data["metrics"].items():
        v = REPO_ROOT / spec["validator"]
        assert v.is_file(), f"validator {v} for {name} must exist"
    av = REPO_ROOT / data["anti_gaming"]["validator"]
    assert av.is_file(), f"anti-gaming validator {av} must exist"


def test_anti_gaming_rule_present():
    data = _load()
    assert data.get("anti_gaming", {}).get("rule")
    assert data["anti_gaming"].get("validator", "").startswith("scripts/")


def test_t7_is_hard_constraint():
    guardrail = _load()["metrics"]["T7_quality"]["guardrail"].upper()
    assert "HARD" in guardrail or "BLOCKER" in guardrail
