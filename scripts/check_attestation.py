#!/usr/bin/env python3
"""check_attestation.py — GATE-4: committed wave-attestation completeness + integrity.

ORGANISM WS8 ATTEST (ADR-0031). DAS-1499's ``wave_runner.run_wave`` emits a
committed, redacted, doubly hash-chained :class:`~wave_runner.WaveAttestation` to
``metrics/attestations/<run_id>.json`` for every wave. This validator PROVES those
committed receipts are trustworthy: a partial, tampered, or fabricated attestation
must not pass silently.

For EACH committed attestation it verifies (fail-closed — exit 1 on ANY gap):

- the ``schema`` tag is the expected ``daslab.attestation.v1``;
- **every planned ticket has a ``run_start`` / ``run_end`` / span** — the emitted
  event counts equal the dispatched-ticket count (``events_emitted`` ==
  ``counts.dispatched`` == ``len(tickets)``), and the wave-open/close checkpoints,
  ledger, and evidence mechanics all fired;
- **``run_end`` carried the ``metrics_lib`` fields** — cross-checked against the
  committed evidence snapshot's redacted completion records (each carries
  ``outcome`` / ``model`` / ``merged_pr`` / ``ci_status`` / ``t7_pass`` /
  ``t7_score``);
- **every counted run has committed evidence** — each ``evidence.run_ids`` entry
  resolves to a committed ``metrics/evidence/<run_id>.json`` snapshot (cross-check
  against ``snapshot_evidence``), the attestation's ``evidence.digest`` recomputes
  from those committed files, and the counted-completion tally matches;
- **the progress-ledger digest is present** (``ledger_digest``);
- **the hash chain (``prev`` / ``self``) is intact across records** — each
  receipt's self-hash recomputes (``wave_runner.verify_attestation``) and its
  ``prev`` links to genesis or to another committed receipt's ``self``.

Inert-by-design: with NO committed attestations the gate exits 0 (a fresh clone,
before any wave has run, has nothing to check) — never a fabricated pass. Once a
sample (or a real wave) is committed the gate BITES.

REUSE, never re-implement: the schema tag, the canonical hashing, the self-hash
recompute, and the genesis sentinel all come from ``wave_runner`` (the producer's
SSOT); the evidence path + completion vocabulary come from ``snapshot_evidence``.
This validator only reads and cross-checks — it never re-derives a schema.

Exit codes: 0 = all committed attestations complete + consistent OR none exist,
1 = a gap/tamper in some attestation, 2 = usage error.

Usage:
    python3 scripts/check_attestation.py
    python3 scripts/check_attestation.py --attest-dir metrics/attestations \\
                                         --evidence-dir metrics/evidence
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import snapshot_evidence
import wave_runner

#: The ``metrics_lib`` evidence fields a ``run_end`` must carry, mirrored into the
#: redacted evidence completion record. Kept in sync with
#: ``dgox.events.RUN_END_METRICS_FIELDS`` (minus ``run_id`` / ``created_at`` which
#: live at the evidence-record top level, not the per-completion dict).
_METRICS_FIELDS = ("outcome", "model", "merged_pr", "ci_status", "t7_pass", "t7_score")

#: Top-level attestation fields every committed receipt must carry.
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

#: Wave mechanics that must have fired (True) for a complete receipt. The OPTIONAL
#: guardrail tripwire (``guardrails_run``) is deliberately excluded — ADR-0031 §2
#: makes it failure-isolated, not load-bearing.
_REQUIRED_MECHANICS = (
    "checkpoint_open",
    "ledger_written",
    "evidence_written",
    "checkpoint_close",
)


def _digest_ok(value: object) -> bool:
    """True if ``value`` is a well-formed ``sha256:<hex>`` digest string."""
    return isinstance(value, str) and value.startswith("sha256:") and len(value) > len("sha256:")


def verify_completeness(payload: dict, evidence_dir: Path | str) -> list[str]:
    """Return the completeness/consistency problems for one attestation (empty == OK).

    Does NOT raise: every gap is reported as a string so the caller aggregates
    them across the whole store and fails once.
    """
    errors: list[str] = []

    if payload.get("schema") != wave_runner.ATTESTATION_SCHEMA:
        errors.append(
            f"schema {payload.get('schema')!r} != {wave_runner.ATTESTATION_SCHEMA!r}"
        )

    missing_top = [k for k in _REQUIRED_TOP_LEVEL if k not in payload]
    if missing_top:
        errors.append(f"missing top-level field(s): {missing_top}")
        return errors  # structure too incomplete to cross-check reliably

    tickets = payload["tickets"]
    counts = payload["counts"]
    mech = payload["mechanics"]
    if not isinstance(tickets, list):
        errors.append("tickets is not a list")
        return errors
    n = len(tickets)

    # --- every planned ticket has run_start / run_end / span + the mechanics fired ---
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

    # --- the progress-ledger digest + event digest are present ---
    if not _digest_ok(payload.get("ledger_digest")):
        errors.append("ledger_digest missing/malformed (progress-ledger not digested)")
    if not _digest_ok(payload.get("event_digest")):
        errors.append("event_digest missing/malformed")

    # --- every counted run has committed evidence + run_end carried metrics fields ---
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

    # Cross-checks that need every referenced evidence file present + parsed.
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

    # --- integrity: self-hash recomputes + chain fields present (never raises) ---
    errors += wave_runner.verify_attestation(payload)
    return errors


def chain_errors(payloads_by_path: dict[Path, dict]) -> list[str]:
    """Return cross-record hash-chain problems (empty == the chain links cleanly).

    Each receipt's ``prev`` must be the genesis sentinel or the ``self`` of another
    committed receipt — a dangling ``prev`` means a link was tampered or a prior
    receipt was dropped.
    """
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
            continue  # already reported by verify_completeness
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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

    # Wave attestations only — a `<run_id>.delivery.json` in the same store is a
    # WS-G evidence-gate receipt (schema daslab.delivery_attestation.v1, verified
    # by check_evidence_gate.py), NOT a wave attestation. Excluding it keeps this
    # glob symmetric with check_evidence_gate.corroborate()'s own wave-file glob so
    # the first real receipt DAS-1595 commits is not mis-read here as a malformed
    # wave attestation (a false FAIL). Fail-closed already, but this removes the
    # forward-looking footgun (DAS-1592 GATE-3 glob-collision follow-up).
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
        # chain problems are attributed to a file already; surface under a sentinel.
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
