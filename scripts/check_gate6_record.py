#!/usr/bin/env python3
"""
check_gate6_record.py — DasLab evidence validator.

Enforces the evidence-gated core IN CODE: no optimization/tuning change is
allowed without a complete GATE-6 record. Closes "silent tuning" (report L5).

How it works:
  - Reads the DGO-X event store (board/.events.jsonl). A missing (gitignored)
    store means no tuning has happened yet -> clean.
  - A tuning event is any line whose change_type is an enumerated tuning action
    OR whose event_type is the `gate6_tuning` marker. A gate6_tuning event
    with a missing/unknown change_type is itself a violation (no silent bypass).
  - For each tuning event, requires a complete GATE-6 record in experiments/
    whose `gate_6_record.id` matches the event's `gate6_id`, with all required
    fields, the proposed_change audit anchors (config_diff_hash + blast_radius),
    and `guardrails.max_quality_drop == 0`.

Usage:
    python scripts/check_gate6_record.py [--events board/.events.jsonl] [--experiments experiments]

Exit 0 = clean. Exit 1 = missing/incomplete record(s). Exit 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

# change_types that REQUIRE a GATE-6 record before applying.
TUNING_CHANGE_TYPES = {
    "tune_concurrency",
    "tune_cadence",
    "tune_model_tier",
    "refill_frontier",
    "auto_approval_rule",
    "capability_promotion",
    "validator_update",
}
# The event-store marker for an optimization/tuning event (experiments/README.md).
TUNING_EVENT_TYPE = "gate6_tuning"

REQUIRED_FIELDS = [
    "hypothesis",
    "baseline_metrics",
    "proposed_change",
    "guardrails",
    "evidence",
    "approval",
    "rollout",
    "result",
]
REQUIRED_GUARDRAILS = ["max_quality_drop", "rollback_condition"]
APPLIED_STATES = {"applied", "reverted", "failed"}


def load_records(experiments: Path) -> tuple[dict[str, dict], set[str]]:
    """Load GATE-6 records keyed by id; also return the set of DUPLICATE ids."""
    records: dict[str, dict] = {}
    duplicates: set[str] = set()
    if not experiments.exists():
        return records, duplicates
    for f in sorted(list(experiments.rglob("*.yaml")) + list(experiments.rglob("*.yml"))):
        if "TEMPLATE" in f.name.upper():
            continue  # GATE6-TEMPLATE.yaml is a blank shape, not a live record
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            continue
        rec = data.get("gate_6_record", data) if isinstance(data, dict) else None
        if isinstance(rec, dict) and rec.get("id"):
            rid = str(rec["id"])
            if rid in records:
                duplicates.add(rid)
            records[rid] = rec
    return records, duplicates


def _as_dict(value) -> dict:
    """Return value if it is a dict, else {} — callers add a 'must be a mapping' problem."""
    return value if isinstance(value, dict) else {}


def record_complete(rec: dict) -> list[str]:
    """Return list of problems; empty == complete. Never raises on a malformed shape."""
    problems = []
    for field in REQUIRED_FIELDS:
        if not rec.get(field):
            problems.append(f"missing '{field}'")

    # proposed_change must be a MAPPING carrying the audit anchors — a one-line
    # string collapses the block and hides config_diff_hash / blast_radius.
    pc = rec.get("proposed_change")
    if pc and not isinstance(pc, dict):
        problems.append("proposed_change must be a mapping with config_diff_hash + blast_radius")
    elif isinstance(pc, dict):
        cdh = str(pc.get("config_diff_hash", "")).strip()
        if not cdh or cdh.upper().endswith("REPLACE"):
            problems.append("proposed_change.config_diff_hash missing or placeholder")
        if not pc.get("blast_radius"):
            problems.append("proposed_change.blast_radius missing")

    guard_raw = rec.get("guardrails")
    if guard_raw and not isinstance(guard_raw, dict):
        problems.append("guardrails must be a mapping")
    guard = _as_dict(guard_raw)
    for g in REQUIRED_GUARDRAILS:
        if g not in guard:
            problems.append(f"guardrails missing '{g}'")
    # quality is a hard constraint: max_quality_drop must be exactly 0 (reject bool).
    mqd = guard.get("max_quality_drop", None)
    if isinstance(mqd, bool) or mqd not in (0, 0.0):
        problems.append("guardrails.max_quality_drop must be 0 (T7 hard constraint)")

    # An actually-applied change needs an approver and at least one evidence entry.
    status = str(_as_dict(rec.get("result")).get("status", "")).strip().lower()
    if status in APPLIED_STATES:
        if not _as_dict(rec.get("approval")).get("approved_by"):
            problems.append(f"result '{status}' requires approval.approved_by")
        ev = _as_dict(rec.get("evidence"))
        if not any(ev.get(k) for k in ("trace_ids", "ci_runs", "review_ids", "experiment_ids")):
            problems.append(f"result '{status}' requires at least one evidence entry")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="board/.events.jsonl")
    ap.add_argument("--experiments", default="experiments")
    args = ap.parse_args(argv)

    events_path = Path(args.events)
    if not events_path.exists():
        # board/.events.jsonl is gitignored runtime state (ADR-006). A missing
        # store means no tuning has happened yet (loop off) -> nothing to gate
        # -> clean. This keeps CI green on a fresh checkout while still failing
        # the moment a real tuning event lacks a complete GATE-6 record.
        print(f"OK: no event store yet ({events_path}); no tuning events to gate.")
        return 0

    records, duplicate_ids = load_records(Path(args.experiments))

    violations: list[str] = []
    tuning_seen = 0
    malformed = 0
    for raw in events_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        change_type = ev.get("change_type")
        is_tuning = change_type in TUNING_CHANGE_TYPES or ev.get("event_type") == TUNING_EVENT_TYPE
        if not is_tuning:
            continue
        tuning_seen += 1
        evid = ev.get("id", "?")
        if change_type not in TUNING_CHANGE_TYPES:
            violations.append(f"event {evid}: tuning event with missing/unknown change_type {change_type!r}")
            continue
        gid = ev.get("gate6_id")
        if not gid:
            violations.append(f"event {evid} ({change_type}): no gate6_id")
            continue
        if str(gid) in duplicate_ids:
            violations.append(f"event {evid}: GATE-6 record id '{gid}' is duplicated in experiments/")
            continue
        rec = records.get(str(gid))
        if rec is None:
            violations.append(f"event {evid}: GATE-6 record '{gid}' not found")
            continue
        for prob in record_complete(rec):
            violations.append(f"GATE-6 {gid}: {prob}")

    if malformed:
        sys.stderr.write(f"WARNING: {malformed} malformed (non-JSON) line(s) skipped in {events_path}\n")

    if violations:
        sys.stderr.write("FAIL: GATE-6 evidence violations:\n")
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        sys.stderr.write(f"\n{len(violations)} issue(s) across {tuning_seen} tuning event(s).\n")
        return 1

    print(f"OK: {tuning_seen} tuning events, all have complete GATE-6 records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
