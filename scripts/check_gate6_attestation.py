#!/usr/bin/env python3
"""check_gate6_attestation.py — every APPLIED GATE-6 record is attested (R-2 / ADR-006).

CI gate: scan experiments/ and require a valid cryptographic attestation on every
record whose result.status is applied/reverted/failed. Inert (exit 0) when no
applied records exist (loop off). Uses GATE6_ATTEST_KEY for signature verification
when present; otherwise still enforces hash integrity + multi-source evidence +
distinct proposer/approver/attester so evidence cannot be fabricated.

Exit codes: 0 = all applied records attested OR none applied, 1 = invalid/missing
attestation, 2 = usage error.

Usage:
    python3 scripts/check_gate6_attestation.py [--experiments experiments]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import attest_gate6
from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

# result.status values that mean a tuning change actually went live (must attest).
APPLIED_STATES = {"applied", "reverted", "failed"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    args = ap.parse_args(argv)

    key = os.environ.get(attest_gate6.ENV_KEY)
    exp = args.experiments
    if not exp.exists():
        print(f"OK: no experiments dir ({exp}); nothing to attest.")
        return 0

    applied = 0
    problems: list[str] = []
    for f in sorted(list(exp.rglob("*.yaml")) + list(exp.rglob("*.yml"))):
        if "TEMPLATE" in f.name.upper():
            continue
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            continue
        record = data.get("gate_6_record", data) if isinstance(data, dict) else None
        if not isinstance(record, dict):
            continue
        status = str((record.get("result") or {}).get("status", "")).strip().lower()
        if status not in APPLIED_STATES:
            continue
        applied += 1
        problems.extend(f"{f.name}: {p}" for p in attest_gate6.verify_attestation(record, key))

    if problems:
        sys.stderr.write("FAIL: GATE-6 attestation (R-2 / ADR-006):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: {applied} applied GATE-6 record(s), all attested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
