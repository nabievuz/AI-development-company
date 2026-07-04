#!/usr/bin/env python3
"""kill_drill.py — REAL kill/resume + fork recovery drill (DAS-1451 / DAS-1501, GATE-4).

Turns the T5 recovery-reliability gate (``scripts/check_recovery.py``) from a
shipped-but-inert lever into a gate backed by live evidence — and, per DAS-1501,
drives its synthetic waves THROUGH the real production wave lifecycle
(``scripts/wave_runner.run_wave``) rather than a hand-rolled dispatcher.  This
proves the ACTUAL wave-runner lifecycle (events + checkpoints + attestation)
survives a genuine ``kill -9`` — not just the recovery primitives in isolation.

  KILL DRILL (``run_kill_drill``)
      1. A *real* child process drives a synthetic 3-wave run THROUGH
         ``wave_runner.run_wave`` — the same deterministic post-decision lifecycle
         production uses: per-wave open/close checkpoints (``pulse_checkpoint``),
         ``run_start`` / ``run_end`` / ``span`` events (``dispatch_emitter``),
         durable per-ticket completion records (the commit point), committed
         redacted evidence, and a doubly hash-chained ``WaveAttestation`` per wave.
         Each wave is its own ``run_id`` so the attestations form a wave-to-wave
         hash chain (``attest_chain.prev`` → the prior wave's ``self``).
      2. The child ``kill -9``s itself (``os.kill(getpid, SIGKILL)``) DEEP INSIDE
         ``run_wave`` mid-wave-2 — right after the wave's first ticket completion
         is durably fsync'd but BEFORE the wave-2 checkpoint/evidence/attestation
         are committed.  A genuine abrupt death: no cleanup, no atexit, no flush.
      3. The parent RESUMES via ``resume_fork`` (DAS-1445): a wave with a committed,
         verifying attestation is done; a wave without one is re-driven through
         ``run_wave`` for EXACTLY the tickets that lack a durable completion record
         (``resume_fork.resume_run`` guards against a corrupted replay; the
         completion records are the durable work-item ledger).  A ticket that
         completed before the crash is NEVER re-dispatched (guard-before-act).
      4. Assert **zero lost** (every planned ticket has a terminal completion),
         **zero duplicated** (no ticket completed twice), a **valid resumed
         attestation chain** (every wave attestation verifies and links to its
         predecessor), and — the ADR-0032 §1 committed-ledger invariant (DAS-1507)
         — that the co-produced ``board/wave-ledger.jsonl`` CHAIN survives the
         crash: after resume it is a valid unbroken hash chain with NO gap and NO
         duplicate that **reconciles against the attestations** (via
         ``wave_runner.verify_wave_ledger`` — the SSOT the ``check_wave_reconciliation``
         gate wraps), all across the crash boundary.

  FORK DRILL (``run_fork_drill``)
      Drive a 2-wave base run THROUGH ``run_wave`` (one ``run_id`` so the
      checkpoint delta-chain traverses wave-001…002), fork from the wave-1
      checkpoint (``resume_fork.fork_run``), drive the fork to a DIVERGENT outcome
      (a ticket the base ran to ``done`` the fork runs to ``blocked``) in its OWN
      event store + attestation tree, and prove the base run is left intact
      (events byte-for-byte unchanged, checkpoints unchanged, its completion ledger
      unchanged, and both attestations still verify).

Both drills emit ``recovery_drill`` events in the EXACT shape
``replay_qa --emit`` writes (``event_type: recovery_drill``, ``outcome``,
``corrupted``, ``run_id``, ``ticket_id``, ``created_at``).  So the existing
``metrics_lib.recovery_reliability`` / ``check_recovery.py`` score them with NO
gate change: a clean resume ⇒ ``outcome=success, corrupted=false``; a corrupted
resume (a broken attestation chain, a lost or duplicated work item) ⇒
``corrupted=true`` ⇒ the gate FAILs (zero-corrupted guardrail).  The T5 math
(``metrics_lib.recovery_reliability``) and ``check_recovery.py``'s default no-arg
scoring/exit contract are untouched (T5 >= 0.99 threshold kept).

Shadow-rule note (mirrors ``resume_fork``): this module DRIVES the write-only
mechanics orchestrator ``wave_runner.run_wave`` (which reads no event store — it
is proven a non-reader by property) and reads durable state ONLY through
``resume_fork`` on the explicit operator-invoked drill path — never in the normal
``/daslab-cycle`` dispatch path.  Per ADR-0025, write-only producers and
operator-recovery readers are load-bearing but NOT shadow-rule violations;
``test_dgox_phase1_shadow.py`` enforces this with a principled reader-vs-router
rule (the ``resume_fork`` recovery marker exempts this module).

CLI
    python3 scripts/kill_drill.py --smoke            # cheap: 1 kill + 1 fork drill (CI, every PR)
    python3 scripts/kill_drill.py --iterations 20    # expensive: >=20 kill drills + fork (scheduled)
    python3 scripts/kill_drill.py --worker <spec>    # internal: the child process entrypoint

Exit codes: 0 = drills passed AND T5 gate exit 0; 1 = a drill failed
(lost/duplicated/broken-chain/not-killed) or the gate FAILed; 2 = usage.
"""
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

# ---------------------------------------------------------------------------
# scripts/ on sys.path (same pattern as the sibling recovery scripts) so the
# child process and the driver resolve pulse_checkpoint / resume_fork / wave_runner.
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc  # noqa: E402
import resume_fork as rf  # noqa: E402  (also the ADR-0025 recovery marker for the shadow gate)
import wave_runner as wr  # noqa: E402

# ---------------------------------------------------------------------------
# Deterministic, strictly-increasing timestamps.
#
# Every wave's ``created_at`` is caller-supplied (wave_runner reads no clock).
# The per-wave timestamps are strictly increasing so ``wave_runner._chain_tip``
# (which orders attestations by ``created_at``) links each wave's attestation to
# the immediately prior wave — including the wave that was resumed after the crash.
# ---------------------------------------------------------------------------
_BASE = datetime(2026, 7, 3, 0, 0, 0, tzinfo=UTC)
_WAVE_STRIDE = 1000  # seconds between wave boundaries — keeps the ordering obvious


def iso_at(seq: int) -> str:
    """Deterministic ISO-8601 ``Z`` timestamp for sequence ``seq`` (sortable)."""
    return (_BASE + timedelta(seconds=seq)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Synthetic plan: 3 waves; the crash lands in wave 2 after its 1st completion.
# ---------------------------------------------------------------------------
DEFAULT_WAVES: list[list[str]] = [
    ["DAS-8001", "DAS-8002"],
    ["DAS-8003", "DAS-8004", "DAS-8005"],
    ["DAS-8006", "DAS-8007"],
]
#: Crash config: SIGKILL inside ``run_wave`` for wave 2, right after ``after``
#: ticket completion(s) are durably written (so the idempotency window — a durable
#: completion with no committed attestation yet — is exercised on resume).
DEFAULT_CRASH: dict[str, int] = {"wave": 2, "after": 1}

_GOAL = "kill-drill"
_ENGINE_VERSION = "1.0.0"
_ROLE = "qa-eng"
_MODEL = "sonnet"


# ---------------------------------------------------------------------------
# The single lifecycle seam — every wave in both drills goes THROUGH run_wave.
# ---------------------------------------------------------------------------


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
    """Drive one wave THROUGH the real ``wave_runner.run_wave`` lifecycle.

    Builds the routing DECISION (``WavePlan``) and collected OUTCOMES
    (``WaveResults``) the orchestrator would hand ``run_wave``, then invokes the
    deterministic post-decision mechanics (checkpoints + events + ledgers +
    per-ticket completions + evidence + attestation).  Guardrails are OFF (the
    OPTIONAL tripwire) so the drill stays hermetic — no board ticket files needed.
    """
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
        # Keep the ADR-0032 wave-ledger co-write hermetic to this drill's tree
        # (never the repo's committed board/wave-ledger.jsonl): co-locate it beside
        # the (already work-dir-local) attest_dir so resume-chain drills are isolated.
        ledger_path=attest_dir.parent / "wave-ledger.jsonl",
        evidence_dir=evidence_dir,
        tickets_dir=tickets_dir,
        # guardrails are OFF, but run_wave resolves the guardrails-dir default
        # eagerly, so pass a hermetic path (never read on the run_guardrails=False path).
        guardrails_dir=tickets_dir,
        run_guardrails=False,
    )


# ---------------------------------------------------------------------------
# Durable-state readers (completion records are the work-item ledger)
# ---------------------------------------------------------------------------


def _completion_records(runs_dir: Path, run_id: str) -> list[dict]:
    """All ``ticket_completion`` records durably written for ``run_id`` (in order)."""
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
    """Last durable completion status per ticket for ``run_id`` (last writer wins)."""
    out: dict[str, str] = {}
    for ev in _completion_records(runs_dir, run_id):
        tid = ev.get("ticket_id")
        if tid:
            out[str(tid)] = str(ev.get("status", ""))
    return out


def _attestation_ok(attest_dir: Path, run_id: str) -> bool:
    """True iff ``run_id`` has a committed attestation whose self-hash verifies."""
    path = wr.attestation_path(run_id, attest_dir)
    if not path.exists():
        return False
    try:
        payload = wr.load_attestation(path)
    except (OSError, json.JSONDecodeError):
        return False
    return not wr.verify_attestation(payload)


def _attestation_chain_valid(attest_dir: Path, ordered_run_ids: list[str]) -> tuple[bool, str]:
    """Verify the wave-to-wave attestation chain over ``ordered_run_ids``.

    Each wave's attestation must (a) exist, (b) verify its own self-hash
    (``wave_runner.verify_attestation``), and (c) link its ``attest_chain.prev``
    to the immediately prior wave's ``self`` (genesis for the first wave).  This
    is the "valid resumed attestation chain" the crash boundary must preserve.
    """
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


# ---------------------------------------------------------------------------
# The synthetic worker — runs in a CHILD process, killed -9 deep inside run_wave
# ---------------------------------------------------------------------------


def _crash_now() -> None:
    """Abrupt process death — SIGKILL to self. No cleanup, no flush, no atexit."""
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGKILL)


def _install_crash_hook(*, crash_wave: int, crash_after: int) -> None:
    """Wrap ``pulse_checkpoint.append_ticket_completion`` to SIGKILL mid-run_wave.

    ``wave_runner.run_wave`` writes each ticket's completion (the commit point)
    via ``pulse_checkpoint.append_ticket_completion``.  Patching that module
    attribute makes the wrapper run for the SAME function object ``run_wave``
    calls (``wave_runner`` imported the module, not the function).  The wrapper
    writes the completion durably FIRST, then — once ``crash_after`` completions
    have landed in the crash wave — kills the process before ``run_wave`` reaches
    its wave-close checkpoint / evidence / attestation steps.
    """
    real = pc.append_ticket_completion
    state = {"n": 0}

    def hook(*args: object, **kwargs: object) -> None:
        real(*args, **kwargs)  # durably fsync the completion BEFORE any crash
        if kwargs.get("wave") == crash_wave:
            state["n"] += 1
            if state["n"] >= crash_after:
                _crash_now()  # genuine kill -9 — never returns

    pc.append_ticket_completion = hook  # type: ignore[assignment]


def _worker_run(spec: dict) -> None:
    """CHILD entrypoint: drive the synthetic waves through run_wave, SIGKILL-ing mid-wave-2."""
    waves: list[list[str]] = spec["waves"]
    run_ids: list[str] = spec["run_ids"]
    wave_ts: list[str] = spec["wave_ts"]
    crash: dict = spec["crash"]
    paths = _spec_paths(spec)

    _install_crash_hook(crash_wave=int(crash["wave"]), crash_after=int(crash["after"]))

    for idx, (tickets, rid, ts) in enumerate(zip(waves, run_ids, wave_ts, strict=True), start=1):
        _drive_wave(run_id=rid, wave_no=idx, tickets=tickets, ts=ts, **paths)
    # Only reached if the crash never fired (a spec with no crash in range).


def _spec_paths(spec: dict) -> dict[str, Path]:
    """The five injectable directories/files a wave drive needs, from a spec dict."""
    return {
        "events_path": Path(spec["events_path"]),
        "runs_dir": Path(spec["runs_dir"]),
        "attest_dir": Path(spec["attest_dir"]),
        "evidence_dir": Path(spec["evidence_dir"]),
        "tickets_dir": Path(spec["tickets_dir"]),
    }


# ---------------------------------------------------------------------------
# KILL DRILL — drive through run_wave, kill mid-wave-2, resume, assert invariants
# ---------------------------------------------------------------------------


def run_kill_drill(
    work_dir: Path,
    *,
    waves: list[list[str]] | None = None,
    crash: dict | None = None,
) -> dict:
    """Run one kill/resume drill in ``work_dir``; return a result dict.

    Returns keys: ``run_id`` (the last wave's id, for recovery_drill emission),
    ``wave_run_ids``, ``killed`` (child died by SIGKILL), ``zero_lost``,
    ``zero_duplicated``, ``chain_clean`` (resumed attestation chain valid),
    ``ledger_reconciles`` (the committed wave-ledger chain is unbroken —
    no gap/duplicate — and reconciles against the attestations post-resume),
    ``ok`` (all hold and the child was killed), plus diagnostic ``lost`` /
    ``dup_completions`` / ``ledger_problems`` / ``corrupted`` / ``resumed`` lists,
    the ``ledger_path``, and the tree paths.
    """
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

    # 1. Spawn the child and let it kill -9 itself deep inside run_wave (mid-wave-2).
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(spec_path)])
    proc.wait()
    killed = proc.returncode == -signal.SIGKILL

    # 2. RESUME via resume_fork: a wave with a committed, verifying attestation is
    #    done; any other wave is re-driven through run_wave for EXACTLY the tickets
    #    that lack a durable completion record.
    resumed: list[str] = []
    for idx, (tickets, rid, ts) in enumerate(zip(waves, run_ids, wave_ts, strict=True), start=1):
        if _attestation_ok(paths["attest_dir"], rid):
            continue  # wave fully committed before the crash — nothing to resume
        # resume_fork.resume_run enforces the T5 zero-corrupted guardrail on the
        # replay and returns started-but-unfinished tickets (empty for a run_wave
        # run, which emits no routing_decision transitions).  The completion
        # records are the durable work-item ledger the re-dispatch set is built from.
        rf.resume_run(rid, paths["events_path"], paths["runs_dir"])
        already_done = pc.get_completed_tickets(rid, paths["runs_dir"])
        todo = [t for t in tickets if t not in already_done]
        if todo:
            _drive_wave(run_id=rid, wave_no=idx, tickets=todo, ts=ts, **paths)
            resumed.extend(todo)

    # 3. Verify the resume boundary from the durable ledger + attestation chain.
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

    # The ADR-0032 §1 committed wave-ledger CHAIN must survive the crash (DAS-1507):
    # after resume it is a valid unbroken chain with no gap/duplicate that reconciles
    # against the attestations.  The drill's ledger is hermetic — co-located beside
    # the (work-dir-local) attest_dir by _drive_wave — never the repo's committed
    # board/wave-ledger.jsonl.  Reconcile it THROUGH the SSOT wave_runner primitive
    # (the same one the check_wave_reconciliation gate wraps), so a dropped ledger
    # line, a chain gap, an orphan attestation, or a tampered attestation_hash all
    # surface here → corrupted=true → the T5 zero-corrupted guardrail FAILs.
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


# ---------------------------------------------------------------------------
# FORK DRILL — fork from a wave-1 checkpoint into a divergent run; base intact
# ---------------------------------------------------------------------------


def run_fork_drill(work_dir: Path) -> dict:
    """Fork from a wave-1 checkpoint to a divergent outcome; prove the base intact.

    Both the base and fork runs go THROUGH ``wave_runner.run_wave``.  The base run
    uses ONE ``run_id`` across two waves so the checkpoint delta-chain traverses
    wave-001…002 and ``resume_fork.fork_run`` can reconstruct the wave-1 state.

    Returns keys: ``base_run``, ``fork_run``, ``fork_events_path`` (str),
    ``divergent``, ``original_intact``, ``chain_clean``, ``ok``, plus
    ``original_final`` / ``fork_final`` for reporting.
    """
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

    # Base run: DAS-8501 is in_progress at the wave-1 boundary, then done at wave-2
    # (SAME run_id so the wave-001…002 checkpoint delta-chain reconstructs).
    _drive_wave(run_id=base_run, wave_no=1, tickets=[anchor], ts=iso_at(1),
                from_status="todo", final_status="in_progress", outcome="in_progress", **base_paths)
    _drive_wave(run_id=base_run, wave_no=2, tickets=[anchor], ts=iso_at(2),
                from_status="in_progress", final_status="done", outcome="success", **base_paths)
    original_status = _completion_status_map(runs_dir, base_run).get(anchor)  # "done"

    # Snapshot the base's on-disk state to prove intactness after the fork.
    events_b_before = events_b.read_bytes()
    cp1_path = runs_dir / base_run / "wave-001.checkpoint.json"
    cp2_path = runs_dir / base_run / "wave-002.checkpoint.json"
    cp1_before = cp1_path.read_bytes()
    cp2_before = cp2_path.read_bytes()
    base_completions_before = (runs_dir / base_run / "completions.jsonl").read_bytes()

    # Fork at wave-1 (resume_fork.fork_run, DAS-1445): new run_id + inherited state.
    fork_run, fork_states = rf.fork_run(base_run, wave_num=1, runs_dir=runs_dir)
    start_status = fork_states.get(anchor, "in_progress")

    # Drive the fork DIVERGENTLY through run_wave in its OWN store + attestation
    # tree: the ticket the base ran to `done`, the fork runs to `blocked`.
    events_f = work_dir / "fork-events.jsonl"
    _drive_wave(run_id=fork_run, wave_no=1, tickets=[anchor], ts=iso_at(11),
                from_status=start_status, final_status="blocked", outcome="blocked",
                events_path=events_f, runs_dir=runs_dir, attest_dir=attest_dir,
                evidence_dir=evidence_dir, tickets_dir=tickets_dir)
    fork_status = _completion_status_map(runs_dir, fork_run).get(anchor)  # "blocked"

    # Divergence: the fork's outcome differs from the base's.
    divergent = fork_status == "blocked" and fork_status != original_status

    # Base intact: bytes unchanged, checkpoints unchanged, completion ledger
    # unchanged, still resolves to its recorded final state, and a fresh run_id.
    original_intact = (
        events_b.read_bytes() == events_b_before
        and cp1_path.read_bytes() == cp1_before
        and cp2_path.read_bytes() == cp2_before
        and (runs_dir / base_run / "completions.jsonl").read_bytes() == base_completions_before
        and _completion_status_map(runs_dir, base_run).get(anchor) == original_status
        and fork_run != base_run
    )

    # Both runs' attestations still verify (no corruption from the fork).
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


# ---------------------------------------------------------------------------
# T5 accumulation + scoring
# ---------------------------------------------------------------------------


def emit_recovery_drill(
    out_store: Path,
    *,
    run_id: str,
    outcome: str,
    corrupted: bool,
    created_at: str | None = None,
) -> None:
    """Append one ``recovery_drill`` event in the EXACT shape ``replay_qa --emit`` writes.

    The T5 gate (``metrics_lib.recovery_reliability`` → ``check_recovery.py``)
    already consumes this shape, so no gate change is needed.  The
    ``outcome``/``corrupted`` verdict is derived by the caller from the drill's
    durable result (zero-lost + zero-duplicated + a valid resumed attestation
    chain), and written here in ``replay_qa``'s own field set.
    """
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
    """Run ``iterations`` kill drills + one fork drill, emit recovery_drill events,
    then score them through check_recovery.py. Returns a process exit code.
    """
    import check_recovery  # noqa: PLC0415 (lazy — only the CLI path needs it)

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
        # Emit the recovery_drill for this iteration's (resumed) run. A broken
        # resume (lost/dup/broken attestation chain OR a broken/unreconciled
        # committed wave-ledger chain) sets corrupted=true → T5 guardrail FAILs.
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

    # Score the emitted recovery_drill events through the EXISTING T5 gate.
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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

    # Child-process mode: run the synthetic worker (it kills -9 itself mid-run_wave).
    if args.worker is not None:
        spec = json.loads(Path(args.worker).read_text(encoding="utf-8"))
        _worker_run(spec)
        return 0  # only reached when the spec has no in-range crash (clean run)

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
