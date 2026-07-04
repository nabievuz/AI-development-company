"""Deterministic verifier — frontend-eng-1 / prop-contract-validation."""
from __future__ import annotations

import json
from pathlib import Path


def _expected_verdict(props: dict, contract_props: dict) -> str:
    known = set(contract_props.keys())
    # Missing required prop.
    for name, spec in contract_props.items():
        if spec.get("required") and name not in props:
            return "invalid"
    # Unknown prop not declared in the contract.
    for name in props:
        if name not in known:
            return "invalid"
    # Type mismatch on a declared prop that IS present.
    for name, value in props.items():
        spec = contract_props[name]
        expected_type = spec.get("type")
        if expected_type == "boolean" and not isinstance(value, bool):
            return "invalid"
        if expected_type == "string" and not isinstance(value, str):
            return "invalid"
    return "valid"


def verify(submission: dict, fixtures: Path) -> float:
    contract = json.loads(
        (fixtures / "component_contract.json").read_text(encoding="utf-8")
    )["props"]
    call_sites = json.loads(
        (fixtures / "call_sites.json").read_text(encoding="utf-8")
    )["call_sites"]

    verdicts = submission.get("verdicts")
    if not isinstance(verdicts, dict) or not call_sites:
        return 0.0

    correct = 0
    for site in call_sites:
        expected = _expected_verdict(site["props"], contract)
        got = verdicts.get(site["id"])
        if isinstance(got, str) and got.strip().lower() == expected:
            correct += 1
    return correct / len(call_sites)
