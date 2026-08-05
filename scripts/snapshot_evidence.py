#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT

EVIDENCE_SCHEMA = "daslab.evidence.v1"


EVIDENCE_DIR: Path = ROOT / "metrics" / "evidence"


def evidence_path(evidence_dir: Path | str, run_id: str) -> Path:
    return Path(evidence_dir) / f"{run_id}.json"


def _is_counted_completion(event: dict) -> bool:
    if not metrics_lib._is_completion_event(event):
        return False
    if not event.get("merged_pr"):
        return False
    if str(event.get("ci_status", "")).lower() not in metrics_lib.GREEN_CI:
        return False
    return metrics_lib._is_true_flag(event.get("t7_pass"))


def completed_run_ids(events: list[dict]) -> set[str]:
    ids: set[str] = set()
    for event in events:
        rid = event.get("run_id")
        if rid and metrics_lib._is_completion_event(event):
            ids.add(str(rid))
    return ids


def counted_run_ids(events: list[dict]) -> set[str]:
    ids: set[str] = set()
    for event in events:
        rid = event.get("run_id")
        if rid and _is_counted_completion(event):
            ids.add(str(rid))
    return ids


def missing_evidence_runs(events: list[dict], evidence_dir: Path | str) -> list[str]:
    return sorted(
        rid
        for rid in counted_run_ids(events)
        if not evidence_path(evidence_dir, rid).exists()
    )


def _coerce_score(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_run_evidence(events: list[dict], run_id: str) -> dict:
    run_events = [e for e in events if str(e.get("run_id", "")) == run_id]
    fraction, stats = wave_kpi.busy_fraction_from_events(run_events)
    intervals = metrics_lib.run_intervals(run_events)
    durations = [(end - start).total_seconds() for start, end in intervals]

    completions: list[dict] = []
    tickets: set[str] = set()
    for event in run_events:
        tid = event.get("ticket_id")
        if tid:
            tickets.add(str(tid))
        if not metrics_lib._is_completion_event(event):
            continue
        completions.append(
            {
                "ticket_id": event.get("ticket_id"),
                "model": str(event.get("model", "")).lower() or None,
                "outcome": event.get("outcome"),
                "ci_status": event.get("ci_status"),
                "merged_pr": bool(event.get("merged_pr")),
                "t7_pass": metrics_lib._is_true_flag(event.get("t7_pass")),
                "t7_score": _coerce_score(event.get("t7_score")),
                "counted": _is_counted_completion(event),
                "created_at": event.get("created_at"),
            }
        )

    return {
        "schema": EVIDENCE_SCHEMA,
        "run_id": run_id,
        "tickets": sorted(tickets),
        "completions": completions,
        "span_aggregate": {
            "runs": len(intervals),
            "total_duration_s": sum(durations),
            "max_duration_s": max(durations) if durations else 0.0,
        },
        "kpi_summary": {
            "busy_fraction": fraction,
            "events": stats["events"],
            "runs_started": stats["runs_started"],
            "runs_completed": stats["runs_completed"],
            "model_mix": stats["model_mix"],
        },
    }


_MODEL_TIERS = ("opus", "sonnet", "haiku")


def model_mix_from_completions(completions: list[dict]) -> dict[str, int]:
    mix = dict.fromkeys(_MODEL_TIERS, 0)
    for comp in completions:
        mdl = str(comp.get("model") or "").lower()
        if mdl in mix:
            mix[mdl] += 1
    return mix


def reconcile_model_mix(evidence: dict) -> bool:
    ks = evidence.get("kpi_summary")
    if not isinstance(ks, dict):
        return False
    fixed = model_mix_from_completions(evidence.get("completions", []))
    if ks.get("model_mix") != fixed:
        ks["model_mix"] = fixed
        return True
    return False


def reconcile_evidence_dir(evidence_dir: Path | str = EVIDENCE_DIR) -> list[Path]:
    changed: list[Path] = []
    for path in sorted(Path(evidence_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if reconcile_model_mix(data):
            path.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            changed.append(path)
    return changed


def write_run_evidence(events: list[dict], run_id: str, evidence_dir: Path | str) -> Path:
    path = evidence_path(evidence_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_run_evidence(events, run_id)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def snapshot_all(events: list[dict], evidence_dir: Path | str = EVIDENCE_DIR) -> list[Path]:
    return [
        write_run_evidence(events, rid, evidence_dir)
        for rid in sorted(completed_run_ids(events))
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='snapshot_evidence.py — committed, git-auditable KPI evidence (P13 / DAS-1460).')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--out", type=Path, default=EVIDENCE_DIR)
    ap.add_argument(
        "--reconcile",
        action="store_true",
        help="repair committed snapshots' model_mix from their own completions "
        "(ORGANISM audit F-2 fix; use when the source event store is gone) and exit",
    )
    args = ap.parse_args(argv)

    if args.reconcile:
        changed = reconcile_evidence_dir(args.out)
        if not changed:
            print("snapshot_evidence: all committed evidence already consistent (nothing to reconcile).")
            return 0
        print(f"snapshot_evidence: reconciled model_mix in {len(changed)} snapshot(s):")
        for path in changed:
            print(f"  - {path.name}")
        return 0

    events = wave_kpi.read_events(str(args.events))
    written = snapshot_all(events, args.out)
    if not written:
        print("snapshot_evidence: no completed runs — nothing to snapshot (inert).")
        return 0
    rel_out = args.out
    print(f"snapshot_evidence: wrote {len(written)} evidence file(s) to {rel_out}:")
    for path in written:
        print(f"  - {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
