#!/usr/bin/env python3
"""adaptive_taxonomy.py — Adaptive Risk Taxonomy.

Self-calibrates the SOFT risk tiers (low / medium / high) from approval + GATE-6
outcome history: a class consistently approved without incident may be proposed
for relaxation; one frequently reverted / incident is proposed for escalation.

HARD CONSTRAINTS (non-negotiable, enforced in propose_recalibration):
  - it NEVER touches the hard-coded never-auto-approve list (QONUN-5, immutable),
  - it NEVER recalibrates 'critical',
  - it NEVER auto-applies — every proposal is emitted as a GATE-6 record DRAFT
    (max_quality_drop 0, human approval required), and the loop stays OFF.
Inert when there is not enough history (trigger-gated).

Usage:
    python3 scripts/adaptive_taxonomy.py [--history board/.events.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

MIN_SAMPLES = 10          # need enough evidence before proposing anything
ESCALATE_RATE = 0.20      # >= 20% reverted/incident -> propose escalate
RELAX_RATE = 0.95         # >= 95% clean -> propose relax
IMMUTABLE_CLASSES = frozenset({"critical"})   # never recalibrated
# The QONUN-5 never-auto-approve FLOOR — HARD-CODED, never read from config/schema.
# The generated Org-Schema SSOT may ADD categories, so we UNION the
# generated set onto this floor. The floor can never shrink (even if the generated
# module is shortened or absent), so this module can never propose relaxing one of the
# seven QONUN-5 categories regardless of import state, casing, or a tampered schema.
_QONUN5_FLOOR = frozenset({
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
})
try:
    from _org_generated import NEVER_AUTO_APPROVE as _GENERATED_NEVER
    IMMUTABLE_NEVER_AUTO = _QONUN5_FLOOR | frozenset(str(x).strip().lower() for x in _GENERATED_NEVER)
except ImportError:
    IMMUTABLE_NEVER_AUTO = _QONUN5_FLOOR
BAD_OUTCOMES = {"reverted", "incident", "failed"}


def _norm(value) -> str:
    return str(value).strip().lower()


def _aggregate(history: list[dict]) -> dict:
    stats: dict[str, dict] = {}
    for h in history:
        cls = h.get("risk_class")
        if not cls:
            continue
        s = stats.setdefault(_norm(cls), {"clean": 0, "bad": 0, "total": 0})
        s["total"] += 1
        if _norm(h.get("outcome", "")) in BAD_OUTCOMES:
            s["bad"] += 1
        else:
            s["clean"] += 1
    return stats


def propose_recalibration(history: list[dict], taxonomy: dict) -> list[dict]:
    """Soft-tier recalibration proposals. The immutability guard is enforced HERE:
    'critical' and EVERY never-auto-approve category (hard-coded + config, normalized)
    are skipped no matter the history, casing, or a missing/empty/null config list."""
    raw = taxonomy.get("never_auto_approve")
    config_never = {_norm(x) for x in raw} if isinstance(raw, list) else set()
    protected = IMMUTABLE_NEVER_AUTO | IMMUTABLE_CLASSES | config_never
    proposals: list[dict] = []
    for cls, s in _aggregate(history).items():
        if cls in protected:
            continue  # IMMUTABLE — never propose recalibrating these
        if s["total"] < MIN_SAMPLES:
            continue
        bad_rate = s["bad"] / s["total"]
        clean_rate = s["clean"] / s["total"]
        if bad_rate >= ESCALATE_RATE:
            proposals.append({"class": cls, "action": "escalate",
                              "reason": f"{bad_rate:.0%} reverted/incident over {s['total']} decisions"})
        elif clean_rate >= RELAX_RATE and cls != "low":
            proposals.append({"class": cls, "action": "relax",
                              "reason": f"{clean_rate:.0%} clean over {s['total']} decisions"})
    return proposals


def to_gate6_draft(proposal: dict, created_at: str) -> dict:
    """Wrap a proposal as a GATE-6 record DRAFT — evidence-gated, never auto-applied."""
    return {
        "gate_6_record": {
            "id": f"GATE6-ADAPTIVE-{proposal['class']}-{proposal['action']}",
            "created_at": created_at,
            "proposed_by": "adaptive_taxonomy",
            "change_type": "auto_approval_rule",
            "hypothesis": f"Recalibrate soft risk tier '{proposal['class']}': {proposal['action']} ({proposal['reason']}).",
            "baseline_metrics": {"note": "from approval/GATE-6 outcome history"},
            "proposed_change": {"description": f"{proposal['action']} class {proposal['class']}",
                                "config_diff_hash": "sha256:PENDING", "blast_radius": "medium"},
            "guardrails": {"max_quality_drop": 0, "rollback_condition": "revert on any incident"},
            "evidence": {"trace_ids": [], "ci_runs": [], "review_ids": [], "experiment_ids": []},
            "approval": {"required_role": "cxo", "approved_by": "", "approved_at": ""},
            "rollout": {"mode": "shadow"},
            "result": {"status": "deferred"},
        }
    }


def _load_history(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--history", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "risk_taxonomy.yaml")
    args = ap.parse_args(argv)

    if not args.config.is_file():
        sys.stderr.write(f"ERROR: risk taxonomy not found: {args.config}\n")
        return 2
    try:
        taxonomy = yaml.safe_load(args.config.read_text())
    except yaml.YAMLError as exc:
        sys.stderr.write(f"ERROR: invalid risk taxonomy: {exc}\n")
        return 2
    taxonomy = taxonomy or {}

    proposals = propose_recalibration(_load_history(args.history), taxonomy)
    if not proposals:
        print("Adaptive taxonomy: no recalibration proposed — insufficient history (P5 is trigger-gated).")
        return 0
    print(f"Adaptive taxonomy: {len(proposals)} soft-tier proposal(s) — GATE-6 drafts, human approval required:")
    for p in proposals:
        print(f"  - {p['action']} '{p['class']}': {p['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
