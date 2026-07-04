#!/usr/bin/env python3
"""snapshot_evidence.py — committed, git-auditable KPI evidence (P13 / DAS-1460).

DasLab's KPI + anti-gaming gates read the append-only DGO-X event store at
``board/.events.jsonl`` — **gitignored runtime state** that never enters git
history. A reviewer on a fresh clone therefore has nothing to audit a claimed
KPI against, and the runtime state can be silently regenerated or lost.

This module builds the durable proof those gates rest on. For each run with a
counted completion it snapshots that run's ``wave_kpi`` summary plus its span /
duration aggregates into a **TRACKED** (committed, NOT gitignored) artifact at
``metrics/evidence/<run_id>.json``. The snapshot is small and **redacted** — it
carries only structural / aggregate metric fields (never a secret, PII, or a
raw prompt/output payload; redaction per the spirit of ADR-0012):

- ``run_id`` and the ticket ids that participated in the run,
- per completion: ``model`` (tier), ``outcome``, ``ci_status``, ``created_at``,
  and the R-9 evidence flags ``merged_pr`` / ``t7_pass`` reduced to booleans
  (presence only — a PR URL body is never written), plus the numeric ``t7_score``,
- a span/duration aggregate (paired ``[run_start, run_end]`` intervals), and
- the ``wave_kpi`` summary stats (events / runs_started / runs_completed /
  model_mix / busy_fraction) for that run's events.

REUSE, do not fork (per ticket): this module imports and calls
``wave_kpi.read_events`` / ``wave_kpi.busy_fraction_from_events`` and
``metrics_lib.run_intervals`` (+ the R-9 field predicates ``GREEN_CI`` /
``_is_true_flag`` / ``_is_completion_event``). It never re-implements event
parsing and never re-derives the evidence field names. It does NOT import
``dgox.*`` (it is a reader/summarizer, not an event producer — the Phase-1
shadow rule stays intact).

Inert-by-design: with an absent/empty store (no runs) nothing is written and no
KPI is fabricated.

Usage:
    python3 scripts/snapshot_evidence.py                       # snapshot the live store
    python3 scripts/snapshot_evidence.py --events board/.events.jsonl
    python3 scripts/snapshot_evidence.py --out metrics/evidence
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import metrics_lib
import wave_kpi
from _paths import ROOT

#: Schema tag stamped into every snapshot (lets a future reader version-gate).
EVIDENCE_SCHEMA = "daslab.evidence.v1"

#: Default committed evidence directory (TRACKED — never gitignored).
EVIDENCE_DIR: Path = ROOT / "metrics" / "evidence"


# --------------------------------------------------------------------------- #
# Path helper
# --------------------------------------------------------------------------- #


def evidence_path(evidence_dir: Path | str, run_id: str) -> Path:
    """Committed snapshot path for a run: ``<evidence_dir>/<run_id>.json``."""
    return Path(evidence_dir) / f"{run_id}.json"


# --------------------------------------------------------------------------- #
# Completion classification (REUSE metrics_lib predicates — no re-derived names)
# --------------------------------------------------------------------------- #


def _is_counted_completion(event: dict) -> bool:
    """True if a completion is COUNTED toward the KPIs — the R-9 evidence bar.

    A completion counts only with a merged PR + green CI + a T7 pass (R-9). This
    reuses ``metrics_lib``'s completion predicate and evidence vocabulary
    (``GREEN_CI`` / ``_is_true_flag``) rather than re-deriving field semantics.
    """
    if not metrics_lib._is_completion_event(event):
        return False
    if not event.get("merged_pr"):
        return False
    if str(event.get("ci_status", "")).lower() not in metrics_lib.GREEN_CI:
        return False
    return metrics_lib._is_true_flag(event.get("t7_pass"))


def completed_run_ids(events: list[dict]) -> set[str]:
    """run_ids that have a completion event (any outcome) and carry a run_id."""
    ids: set[str] = set()
    for event in events:
        rid = event.get("run_id")
        if rid and metrics_lib._is_completion_event(event):
            ids.add(str(rid))
    return ids


def counted_run_ids(events: list[dict]) -> set[str]:
    """run_ids whose completion is COUNTED toward the KPIs (clean per R-9).

    Only run_id-bearing completions are returned — an evidence file is keyed by
    ``run_id``, so a completion without one cannot be mapped to a snapshot and is
    out of scope for the committed-evidence requirement.
    """
    ids: set[str] = set()
    for event in events:
        rid = event.get("run_id")
        if rid and _is_counted_completion(event):
            ids.add(str(rid))
    return ids


def missing_evidence_runs(events: list[dict], evidence_dir: Path | str) -> list[str]:
    """Counted run_ids that lack a committed ``<run_id>.json`` snapshot (sorted)."""
    return sorted(
        rid
        for rid in counted_run_ids(events)
        if not evidence_path(evidence_dir, rid).exists()
    )


# --------------------------------------------------------------------------- #
# Snapshot builder — REDACTED per-run aggregate
# --------------------------------------------------------------------------- #


def _coerce_score(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def build_run_evidence(events: list[dict], run_id: str) -> dict:
    """Build the REDACTED evidence snapshot for one ``run_id``.

    Filters the store to this run's events, then summarizes them via the reused
    readers. Only structural/aggregate fields are emitted — ``merged_pr`` and
    ``t7_pass`` are reduced to booleans (presence only) so no PR URL / payload
    leaks into committed history.
    """
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


#: Model tiers tallied in ``kpi_summary.model_mix`` (matches wave_kpi's tiers).
_MODEL_TIERS = ("opus", "sonnet", "haiku")


def model_mix_from_completions(completions: list[dict]) -> dict[str, int]:
    """Per-tier model tally derived from a snapshot's own ``completions``.

    The authoritative source is the event store's ``run_end`` model (built by
    ``build_run_evidence`` via ``wave_kpi``), but that store is gitignored runtime
    state. For repairing an ALREADY-committed snapshot whose events are gone, this
    re-derives the tally from the completions the snapshot itself carries — which,
    for a single-run snapshot, are exactly its ``run_end`` completion(s).
    """
    mix = dict.fromkeys(_MODEL_TIERS, 0)
    for comp in completions:
        mdl = str(comp.get("model") or "").lower()
        if mdl in mix:
            mix[mdl] += 1
    return mix


def reconcile_model_mix(evidence: dict) -> bool:
    """Repair a pre-fix snapshot whose ``kpi_summary.model_mix`` is inconsistent
    with its own completions (ORGANISM audit F-2). Mutates ``evidence`` in place;
    returns True when a change was made.
    """
    ks = evidence.get("kpi_summary")
    if not isinstance(ks, dict):
        return False
    fixed = model_mix_from_completions(evidence.get("completions", []))
    if ks.get("model_mix") != fixed:
        ks["model_mix"] = fixed
        return True
    return False


def reconcile_evidence_dir(evidence_dir: Path | str = EVIDENCE_DIR) -> list[Path]:
    """Reconcile every committed snapshot's model_mix in place; return changed paths."""
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
    """Write one run's redacted snapshot to ``<evidence_dir>/<run_id>.json``."""
    path = evidence_path(evidence_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_run_evidence(events, run_id)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def snapshot_all(events: list[dict], evidence_dir: Path | str = EVIDENCE_DIR) -> list[Path]:
    """Write a snapshot for every completed run; returns the written paths.

    Inert-by-design: with no completion events nothing is written (returns []).
    """
    return [
        write_run_evidence(events, rid, evidence_dir)
        for rid in sorted(completed_run_ids(events))
    ]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
