#!/usr/bin/env python3
"""tests/test_check_gate6_record.py — GATE-6 evidence validator (R-2 / ADR-003).

Proves: a complete GATE-6 record passes; an incomplete record, a non-zero
max_quality_drop, a missing gate6_id, and a dangling record reference all fail;
and a missing/empty event store is clean (gitignored runtime, loop off).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_gate6_record as cg  # noqa: E402  (import after path manipulation)


def _golden(gid: str = "GATE6-20260622-0001") -> dict:
    return {
        "gate_6_record": {
            "id": gid,
            "hypothesis": "If concurrency 4->6, T1 rises >=10pp without T7 drop.",
            "baseline_metrics": {"T1_busy_fraction": 0.11, "T7_quality": 1.00},
            "proposed_change": {
                "description": "raise dispatch cap 4->6",
                "config_diff_hash": "sha256:abc",
                "blast_radius": "medium",
            },
            "guardrails": {"max_quality_drop": 0, "rollback_condition": "revert if T7 drops"},
            "evidence": {"trace_ids": ["t1"], "ci_runs": ["c1"], "review_ids": ["r1"]},
            "approval": {"required_role": "cxo", "approved_by": "cto", "approved_at": "2026-06-22"},
            "rollout": {"mode": "shadow", "feature_flag": "cap6"},
            "result": {"status": "deferred"},
        }
    }


def _tuning_event(gate6_id: str | None, change_type: str = "tune_concurrency", ev_id: str = "ev-1") -> dict:
    ev = {
        "id": ev_id,
        "event_type": "gate6_tuning",
        "ticket_id": "DAS-1382",
        "created_at": "2026-06-22T00:00:00Z",
        "change_type": change_type,
    }
    if gate6_id is not None:
        ev["gate6_id"] = gate6_id
    return ev


def _setup(tmp_path: Path, events: list[dict], records: list[dict]) -> tuple[Path, Path]:
    exp = tmp_path / "experiments"
    exp.mkdir()
    for i, rec in enumerate(records):
        (exp / f"GATE6-rec-{i}.yaml").write_text(yaml.safe_dump(rec), encoding="utf-8")
    ev = tmp_path / ".events.jsonl"
    ev.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return ev, exp


def _run(tmp_path: Path, events: list[dict], records: list[dict]) -> int:
    ev, exp = _setup(tmp_path, events, records)
    return cg.main(["--events", str(ev), "--experiments", str(exp)])


# --------------------------------------------------------------------------- #
# record_complete unit checks
# --------------------------------------------------------------------------- #

def test_golden_record_is_complete():
    assert cg.record_complete(_golden()["gate_6_record"]) == []


def test_missing_field_flagged():
    rec = _golden()["gate_6_record"]
    del rec["hypothesis"]
    assert any("hypothesis" in p for p in cg.record_complete(rec))


def test_nonzero_max_quality_drop_flagged():
    rec = _golden()["gate_6_record"]
    rec["guardrails"]["max_quality_drop"] = 0.05
    assert any("max_quality_drop" in p for p in cg.record_complete(rec))


# --------------------------------------------------------------------------- #
# end-to-end exit codes
# --------------------------------------------------------------------------- #

def test_complete_record_passes(tmp_path):
    gid = "GATE6-20260622-0001"
    assert _run(tmp_path, [_tuning_event(gid)], [_golden(gid)]) == 0


def test_incomplete_record_fails(tmp_path):
    gid = "GATE6-20260622-0002"
    rec = _golden(gid)
    del rec["gate_6_record"]["result"]
    assert _run(tmp_path, [_tuning_event(gid)], [rec]) == 1


def test_nonzero_quality_drop_fails(tmp_path):
    gid = "GATE6-20260622-0003"
    rec = _golden(gid)
    rec["gate_6_record"]["guardrails"]["max_quality_drop"] = 1
    assert _run(tmp_path, [_tuning_event(gid)], [rec]) == 1


def test_missing_gate6_id_fails(tmp_path):
    assert _run(tmp_path, [_tuning_event(None)], [_golden()]) == 1


def test_dangling_record_reference_fails(tmp_path):
    assert _run(tmp_path, [_tuning_event("GATE6-DOES-NOT-EXIST")], [_golden()]) == 1


def test_non_tuning_events_are_clean(tmp_path):
    ev = {"event_type": "routing_decision", "ticket_id": "DAS-1", "created_at": "2026-06-22T00:00:00Z"}
    assert _run(tmp_path, [ev], []) == 0


def test_empty_event_store_is_clean(tmp_path):
    assert _run(tmp_path, [], []) == 0


def test_missing_event_store_is_clean(tmp_path):
    exp = tmp_path / "experiments"
    exp.mkdir()
    assert cg.main(["--events", str(tmp_path / "nope.jsonl"), "--experiments", str(exp)]) == 0


def test_template_file_is_not_treated_as_record(tmp_path):
    # A GATE6-TEMPLATE.yaml in experiments/ must be ignored, so a tuning event
    # referencing the template id has NO backing record -> fail.
    exp = tmp_path / "experiments"
    exp.mkdir()
    (exp / "GATE6-TEMPLATE.yaml").write_text(yaml.safe_dump(_golden("GATE6-TEMPLATE-1")), encoding="utf-8")
    ev = tmp_path / ".events.jsonl"
    ev.write_text(json.dumps(_tuning_event("GATE6-TEMPLATE-1")) + "\n", encoding="utf-8")
    assert cg.main(["--events", str(ev), "--experiments", str(exp)]) == 1


# --- review-found bypass / hardening regression tests ---

def test_gate6_tuning_marker_missing_change_type_fails(tmp_path):
    ev = {"id": "ev-x", "event_type": "gate6_tuning", "ticket_id": "DAS-1382",
          "created_at": "2026-06-22T00:00:00Z"}  # marker but no change_type / gate6_id
    assert _run(tmp_path, [ev], []) == 1


def test_gate6_tuning_unlisted_change_type_fails(tmp_path):
    ev = {"id": "ev-x", "event_type": "gate6_tuning", "ticket_id": "DAS-1382",
          "created_at": "2026-06-22T00:00:00Z", "change_type": "tune_timeout"}
    assert _run(tmp_path, [ev], []) == 1


def test_missing_config_diff_hash_flagged():
    rec = _golden()["gate_6_record"]
    del rec["proposed_change"]["config_diff_hash"]
    assert any("config_diff_hash" in p for p in cg.record_complete(rec))


def test_placeholder_config_diff_hash_flagged():
    rec = _golden()["gate_6_record"]
    rec["proposed_change"]["config_diff_hash"] = "sha256:REPLACE"
    assert any("config_diff_hash" in p for p in cg.record_complete(rec))


def test_bool_max_quality_drop_flagged():
    rec = _golden()["gate_6_record"]
    rec["guardrails"]["max_quality_drop"] = False
    assert any("max_quality_drop" in p for p in cg.record_complete(rec))


def test_applied_record_requires_evidence_and_approver():
    rec = _golden()["gate_6_record"]
    rec["result"]["status"] = "applied"
    rec["evidence"] = {"trace_ids": [], "ci_runs": [], "review_ids": [], "experiment_ids": []}
    rec["approval"] = {"required_role": "cxo", "approved_by": "", "approved_at": ""}
    probs = cg.record_complete(rec)
    assert any("approved_by" in p for p in probs)
    assert any("evidence" in p for p in probs)


def test_duplicate_record_id_fails(tmp_path):
    gid = "GATE6-DUP-1"
    exp = tmp_path / "experiments"
    exp.mkdir()
    (exp / "GATE6-a.yaml").write_text(yaml.safe_dump(_golden(gid)), encoding="utf-8")
    (exp / "GATE6-b.yaml").write_text(yaml.safe_dump(_golden(gid)), encoding="utf-8")
    ev = tmp_path / ".events.jsonl"
    ev.write_text(json.dumps(_tuning_event(gid)) + "\n", encoding="utf-8")
    assert cg.main(["--events", str(ev), "--experiments", str(exp)]) == 1


def test_non_dict_proposed_change_flagged():
    rec = _golden()["gate_6_record"]
    rec["proposed_change"] = "raise dispatch cap 4->6"  # collapsed to a one-line string
    assert any("proposed_change must be a mapping" in p for p in cg.record_complete(rec))


def test_status_with_whitespace_still_requires_evidence():
    rec = _golden()["gate_6_record"]
    rec["result"]["status"] = " applied "  # whitespace padding must not dodge the rule
    rec["evidence"] = {"trace_ids": [], "ci_runs": [], "review_ids": [], "experiment_ids": []}
    rec["approval"] = {"required_role": "cxo", "approved_by": "", "approved_at": ""}
    assert any("approved_by" in p for p in cg.record_complete(rec))


def test_non_dict_guardrails_does_not_crash():
    rec = _golden()["gate_6_record"]
    rec["guardrails"] = "see policy doc"  # truthy non-dict must not raise AttributeError
    assert any("guardrails must be a mapping" in p for p in cg.record_complete(rec))
