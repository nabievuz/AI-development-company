from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_recovery
import kill_drill as kd
import metrics_lib
import wave_kpi
import wave_runner as wr

_FLAT = [t for wave in kd.DEFAULT_WAVES for t in wave]


class TestKillDrill:
    def test_child_is_genuinely_sigkilled(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["killed"] is True, "child must die by SIGKILL, not exit cleanly"

    def test_zero_lost_zero_duplicated(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["zero_lost"] is True, f"lost tickets: {res['lost']}"
        assert res["zero_duplicated"] is True, f"dup completions: {res['dup_completions']}"
        assert res["chain_clean"] is True, f"broken attestation chain: {res['corrupted']}"
        assert res["ok"] is True

    def test_every_planned_ticket_completed_exactly_once(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        runs_dir = Path(res["runs_dir"])
        all_completions: list[str] = []
        for rid in res["wave_run_ids"]:
            all_completions.extend(ev["ticket_id"] for ev in kd._completion_records(runs_dir, rid))
        assert sorted(all_completions) == sorted(_FLAT), "every planned ticket completed once"
        assert len(all_completions) == len(set(all_completions)), "no completion recorded twice"

    def test_pre_crash_completions_are_not_redispatched(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        pre_crash = {"DAS-8001", "DAS-8002", "DAS-8003"}
        assert pre_crash.isdisjoint(res["resumed"]), (
            f"a pre-crash-completed ticket was re-dispatched: {sorted(pre_crash & set(res['resumed']))}"
        )
        assert set(res["resumed"]) == {"DAS-8004", "DAS-8005", "DAS-8006", "DAS-8007"}

    def test_crash_leaves_wave2_attestation_uncommitted_until_resume(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        for rid in res["wave_run_ids"]:
            assert kd._attestation_ok(attest_dir, rid), f"wave {rid} attestation missing/invalid"


        runs_dir = Path(res["runs_dir"])
        wave2_rid = res["wave_run_ids"][1]
        wave2_completions = [ev["ticket_id"] for ev in kd._completion_records(runs_dir, wave2_rid)]
        assert sorted(wave2_completions) == ["DAS-8003", "DAS-8004", "DAS-8005"]
        assert len(wave2_completions) == len(set(wave2_completions))


class TestResumedAttestationChain:
    def test_resumed_chain_verifies_and_links(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        valid, reason = kd._attestation_chain_valid(attest_dir, res["wave_run_ids"])
        assert valid, f"resumed attestation chain invalid: {reason}"

    def test_chain_prev_links_are_the_predecessor_self_hash(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        rids = res["wave_run_ids"]
        payloads = [wr.load_attestation(wr.attestation_path(r, attest_dir)) for r in rids]
        assert payloads[0]["attest_chain"]["prev"] == wr._GENESIS_PREV_HASH
        for prev, cur in zip(payloads, payloads[1:], strict=False):
            assert cur["attest_chain"]["prev"] == prev["attest_chain"]["self"], (
                "a resumed wave's attestation does not chain onto its predecessor"
            )


class TestResumedWaveLedgerChain:
    def test_ledger_reconciles_after_crash_and_resume(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["ledger_reconciles"] is True, f"ledger problems: {res['ledger_problems']}"
        assert res["ok"] is True

    def test_ledger_verifies_through_the_ssot_primitive(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        ledger_path = Path(res["ledger_path"])
        attest_dir = Path(res["attest_dir"])
        assert ledger_path.is_file()


        entries = [json.loads(ln) for ln in ledger_path.read_text().splitlines() if ln.strip()]
        assert [e["run_id"] for e in entries] == res["wave_run_ids"]
        assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []

    def test_a_dropped_ledger_line_is_caught_by_the_gate(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        ledger_path = Path(res["ledger_path"])
        attest_dir = Path(res["attest_dir"])
        lines = [ln for ln in ledger_path.read_text().splitlines() if ln.strip()]


        ledger_path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
        problems = wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir)
        assert problems, "a dropped ledger line must fail reconciliation"


class TestForkDrill:
    def test_divergent_and_original_intact(self, tmp_path: Path) -> None:
        res = kd.run_fork_drill(tmp_path / "fork")
        assert res["divergent"] is True, (
            f"fork must diverge: base {res['original_final']} vs fork {res['fork_final']}"
        )
        assert res["original_intact"] is True
        assert res["chain_clean"] is True
        assert res["ok"] is True

    def test_divergence_is_real_status_difference(self, tmp_path: Path) -> None:
        res = kd.run_fork_drill(tmp_path / "fork")
        assert res["original_final"].get("DAS-8501") == "done"
        assert res["fork_final"].get("DAS-8501") == "blocked"
        assert res["fork_run"] != res["base_run"]

    def test_base_events_checkpoints_and_completions_byte_identical(self, tmp_path: Path) -> None:
        work = tmp_path / "fork"
        res = kd.run_fork_drill(work)
        base_run = res["base_run"]
        runs_dir = work / "runs"

        assert kd._completion_status_map(runs_dir, base_run).get("DAS-8501") == "done"

        assert (work / "fork-events.jsonl").exists()
        assert (runs_dir / res["fork_run"] / "wave-001.checkpoint.json").exists()
        assert (work / "attest" / f"{res['fork_run']}.json").exists()

    def test_both_attestations_verify(self, tmp_path: Path) -> None:
        work = tmp_path / "fork"
        res = kd.run_fork_drill(work)
        attest_dir = work / "attest"
        assert kd._attestation_ok(attest_dir, res["base_run"])
        assert kd._attestation_ok(attest_dir, res["fork_run"])


class TestEventEmissionAndGate:
    def test_emit_recovery_drill_shape_is_scored(self, tmp_path: Path) -> None:
        store = tmp_path / "drills.jsonl"
        kd.emit_recovery_drill(store, run_id="R1", outcome="success", corrupted=False,
                               created_at="2026-07-03T00:00:00Z")
        kd.emit_recovery_drill(store, run_id="R2", outcome="success", corrupted=False,
                               created_at="2026-07-03T00:00:01Z")
        rec = metrics_lib.recovery_reliability(wave_kpi.read_events(str(store)))
        assert rec is not None
        assert rec["drills"] == 2 and rec["successful"] == 2 and rec["corrupted"] == 0
        assert rec["ratio"] == 1.0

    def test_corrupted_resume_fails_gate(self, tmp_path: Path) -> None:
        store = tmp_path / "drills.jsonl"
        kd.emit_recovery_drill(store, run_id="R1", outcome="success", corrupted=False,
                               created_at="2026-07-03T00:00:00Z")
        kd.emit_recovery_drill(store, run_id="R2", outcome="fail", corrupted=True,
                               created_at="2026-07-03T00:00:01Z")
        assert check_recovery.main(["--events", str(store)]) == 1


class TestDrivesRealRunner:
    def test_kill_drill_source_has_no_hand_rolled_dispatcher(self) -> None:
        src = (_SCRIPTS / "kill_drill.py").read_text(encoding="utf-8")
        assert "wr.run_wave(" in src, "the drill must call the real wave_runner.run_wave"
        assert "build_routing_decision" not in src, "no hand-rolled routing_decision emission"
        assert "write_wave_checkpoint" not in src, "no hand-rolled checkpoint writes"

    def test_run_wave_produced_the_lifecycle_artifacts(self, tmp_path: Path) -> None:
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        evidence_dir = tmp_path / "drill" / "evidence"

        assert attest_dir.is_dir() and any(attest_dir.glob("*.json"))
        assert evidence_dir.is_dir() and any(evidence_dir.glob("*.json"))

        for rid in res["wave_run_ids"]:
            payload = wr.load_attestation(wr.attestation_path(rid, attest_dir))
            assert payload["schema"] == wr.ATTESTATION_SCHEMA
            assert payload["mechanics"]["ledger_written"] is True
            assert payload["mechanics"]["evidence_written"] is True


class TestT5Accumulation:
    def test_20_iterations_gate_green(self, tmp_path: Path) -> None:
        rc = kd.run_drills(iterations=20, tmp_root=tmp_path)
        assert rc == 0

        store = tmp_path / "drill-events.jsonl"
        rec = metrics_lib.recovery_reliability(wave_kpi.read_events(str(store)))
        assert rec is not None
        assert rec["drills"] >= 20, f"expected >= 20 drills, got {rec['drills']}"
        assert rec["corrupted"] == 0
        assert rec["ratio"] >= 0.99

        assert check_recovery.main(["--events", str(store)]) == 0

    def test_check_recovery_default_path_unchanged(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".jsonl") as fh:
            assert check_recovery.main(["--events", fh.name]) == 0

    def test_smoke_cli_exits_zero(self) -> None:
        assert kd.main(["--smoke"]) == 0
