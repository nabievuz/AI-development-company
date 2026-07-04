#!/usr/bin/env python3
"""tests/test_snapshot_evidence.py — committed KPI evidence (P13 / DAS-1460).

Proves the committed-evidence mechanism:
- ``snapshot_evidence`` writes a TRACKED, REDACTED ``metrics/evidence/<run_id>.json``
  per counted run, keyed by ``run_id``, whose contents match the run's events;
- it is inert when no runs exist (writes nothing, fabricates nothing);
- ``check_metric_gaming`` REQUIRES a committed evidence file for a counted run:
  (a) run WITH evidence passes, (b) counted run WITHOUT evidence fails,
  (c) no completions => inert exit 0 — with the R-9 gaming check preserved;
- ``metrics/evidence/`` is committed, not gitignored (a ``.gitkeep`` is tracked).

All snapshot writes target a ``tmp_path`` — never the real ``metrics/evidence/``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_metric_gaming as cmg  # noqa: E402  (import after path manipulation)
import snapshot_evidence as se  # noqa: E402
from dispatch_emitter import DispatchRecord, build_wave_events  # noqa: E402

# Fields that must NEVER appear verbatim in a redacted snapshot (payload / secrets).
_FORBIDDEN_KEYS = {
    "context_contract",
    "allowed_tools",
    "secrets_policy",
    "exit_contract",
    "prompt",
    "output",
    "gen_ai.request.model",
}
_PR_URL = "https://example/pr/42"


def _record(
    *,
    ticket_id: str = "DAS-9001",
    run_id: str = "run-9001",
    start: str = "2026-07-03T00:00:00Z",
    end: str = "2026-07-03T00:05:00Z",
    model: str = "sonnet",
    outcome: str = "success",
    merged_pr: object = _PR_URL,
    ci_status: str = "green",
    t7_pass: object = "pass",
    t7_score: float = 0.95,
) -> DispatchRecord:
    return DispatchRecord(
        ticket_id=ticket_id,
        run_id=run_id,
        goal="organism-ws3-slice2",
        engine_version="1.2.0",
        model=model,
        role_key="qa-lead",
        start=start,
        end=end,
        outcome=outcome,
        merged_pr=merged_pr,
        ci_status=ci_status,
        t7_pass=t7_pass,
        t7_score=t7_score,
    )


def _events(*records: DispatchRecord) -> list[dict]:
    return build_wave_events(list(records))


def _write_store(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Snapshot builder
# --------------------------------------------------------------------------- #


def test_snapshot_writes_file_keyed_by_run_id(tmp_path: Path):
    events = _events(_record(run_id="run-A"))
    written = se.snapshot_all(events, tmp_path)
    assert written == [tmp_path / "run-A.json"]
    assert written[0].exists()
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["run_id"] == "run-A"
    assert data["schema"] == se.EVIDENCE_SCHEMA


def test_snapshot_contents_match_event_data(tmp_path: Path):
    events = _events(_record(run_id="run-B", model="haiku", outcome="success", t7_score=0.9))
    se.snapshot_all(events, tmp_path)
    data = json.loads((tmp_path / "run-B.json").read_text(encoding="utf-8"))
    assert data["tickets"] == ["DAS-9001"]
    assert len(data["completions"]) == 1
    comp = data["completions"][0]
    assert comp["model"] == "haiku"
    assert comp["outcome"] == "success"
    assert comp["ci_status"] == "green"
    assert comp["merged_pr"] is True
    assert comp["t7_pass"] is True
    assert comp["counted"] is True
    # wave_kpi summary + span aggregate are present and real (one paired run).
    assert data["kpi_summary"]["runs_completed"] == 1
    assert data["span_aggregate"]["runs"] == 1


# --------------------------------------------------------------------------- #
# F-2 regression — kpi_summary.model_mix must reflect the run_end model
# --------------------------------------------------------------------------- #


def test_snapshot_model_mix_counts_run_end_model(tmp_path: Path):
    """ORGANISM audit F-2: model_mix was read off run_start (which carries no
    ``model``), so a real opus/sonnet run snapshotted an all-zero mix. It must now
    tally the run_end completion's model."""
    events = _events(_record(run_id="run-mix", model="opus"))
    se.snapshot_all(events, tmp_path)
    data = json.loads((tmp_path / "run-mix.json").read_text(encoding="utf-8"))
    assert data["kpi_summary"]["model_mix"] == {"opus": 1, "sonnet": 0, "haiku": 0}
    # And it is internally consistent with the completion it recorded.
    assert sum(data["kpi_summary"]["model_mix"].values()) == len(data["completions"])


def test_snapshot_model_mix_multi_tier(tmp_path: Path):
    events = _events(
        _record(ticket_id="DAS-1", run_id="r1", model="opus"),
        _record(ticket_id="DAS-2", run_id="r2", model="haiku"),
    )
    se.snapshot_all(events, tmp_path)
    d1 = json.loads((tmp_path / "r1.json").read_text(encoding="utf-8"))
    d2 = json.loads((tmp_path / "r2.json").read_text(encoding="utf-8"))
    assert d1["kpi_summary"]["model_mix"] == {"opus": 1, "sonnet": 0, "haiku": 0}
    assert d2["kpi_summary"]["model_mix"] == {"opus": 0, "sonnet": 0, "haiku": 1}


def test_reconcile_repairs_zeroed_model_mix():
    """The F-2 repair path: a pre-fix snapshot (mix all-zero, completion carries a
    model) is corrected from its own completions and is idempotent."""
    evidence = {
        "completions": [{"model": "opus"}],
        "kpi_summary": {"busy_fraction": 1.0, "runs_completed": 1,
                        "model_mix": {"opus": 0, "sonnet": 0, "haiku": 0}},
    }
    assert se.reconcile_model_mix(evidence) is True
    assert evidence["kpi_summary"]["model_mix"] == {"opus": 1, "sonnet": 0, "haiku": 0}
    assert se.reconcile_model_mix(evidence) is False  # already consistent


def test_reconcile_noop_when_already_consistent():
    evidence = {
        "completions": [{"model": "sonnet"}],
        "kpi_summary": {"model_mix": {"opus": 0, "sonnet": 1, "haiku": 0}},
    }
    assert se.reconcile_model_mix(evidence) is False


def test_committed_evidence_model_mix_is_consistent():
    """Anti-regression over the REAL committed evidence: every snapshot's model_mix
    must account for the models its completions carry (F-2 can never re-slip into
    git history). Guards the exact anomaly: busy_fraction set but model_mix zeroed."""
    evidence_dir = REPO_ROOT / "metrics" / "evidence"
    files = sorted(evidence_dir.glob("*.json"))
    assert files, "expected committed evidence snapshots to exist"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        ks = data["kpi_summary"]
        modeled = [c for c in data["completions"]
                   if str(c.get("model") or "").lower() in ("opus", "sonnet", "haiku")]
        assert sum(ks["model_mix"].values()) == len(modeled), (
            f"{path.name}: model_mix {ks['model_mix']} inconsistent with "
            f"{len(modeled)} modeled completion(s)"
        )
        # The exact F-2 shape: a busy run with modeled completions cannot report a
        # zeroed mix.
        if ks.get("busy_fraction") and modeled:
            assert sum(ks["model_mix"].values()) >= ks["runs_completed"], (
                f"{path.name}: busy run with zeroed model_mix (F-2)"
            )


def test_snapshot_is_redacted(tmp_path: Path):
    """No secret/PII/payload fields; presence-only booleans, no PR URL body."""
    events = _events(_record(run_id="run-C", merged_pr=_PR_URL))
    se.snapshot_all(events, tmp_path)
    text = (tmp_path / "run-C.json").read_text(encoding="utf-8")
    # The raw PR URL must not leak — merged_pr is reduced to a boolean.
    assert _PR_URL not in text
    data = json.loads(text)
    comp = data["completions"][0]
    assert isinstance(comp["merged_pr"], bool)
    assert isinstance(comp["t7_pass"], bool)

    def _keys(obj) -> set[str]:
        found: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                found.add(k)
                found |= _keys(v)
        elif isinstance(obj, list):
            for item in obj:
                found |= _keys(item)
        return found

    assert not (_keys(data) & _FORBIDDEN_KEYS)


def test_snapshot_inert_when_no_events(tmp_path: Path):
    assert se.snapshot_all([], tmp_path) == []
    assert list(tmp_path.glob("*.json")) == []


def test_snapshot_skips_uncompleted_run(tmp_path: Path):
    """A store with only a run_start (no completion) yields no snapshot."""
    start_only = [e for e in _events(_record(run_id="run-D")) if e["event_type"] == "run_start"]
    assert se.snapshot_all(start_only, tmp_path) == []


# --------------------------------------------------------------------------- #
# Run-close wiring (DAS-1462) — the exact call /daslab-cycle step 6 makes
# --------------------------------------------------------------------------- #


def test_run_close_wiring_writes_committed_evidence_file(tmp_path: Path):
    """A run's emitted events -> ``write_run_evidence`` -> a committed file.

    Mirrors the /daslab-cycle step-6 run-close wiring: after
    ``dispatch_emitter.emit_wave`` appends a wave's ``run_start``/``run_end``/span
    triplet, the orchestrator passes those same events plus the wave ``run_id`` to
    ``snapshot_evidence.write_run_evidence(events, run_id, EVIDENCE_DIR)``. This
    proves that single call materialises a tracked, redacted
    ``metrics/evidence/<run_id>.json`` whose contents match the run's events —
    without ``snapshot_all`` (the run-close writes exactly one run).
    """
    run_id = "run-close-1462"
    events = _events(_record(run_id=run_id, model="opus", t7_score=0.97))

    path = se.write_run_evidence(events, run_id, tmp_path)

    assert path == tmp_path / f"{run_id}.json"
    assert path.exists(), "run-close must write a committed evidence file"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == run_id
    assert data["schema"] == se.EVIDENCE_SCHEMA
    assert data["tickets"] == ["DAS-9001"]
    assert len(data["completions"]) == 1
    assert data["completions"][0]["counted"] is True
    # Redaction holds through the run-close path too: no raw PR URL body.
    assert _PR_URL not in path.read_text(encoding="utf-8")
    # The written file satisfies the committed-evidence gate for this counted run.
    assert se.missing_evidence_runs(events, tmp_path) == []


# --------------------------------------------------------------------------- #
# Evidence-presence helpers
# --------------------------------------------------------------------------- #


def test_missing_evidence_runs_flags_counted_run_without_file(tmp_path: Path):
    events = _events(_record(run_id="run-E"))
    assert se.missing_evidence_runs(events, tmp_path) == ["run-E"]
    se.snapshot_all(events, tmp_path)
    assert se.missing_evidence_runs(events, tmp_path) == []


def test_counted_run_ids_excludes_gamed_and_run_id_less(tmp_path: Path):
    # A gamed completion (no merged PR) is NOT counted, so needs no evidence.
    gamed = _events(_record(run_id="run-F", merged_pr=None))
    assert se.counted_run_ids(gamed) == set()
    assert se.missing_evidence_runs(gamed, tmp_path) == []


# --------------------------------------------------------------------------- #
# check_metric_gaming — the committed-evidence gate teeth
# --------------------------------------------------------------------------- #


def test_gate_counted_run_without_evidence_fails(tmp_path: Path):
    store = _write_store(tmp_path, _events(_record(run_id="run-G")))
    empty_evidence = tmp_path / "evidence"
    rc = cmg.main(["--events", str(store), "--evidence-dir", str(empty_evidence)])
    assert rc == 1


def test_gate_counted_run_with_evidence_passes(tmp_path: Path):
    events = _events(_record(run_id="run-H"))
    store = _write_store(tmp_path, events)
    evidence = tmp_path / "evidence"
    se.snapshot_all(events, evidence)
    rc = cmg.main(["--events", str(store), "--evidence-dir", str(evidence)])
    assert rc == 0


def test_gate_inert_when_no_completions(tmp_path: Path):
    assert cmg.main(["--events", str(tmp_path / "nope.jsonl"),
                     "--evidence-dir", str(tmp_path / "evidence")]) == 0


def test_gate_gaming_violation_still_fails(tmp_path: Path):
    # R-9 preserved: a gamed completion fails regardless of evidence presence.
    store = _write_store(tmp_path, _events(_record(run_id="run-I", ci_status="red")))
    evidence = tmp_path / "evidence"
    se.snapshot_all(_events(_record(run_id="run-I", ci_status="red")), evidence)
    assert cmg.main(["--events", str(store), "--evidence-dir", str(evidence)]) == 1


# --------------------------------------------------------------------------- #
# metrics/evidence/ is committed, not gitignored
# --------------------------------------------------------------------------- #


def test_evidence_dir_is_committed_not_ignored():
    gitkeep = REPO_ROOT / "metrics" / "evidence" / ".gitkeep"
    assert gitkeep.is_file(), "metrics/evidence/.gitkeep must exist (tracked dir)"
    # A snapshot path under metrics/evidence/ must NOT be gitignored.
    probe = REPO_ROOT / "metrics" / "evidence" / "run-probe.json"
    result = subprocess.run(
        ["git", "check-ignore", str(probe)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # git check-ignore exits 1 when the path is NOT ignored (the required state).
    assert result.returncode == 1, (
        f"metrics/evidence/ is gitignored — snapshots would not be committed: "
        f"{result.stdout}"
    )
