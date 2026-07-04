#!/usr/bin/env python3
"""attest_gate6.py — cryptographic attestation for GATE-6 records (R-2 / ADR-006).

So GATE-6 evidence cannot be fabricated, every APPLIED tuning record must carry a
tamper-evident attestation:
  - content_hash: sha256 of the record (minus the attestation block) — any edit
    after attestation breaks the hash;
  - optional HMAC signature over that hash with GATE6_ATTEST_KEY (a CI secret);
  - distinct proposed_by / approved_by / attested_by (author != reviewer != attester);
  - multi-source evidence (>=1 ci_run AND >=1 review_id).

Library + CLI:
    python3 scripts/attest_gate6.py stamp  --record experiments/GATE6-....yaml --attested-by ci-bot --ci-run 123
    python3 scripts/attest_gate6.py verify --record experiments/GATE6-....yaml
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

ENV_KEY = "GATE6_ATTEST_KEY"


def canonical_json(record: dict) -> str:
    """Stable JSON of the record EXCLUDING its attestation block."""
    payload = {k: v for k, v in record.items() if k != "attestation"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(record: dict) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def _signing_material(content_hash_hex: str, att: dict) -> str:
    """The bytes the HMAC covers: the content hash AND the attester identity
    (attested_by / attested_at / ci_run), so WHO attested and WHEN cannot be
    forged without re-signing."""
    return "\n".join([
        content_hash_hex,
        str(att.get("attested_by", "")),
        str(att.get("attested_at", "")),
        str(att.get("ci_run", "")),
    ])


def hmac_sign(material: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), material.encode("utf-8"), hashlib.sha256).hexdigest()


def build_attestation(
    record: dict, *, attested_by: str, ci_run: str, attested_at: str, key: str | None = None
) -> dict:
    digest = content_hash(record)
    att = {
        "algo": "sha256",
        "content_hash": digest,
        "attested_by": attested_by,
        "attested_at": attested_at,
        "ci_run": ci_run,
    }
    if key:
        att["sig_algo"] = "hmac-sha256"
        att["signature"] = hmac_sign(_signing_material(digest, att), key)
    return att


def verify_attestation(record: dict, key: str | None = None) -> list[str]:
    """Return a list of problems; empty == a valid, tamper-evident attestation."""
    problems: list[str] = []
    att = record.get("attestation")
    if not isinstance(att, dict):
        return ["missing attestation block"]

    expected = content_hash(record)
    if att.get("content_hash") != expected:
        problems.append("content_hash does not match record (tampered after attestation)")

    ev = record.get("evidence")
    if not (isinstance(ev, dict) and ev.get("ci_runs") and ev.get("review_ids")):
        problems.append("requires >=1 ci_run AND >=1 review_id (multi-source evidence)")

    proposer = str(record.get("proposed_by", "")).strip()
    approver = str((record.get("approval") or {}).get("approved_by", "")).strip()
    attester = str(att.get("attested_by", "")).strip()
    if not (proposer and approver and attester):
        problems.append("requires proposed_by, approved_by and attested_by")
    elif len({proposer.casefold(), approver.casefold(), attester.casefold()}) < 3:
        problems.append("proposed_by / approved_by / attested_by must be three distinct identities")

    if key:
        sig = str(att.get("signature", ""))
        if not sig or not hmac.compare_digest(sig, hmac_sign(_signing_material(expected, att), key)):
            problems.append("HMAC signature invalid")
    elif att.get("signature") or att.get("sig_algo"):
        # A signed record verified without the key must fail CLOSED — the keyless
        # hash is attacker-recomputable, so don't silently downgrade.
        problems.append("record advertises a signature but no GATE6_ATTEST_KEY available to verify")
    return problems


def _load(path: Path) -> tuple[dict, dict]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        return {}, {}
    record = data.get("gate_6_record", data)
    return data, (record if isinstance(record, dict) else {})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    stamp = sub.add_parser("stamp", help="add an attestation block to a record")
    stamp.add_argument("--record", type=Path, required=True)
    stamp.add_argument("--attested-by", required=True)
    stamp.add_argument("--ci-run", required=True)
    verify = sub.add_parser("verify", help="verify a record's attestation")
    verify.add_argument("--record", type=Path, required=True)
    args = ap.parse_args(argv)

    key = os.environ.get(ENV_KEY)
    if not args.record.is_file():
        sys.stderr.write(f"ERROR: record not found: {args.record}\n")
        return 2
    data, record = _load(args.record)

    if args.cmd == "stamp":
        record["attestation"] = build_attestation(
            record,
            attested_by=args.attested_by,
            ci_run=args.ci_run,
            attested_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            key=key,
        )
        args.record.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        signed = " (signed)" if key else " (unsigned — no GATE6_ATTEST_KEY)"
        print(f"stamped {args.record.name}: content_hash {record['attestation']['content_hash'][:12]}…{signed}")
        return 0

    problems = verify_attestation(record, key)
    if problems:
        sys.stderr.write(f"FAIL: GATE-6 attestation invalid ({args.record.name}):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: GATE-6 attestation valid ({args.record.name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
