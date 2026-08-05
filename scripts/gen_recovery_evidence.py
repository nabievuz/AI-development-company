#!/usr/bin/env python3


from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import kill_drill

DEFAULT_RUNS_DIR = _ROOT / "board" / "runs"


def _utc_now() -> str:
    return dt.datetime.now(tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _render_summary(kill: dict, fork: dict, generated_at: str) -> str:
    proof = {
        "generated_at": generated_at,
        "kind": "recovery_drill_evidence",
        "source": (
            "scripts/kill_drill.py run_kill_drill + run_fork_drill "
            "(production wave_runner.run_wave path)"
        ),
        "kill_drill": {
            k: kill.get(k)
            for k in (
                "run_id", "wave_run_ids", "killed", "zero_lost", "zero_duplicated",
                "chain_clean", "ledger_reconciles", "resumed", "ok",
            )
        },
        "fork_drill": {
            k: fork.get(k)
            for k in ("base_run", "fork_run", "divergent", "original_intact", "chain_clean", "ok")
        },
        "overall_ok": bool(kill.get("ok") and fork.get("ok")),
    }
    verdict = "PASS" if proof["overall_ok"] else "MISS"
    proof_json = json.dumps(proof, indent=2, ensure_ascii=False)
    if proof["overall_ok"]:
        intro = (
            "One REAL interrupted run (SIGKILL mid-wave-2) resumed with zero loss through "
            "the production `wave_runner.run_wave` path, plus a time-travel fork drill "
            "proving the base run byte-identical (R1 durable execution)."
        )
    else:
        intro = (
            "A recovery drill was run through the production `wave_runner.run_wave` path but "
            "did NOT hold (see the failing invariants below). This receipt records the MISS "
            "honestly; it does NOT assert a successful recovery."
        )
    return (
        f"# Recovery drill evidence — {verdict}\n\n"
        f"{intro}\n\n"
        f"- generated_at: `{generated_at}`\n"
        f"- kill-drill run_id: `{kill.get('run_id')}`\n"
        f"- killed (real SIGKILL mid-wave-2): **{kill.get('killed')}**\n"
        f"- zero_lost: **{kill.get('zero_lost')}** · zero_duplicated: **{kill.get('zero_duplicated')}**\n"
        f"- resumed attestation chain clean: **{kill.get('chain_clean')}** · "
        f"wave-ledger reconciles: **{kill.get('ledger_reconciles')}**\n"
        f"- resumed tickets: `{kill.get('resumed')}`\n"
        f"- fork drill: divergent=**{fork.get('divergent')}** · "
        f"original_intact=**{fork.get('original_intact')}**\n"
        f"- **overall verdict: {verdict}**\n\n"
        "The drill trees (events / checkpoints / attestations / wave-ledger) are "
        "hermetic and discarded; this run-summary is the durable, git-tracked receipt.\n\n"
        f"```json\n{proof_json}\n```\n"
    )


def generate(runs_dir: Path, *, work_root: Path | None = None) -> dict:
    tmp = Path(
        tempfile.mkdtemp(prefix="recovery-evidence-", dir=str(work_root) if work_root else None)
    )
    try:
        kill = kill_drill.run_kill_drill(tmp / "kill")
        fork = kill_drill.run_fork_drill(tmp / "fork")
        generated_at = _utc_now()
        run_id = str(kill.get("run_id"))
        out_dir = Path(runs_dir) / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = out_dir / "run-summary.md"
        summary_path.write_text(_render_summary(kill, fork, generated_at), encoding="utf-8")
        return {
            "run_id": run_id,
            "summary_path": str(summary_path),
            "overall_ok": bool(kill.get("ok") and fork.get("ok")),
            "kill": kill,
            "fork": fork,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='gen_recovery_evidence.py — commit a REAL interrupted-run recovery proof (R1).')
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = generate(args.runs_dir)
    verdict = "PASS" if result["overall_ok"] else "MISS"
    if args.json:
        print(json.dumps({k: result[k] for k in ("run_id", "summary_path", "overall_ok")}, indent=2))
    else:
        print(f"[recovery-evidence] {verdict} — wrote {result['summary_path']} (run_id={result['run_id']})")
    return 0 if result["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
