#!/usr/bin/env python3
"""check_memory_governance.py — ArcRift memory governance gate (R-5 / ADR-005).

Validates a memory store against config/memory_governance.yaml: every memory
carries the migrated schema (trust_score + created_at), each trust_score is
consistent with its provenance tier, and a memory that declares a contradiction
is quarantined (excluded from recall). Reports recallable / excluded / duplicate
counts and the memory-health score. Inert (exit 0) when no store exists — the live
store is the external ArcRift; board/.arcrift-outbox.jsonl is gitignored runtime.

Exit codes: 0 = governed/clean OR unmeasured, 1 = schema/trust/contradiction
violation, 2 = usage error.

Usage:
    python3 scripts/check_memory_governance.py [--store board/.arcrift-outbox.jsonl] [--config config/memory_governance.yaml] [--now ISO8601Z]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import memory_lib
from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

TRUST_EPS = 1e-6


def load_memories(path: str) -> list[dict]:
    mems: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    mems.append(obj)
    except FileNotFoundError:
        return []
    return mems


def violations(memories: list[dict], config: dict, now: datetime) -> list[str]:
    required = config.get("schema", {}).get("required_fields", [])
    tiers = config.get("trust_tiers", {}) or {}
    ids = {str(m.get("id")) for m in memories}
    probs: list[str] = []
    for m in memories:
        mid = str(m.get("id", "?"))
        for f in required:
            if f not in m or m.get(f) in (None, ""):
                probs.append(f"{mid}: missing required field '{f}'")
        prov = m.get("provenance")
        if prov is not None and "trust_score" in m:
            expected = memory_lib.trust_for(prov, tiers)
            raw = m.get("trust_score")
            actual = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
            if actual is not None and abs(actual - expected) > TRUST_EPS:
                probs.append(f"{mid}: trust_score {actual} != provenance '{prov}' tier {expected}")
        created = m.get("created_at")
        if created and memory_lib.parse_iso(str(created)) is None:
            probs.append(f"{mid}: unparseable created_at {created!r} (would never expire)")
        if m.get("contradicts") and str(m.get("status", "")).lower() not in ("quarantined", "contradicted"):
            probs.append(f"{mid}: declares a contradiction but is not quarantined (would still recall)")
        for ref in m.get("contradicts") or []:
            if str(ref) not in ids:
                probs.append(f"{mid}: contradicts unknown memory '{ref}'")
    return probs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", type=Path, default=ROOT / "board" / ".arcrift-outbox.jsonl")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "memory_governance.yaml")
    ap.add_argument("--now", default=None, help="ISO-8601 Z 'now' override (default: current UTC)")
    args = ap.parse_args(argv)

    if not args.config.is_file():
        sys.stderr.write(f"ERROR: config not found: {args.config}\n")
        return 2
    config = yaml.safe_load(args.config.read_text()) or {}

    memories = load_memories(str(args.store))
    if not memories:
        print(f"Memory governance: unmeasured — no memory store yet ({args.store}). Gate inert.")
        return 0

    now = memory_lib.parse_iso(args.now) if args.now else datetime.now(tz=UTC).replace(tzinfo=None)
    if now is None:
        sys.stderr.write(f"ERROR: --now must be ISO-8601 Z; got {args.now!r}\n")
        return 2

    probs = violations(memories, config, now)
    recall = memory_lib.recallable(memories, now, config)
    health = memory_lib.memory_health(memories, now, config)
    dupes = memory_lib.duplicate_pairs(
        memories, float(config.get("recall", {}).get("dedupe_similarity", 0.85))
    )
    summary = (
        f"{len(memories)} memories: {len(recall)} recallable, "
        f"{len(memories) - len(recall)} excluded, {len(dupes)} duplicate pair(s); health {health:.2f}."
    )
    if probs:
        sys.stderr.write("FAIL: memory governance (R-5 / ADR-005):\n")
        for p in probs:
            sys.stderr.write(f"  - {p}\n")
        sys.stderr.write(f"\n{len(probs)} issue(s). {summary}\n")
        return 1

    print(f"OK: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
