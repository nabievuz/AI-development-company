#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import check_never_auto_approve as nap
import gen_org
from _paths import ROOT

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


QONUN5_IMMUTABLE = frozenset({
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
})

_MATCHER_SELECTORS = ("ticket_type", "stage", "labels", "paths")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_org_drift.py — generate-and-diff drift gate for the Org Schema (R-12 / ADR-009).')
    ap.add_argument("--schema", type=Path, default=gen_org.SCHEMA_PATH)
    ap.add_argument("--generated", type=Path, default=gen_org.GENERATED_PATH)
    ap.add_argument("--risk-taxonomy", type=Path, default=ROOT / "config" / "risk_taxonomy.yaml")
    args = ap.parse_args(argv)

    if not args.schema.is_file():
        sys.stderr.write(f"ERROR: Org Schema not found: {args.schema}\n")
        return 2
    schema = gen_org.load_schema(args.schema)
    expected = gen_org.render(schema)

    problems: list[str] = []


    schema_never = {str(x).strip().lower() for x in (schema.get("never_auto_approve") or [])}
    missing = QONUN5_IMMUTABLE - schema_never
    if missing:
        problems.append(
            f"Org Schema dropped immutable QONUN-5 categories {sorted(missing)} — "
            "these may never be removed (only added to)"
        )
    try:
        committed = args.generated.read_text(encoding="utf-8")
    except OSError:
        committed = None
    if committed is None:
        problems.append(f"{args.generated.name} is missing — run scripts/gen_org.py")
    elif committed != expected:
        problems.append(f"{args.generated.name} drifted from the schema — run scripts/gen_org.py (never hand-edit it)")


    rt = None
    if not args.risk_taxonomy.is_file():
        problems.append(
            f"{args.risk_taxonomy.name} is missing — never_auto_approve consistency unverifiable (fail closed)"
        )
    else:
        try:
            loaded = yaml.safe_load(args.risk_taxonomy.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            problems.append(f"{args.risk_taxonomy.name} is unreadable or invalid YAML: {exc}")
        else:
            if loaded is None:
                rt = {}
            elif isinstance(loaded, dict):
                rt = loaded
            else:
                problems.append(f"{args.risk_taxonomy.name} is not a YAML mapping (got {type(loaded).__name__})")
    if isinstance(rt, dict):
        if set(rt.get("never_auto_approve", []) or []) != set(schema.get("never_auto_approve", []) or []):
            problems.append("config/risk_taxonomy.yaml never_auto_approve differs from the Org Schema SSOT")
        matchers = rt.get("matchers", {}) or {}
        for cat in sorted(QONUN5_IMMUTABLE):
            m = matchers.get(cat)


            if not isinstance(m, dict) or not any(nap._clean_tokens(m.get(k)) for k in _MATCHER_SELECTORS):
                problems.append(
                    f"config/risk_taxonomy.yaml matcher for immutable category '{cat}' is missing or "
                    "binds no tickets (empty/blank/scalar/malformed selector protects nothing)"
                )

    if problems:
        sys.stderr.write("FAIL: Org Schema drift (R-12 / ADR-009):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1

    print("OK: org constants in sync with the schema; never_auto_approve consistent across schema + config.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
