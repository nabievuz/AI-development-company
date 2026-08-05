#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import snapshot_evidence
import wave_runner


_METRICS_FIELDS = ("outcome", "model", "merged_pr", "ci_status", "t7_pass", "t7_score")


_REQUIRED_TOP_LEVEL = (
    "run_id",
    "wave",
    "engine_version",
    "created_at",
    "tickets",
    "mechanics",
    "counts",
    "event_digest",
    "evidence",
    "ledger_digest",
    "attest_chain",
)


_REQUIRED_MECHANICS = (
    "checkpoint_open",
    "ledger_written",
    "evidence_written",
    "checkpoint_close",
)


def _digest_ok(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) > len("sha256:")


def verify_completeness(payload: dict, evidence_dir: Path | str) -> list[str]:
    errors: list[str] = []

    if payload.get("schema") != wave_runner.ATTESTATION_SCHEMA:
        errors.append(
            f"schema {payload.get('schema')!r} != {wave_runner.ATTESTATION_SCHEMA!r}"
        )

    missing_top = [k for k in _REQUIRED_TOP_LEVEL if k not in payload]
    if missing_top:
        errors.append(f"missing top-level field(s): {missing_top}")
        return errors

    tickets = payload["tickets"]
    counts = payload["counts"]
    mech = payload["mechanics"]
    if not isinstance(tickets, list):
        errors.append("tickets is not a list")
        return errors
    n = len(tickets)


    for flag in _REQUIRED_MECHANICS:
        if mech.get(flag) is not True:
            errors.append(f"mechanics.{flag} is not True (mechanic did not fire)")
    emitted = mech.get("events_emitted")
    if not isinstance(emitted, dict):
        errors.append("mechanics.events_emitted missing/malformed")
    else:
        for etype in ("run_start", "run_end", "span"):
            got = emitted.get(etype)
            if got != n:
                errors.append(
                    f"events_emitted.{etype}={got!r} != {n} (a planned ticket lacks a {etype})"
                )
    if counts.get("dispatched") != n:
        errors.append(f"counts.dispatched={counts.get('dispatched')!r} != len(tickets) {n}")
    counted = counts.get("counted_completions")
    if not isinstance(counted, int) or counted < 0 or counted > n:
        errors.append(f"counts.counted_completions={counted!r} out of range [0,{n}]")


    if not _digest_ok(payload.get("ledger_digest")):
        errors.append("ledger_digest missing/malformed (progress-ledger not digested)")
    if not _digest_ok(payload.get("event_digest")):
        errors.append("event_digest missing/malformed")


    ev = payload["evidence"]
    run_ids = ev.get("run_ids") if isinstance(ev, dict) else None
    if not isinstance(run_ids, list):
        errors.append("evidence.run_ids missing/malformed")
        return errors + wave_runner.verify_attestation(payload)
    if n > 0 and not run_ids:
        errors.append("evidence.run_ids empty for a non-empty plan")

    ev_payloads: dict[str, dict] = {}
    counted_in_evidence = 0
    for rid in run_ids:
        path = snapshot_evidence.evidence_path(evidence_dir, rid)
        if not path.is_file():
            errors.append(f"counted run {rid!r}: no committed evidence file ({path})")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"evidence {rid!r}: unreadable/invalid JSON ({exc})")
            continue
        ev_payloads[rid] = data
        for comp in data.get("completions", []):
            missing = [f for f in _METRICS_FIELDS if f not in comp]
            if missing:
                errors.append(
                    f"evidence {rid!r}: a completion is missing metrics_lib field(s) {missing}"
                )
            if comp.get("counted"):
                counted_in_evidence += 1


    all_present = len(ev_payloads) == len(run_ids)
    if all_present and run_ids:
        recomputed = wave_runner._sha256({rid: ev_payloads[rid] for rid in run_ids})
        if recomputed != ev.get("digest"):
            errors.append(
                f"evidence.digest mismatch: stored {ev.get('digest')!r} != "
                f"recomputed {recomputed!r} (committed evidence tampered)"
            )
    if all_present and isinstance(counted, int) and counted_in_evidence != counted:
        errors.append(
            f"counts.counted_completions={counted} != {counted_in_evidence} counted "
            "in committed evidence"
        )


    errors += wave_runner.verify_attestation(payload)
    return errors


def chain_errors(payloads_by_path: dict[Path, dict]) -> list[str]:
    errors: list[str] = []
    self_hashes = {
        chain["self"]
        for payload in payloads_by_path.values()
        if isinstance((chain := payload.get("attest_chain")), dict)
        and isinstance(chain.get("self"), str)
    }
    for path, payload in sorted(payloads_by_path.items()):
        chain = payload.get("attest_chain")
        if not isinstance(chain, dict):
            continue
        prev = chain.get("prev")
        if prev == wave_runner._GENESIS_PREV_HASH:
            continue
        if prev not in self_hashes:
            errors.append(
                f"{path.name}: attest_chain.prev {prev!r} links to no committed "
                "receipt (dangling/tampered chain)"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_attestation.py — GATE-4: committed wave-attestation completeness + integrity.')
    ap.add_argument(
        "--attest-dir",
        type=Path,
        default=wave_runner.ATTEST_DIR,
        help="committed attestation directory (default: metrics/attestations)",
    )
    ap.add_argument(
        "--evidence-dir",
        type=Path,
        default=snapshot_evidence.EVIDENCE_DIR,
        help="committed evidence directory (default: metrics/evidence)",
    )
    args = ap.parse_args(argv)


    files = (
        sorted(p for p in args.attest_dir.glob("*.json") if not p.name.endswith(".delivery.json"))
        if args.attest_dir.is_dir()
        else []
    )
    if not files:
        print(
            "check_attestation: no committed attestations — gate inert (exit 0). "
            "The gate BITES once a wave commits a receipt."
        )
        return 0

    payloads: dict[Path, dict] = {}
    problems: dict[Path, list[str]] = {}
    for path in files:
        try:
            payload = wave_runner.load_attestation(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems[path] = [f"unreadable/invalid JSON: {exc}"]
            continue
        payloads[path] = payload
        errs = verify_completeness(payload, args.evidence_dir)
        if errs:
            problems.setdefault(path, []).extend(errs)

    for e in chain_errors(payloads):

        problems.setdefault(args.attest_dir, []).append(e)

    if problems:
        sys.stderr.write(
            "FAIL: attestation gate (GATE-4 / ADR-0031) — committed receipt(s) "
            "incomplete or inconsistent:\n"
        )
        for _path, errs in sorted(problems.items()):
            for e in errs:
                sys.stderr.write(f"  - {e}\n")
        total = sum(len(v) for v in problems.values())
        sys.stderr.write(
            f"\n{total} problem(s) across {len(files)} committed attestation(s).\n"
        )
        return 1

    print(
        f"OK: {len(files)} committed attestation(s) complete "
        "(every ticket run_start/run_end/span, evidence + ledger digests, "
        "hash-chain intact)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
