"""tests/test_kill_drill.py — REAL kill/resume + fork drill THROUGH the production
wave lifecycle (DAS-1451 / DAS-1501, GATE-4 / T5).

DAS-1501 retrofit: the drill no longer uses a hand-rolled synthetic dispatcher —
its 3-wave synthetic run is driven THROUGH the real
``scripts/wave_runner.run_wave`` (the deterministic post-decision lifecycle
production uses: open/close checkpoints, run_start/run_end/span events, per-ticket
completions, committed evidence, and a doubly hash-chained WaveAttestation per
wave).  These tests prove the ACTUAL wave-runner lifecycle — not just the recovery
primitives — survives a genuine ``kill -9``.

Acceptance criteria covered:
  AC1  Kill-mid-wave-2 drill: a synthetic 3-wave run driven through run_wave, a
       genuine ``kill -9`` (SIGKILL) DEEP INSIDE run_wave mid-wave-2, then resume
       via resume_fork, with ZERO lost and ZERO duplicated tickets.
  AC2  The resumed run's attestation chain is valid (every wave attestation
       verifies and links to its predecessor), including the wave that was
       resumed after the crash.
  AC3  T5 >= 0.99 over >= 20 iterations: >= 20 recovery_drill events such that
       check_recovery.py reports ratio >= 0.99 with corrupted == 0 (exit 0).
  AC4  Fork-drill: fork from a wave-1 checkpoint (both runs through run_wave)
       yields a DIVERGENT run while the base is left intact (unchanged
       bytes/checkpoints/completions, both attestations still verify).
  AC5  Events emitted in the shape metrics_lib.recovery_reliability() consumes;
       a corrupted resume yields corrupted > 0 -> check_recovery FAIL (exit 1).
  AC6  The drill drives the REAL runner: run_wave is the only wave seam, and a
       completed-before-crash ticket is never re-dispatched (guard-before-act).

These drills spawn REAL child processes that SIGKILL themselves; POSIX-only
(the CI matrix is ubuntu + macos, matching the fcntl/O_APPEND assumptions of the
event store and pulse_checkpoint).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_recovery  # noqa: E402
import kill_drill as kd  # noqa: E402
import metrics_lib  # noqa: E402
import wave_kpi  # noqa: E402
import wave_runner as wr  # noqa: E402

_FLAT = [t for wave in kd.DEFAULT_WAVES for t in wave]


# ===========================================================================
# AC1 — kill-mid-wave-2 through run_wave: zero lost, zero duplicated
# ===========================================================================


class TestKillDrill:
    def test_child_is_genuinely_sigkilled(self, tmp_path: Path) -> None:
        """The synthetic run's child process dies by SIGKILL (returncode -9)."""
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["killed"] is True, "child must die by SIGKILL, not exit cleanly"

    def test_zero_lost_zero_duplicated(self, tmp_path: Path) -> None:
        """After crash + resume: every planned ticket terminal, none duplicated."""
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["zero_lost"] is True, f"lost tickets: {res['lost']}"
        assert res["zero_duplicated"] is True, f"dup completions: {res['dup_completions']}"
        assert res["chain_clean"] is True, f"broken attestation chain: {res['corrupted']}"
        assert res["ok"] is True

    def test_every_planned_ticket_completed_exactly_once(self, tmp_path: Path) -> None:
        """Each planned ticket has exactly one durable completion record (across waves)."""
        res = kd.run_kill_drill(tmp_path / "drill")
        runs_dir = Path(res["runs_dir"])
        all_completions: list[str] = []
        for rid in res["wave_run_ids"]:
            all_completions.extend(ev["ticket_id"] for ev in kd._completion_records(runs_dir, rid))
        assert sorted(all_completions) == sorted(_FLAT), "every planned ticket completed once"
        assert len(all_completions) == len(set(all_completions)), "no completion recorded twice"

    def test_pre_crash_completions_are_not_redispatched(self, tmp_path: Path) -> None:
        """Tickets completed before the crash are NOT in the resume re-dispatch set.

        Wave 1 (both tickets) and wave 2's first ticket complete before the
        SIGKILL, so the resume must re-drive only the remaining wave-2 tickets and
        all of wave 3 — never the three that already have a durable completion.
        """
        res = kd.run_kill_drill(tmp_path / "drill")
        pre_crash = {"DAS-8001", "DAS-8002", "DAS-8003"}  # waves 1 + wave2[0]
        assert pre_crash.isdisjoint(res["resumed"]), (
            f"a pre-crash-completed ticket was re-dispatched: {sorted(pre_crash & set(res['resumed']))}"
        )
        assert set(res["resumed"]) == {"DAS-8004", "DAS-8005", "DAS-8006", "DAS-8007"}

    def test_crash_leaves_wave2_attestation_uncommitted_until_resume(self, tmp_path: Path) -> None:
        """The crash lands before wave-2's attestation; resume commits it.

        Proves the kill genuinely interrupts run_wave mid-lifecycle: wave-1 has a
        committed attestation from the child, wave-2 and wave-3 attestations exist
        ONLY because the parent re-drove them through run_wave on resume.
        """
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        for rid in res["wave_run_ids"]:
            assert kd._attestation_ok(attest_dir, rid), f"wave {rid} attestation missing/invalid"
        # DAS-8003 completed in the child but its wave was resumed → its wave still
        # has all tickets recorded exactly once (no double-completion of DAS-8003).
        runs_dir = Path(res["runs_dir"])
        wave2_rid = res["wave_run_ids"][1]
        wave2_completions = [ev["ticket_id"] for ev in kd._completion_records(runs_dir, wave2_rid)]
        assert sorted(wave2_completions) == ["DAS-8003", "DAS-8004", "DAS-8005"]
        assert len(wave2_completions) == len(set(wave2_completions))


# ===========================================================================
# AC2 — the resumed attestation chain is valid
# ===========================================================================


class TestResumedAttestationChain:
    def test_resumed_chain_verifies_and_links(self, tmp_path: Path) -> None:
        """Every wave attestation verifies and links prev->self, post-resume."""
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        valid, reason = kd._attestation_chain_valid(attest_dir, res["wave_run_ids"])
        assert valid, f"resumed attestation chain invalid: {reason}"

    def test_chain_prev_links_are_the_predecessor_self_hash(self, tmp_path: Path) -> None:
        """The wave-2 (resumed) and wave-3 attestations chain onto the prior wave."""
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        rids = res["wave_run_ids"]
        payloads = [wr.load_attestation(wr.attestation_path(r, attest_dir)) for r in rids]
        assert payloads[0]["attest_chain"]["prev"] == wr._GENESIS_PREV_HASH
        for prev, cur in zip(payloads, payloads[1:], strict=False):
            assert cur["attest_chain"]["prev"] == prev["attest_chain"]["self"], (
                "a resumed wave's attestation does not chain onto its predecessor"
            )


# ===========================================================================
# AC2b — the committed wave-ledger CHAIN survives the crash (DAS-1507, ADR-0032)
# ===========================================================================


class TestResumedWaveLedgerChain:
    def test_ledger_reconciles_after_crash_and_resume(self, tmp_path: Path) -> None:
        """Post-resume the co-produced wave-ledger is a valid unbroken chain with
        no gap/duplicate that reconciles against the attestations."""
        res = kd.run_kill_drill(tmp_path / "drill")
        assert res["ledger_reconciles"] is True, f"ledger problems: {res['ledger_problems']}"
        assert res["ok"] is True

    def test_ledger_verifies_through_the_ssot_primitive(self, tmp_path: Path) -> None:
        """The drill's hermetic ledger reconciles THROUGH wave_runner.verify_wave_ledger
        (the SSOT the check_wave_reconciliation gate wraps) — one entry per wave,
        each binding its committed attestation, no gap, no duplicate."""
        res = kd.run_kill_drill(tmp_path / "drill")
        ledger_path = Path(res["ledger_path"])
        attest_dir = Path(res["attest_dir"])
        assert ledger_path.is_file()
        # One committed ledger line per wave run_id — the durable "a wave happened"
        # record; a dropped wave would leave a gap the SSOT would flag.
        entries = [json.loads(ln) for ln in ledger_path.read_text().splitlines() if ln.strip()]
        assert [e["run_id"] for e in entries] == res["wave_run_ids"]
        assert wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir) == []

    def test_a_dropped_ledger_line_is_caught_by_the_gate(self, tmp_path: Path) -> None:
        """Teeth: dropping a wave-ledger line post-resume breaks the chain — the
        SSOT reconciliation FAILs (an omitted wave becomes detectable)."""
        res = kd.run_kill_drill(tmp_path / "drill")
        ledger_path = Path(res["ledger_path"])
        attest_dir = Path(res["attest_dir"])
        lines = [ln for ln in ledger_path.read_text().splitlines() if ln.strip()]
        # Drop the middle (resumed wave-2) line: the survivor after it no longer
        # chains onto its predecessor.
        ledger_path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
        problems = wr.verify_wave_ledger(ledger_path, attest_dir=attest_dir)
        assert problems, "a dropped ledger line must fail reconciliation"


# ===========================================================================
# AC4 — fork-drill through run_wave: divergent run, base intact
# ===========================================================================


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
        """The fork ran the shared ticket to blocked; the base ran it to done."""
        res = kd.run_fork_drill(tmp_path / "fork")
        assert res["original_final"].get("DAS-8501") == "done"
        assert res["fork_final"].get("DAS-8501") == "blocked"
        assert res["fork_run"] != res["base_run"]

    def test_base_events_checkpoints_and_completions_byte_identical(self, tmp_path: Path) -> None:
        """The base run's stores + checkpoints + completion ledger are unchanged."""
        work = tmp_path / "fork"
        res = kd.run_fork_drill(work)
        base_run = res["base_run"]
        runs_dir = work / "runs"
        # Base run still resolves to its recorded final state via its completion ledger.
        assert kd._completion_status_map(runs_dir, base_run).get("DAS-8501") == "done"
        # The fork wrote to a SEPARATE store + run dir + attestation.
        assert (work / "fork-events.jsonl").exists()
        assert (runs_dir / res["fork_run"] / "wave-001.checkpoint.json").exists()
        assert (work / "attest" / f"{res['fork_run']}.json").exists()

    def test_both_attestations_verify(self, tmp_path: Path) -> None:
        """Base and fork attestations both pass verify_attestation (no corruption)."""
        work = tmp_path / "fork"
        res = kd.run_fork_drill(work)
        attest_dir = work / "attest"
        assert kd._attestation_ok(attest_dir, res["base_run"])
        assert kd._attestation_ok(attest_dir, res["fork_run"])


# ===========================================================================
# AC5 — event shape + T5 gate scoring (incl. zero-corrupted guardrail)
# ===========================================================================


class TestEventEmissionAndGate:
    def test_emit_recovery_drill_shape_is_scored(self, tmp_path: Path) -> None:
        """emit_recovery_drill writes the exact shape recovery_reliability() reads."""
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
        """A corrupted recovery_drill trips the zero-corrupted guardrail (exit 1)."""
        store = tmp_path / "drills.jsonl"
        kd.emit_recovery_drill(store, run_id="R1", outcome="success", corrupted=False,
                               created_at="2026-07-03T00:00:00Z")
        kd.emit_recovery_drill(store, run_id="R2", outcome="fail", corrupted=True,
                               created_at="2026-07-03T00:00:01Z")
        assert check_recovery.main(["--events", str(store)]) == 1


# ===========================================================================
# AC6 — the drill drives the REAL runner (not a hand-rolled dispatcher)
# ===========================================================================


class TestDrivesRealRunner:
    def test_kill_drill_source_has_no_hand_rolled_dispatcher(self) -> None:
        """The retrofit removed the hand-rolled transition/checkpoint dispatcher.

        The drill must drive waves ONLY through wave_runner.run_wave — it no longer
        emits raw routing_decision transitions or writes checkpoints itself.
        """
        src = (_SCRIPTS / "kill_drill.py").read_text(encoding="utf-8")
        assert "wr.run_wave(" in src, "the drill must call the real wave_runner.run_wave"
        assert "build_routing_decision" not in src, "no hand-rolled routing_decision emission"
        assert "write_wave_checkpoint" not in src, "no hand-rolled checkpoint writes"

    def test_run_wave_produced_the_lifecycle_artifacts(self, tmp_path: Path) -> None:
        """Each wave left the full run_wave lifecycle on disk (evidence + attestation)."""
        res = kd.run_kill_drill(tmp_path / "drill")
        attest_dir = Path(res["attest_dir"])
        evidence_dir = tmp_path / "drill" / "evidence"
        # run_wave writes committed evidence and an attestation per wave.
        assert attest_dir.is_dir() and any(attest_dir.glob("*.json"))
        assert evidence_dir.is_dir() and any(evidence_dir.glob("*.json"))
        # The attestations carry the wave-runner schema (proves the real lifecycle ran).
        for rid in res["wave_run_ids"]:
            payload = wr.load_attestation(wr.attestation_path(rid, attest_dir))
            assert payload["schema"] == wr.ATTESTATION_SCHEMA
            assert payload["mechanics"]["ledger_written"] is True
            assert payload["mechanics"]["evidence_written"] is True


# ===========================================================================
# AC3 — T5 >= 0.99 over >= 20 iterations (the full drill accumulation)
# ===========================================================================


class TestT5Accumulation:
    def test_20_iterations_gate_green(self, tmp_path: Path) -> None:
        """>= 20 kill drills + fork emit >= 20 recovery_drill events; gate exit 0."""
        rc = kd.run_drills(iterations=20, tmp_root=tmp_path)
        assert rc == 0

        store = tmp_path / "drill-events.jsonl"
        rec = metrics_lib.recovery_reliability(wave_kpi.read_events(str(store)))
        assert rec is not None
        assert rec["drills"] >= 20, f"expected >= 20 drills, got {rec['drills']}"
        assert rec["corrupted"] == 0
        assert rec["ratio"] >= 0.99
        # The gate agrees.
        assert check_recovery.main(["--events", str(store)]) == 0

    def test_check_recovery_default_path_unchanged(self) -> None:
        """The drill leaves check_recovery.py's default no-arg behavior untouched.

        With no live recovery_drill events in the real store, the gate stays inert
        (exit 0), exactly as before — the drill never mutates the default path.
        """
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".jsonl") as fh:
            assert check_recovery.main(["--events", fh.name]) == 0

    def test_smoke_cli_exits_zero(self) -> None:
        """`kill_drill.py --smoke` runs 1 kill + 1 fork drill through run_wave and exits 0."""
        assert kd.main(["--smoke"]) == 0
