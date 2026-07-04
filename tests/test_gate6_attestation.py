#!/usr/bin/env python3
"""tests/test_gate6_attestation.py — cryptographic GATE-6 attestation (R-2 / ADR-006)."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import attest_gate6 as ag  # noqa: E402  (import after path manipulation)
import check_gate6_attestation as cga  # noqa: E402

AT = "2026-06-22T00:00:00Z"


def _record(status: str = "applied") -> dict:
    return {
        "id": "GATE6-1",
        "proposed_by": "ai-agent",
        "hypothesis": "raise concurrency",
        "baseline_metrics": {"T7_quality": 1.0},
        "proposed_change": {"config_diff_hash": "sha256:abc", "blast_radius": "low"},
        "guardrails": {"max_quality_drop": 0, "rollback_condition": "revert"},
        "evidence": {"ci_runs": ["ci-1"], "review_ids": ["rev-1"], "trace_ids": [], "experiment_ids": []},
        "approval": {"approved_by": "cto"},
        "rollout": {"mode": "limited_live"},
        "result": {"status": status},
    }


def _attested(key: str | None = None, attested_by: str = "ci-bot") -> dict:
    rec = _record()
    rec["attestation"] = ag.build_attestation(rec, attested_by=attested_by, ci_run="ci-1", attested_at=AT, key=key)
    return rec


# --------------------------------------------------------------------------- #
# Hash + verify
# --------------------------------------------------------------------------- #

def test_valid_attestation_verifies():
    assert ag.verify_attestation(_attested()) == []


def test_tampered_record_breaks_hash():
    rec = _attested()
    rec["hypothesis"] = "something else entirely"  # edited AFTER attestation
    assert any("content_hash" in p for p in ag.verify_attestation(rec))


def test_self_attestation_rejected():
    rec = _attested(attested_by="ai-agent")  # == proposed_by
    assert any("distinct" in p for p in ag.verify_attestation(rec))


def test_missing_multisource_evidence_rejected():
    rec = _record()
    rec["evidence"] = {"ci_runs": [], "review_ids": [], "trace_ids": [], "experiment_ids": []}
    rec["attestation"] = ag.build_attestation(rec, attested_by="ci-bot", ci_run="ci-1", attested_at=AT)
    assert any("multi-source" in p for p in ag.verify_attestation(rec))


def test_missing_attestation_block():
    assert ag.verify_attestation(_record()) == ["missing attestation block"]


def test_signature_valid_with_key():
    rec = _attested(key="s3cret")
    assert ag.verify_attestation(rec, key="s3cret") == []


def test_signature_invalid_with_wrong_key():
    rec = _attested(key="s3cret")
    assert any("signature" in p for p in ag.verify_attestation(rec, key="WRONG"))


# --------------------------------------------------------------------------- #
# CI validator + stamp CLI
# --------------------------------------------------------------------------- #

def _write_record(tmp_path: Path, rec: dict, name: str = "GATE6-1.yaml") -> Path:
    exp = tmp_path / "experiments"
    exp.mkdir(exist_ok=True)
    (exp / name).write_text(yaml.safe_dump({"gate_6_record": rec}, sort_keys=False), encoding="utf-8")
    return exp


def test_check_inert_when_no_experiments(tmp_path):
    assert cga.main(["--experiments", str(tmp_path / "nope")]) == 0


def test_check_deferred_record_is_inert(tmp_path):
    exp = _write_record(tmp_path, _record(status="deferred"))
    assert cga.main(["--experiments", str(exp)]) == 0  # not applied -> nothing to attest


def test_check_applied_unattested_fails(tmp_path):
    exp = _write_record(tmp_path, _record(status="applied"))  # no attestation block
    assert cga.main(["--experiments", str(exp)]) == 1


def test_check_applied_attested_passes(tmp_path):
    exp = _write_record(tmp_path, _attested())
    assert cga.main(["--experiments", str(exp)]) == 0


def test_stamp_then_verify_roundtrip(tmp_path):
    exp = _write_record(tmp_path, _record(status="applied"), name="GATE6-2.yaml")
    rec_path = exp / "GATE6-2.yaml"
    assert ag.main(["stamp", "--record", str(rec_path), "--attested-by", "ci-bot", "--ci-run", "99"]) == 0
    assert ag.main(["verify", "--record", str(rec_path)]) == 0
    assert cga.main(["--experiments", str(exp)]) == 0


def test_forged_attester_with_key_is_rejected():
    # rewriting attested_by WITHOUT re-signing must break the HMAC (identity is bound)
    rec = _attested(key="prod-key")
    rec["attestation"]["attested_by"] = "ciso-alice"  # forged, not re-signed
    assert any("signature" in p for p in ag.verify_attestation(rec, key="prod-key"))


def test_forged_attested_at_and_ci_run_rejected():
    rec = _attested(key="prod-key")
    rec["attestation"]["attested_at"] = "2020-01-01T00:00:00Z"
    rec["attestation"]["ci_run"] = "fake-9999"
    assert any("signature" in p for p in ag.verify_attestation(rec, key="prod-key"))


def test_signed_record_without_key_fails_closed():
    # a record that advertises a signature, verified WITHOUT the key, must fail closed
    rec = _attested(key="prod-key")
    assert any("no GATE6_ATTEST_KEY" in p for p in ag.verify_attestation(rec, key=None))


def test_case_only_distinct_identities_rejected():
    rec = _record()
    rec["proposed_by"] = "Alice"
    rec["approval"] = {"approved_by": "alice"}
    rec["attestation"] = ag.build_attestation(rec, attested_by=" ALICE ", ci_run="ci-1", attested_at=AT)
    assert any("distinct" in p for p in ag.verify_attestation(rec))


def test_non_dict_yaml_doc_skipped_not_crashed(tmp_path):
    exp = tmp_path / "experiments"
    exp.mkdir()
    (exp / "stray.yaml").write_text("- a\n- b\n", encoding="utf-8")  # a list, not a record
    assert cga.main(["--experiments", str(exp)]) == 0  # skipped, no crash
