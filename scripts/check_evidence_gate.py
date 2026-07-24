#!/usr/bin/env python3
"""check_evidence_gate.py — WS-G GATE-3: the 0->100 evidence + attestation gate.

ORGANISM WS-G PROOF (ADR-0037 ED-1/ED-4, DAS-1592). "Finished" for a MUSTAQIL
delivery is defined ONLY by evidence, never by a self-report (ED-1). This
validator COMPOSES the six ED-1 completion-contract dimensions a delivery
run-scorecard reports (``daslab.delivery_scorecard.v1`` — DAS-1591) with the
already-committed attestation + evidence artifacts, and — only on a genuine
all-pass delivery — commits a hash-chained 0->100 receipt:

    metrics/attestations/<run_id>.delivery.json   (schema daslab.delivery_attestation.v1)

It does **not** re-implement attestation/evidence primitives — every
completeness/integrity check is delegated to ``check_attestation`` and every
counted-completion read goes through ``snapshot_evidence``'s own committed
evidence file shape (never re-derived field names). It also does **not**
trust the scorecard's self-reported ``status`` for ANY of the six dimensions:
D2 ``merged_pr_green_ci`` / D3 ``wave_attestation`` are independently
re-derived from the committed wave-attestation + evidence store (below).

**TRUST BOUNDARY (DAS-1594 GATE-4 hole, closed here — read this before touching
D1/D4/D5).** D1 ``aadl_gates_closed`` / D4 ``diagnostics_100`` / D5
``golden_eval`` are, at best, *re-measured* by invoking
``agent_eval.score_delivery`` (DAS-1591's dimension verifiers, reused
READ-ONLY) over the delivery's ``fixtures/`` directory — but that directory is
authored by the SAME actor who benefits from a green verdict, and nothing in
the committed, hash-chained evidence chain (``metrics/evidence/<run_id>.json``
+ the ``WaveAttestation`` D2/D3 corroborate against) records a proof
delivery's real AADL gate state, diagnostics score, or golden-eval accuracy —
ADR-0031/0032 never extended the attested chain to carry those three facts.
A "pass" re-measured from ``fixtures/`` alone is therefore a *plausible claim*,
not independently attested evidence: a deliverer willing to hand-author
believable-looking ``stage-board.md`` / ``diagnostics.json`` /
``golden-eval.json`` content (rather than omit the files, which the prior
GATE-3 fix already catches as ``skipped``) can make ``score_delivery`` report
"pass" with zero real backing — the exact hole DAS-1594's QA red-team
reproduced live. Since no trustworthy anchor exists YET to corroborate a
*positive* D1/D4/D5 claim, this gate never accepts one: a re-measured
``pass`` for these three is downgraded to ``skipped`` (unattested, ADR-0020 —
unmeasured is never green). A re-measured ``fail`` is NOT downgraded — the
artifact genuinely disagreeing with the claim (an open gate, a sub-100 score)
is real, self-evident badness that needs no external corroboration to trust,
only a real green does. D6 ``anti_gaming_probe`` is untouched by this
boundary: ``agent_eval.mutation_probe`` actually EXECUTES the delivery's own
suite against a mutated implementation, so a measured "pass" there is
execution-verified, not a bare file claim, and stays authoritative. Closing
this hole for good (letting D1/D4/D5 genuinely reach "pass") needs a follow-up
that extends the attested evidence chain to actually record these three facts
(Option A) or re-runs the real validators live per delivery (Option B) — out
of THIS ticket's file scope (``scripts/check_evidence_gate.py`` only); until
then a caller-supplied scorecard is corroborating input, never an
authoritative source (GATE-3 red-team finding, DAS-1592; GATE-4 hole,
DAS-1594; this fix, DAS-1592 re-opened).

The six ED-1 dimensions (docs/design/ws-g-proof-delivery.md §1.2):

    aadl_gates_closed | merged_pr_green_ci | wave_attestation
    diagnostics_100    | golden_eval        | anti_gaming_probe

Fail-closed rules (no false-green, ADR-0020 / §2.3):

  1. **Missing artifact -> FAIL.** No scorecard, no committed wave attestation
     for the claimed ``run_id``, or an attestation that ``check_attestation``
     itself rejects -> the composed verdict is ``incomplete`` and the gate
     exits non-zero.
  2. **SKIP is never a pass.** A dimension the scorecard reports ``skipped``
     (unmeasured) does NOT satisfy the gate; only ``pass`` counts. ``verdict``
     is ``complete`` iff every one of the six dimensions is ``pass``.
  3. **Cross-artifact corroboration, all six dimensions.** The claimed delivery
     must agree with independently-committed evidence for EVERY dimension, not
     just two: ``merged_pr_green_ci`` / ``wave_attestation`` are re-derived from
     the counted completions + committed wave attestation (never taken from the
     scorecard's own say-so); ``anti_gaming_probe`` is re-measured by actually
     EXECUTING the delivery's suite against a mutated implementation
     (``agent_eval.mutation_probe``); and ``aadl_gates_closed`` /
     ``diagnostics_100`` / ``golden_eval`` are re-measured by
     ``agent_eval.score_delivery`` over the delivery's ``fixtures/`` artifacts
     but a re-measured ``pass`` for these three is NEVER accepted (see the
     TRUST BOUNDARY note above) — no attested anchor exists yet to corroborate
     a positive claim, so it is downgraded to ``skipped``; a re-measured
     ``fail`` (the artifact itself disagreeing) passes through unchanged. A
     scorecard's self-reported status is used ONLY to detect disagreement with
     the measured artifact; the measured status always wins, and any
     disagreement is itself a rejection reason (a forged self-report with no
     backing artifact, or one backed only by a plausible-looking but
     unattested artifact, measures ``skipped``, never ``pass``).
  4. **Chain-integrity walk.** The receipt's ``attest_chain.prev`` must equal
     the SHA-256 of the referenced wave attestation's canonical bytes, and the
     whole committed attestation store must still hash-chain cleanly
     (``check_attestation.chain_errors``) — a tampered/re-ordered chain FAILS.

Inert-by-design (ADR-0020 "honest empty", §2.1): with ``ws_g_proof`` OFF, or
with no scorecard given/found, there is no claimed delivery to compose and the
gate exits 0 without writing anything — it never fabricates a requirement and
never fabricates a receipt. It has teeth ONLY once a delivery scorecard claims
"done".

REUSE, never fork (ADR-0029): the hash-chain primitives
(``wave_runner._sha256`` / ``wave_runner._attest_self_hash`` /
``wave_runner._GENESIS_PREV_HASH``), the attestation reader/verifier
(``wave_runner.load_attestation`` / ``wave_runner.attestation_path``), and the
whole completeness + chain walk (``check_attestation.verify_completeness`` /
``check_attestation.chain_errors``) come from the landed producer/validator —
this module composes them, it does not re-implement them.

Exit codes: 0 = inert (no claimed delivery) OR a genuine all-pass delivery
whose receipt was committed clean; 1 = a false-green was rejected (missing
artifact / skip / cross-check mismatch / chain break); 2 = usage error.

Usage:
    python3 scripts/check_evidence_gate.py
    python3 scripts/check_evidence_gate.py --scorecard metrics/scorecards/<run_id>.json \\
        --created-at 2026-07-24T12:41:00Z
"""
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

#: Schema tag stamped into every committed delivery receipt.
DELIVERY_SCHEMA = "daslab.delivery_attestation.v1"

#: Schema tag a delivery run-scorecard must carry (DAS-1591's producer SSOT;
#: this gate only READS the shape, it never re-derives it).
SCORECARD_SCHEMA = "daslab.delivery_scorecard.v1"

#: The six ED-1 completion-contract dimensions, fixed order (design §1.2).
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
    """Committed delivery-receipt path: ``<attest_dir>/<run_id>.delivery.json``."""
    base = Path(attest_dir) if attest_dir is not None else wave_runner.ATTEST_DIR
    return base / f"{run_id}.delivery.json"


def load_scorecard(path: Path | str) -> dict[str, Any]:
    """Load a delivery run-scorecard payload from disk (raises on I/O/JSON error)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dimension_statuses(scorecard: dict[str, Any]) -> dict[str, str]:
    """Extract ``{dimension: status}`` from a scorecard, one entry per §1.2 dimension.

    A dimension the scorecard's ``dimensions`` list omits, or reports with an
    unrecognised status, is treated as ``skipped`` (ADR-0020 — unmeasured is
    SKIPPED, never assumed pass). This is the single place a missing dimension
    becomes an honest tri-state rather than a silent green.
    """
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
    """``complete`` iff every one of the six dimensions is ``pass`` (§1.4/§2.2)."""
    return "complete" if all(statuses.get(d) == "pass" for d in SIX_DIMENSIONS) else "incomplete"


def _counted_completions_for(run_ids: list[str], evidence_dir: Path | str) -> int:
    """Sum of ``counted`` completions across the referenced committed evidence.

    Reads the already-committed, already-redacted snapshot shape
    (``snapshot_evidence.build_run_evidence``'s ``completions[].counted``) —
    never re-derives the R-9 counted-completion predicate.
    """
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


#: Dimensions D2/D3 corroborate against the real committed wave-attestation +
#: evidence store (below, already stronger than a ``fixtures/`` snapshot).
_STORE_CORROBORATED_DIMENSIONS: tuple[str, ...] = ("merged_pr_green_ci", "wave_attestation")

#: The four dimensions the GATE-3 red-team found were trusted VERBATIM from the
#: scorecard's self-report — re-measured from committed artifacts via
#: ``agent_eval.score_delivery`` (never taken from the scorecard's own say-so).
_ARTIFACT_MEASURED_DIMENSIONS: tuple[str, ...] = tuple(
    d for d in SIX_DIMENSIONS if d not in _STORE_CORROBORATED_DIMENSIONS
)

#: D6 is EXECUTION-verified (``agent_eval.mutation_probe`` actually runs the
#: delivery's suite against a mutated implementation) — a measured "pass" is
#: trustworthy and untouched by the D1/D4/D5 trust boundary below.
_EXECUTION_VERIFIED_DIMENSIONS: tuple[str, ...] = ("anti_gaming_probe",)

#: DAS-1594 GATE-4 hole: these three dimensions' ``agent_eval.score_delivery``
#: verifiers read NOTHING but a self-authored ``fixtures/`` file (a delivery
#: author fully controls ``stage-board.md`` / ``diagnostics.json`` /
#: ``golden-eval.json``), and no independently-committed, hash-chained anchor
#: exists (yet) to corroborate a POSITIVE claim for any of them — see the
#: module docstring's TRUST BOUNDARY section. A re-measured ``pass`` for these
#: three is never accepted outright by this gate (downgraded to ``skipped`` in
#: :func:`measured_dimensions`); a re-measured ``fail`` is real, self-evident
#: badness and passes through unchanged (detecting a lie needs no
#: corroboration, only trusting a claimed truth does).
_UNCORROBORATED_CLAIM_DIMENSIONS: tuple[str, ...] = (
    "aadl_gates_closed",
    "diagnostics_100",
    "golden_eval",
)


def measured_dimensions(delivery_dir: Path | str) -> dict[str, str]:
    """Independently re-measure D1/D4/D5/D6 from the delivery's real artifacts.

    Delegates to ``agent_eval.score_delivery`` (DAS-1591's six deterministic,
    artifact-only dimension verifiers) READ-ONLY — this module never forks a
    second measurer. Only :data:`_ARTIFACT_MEASURED_DIMENSIONS` are read from
    the result; D2/D3 are excluded on purpose because :func:`corroborate`
    already independently re-derives those two from the committed wave
    attestation + evidence store, a stronger signal than the ``fixtures/``
    snapshot ``score_delivery`` reads. A missing/absent delivery dir or
    fixture file measures ``skipped`` for every dimension (never ``pass`` —
    ADR-0020): this is precisely what makes the GATE-3 forge (all-pass
    self-report, zero real artifacts) measure honest and fail closed.

    **DAS-1594 GATE-4 fix:** for :data:`_UNCORROBORATED_CLAIM_DIMENSIONS`
    (D1/D4/D5) a measured ``pass`` is downgraded to ``skipped`` — there is no
    tamper-evident anchor yet to corroborate a POSITIVE claim for these three,
    so ``score_delivery`` reading a plausible-looking (but self-authored,
    unattested) ``fixtures/`` artifact can never alone earn green. A measured
    ``fail`` (the artifact itself shows real badness — an open gate, a
    sub-100 score, a sub-bar accuracy) is NOT downgraded; only a claimed
    ``pass`` needs corroboration this gate cannot yet provide. D6
    (:data:`_EXECUTION_VERIFIED_DIMENSIONS`) is untouched — it is proven by
    actually running code, not by reading a claim.
    """
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
    """Compose the scorecard's six dimensions with the committed artifacts (§2.1/§2.3).

    Returns ``(statuses, errors, counts)``:

    * ``statuses`` — one tri-state per dimension, but NEVER the scorecard's own
      say-so: ``merged_pr_green_ci`` / ``wave_attestation`` are DOWNGRADED to
      ``fail`` whenever the committed wave-attestation/evidence store
      disagrees (ED-3), and ``aadl_gates_closed`` / ``diagnostics_100`` /
      ``golden_eval`` / ``anti_gaming_probe`` are REPLACED outright by the
      independently measured status from :func:`measured_dimensions` — a
      caller-supplied ``pass`` with no real backing artifact measures
      ``skipped`` and is never accepted (the GATE-3 red-team hole, closed);
    * ``errors`` — fail-closed reasons a claimed-done delivery is rejected
      (missing artifact / cross-check mismatch / chain break / a self-report
      that disagrees with an independently measured artifact); empty means
      the composed evidence corroborates the scorecard's claim;
    * ``counts`` — ``{counted_tickets, waves}`` INDEPENDENTLY derived from the
      committed evidence + attestation (never taken from the scorecard).
    """
    errors: list[str] = []
    statuses = dimension_statuses(scorecard)
    attest_dir = Path(attest_dir)
    evidence_dir = Path(evidence_dir)

    # D1/D4/D5/D6: never trust the self-report — replace it outright with the
    # independently measured artifact status (GATE-3 red-team fix, DAS-1592).
    # Done FIRST (before any early-return below) so every code path — including
    # a scorecard missing its own `run_id` — carries honestly measured statuses,
    # not the caller's optimistic self-report. A disagreement (the self-report
    # claiming something the real artifact does not back) is itself flagged as
    # a rejection reason, not silently papered over by the measured status alone.
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

    # Every committed WAVE attestation (never a delivery receipt) in this store,
    # for the whole-store chain walk `check_attestation.chain_errors` needs.
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
    """Build the committed 0->100 delivery receipt, hash-chained onto the wave
    attestation (ADR-0031/0032 canonical hashing, reused verbatim — never forked).

    ``attest_chain.prev`` = SHA-256 of the referenced wave attestation's exact
    canonical bytes (the closing bookend on that run's chain, design §2.2); when
    no wave attestation is committed for this run at all, ``prev`` falls back to
    the shared genesis sentinel (mirrors ``check_attestation``'s own convention),
    which is itself flagged an error by :func:`corroborate` — a fabricated
    "finished" claim never gets a phantom chain link.
    """
    run_id = scorecard.get("run_id", "")
    attest_dir = Path(attest_dir)
    att_path = wave_runner.attestation_path(run_id, attest_dir)
    if att_path.is_file():
        try:
            att_payload = wave_runner.load_attestation(att_path)
            prev = wave_runner._sha256(att_payload)  # noqa: SLF001 - reused SSOT primitive
        except (OSError, json.JSONDecodeError):
            prev = wave_runner._GENESIS_PREV_HASH  # noqa: SLF001
    else:
        prev = wave_runner._GENESIS_PREV_HASH  # noqa: SLF001

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
    payload["attest_chain"]["self"] = wave_runner._attest_self_hash(payload)  # noqa: SLF001
    return payload


def write_receipt(payload: dict[str, Any], attest_dir: Path | str) -> Path:
    """Commit the delivery receipt (TRACKED — never gitignored, ADR-0031 §4 posture)."""
    path = delivery_receipt_path(payload["run_id"], attest_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def verify_receipt(payload: dict[str, Any], attest_dir: Path | str, evidence_dir: Path | str) -> list[str]:
    """Re-verify an ALREADY-COMMITTED delivery receipt (the CI-gate walk, §2.3).

    Recomputes the self-hash, recomputes ``prev`` against the referenced wave
    attestation's current committed bytes, re-derives the counted-tickets tally
    from committed evidence, and re-asserts ``verdict`` matches the dimensions —
    so a hand-tampered/forged receipt (a re-ordered chain, a disagreeing count,
    a claimed ``complete`` with a non-pass dimension) is caught, never trusted.
    """
    errors: list[str] = []
    if payload.get("schema") != DELIVERY_SCHEMA:
        errors.append(f"schema {payload.get('schema')!r} != {DELIVERY_SCHEMA!r}")
        return errors

    chain = payload.get("attest_chain")
    if not isinstance(chain, dict) or "prev" not in chain or "self" not in chain:
        errors.append("attest_chain must carry 'prev' and 'self'")
        return errors

    recomputed_self = wave_runner._attest_self_hash(payload)  # noqa: SLF001
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
            expected_prev = wave_runner._sha256(att_payload)  # noqa: SLF001
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"referenced attestation {att_path} unreadable ({exc})")
            expected_prev = None
        if expected_prev is not None and expected_prev != chain.get("prev"):
            errors.append(
                f"attest_chain.prev {chain.get('prev')!r} != recomputed "
                f"{expected_prev!r} (does not link to the referenced wave attestation)"
            )
    else:
        if chain.get("prev") != wave_runner._GENESIS_PREV_HASH:  # noqa: SLF001
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
    """Re-verify every ALREADY-COMMITTED ``*.delivery.json`` receipt (the CI walk).

    Mirrors ``check_attestation``'s own directory-scan posture: a committed
    receipt with an honest ``verdict: incomplete`` is NOT a failure (an
    unfinished delivery telling the truth is exactly what ADR-0020 wants) — only
    a receipt :func:`verify_receipt` finds tampered, re-ordered, or disagreeing
    with the committed evidence is a problem. Inert (returns ``{}``) when the
    directory holds no delivery receipt.
    """
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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

    # Always re-verify whatever delivery receipts are ALREADY committed — a
    # tampered/re-ordered chain FAILS regardless of whether a new one is composed
    # this run (mirrors check_attestation's directory-scan posture).
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
