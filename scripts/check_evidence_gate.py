#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import agent_eval
import check_attestation
import feature_flags
import snapshot_evidence
import wave_runner


DELIVERY_SCHEMA = "daslab.delivery_attestation.v1"


SCORECARD_SCHEMA = "daslab.delivery_scorecard.v1"


SIX_DIMENSIONS: tuple[str, ...] = (
    "aadl_gates_closed",
    "merged_pr_green_ci",
    "wave_attestation",
    "diagnostics_100",
    "golden_eval",
    "anti_gaming_probe",
)

_TRI_STATE = ("pass", "fail", "skipped")


def delivery_receipt_path(run_id: str, attest_dir: Path | str | None = None) -> Path:
    base = Path(attest_dir) if attest_dir is not None else wave_runner.ATTEST_DIR
    return base / f"{run_id}.delivery.json"


def load_scorecard(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dimension_statuses(scorecard: dict[str, Any]) -> dict[str, str]:
    statuses = dict.fromkeys(SIX_DIMENSIONS, "skipped")
    entries = scorecard.get("dimensions") if isinstance(scorecard, dict) else None
    if not isinstance(entries, list):
        return statuses
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        dim = entry.get("dimension")
        status = entry.get("status")
        if dim in statuses and status in _TRI_STATE:
            statuses[dim] = status
    return statuses


def verdict_of(statuses: dict[str, str]) -> str:
    return "complete" if all(statuses.get(d) == "pass" for d in SIX_DIMENSIONS) else "incomplete"


def _counted_completions_for(run_ids: list[str], evidence_dir: Path | str) -> int:
    total = 0
    for rid in run_ids:
        path = snapshot_evidence.evidence_path(evidence_dir, rid)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total += sum(1 for c in data.get("completions", []) if c.get("counted"))
    return total


_STORE_CORROBORATED_DIMENSIONS: tuple[str, ...] = ("merged_pr_green_ci", "wave_attestation")


_ARTIFACT_MEASURED_DIMENSIONS: tuple[str, ...] = tuple(
    d for d in SIX_DIMENSIONS if d not in _STORE_CORROBORATED_DIMENSIONS
)


_EXECUTION_VERIFIED_DIMENSIONS: tuple[str, ...] = ("anti_gaming_probe",)


_UNCORROBORATED_CLAIM_DIMENSIONS: tuple[str, ...] = (
    "aadl_gates_closed",
    "diagnostics_100",
    "golden_eval",
)


def measured_dimensions(delivery_dir: Path | str) -> dict[str, str]:
    card = agent_eval.score_delivery(delivery_dir, enabled=True)
    by_dim = {d.dimension: d.status for d in card.dimensions}
    measured: dict[str, str] = {}
    for dim in _ARTIFACT_MEASURED_DIMENSIONS:
        status = by_dim.get(dim)
        status = status if status in _TRI_STATE else "skipped"
        if dim in _UNCORROBORATED_CLAIM_DIMENSIONS and status == "pass":
            status = "skipped"
        measured[dim] = status
    return measured


def corroborate(
    scorecard: dict[str, Any],
    attest_dir: Path | str,
    evidence_dir: Path | str,
    delivery_dir: Path | str,
) -> tuple[dict[str, str], list[str], dict[str, int]]:
    errors: list[str] = []
    statuses = dimension_statuses(scorecard)
    attest_dir = Path(attest_dir)
    evidence_dir = Path(evidence_dir)


    measured = measured_dimensions(delivery_dir)
    for dim in _ARTIFACT_MEASURED_DIMENSIONS:
        self_reported = statuses.get(dim)
        measured_status = measured.get(dim, "skipped")
        if self_reported != measured_status:
            errors.append(
                f"{dim}: self-reported {self_reported!r} disagrees with the independently "
                f"measured {measured_status!r} (agent_eval.score_delivery over {delivery_dir}) "
                "— a self-report is never authoritative (ED-1)"
            )
        statuses[dim] = measured_status

    run_id = scorecard.get("run_id")
    if not run_id:
        errors.append("scorecard missing 'run_id' — cannot locate its wave attestation")
        return statuses, errors, {"counted_tickets": 0, "waves": 0}


    wave_files = (
        sorted(p for p in attest_dir.glob("*.json") if not p.name.endswith(".delivery.json"))
        if attest_dir.is_dir()
        else []
    )
    payloads_by_path: dict[Path, dict[str, Any]] = {}
    for p in wave_files:
        try:
            payloads_by_path[p] = wave_runner.load_attestation(p)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"attestation {p}: unreadable/invalid JSON ({exc})")

    att_path = wave_runner.attestation_path(run_id, attest_dir)
    att_payload = payloads_by_path.get(att_path)
    counted_tickets = 0
    waves = 0
    if att_payload is None:
        errors.append(
            f"D3 wave_attestation: no committed wave attestation for run_id {run_id!r} "
            f"({att_path}) — a claimed dimension without its artifact is false (ED-3)"
        )
        statuses["wave_attestation"] = "fail"
    else:
        completeness_errs = check_attestation.verify_completeness(att_payload, evidence_dir)
        if completeness_errs:
            errors.append(
                "D3 wave_attestation: committed receipt incomplete/tampered — "
                + "; ".join(completeness_errs)
            )
            statuses["wave_attestation"] = "fail"
        chain_errs = check_attestation.chain_errors(payloads_by_path)
        if chain_errs:
            errors.append("chain-integrity: " + "; ".join(chain_errs))
            statuses["wave_attestation"] = "fail"

        evidence = att_payload.get("evidence")
        run_ids = evidence.get("run_ids") if isinstance(evidence, dict) else None
        if isinstance(run_ids, list):
            counted_tickets = _counted_completions_for(run_ids, evidence_dir)
        waves = att_payload.get("wave") if isinstance(att_payload.get("wave"), int) else 0

        if statuses.get("merged_pr_green_ci") == "pass" and counted_tickets == 0:
            errors.append(
                "D2 merged_pr_green_ci: scorecard claims pass but the committed evidence "
                f"({evidence_dir}) shows 0 counted completions for run_id {run_id!r} "
                "(cross-artifact corroboration failed — a forged claim)"
            )
            statuses["merged_pr_green_ci"] = "fail"

    return statuses, errors, {"counted_tickets": counted_tickets, "waves": waves}


def build_receipt(
    scorecard: dict[str, Any],
    statuses: dict[str, str],
    counts: dict[str, int],
    attest_dir: Path | str,
    created_at: str,
) -> dict[str, Any]:
    run_id = scorecard.get("run_id", "")
    attest_dir = Path(attest_dir)
    att_path = wave_runner.attestation_path(run_id, attest_dir)
    if att_path.is_file():
        try:
            att_payload = wave_runner.load_attestation(att_path)
            prev = wave_runner._sha256(att_payload)
        except (OSError, json.JSONDecodeError):
            prev = wave_runner._GENESIS_PREV_HASH
    else:
        prev = wave_runner._GENESIS_PREV_HASH

    payload: dict[str, Any] = {
        "schema": DELIVERY_SCHEMA,
        "proof": scorecard.get("proof", ""),
        "run_id": run_id,
        "created_at": created_at,
        "verdict": verdict_of(statuses),
        "dimensions": dict(statuses),
        "counts": dict(counts),
        "attest_chain": {"prev": prev, "self": ""},
    }
    payload["attest_chain"]["self"] = wave_runner._attest_self_hash(payload)
    return payload


def write_receipt(payload: dict[str, Any], attest_dir: Path | str) -> Path:
    path = delivery_receipt_path(payload["run_id"], attest_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def verify_receipt(payload: dict[str, Any], attest_dir: Path | str, evidence_dir: Path | str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != DELIVERY_SCHEMA:
        errors.append(f"schema {payload.get('schema')!r} != {DELIVERY_SCHEMA!r}")
        return errors

    chain = payload.get("attest_chain")
    if not isinstance(chain, dict) or "prev" not in chain or "self" not in chain:
        errors.append("attest_chain must carry 'prev' and 'self'")
        return errors

    recomputed_self = wave_runner._attest_self_hash(payload)
    if recomputed_self != chain.get("self"):
        errors.append(
            f"attest_chain.self mismatch: stored {chain.get('self')!r} != "
            f"recomputed {recomputed_self!r} (tampered receipt)"
        )

    run_id = str(payload.get("run_id", ""))
    att_path = wave_runner.attestation_path(run_id, attest_dir)
    if att_path.is_file():
        try:
            att_payload = wave_runner.load_attestation(att_path)
            expected_prev = wave_runner._sha256(att_payload)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"referenced attestation {att_path} unreadable ({exc})")
            expected_prev = None
        if expected_prev is not None and expected_prev != chain.get("prev"):
            errors.append(
                f"attest_chain.prev {chain.get('prev')!r} != recomputed "
                f"{expected_prev!r} (does not link to the referenced wave attestation)"
            )
    else:
        if chain.get("prev") != wave_runner._GENESIS_PREV_HASH:
            errors.append(
                f"no committed wave attestation for run_id {run_id!r}, but "
                f"attest_chain.prev {chain.get('prev')!r} is not the genesis sentinel"
            )

    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict):
        errors.append("dimensions missing/malformed")
    else:
        recomputed_verdict = verdict_of({d: dimensions.get(d) for d in SIX_DIMENSIONS})
        if recomputed_verdict != payload.get("verdict"):
            errors.append(
                f"verdict {payload.get('verdict')!r} disagrees with its own dimensions "
                f"(recomputed {recomputed_verdict!r}) — a forged claim"
            )

    counts = payload.get("counts")
    evidence = None
    if att_path.is_file():
        try:
            evidence = wave_runner.load_attestation(att_path).get("evidence")
        except (OSError, json.JSONDecodeError):
            evidence = None
    run_ids = evidence.get("run_ids") if isinstance(evidence, dict) else None
    if isinstance(counts, dict) and isinstance(run_ids, list):
        recomputed_counted = _counted_completions_for(run_ids, evidence_dir)
        if recomputed_counted != counts.get("counted_tickets"):
            errors.append(
                f"counts.counted_tickets={counts.get('counted_tickets')!r} != "
                f"{recomputed_counted} recomputed from committed evidence "
                "(a forged receipt disagreeing with the counted-completion evidence)"
            )

    return errors


def _flag_gate_inert(flags_path: Path | None) -> bool:
    return not feature_flags.enabled("ws_g_proof", flags_path)


def scan_committed_receipts(
    attest_dir: Path | str, evidence_dir: Path | str
) -> dict[Path, list[str]]:
    problems: dict[Path, list[str]] = {}
    base = Path(attest_dir)
    if not base.is_dir():
        return problems
    for path in sorted(base.glob("*.delivery.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems[path] = [f"unreadable/invalid JSON: {exc}"]
            continue
        errs = verify_receipt(payload, attest_dir, evidence_dir)
        if errs:
            problems[path] = errs
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_evidence_gate.py — WS-G GATE-3: the 0->100 evidence + attestation gate.')
    ap.add_argument("--scorecard", type=Path, default=None, help="delivery run-scorecard JSON to compose")
    ap.add_argument("--attest-dir", type=Path, default=wave_runner.ATTEST_DIR)
    ap.add_argument("--evidence-dir", type=Path, default=snapshot_evidence.EVIDENCE_DIR)
    ap.add_argument(
        "--delivery-dir",
        type=Path,
        default=None,
        help="delivery dir whose fixtures/ D1/D4/D5/D6 are independently re-measured via "
        "agent_eval.score_delivery (default: the --scorecard file's parent directory)",
    )
    ap.add_argument(
        "--created-at",
        default=None,
        help="ISO-8601 timestamp stamped into a newly-written receipt (no clock read, caller-supplied)",
    )
    ap.add_argument("--features", type=Path, default=None, help="config/features.yaml path override")
    args = ap.parse_args(argv)

    if _flag_gate_inert(args.features):
        print(
            "check_evidence_gate: ws_g_proof OFF — gate inert (exit 0), "
            "byte-identical to pre-merge."
        )
        return 0


    scan_problems = scan_committed_receipts(args.attest_dir, args.evidence_dir)

    if args.scorecard is None or not args.scorecard.is_file():
        if scan_problems:
            sys.stderr.write(
                "FAIL: evidence gate (GATE-3 / ADR-0037 ED-1) — a committed delivery "
                "receipt is tampered or inconsistent:\n"
            )
            for path, errs in sorted(scan_problems.items()):
                for e in errs:
                    sys.stderr.write(f"  - {path.name}: {e}\n")
            return 1
        print(
            "check_evidence_gate: no delivery scorecard given/found — nothing claimed "
            "done, gate inert (exit 0). The gate BITES once a delivery is claimed."
        )
        return 0

    try:
        scorecard = load_scorecard(args.scorecard)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"FAIL: unreadable/invalid scorecard {args.scorecard}: {exc}\n")
        return 1

    if scorecard.get("schema") != SCORECARD_SCHEMA:
        sys.stderr.write(
            f"FAIL: scorecard schema {scorecard.get('schema')!r} != {SCORECARD_SCHEMA!r}\n"
        )
        return 1

    delivery_dir = args.delivery_dir if args.delivery_dir is not None else args.scorecard.parent
    statuses, errors, counts = corroborate(scorecard, args.attest_dir, args.evidence_dir, delivery_dir)
    verdict = verdict_of(statuses)

    created_at = args.created_at or scorecard.get("created_at")
    if not created_at:
        sys.stderr.write("FAIL: no --created-at given and scorecard carries none (no clock read)\n")
        return 2

    payload = build_receipt(scorecard, statuses, counts, args.attest_dir, created_at)
    path = write_receipt(payload, args.attest_dir)

    if scan_problems or errors or verdict != "complete":
        sys.stderr.write(
            "FAIL: evidence gate (GATE-3 / ADR-0037 ED-1) — delivery is NOT a genuine "
            f"all-pass 0->100 (verdict={verdict!r}); receipt committed at {path} for audit:\n"
        )
        for dim in SIX_DIMENSIONS:
            sys.stderr.write(f"  - {dim}: {statuses.get(dim)}\n")
        for e in errors:
            sys.stderr.write(f"  ! {e}\n")
        for other_path, errs in sorted(scan_problems.items()):
            for e in errs:
                sys.stderr.write(f"  ! {other_path.name}: {e}\n")
        return 1

    print(
        f"OK: genuine all-pass delivery (verdict=complete) — receipt committed at {path} "
        "(hash-chained onto the wave attestation, ADR-0031/0032)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
