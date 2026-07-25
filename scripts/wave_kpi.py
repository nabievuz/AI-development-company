#!/usr/bin/env python3
"""
wave_kpi.py — DasLab wave throughput KPI

Parses the wave/idle markers written by /daslab-cycle and /daslab-run to
board/.wave-log and reports real numbers: active vs idle waves, per-wave
active duration, tickets dispatched, model mix, and tickets-per-active-hour.
This is the baseline you measure "10x" against.

Log format (append-only, written by /daslab-cycle + /daslab-run):
  ===== wave YYYY-MM-DD HH:MM:SS =====
  | DAS-xxxx  slug  old-status → new-status  assignee  model |
  nothing actionable — YYYY-MM-DD HH:MM:SS
  [idle Ns before next wave — HH:MM:SS]

Default log path : board/.wave-log   (live log from /daslab-run / /daslab-cycle)
Legacy log path  : board/.night-waves.log  (archived; accepted via path arg)

Usage:
    python3 scripts/wave_kpi.py                           # reads board/.wave-log
    python3 scripts/wave_kpi.py board/.night-waves.log    # legacy archived log
    python3 scripts/wave_kpi.py /path/to/any.log          # explicit path
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys

from dgox.created_at import parse_created_at

WAVE = re.compile(r"^===== wave (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) =====")
IDLE = re.compile(r"^\[idle (\d+)s before next wave — (\d{2}:\d{2}:\d{2})\]")
# A dispatch table row: starts with |, names a DAS ticket, has a status arrow,
# and names the model the agent ran on. Blocked/skipped tables lack the arrow+model.
DISPATCH = re.compile(r"^\|\s*DAS-\d+.*→.*\b(opus|sonnet|haiku)\b", re.I)
NONE_ACT = re.compile(r"nothing actionable", re.I)


def parse(path):
    waves, cur = [], None
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for line in lines:
        m = WAVE.match(line)
        if m:
            if cur:
                waves.append(cur)
            start = dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
            cur = {"date": m.group(1), "start": start, "end": None,
                   "idle_decl": None, "txt": [], "disp": []}
            continue
        if cur is None:
            continue
        mi = IDLE.match(line)
        if mi:
            end = dt.datetime.strptime(f"{cur['date']} {mi.group(2)}", "%Y-%m-%d %H:%M:%S")
            if end < cur["start"]:
                end += dt.timedelta(days=1)
            cur["end"], cur["idle_decl"] = end, int(mi.group(1))
            continue
        cur["txt"].append(line)
        md = DISPATCH.match(line)
        if md:
            cur["disp"].append(md.group(1).lower())
    if cur:
        waves.append(cur)
    return waves


def fmt(sec):
    if sec is None:
        return "   n/a"
    m, s = divmod(int(sec), 60)
    return f"{m:>2}m{s:02d}s"


LIVE_LOG = "board/.wave-log"
LEGACY_LOG = "board/.night-waves.log"
EVENTS_LOG = "board/.events.jsonl"   # DGO-X event store (gitignored runtime)


# --------------------------------------------------------------------------- #
# DGO-X event-store reader: wave_kpi reads the live event store too.
# Additive — the .wave-log parser above is untouched. These helpers let
# check_busy_fraction.py read T1 from board/.events.jsonl when real run events
# exist, and return None (inert) when they do not — never a fabricated number.
# --------------------------------------------------------------------------- #

def _parse_iso(ts: str) -> dt.datetime | None:
    """Parse a ``created_at`` timestamp against the shared write-seam contract.

    DAS-1633: delegates to ``dgox.created_at.parse_created_at`` (the single
    source of truth shared with ``cost_ledger``/``metrics_history_feeder``/
    ``metrics_lib``/``trends``) instead of a locally re-implemented ``strptime``.
    """
    return parse_created_at(ts)


def read_events(path: str = EVENTS_LOG) -> list[dict]:
    """Read the DGO-X JSONL event store; [] if absent (no live waves yet)."""
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return events


def _union_seconds(intervals: list[tuple[dt.datetime, dt.datetime]]) -> float:
    """Total seconds covered by the union of [start, end] datetime intervals."""
    total = 0.0
    cur_s: dt.datetime | None = None
    cur_e: dt.datetime | None = None
    for s, e in sorted((s, e) for s, e in intervals if e >= s):
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
    if cur_s is not None:
        total += (cur_e - cur_s).total_seconds()
    return total


def busy_fraction_from_events(events: list[dict]) -> tuple[float | None, dict]:
    """T1 busy fraction from the event store, or (None, stats) if insufficient.

    Active time = union of [run_start, run_end] intervals paired by ``run_id``.
    Span = wall-clock between the first and last event. Returns the ratio in
    [0, 1], or None when there are no paired runs or zero span (loop-off / no
    live waves — the gate is inert, not failing). Never fabricates a value.
    """
    starts: dict[str, dt.datetime] = {}
    ends: dict[str, dt.datetime] = {}
    all_ts: list[dt.datetime] = []
    model_mix = {"opus": 0, "sonnet": 0, "haiku": 0}
    dropped_undated = 0
    for ev in events:
        ts = _parse_iso(str(ev.get("created_at", "")))
        if ts is not None:
            all_ts.append(ts)
        else:
            # DAS-1633 — surfaced instead of a silent skip; this event is
            # excluded from both the T1 span and any run_start/run_end pairing.
            dropped_undated += 1
        rid = ev.get("run_id")
        et = ev.get("event_type")
        if et == "run_start" and rid and ts is not None:
            starts[str(rid)] = ts
        elif et == "run_end" and rid and ts is not None:
            ends[str(rid)] = ts
            # T4 model_mix: the model lives on the ``run_end`` completion event
            # (ADR-0023 §4 — ``run_start`` carries no ``model`` field). Counting it
            # off ``run_start`` here left model_mix all-zero even for real opus/sonnet
            # runs (ORGANISM audit F-2). One run has exactly one ``run_end``, so this
            # tallies each run's model once.
            mdl = str(ev.get("model", "")).lower()
            if mdl in model_mix:
                model_mix[mdl] += 1
    intervals = [(starts[r], ends[r]) for r in starts if r in ends]
    stats = {
        "events": len(events),
        "runs_started": len(starts),
        "runs_completed": len(intervals),
        "model_mix": model_mix,
        "dropped_undated": dropped_undated,  # DAS-1633
    }
    if not intervals or len(all_ts) < 2:
        return None, stats
    span = (max(all_ts) - min(all_ts)).total_seconds()
    if span <= 0:
        return None, stats
    return _union_seconds(intervals) / span, stats


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else LIVE_LOG
    try:
        waves = parse(path)
    except FileNotFoundError:
        print(f"Log not found: {path}")
        if path == LIVE_LOG:
            print("(No waves have been run yet; /daslab-cycle writes board/.wave-log "
                  "on first wave. To read an archived log: python3 scripts/wave_kpi.py "
                  f"{LEGACY_LOG})")
        else:
            print("(Pass an explicit log path, e.g. board/.wave-log or "
                  "board/archive/<name>.log)")
        return
    if not waves:
        print("No waves found in", path)
        return

    active_secs, dispatched, models = 0, 0, {"opus": 0, "sonnet": 0, "haiku": 0}
    none_waves = 0
    print(f"DasLab wave KPI  —  {path}")
    print("=" * 72)
    print(f"{'#':>2}  {'start':<19}  {'active':>7}  {'tickets':>7}  note")
    print("-" * 72)
    for i, w in enumerate(waves, 1):
        active = (w["end"] - w["start"]).total_seconds() if w["end"] else None
        nd = len(w["disp"])
        none_act = bool(NONE_ACT.search("\n".join(w["txt"])))
        if none_act:
            none_waves += 1
        if active is not None:
            active_secs += active
        dispatched += nd
        for mdl in w["disp"]:
            models[mdl] = models.get(mdl, 0) + 1
        note = "nothing actionable" if none_act else (f"{nd} dispatched" if nd else "")
        print(f"{i:>2}  {w['start']:%Y-%m-%d %H:%M:%S}  {fmt(active):>7}  {nd:>7}  {note}")

    span = (waves[-1]["end"] or waves[-1]["start"]) - waves[0]["start"]
    span_h = span.total_seconds() / 3600
    active_h = active_secs / 3600
    act_waves = sum(1 for w in waves if w["disp"])
    print("=" * 72)
    print(f"Waves logged ............ {len(waves)}")
    print(f"  with dispatch ......... {act_waves}")
    print(f"  'nothing actionable' .. {none_waves}")
    print(f"  idle/empty ............ {len(waves) - act_waves}  ({(len(waves)-act_waves)/len(waves)*100:.0f}% of waves)")
    print(f"Tickets dispatched ...... {dispatched}")
    print(f"  model mix ............. opus {models['opus']} · sonnet {models['sonnet']} · haiku {models['haiku']}")
    print(f"Total ACTIVE work time .. {active_h:.2f} h  ({active_secs/60:.0f} min)")
    print(f"Total elapsed span ...... {span_h:.2f} h")
    if active_h > 0:
        print(f"Throughput (active) ..... {dispatched/active_h:.1f} dispatched-tickets / active-hour")
    if span_h > 0:
        print(f"Throughput (elapsed) .... {dispatched/span_h:.2f} dispatched-tickets / elapsed-hour")
        print(f"Busy fraction ........... {active_h/span_h*100:.1f}%  (rest is sleep/idle)")
    else:
        print("Throughput (elapsed) .... n/a (single wave / zero elapsed span)")
    if act_waves:
        print(f"Avg active wave ......... {fmt(active_secs/act_waves)}")


if __name__ == "__main__":
    main()
