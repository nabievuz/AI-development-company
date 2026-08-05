#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path


_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc
import resume_fork as rf
import wave_runner as wr


_BASE = datetime(2026, 7, 3, 0, 0, 0, tzinfo=UTC)
_WAVE_STRIDE = 1000


def iso_at(seq: int) -> str:
    return (_BASE + timedelta(seconds=seq)).strftime("%Y-%m-%dT%H:%M:%SZ")


DEFAULT_WAVES: list[list[str]] = [
    ["DAS-8001", "DAS-8002"],
    ["DAS-8003", "DAS-8004", "DAS-8005"],
    ["DAS-8006", "DAS-8007"],
]


DEFAULT_CRASH: dict[str, int] = {"wave": 2, "after": 1}

_GOAL = "kill-drill"
_ENGINE_VERSION = "1.0.0"
_ROLE = "qa-eng"
_MODEL = "sonnet"


def _drive_wave(
    *,
    run_id: str,
    wave_no: int,
    tickets: list[str],
    ts: str,
    events_path: Path,
    runs_dir: Path,
    attest_dir: Path,
    evidence_dir: Path,
    tickets_dir: Path,
    from_status: str = "todo",
    final_status: str = "done",
    outcome: str = "success",
) -> wr.WaveAttestation | None:
    plan = wr.WavePlan(
        run_id=run_id,
        wave=wave_no,
        goal=_GOAL,
        engine_version=_ENGINE_VERSION,
        tickets=[wr.TicketPlan(t, role=_ROLE, model=_MODEL, from_status=from_status) for t in tickets],
        anchor_ticket=tickets[0],
    )
    results = wr.WaveResults(
        tickets=[
            wr.TicketResult(
                ticket_id=t,
                outcome=outcome,
                merged_pr=True,
                ci_status="green",
                t7_pass=True,
                t7_score=0.95,
                start=ts,
                end=ts,
                final_status=final_status,
                output=f"kill-drill {t}",
            )
            for t in tickets
        ],
        request_satisfied=True,
        in_loop=False,
        progress_being_made=True,
    )
    return wr.run_wave(
        plan,
        results,
        created_at=ts,
        store_path=events_path,
        runs_dir=runs_dir,
        attest_dir=attest_dir,


        ledger_path=attest_dir.parent / "wave-ledger.jsonl",
        evidence_dir=evidence_dir,
        tickets_dir=tickets_dir,


        guardrails_dir=tickets_dir,
        run_guardrails=False,
    )


def _completion_records(runs_dir: Path, run_id: str) -> list[dict]:
    path = Path(runs_dir) / run_id / "completions.jsonl"
    recs: list[dict] = []
    if not path.exists():
        return recs
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("event_type") == "ticket_completion" and ev.get("run_id") == run_id:
            recs.append(ev)
    return recs


def _completion_status_map(runs_dir: Path, run_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for ev in _completion_records(runs_dir, run_id):
        tid = ev.get("ticket_id")
        if tid:
            out[str(tid)] = str(ev.get("status", ""))
    return out


def _attestation_ok(attest_dir: Path, run_id: str) -> bool:
    path = wr.attestation_path(run_id, attest_dir)
    if not path.exists():
        return False
    try:
        payload = wr.load_attestation(path)
    except (OSError, json.JSONDecodeError):
        return False
    return not wr.verify_attestation(payload)


def _attestation_chain_valid(attest_dir: Path, ordered_run_ids: list[str]) -> tuple[bool, str]:
    prev_expected = wr._GENESIS_PREV_HASH
    for rid in ordered_run_ids:
        path = wr.attestation_path(rid, attest_dir)
        if not path.exists():
            return False, f"missing attestation for {rid}"
        payload = wr.load_attestation(path)
        problems = wr.verify_attestation(payload)
        if problems:
            return False, f"attestation {rid} fails verification: {problems}"
        chain = payload.get("attest_chain", {})
        if chain.get("prev") != prev_expected:
            return False, (
                f"broken link at {rid}: prev {chain.get('prev')!r} != expected {prev_expected!r}"
            )
        prev_expected = str(chain.get("self"))
    return True, ""


def _crash_now() -> None:
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGKILL)


def _install_crash_hook(*, crash_wave: int, crash_after: int) -> None:
    real = pc.append_ticket_completion
    state = {"n": 0}

    def hook(*args: object, **kwargs: object) -> None:
        real(*args, **kwargs)
        if kwargs.get("wave") == crash_wave:
            state["n"] += 1
            if state["n"] >= crash_after:
                _crash_now()

    pc.append_ticket_completion = hook


def _worker_run(spec: dict) -> None:
    waves: list[list[str]] = spec["waves"]
    run_ids: list[str] = spec["run_ids"]
    wave_ts: list[str] = spec["wave_ts"]
    crash: dict = spec["crash"]
    paths = _spec_paths(spec)

    _install_crash_hook(crash_wave=int(crash["wave"]), crash_after=int(crash["after"]))

    for idx, (tickets, rid, ts) in enumerate(zip(waves, run_ids, wave_ts, strict=True), start=1):
        _drive_wave(run_id=rid, wave_no=idx, tickets=tickets, ts=ts, **paths)


def _spec_paths(spec: dict) -> dict[str, Path]:
    return {
        "events_path": Path(spec["events_path"]),
        "runs_dir": Path(spec["runs_dir"]),
        "attest_dir": Path(spec["attest_dir"]),
        "evidence_dir": Path(spec["evidence_dir"]),
        "tickets_dir": Path(spec["tickets_dir"]),
    }


def run_kill_drill(
    work_dir: Path,
    *,
    waves: list[list[str]] | None = None,
    crash: dict | None = None,
) -> dict:
    waves = waves if waves is not None else DEFAULT_WAVES
    crash = crash if crash is not None else DEFAULT_CRASH

    work_dir.mkdir(parents=True, exist_ok=True)
    run_ids = [pc.generate_ulid() for _ in waves]
    wave_ts = [iso_at((i + 1) * _WAVE_STRIDE) for i in range(len(waves))]
    paths = {
        "events_path": work_dir / "events.jsonl",
        "runs_dir": work_dir / "runs",
        "attest_dir": work_dir / "attest",
        "evidence_dir": work_dir / "evidence",
        "tickets_dir": work_dir / "tickets",
    }
    spec = {
        "waves": waves,
        "run_ids": run_ids,
        "wave_ts": wave_ts,
        "crash": crash,
        **{k: str(v) for k, v in paths.items()},
    }
    spec_path = work_dir / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")


    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(spec_path)])
    proc.wait()
    killed = proc.returncode == -signal.SIGKILL


    resumed: list[str] = []
    for idx, (tickets, rid, ts) in enumerate(zip(waves, run_ids, wave_ts, strict=True), start=1):
        if _attestation_ok(paths["attest_dir"], rid):
            continue


        rf.resume_run(rid, paths["events_path"], paths["runs_dir"])
        already_done = pc.get_completed_tickets(rid, paths["runs_dir"])
        todo = [t for t in tickets if t not in already_done]
        if todo:
            _drive_wave(run_id=rid, wave_no=idx, tickets=todo, ts=ts, **paths)
            resumed.extend(todo)


    flat = [t for wave in waves for t in wave]
    completed_status: dict[str, str] = {}
    dup: list[str] = []
    for rid in run_ids:
        counts = Counter(ev["ticket_id"] for ev in _completion_records(paths["runs_dir"], rid))
        dup.extend(t for t, c in counts.items() if c > 1)
        completed_status.update(_completion_status_map(paths["runs_dir"], rid))
    lost = [t for t in flat if completed_status.get(t) not in ("done", "blocked")]
    dup_completions = sorted(set(dup))
    chain_valid, chain_reason = _attestation_chain_valid(paths["attest_dir"], run_ids)


    ledger_path = paths["attest_dir"].parent / "wave-ledger.jsonl"
    ledger_problems = wr.verify_wave_ledger(ledger_path, attest_dir=paths["attest_dir"])
    ledger_reconciles = not ledger_problems

    zero_lost = not lost
    zero_duplicated = not dup_completions
    chain_clean = chain_valid
    ok = killed and zero_lost and zero_duplicated and chain_clean and ledger_reconciles
    corrupted: list[str] = []
    if not chain_valid:
        corrupted.append(chain_reason)
    corrupted.extend(ledger_problems)
    return {
        "run_id": run_ids[-1],
        "wave_run_ids": run_ids,
        "killed": killed,
        "zero_lost": zero_lost,
        "zero_duplicated": zero_duplicated,
        "chain_clean": chain_clean,
        "ledger_reconciles": ledger_reconciles,
        "ledger_problems": ledger_problems,
        "ledger_path": str(ledger_path),
        "ok": ok,
        "lost": lost,
        "dup_completions": dup_completions,
        "corrupted": corrupted,
        "resumed": sorted(resumed),
        "events_path": str(paths["events_path"]),
        "attest_dir": str(paths["attest_dir"]),
        "runs_dir": str(paths["runs_dir"]),
    }


def run_fork_drill(work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    base_run = pc.generate_ulid()
    anchor = "DAS-8501"
    runs_dir = work_dir / "runs"
    attest_dir = work_dir / "attest"
    evidence_dir = work_dir / "evidence"
    tickets_dir = work_dir / "tickets"
    events_b = work_dir / "base-events.jsonl"

    base_paths = {
        "events_path": events_b,
        "runs_dir": runs_dir,
        "attest_dir": attest_dir,
        "evidence_dir": evidence_dir,
        "tickets_dir": tickets_dir,
    }


    _drive_wave(run_id=base_run, wave_no=1, tickets=[anchor], ts=iso_at(1),
                from_status="todo", final_status="in_progress", outcome="in_progress", **base_paths)
    _drive_wave(run_id=base_run, wave_no=2, tickets=[anchor], ts=iso_at(2),
                from_status="in_progress", final_status="done", outcome="success", **base_paths)
    original_status = _completion_status_map(runs_dir, base_run).get(anchor)


    events_b_before = events_b.read_bytes()
    cp1_path = runs_dir / base_run / "wave-001.checkpoint.json"
    cp2_path = runs_dir / base_run / "wave-002.checkpoint.json"
    cp1_before = cp1_path.read_bytes()
    cp2_before = cp2_path.read_bytes()
    base_completions_before = (runs_dir / base_run / "completions.jsonl").read_bytes()


    fork_run, fork_states = rf.fork_run(base_run, wave_num=1, runs_dir=runs_dir)
    start_status = fork_states.get(anchor, "in_progress")


    events_f = work_dir / "fork-events.jsonl"
    _drive_wave(run_id=fork_run, wave_no=1, tickets=[anchor], ts=iso_at(11),
                from_status=start_status, final_status="blocked", outcome="blocked",
                events_path=events_f, runs_dir=runs_dir, attest_dir=attest_dir,
                evidence_dir=evidence_dir, tickets_dir=tickets_dir)
    fork_status = _completion_status_map(runs_dir, fork_run).get(anchor)


    divergent = fork_status == "blocked" and fork_status != original_status


    original_intact = (
        events_b.read_bytes() == events_b_before
        and cp1_path.read_bytes() == cp1_before
        and cp2_path.read_bytes() == cp2_before
        and (runs_dir / base_run / "completions.jsonl").read_bytes() == base_completions_before
        and _completion_status_map(runs_dir, base_run).get(anchor) == original_status
        and fork_run != base_run
    )


    chain_clean = _attestation_ok(attest_dir, base_run) and _attestation_ok(attest_dir, fork_run)
    ok = divergent and original_intact and chain_clean
    return {
        "base_run": base_run,
        "fork_run": fork_run,
        "fork_events_path": str(events_f),
        "divergent": divergent,
        "original_intact": original_intact,
        "chain_clean": chain_clean,
        "ok": ok,
        "original_final": {anchor: original_status},
        "fork_final": {anchor: fork_status},
    }


def emit_recovery_drill(
    out_store: Path,
    *,
    run_id: str,
    outcome: str,
    corrupted: bool,
    created_at: str | None = None,
) -> None:
    now = created_at or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "event_type": "recovery_drill",
        "ticket_id": "DAS-KILLDRILL",
        "run_id": run_id,
        "created_at": now,
        "outcome": outcome,
        "corrupted": corrupted,
    }
    with open(out_store, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def run_drills(*, iterations: int, tmp_root: Path, target: float = 0.99) -> int:
    import check_recovery

    out_store = tmp_root / "drill-events.jsonl"
    failures: list[str] = []

    print(f"kill-drill: running {iterations} kill drill iteration(s) + 1 fork drill "
          f"THROUGH wave_runner.run_wave...")
    for i in range(iterations):
        res = run_kill_drill(tmp_root / f"kill-{i:03d}")
        status = "ok" if res["ok"] else "FAIL"
        print(
            f"  kill[{i:03d}] {status}: killed={res['killed']} "
            f"zero_lost={res['zero_lost']} zero_dup={res['zero_duplicated']} "
            f"chain_clean={res['chain_clean']} ledger_reconciles={res['ledger_reconciles']} "
            f"resumed={res['resumed']}"
        )
        if not res["ok"]:
            failures.append(
                f"kill[{i}] lost={res['lost']} corrupted={res['corrupted']} "
                f"dup={res['dup_completions']} ledger={res['ledger_problems']} "
                f"killed={res['killed']}"
            )


        emit_recovery_drill(
            out_store,
            run_id=res["run_id"],
            outcome="success" if res["ok"] else "fail",
            corrupted=(
                not res["chain_clean"]
                or not res["zero_lost"]
                or not res["zero_duplicated"]
                or not res["ledger_reconciles"]
            ),
        )

    fork = run_fork_drill(tmp_root / "fork")
    fstatus = "ok" if fork["ok"] else "FAIL"
    print(
        f"  fork      {fstatus}: divergent={fork['divergent']} "
        f"(base {fork['original_final']} -> fork {fork['fork_final']}), "
        f"original_intact={fork['original_intact']}"
    )
    if not fork["ok"]:
        failures.append(f"fork divergent={fork['divergent']} intact={fork['original_intact']}")
    emit_recovery_drill(
        out_store,
        run_id=fork["fork_run"],
        outcome="success" if fork["ok"] else "fail",
        corrupted=not fork["chain_clean"],
    )


    print("kill-drill: scoring emitted recovery_drill events via check_recovery.py...")
    gate_rc = check_recovery.main(["--events", str(out_store), "--target", str(target)])

    if failures:
        sys.stderr.write("kill-drill FAILED:\n" + "\n".join(f"  - {f}" for f in failures) + "\n")
        return 1
    if gate_rc != 0:
        sys.stderr.write(f"kill-drill: T5 gate reported non-zero exit ({gate_rc}).\n")
        return 1
    print("kill-drill: OK — all drills passed and the T5 gate is green.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='kill_drill.py — REAL kill/resume + fork recovery drill (DAS-1451 / DAS-1501, GATE-4).')
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--smoke", action="store_true",
                       help="cheap CI variant: 1 kill drill + 1 fork drill, emit + score")
    group.add_argument("--iterations", type=int, default=None,
                       help="expensive scheduled variant: run N kill drills (>=20) + fork")
    group.add_argument("--worker", type=Path, default=None,
                       help="internal: child-process entrypoint; value is the spec JSON path")
    ap.add_argument("--target", type=float, default=0.99, help="T5 ratio target (default 0.99)")
    ap.add_argument("--keep", action="store_true", help="keep the temp drill directory (debug)")
    args = ap.parse_args(argv)


    if args.worker is not None:
        spec = json.loads(Path(args.worker).read_text(encoding="utf-8"))
        _worker_run(spec)
        return 0

    iterations = 1 if args.smoke else (args.iterations if args.iterations is not None else 1)
    if iterations < 1:
        sys.stderr.write("--iterations must be >= 1\n")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="daslab-kill-drill-"))
    try:
        return run_drills(iterations=iterations, tmp_root=tmp_root, target=args.target)
    finally:
        if not args.keep:
            import shutil

            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
