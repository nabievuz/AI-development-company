
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import gen_recovery_evidence as gre


def _extract_json(md: str) -> dict:
    block = md.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(block)


def test_generate_writes_passing_recovery_evidence(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    result = gre.generate(runs, work_root=tmp_path)

    assert result["overall_ok"] is True
    summary = Path(result["summary_path"])
    assert summary.name == "run-summary.md"
    assert summary.parent.parent == runs
    assert summary.parent.name == result["run_id"]

    text = summary.read_text(encoding="utf-8")
    assert "Recovery drill evidence — PASS" in text

    proof = _extract_json(text)
    kd = proof["kill_drill"]
    assert kd["killed"] is True
    assert kd["zero_lost"] is True and kd["zero_duplicated"] is True
    assert kd["chain_clean"] is True and kd["ledger_reconciles"] is True
    assert proof["fork_drill"]["original_intact"] is True
    assert proof["fork_drill"]["divergent"] is True
    assert proof["overall_ok"] is True


def test_generate_leaves_only_run_summary(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    result = gre.generate(runs, work_root=tmp_path)
    run_dir = Path(result["summary_path"]).parent

    assert [p.name for p in run_dir.iterdir()] == ["run-summary.md"]


def test_miss_path_is_honest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    def _fake_kill(*_args: object) -> dict:
        return {
            "run_id": "MISSRUN", "wave_run_ids": ["MISSRUN"], "killed": False,
            "zero_lost": False, "zero_duplicated": True, "chain_clean": True,
            "ledger_reconciles": True, "resumed": [], "ok": False,
        }

    def _fake_fork(*_args: object) -> dict:
        return {"base_run": "b", "fork_run": "f", "divergent": True,
                "original_intact": True, "chain_clean": True, "ok": True}

    monkeypatch.setattr(gre.kill_drill, "run_kill_drill", _fake_kill)
    monkeypatch.setattr(gre.kill_drill, "run_fork_drill", _fake_fork)

    result = gre.generate(tmp_path / "runs", work_root=tmp_path)
    assert result["overall_ok"] is False
    text = Path(result["summary_path"]).read_text(encoding="utf-8")
    assert "MISS" in text
    assert "resumed with zero loss" not in text
    assert gre.main(["--runs-dir", str(tmp_path / "runs2")]) == 1
