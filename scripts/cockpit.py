#!/usr/bin/env python3
"""cockpit.py — Operator Cockpit v1.

A PASSIVE, live, multi-panel, view-only cockpit, each panel bound to a REAL data
source. Where live telemetry does not exist yet (the loop is in shadow mode and no
waves have run), the panel says so plainly — nothing is mocked, no number is
fabricated. Beyond the six base health panels it renders the live run feed, wave
timeline, per-agent + per-tool usage, budget burn (cost-ledger), the T1-T7 metric
sparklines (trends), and an ACTION CONSOLE that surfaces pending interrupt-cards
(board/interrupts/) with copy-paste ``resume:<value>`` answer stubs so the Founder
can answer in under 60 seconds. Every §5 contract number (T1-T7, spans, cost) is
visible; an empty source renders the NODATA sentinel — never a crash, never a
fabricated number.
UAT: an operator can explain the current system state in plain
English from this cockpit alone — the plain-English glossary (--glossary) backs that.

Usage:
    python3 scripts/cockpit.py
    python3 scripts/cockpit.py --glossary
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import memory_lib
import metrics_lib
import trends
import wave_kpi
from _paths import ROOT
from cost.cost_ledger import aggregate_spans

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    yaml = None

GLOSSARY = {
    "QONUN-5": "The human-only approval law — new goals, security, schema migrations, GATE-5 deploys, "
               "governance, and permission/secret changes are NEVER auto-approved.",
    "AADL": "The six-stage lifecycle every build follows: Planning -> Design -> Development -> Testing -> "
            "Deployment -> Maintenance, each closed by a GATE.",
    "T1-T7": "The seven health metrics: T1 busy fraction, T2 idle waves, T3 concurrency, T4 cost/model-mix, "
             "T5 recovery, T6 review efficiency, T7 quality (the immutable hard blocker).",
    "GATE-6": "The evidence record every self-tuning change must file before it applies (max quality drop = 0).",
    "BREAK-GLASS": "A 60-minute, single-rollback emergency override — logged, auto-expiring, with a "
                   "mandatory post-incident review within 24h.",
    "shadow mode": "The self-optimizing loop is OFF: it may read metrics but applies no change. Real numbers "
                   "appear here once live waves run.",
    "intent preview": "Before an agent runs, see what it plans to do and whether it needs human approval "
                      "(scripts/intent_preview.py).",
    "escalation context": "When an agent escalates, the decision trace + recent memory + error context in one "
                          "package (scripts/escalation_context.py).",
    "approval digest": "Low-risk pending approvals batched into one summary; QONUN-5 items routed to individual "
                       "review (scripts/approval_digest.py).",
    "alerting": "Threshold-based proactive notifications; Quiet Mode alerts only on anomalies "
                "(scripts/alerting.py). P5 — trigger-gated.",
    "trends": "Time-series trend (improving/degrading) of the metrics over windows (scripts/trends.py). P5.",
    "adaptive taxonomy": "Proposes SOFT risk-tier recalibrations from history as GATE-6 drafts — NEVER the "
                         "immutable QONUN-5 list, never auto-applied (scripts/adaptive_taxonomy.py). P5.",
    "blind review": "Reviewer doesn't see the author + rotation, to prevent T6 reviewer drift "
                    "(scripts/check_blind_review.py). P5.",
    "loop controller": "Reports whether the self-optimizing loop may advance a rung "
                       "(shadow->measured->limited_live->full) — requires >=1wk clean live T1-T7 + a "
                       "human-approved GATE-6 record; NEVER auto-promotes (scripts/loop_controller.py). P6 capstone.",
}

NODATA = "(no data yet — appears once live waves run; the loop is in shadow mode)"


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def _load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:  # missing, a directory, or unreadable — treat as no data
        return []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def panel_current_wave(waves: list[dict]) -> list[str]:
    if not waves:
        return [NODATA]
    w = waves[-1]
    disp = w.get("disp") or []
    mix: dict[str, int] = {}
    for m in disp:
        mix[m] = mix.get(m, 0) + 1
    mix_str = ", ".join(f"{n} {mdl}" for mdl, n in sorted(mix.items())) or "none"
    return [
        f"latest wave: {w['start']:%Y-%m-%d %H:%M}",
        f"dispatched: {len(disp)} (models: {mix_str})",
    ]


def panel_frontier(waves: list[dict]) -> list[str]:
    r = metrics_lib.idle_wave_rates(waves)
    if r is None:
        return [NODATA]
    return [f"idle (T2a): {r['t2a_rate']:.0%}", f"blocked (T2b): {r['t2b_rate']:.0%}", f"over {r['total']} wave(s)"]


def panel_quality(events: list[dict]) -> list[str]:
    lines = ["T7 rubric: intact, immutable (hard blocker)"]
    eff = metrics_lib.review_efficiency(events)
    if eff is None:
        lines.append(f"reviews: {NODATA}")
    else:
        lines.append(
            f"reviews: {eff['reviews']}, rework {eff['rework_rate']:.0%}, "
            f"median cycle {eff['median_cycle_s'] / 60:.0f}m"
        )
    return lines


def panel_gate6(experiments: Path, events: list[dict]) -> list[str]:
    counts = {"applied": 0, "reverted": 0, "deferred": 0, "failed": 0}
    if yaml is not None and experiments.exists():
        for f in sorted(list(experiments.rglob("*.yaml")) + list(experiments.rglob("*.yml"))):
            if "TEMPLATE" in f.name.upper():
                continue
            try:
                data = yaml.safe_load(f.read_text())
            except yaml.YAMLError:
                continue
            rec = data.get("gate_6_record", data) if isinstance(data, dict) else None
            if isinstance(rec, dict):
                status = str((rec.get("result") or {}).get("status", "")).lower()
                if status in counts:
                    counts[status] += 1
    tuning = sum(1 for e in events if e.get("event_type") == "gate6_tuning" or e.get("change_type"))
    if sum(counts.values()) == 0 and tuning == 0:
        return ["no tuning changes — loop is OFF (shadow); ship levers, not results"]
    return [
        f"records: applied {counts['applied']}, reverted {counts['reverted']}, deferred {counts['deferred']}",
        f"tuning events: {tuning}",
    ]


def panel_risk(board: Path) -> list[str]:
    tickets_dir = board / "tickets"
    tickets = sorted(tickets_dir.glob("DAS-*.md")) if tickets_dir.is_dir() else []
    if not tickets:
        return [NODATA]
    p0 = blocked = in_review = 0
    for t in tickets:
        try:
            text = t.read_text(encoding="utf-8", errors="ignore")
        except OSError:  # unreadable / directory — skip, never crash the cockpit
            continue
        fm = _frontmatter(text)
        p0 += fm.get("priority") == "p0"
        blocked += fm.get("status") == "blocked"
        in_review += fm.get("status") == "in_review"
    return [
        f"tickets: {len(tickets)}",
        f"p0 high-risk: {p0}, blocked: {blocked}, in-review (pending approval): {in_review}",
    ]


def panel_memory(store: Path, config: dict, now: datetime) -> list[str]:
    mems = _load_jsonl(store)
    if not mems:
        return ["no memory store yet (ArcRift is the live backend)"]
    recall = memory_lib.recallable(mems, now, config)
    health = memory_lib.memory_health(mems, now, config)
    return [f"memories: {len(mems)}, recallable: {len(recall)}", f"health score: {health:.0%}"]


# --------------------------------------------------------------------------- #
# ORGANISM WS5 O5-T02/T03 (DAS-1481) — additional live panels + Action Console.
# All read the SAME event store / cost-ledger / interrupts dir cockpit already
# knows; every one degrades to NODATA (or an honest empty-state line) — nothing
# is fabricated, nothing crashes.
# --------------------------------------------------------------------------- #

_SPARK = "▁▂▃▄▅▆▇█"

ACTION_CONSOLE_EMPTY = "no pending interrupt-cards — nothing awaits a Founder answer"


def _safe_int(value: object) -> int:
    """Coerce a token field to a non-negative int; 0 on None / bad value."""
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _tier(model: str) -> str:
    """Map a raw model id to opus/sonnet/haiku (else the lower-cased raw string)."""
    m = model.lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in m:
            return tier
    return m or "(unknown)"


def _sparkline(values: list[float]) -> str:
    """Render a unicode block sparkline of a numeric series; '' when empty."""
    nums = [float(v) for v in values if isinstance(v, int | float)]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    if hi <= lo:
        return _SPARK[0] * len(nums)
    span = hi - lo
    return "".join(_SPARK[int((v - lo) / span * (len(_SPARK) - 1))] for v in nums)


def panel_run_feed(events: list[dict], limit: int = 5) -> list[str]:
    """Live run feed: T1 busy fraction + run_start/run_end counts + the last N runs."""
    runs = [e for e in events if e.get("event_type") in ("run_start", "run_end")]
    if not runs:
        return [NODATA]
    t1, stats = wave_kpi.busy_fraction_from_events(events)
    lines = [f"T1 busy fraction: {t1:.0%}" if t1 is not None else f"T1 busy fraction: {NODATA}"]
    lines.append(f"runs started: {stats['runs_started']}, completed: {stats['runs_completed']}")
    for e in runs[-limit:]:
        ts = str(e.get("created_at", "?"))
        marker = "start" if e.get("event_type") == "run_start" else "end  "
        extra = f" [{e.get('outcome', '?')}]" if e.get("event_type") == "run_end" else ""
        lines.append(f"{ts}  {marker}  {e.get('ticket_id', '?')}{extra}")
    return lines


def panel_wave_timeline(waves: list[dict], events: list[dict], limit: int = 6) -> list[str]:
    """Wave timeline: T3 concurrency + a per-wave dispatched sparkline + recent waves."""
    if not waves:
        return [NODATA]
    conc = metrics_lib.concurrency_stats(events)
    if conc is None:
        lines = [f"T3 concurrency: {NODATA}"]
    else:
        lines = [f"T3 concurrency: median {conc['median']:.1f}, p95 {conc['p95']:.1f} "
                 f"({conc['samples']} sample(s))"]
    counts = [float(len(w.get("disp") or [])) for w in waves]
    lines.append(f"waves: {len(waves)}, dispatched: {_sparkline(counts) or '(none)'}")
    for w in waves[-limit:]:
        nd = len(w.get("disp") or [])
        note = "idle" if not nd else f"{nd} dispatched"
        lines.append(f"{w['start']:%Y-%m-%d %H:%M}  {note}")
    return lines


def panel_per_agent(events: list[dict]) -> list[str]:
    """Per-agent success / tokens / tier, rolled up from the span event stream."""
    rollup: dict[str, dict] = {}
    for e in events:
        if e.get("event_type") != "span":
            continue
        name = str(e.get("gen_ai.agent.name") or "(unknown agent)")
        a = rollup.setdefault(name, {"spans": 0, "ok": 0, "in": 0, "out": 0, "tiers": set()})
        a["spans"] += 1
        if str(e.get("status", "")).lower() == "ok":
            a["ok"] += 1
        a["in"] += _safe_int(e.get("gen_ai.usage.input_tokens"))
        a["out"] += _safe_int(e.get("gen_ai.usage.output_tokens"))
        mdl = str(e.get("gen_ai.request.model") or "")
        if mdl:
            a["tiers"].add(_tier(mdl))
    if not rollup:
        return [NODATA]
    lines = []
    for name, a in sorted(rollup.items(), key=lambda kv: -kv[1]["spans"]):
        succ = a["ok"] / a["spans"] if a["spans"] else 0.0
        tiers = ",".join(sorted(a["tiers"])) or "?"
        lines.append(f"{name}: {succ:.0%} ok ({a['ok']}/{a['spans']}), "
                     f"tok in {a['in']}/out {a['out']}, tier {tiers}")
    return lines


def panel_per_tool(events: list[dict]) -> list[str]:
    """Per-tool usage: tool_call events by name + span-kind mix + tool_unavailable count."""
    tools: dict[str, int] = {}
    kinds: dict[str, int] = {}
    unavailable = 0
    for e in events:
        et = e.get("event_type")
        if et == "tool_call":
            name = str(e.get("tool") or e.get("tool_name") or e.get("name") or "(unnamed)")
            tools[name] = tools.get(name, 0) + 1
        elif et == "span":
            k = str(e.get("kind") or "?")
            kinds[k] = kinds.get(k, 0) + 1
        elif et == "tool_unavailable":
            unavailable += 1
    if not tools and not kinds and not unavailable:
        return [NODATA]
    lines = []
    for name, n in sorted(tools.items(), key=lambda kv: -kv[1]):
        lines.append(f"tool {name}: {n} call(s)")
    if kinds:
        mix = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
        lines.append(f"span kinds: {mix}")
    if unavailable:
        lines.append(f"tool_unavailable events: {unavailable}")
    return lines


def panel_budget_burn(events_path: Path) -> list[str]:
    """Budget burn from the cost-ledger: total spans, est USD cost, tokens, per-tier."""
    try:
        ledger = aggregate_spans(store_path=events_path)
    except (OSError, ValueError):  # missing budgets / unreadable store — never crash
        ledger = None
    if ledger is None:
        return [NODATA]
    lines = [
        f"spans: {ledger.raw_span_count}, est cost: ${ledger.raw_estimated_cost_usd:.4f}",
        f"tokens: in {ledger.raw_input_tokens}, out {ledger.raw_output_tokens}, "
        f"cached {ledger.raw_cached_input_tokens}",
    ]
    for tier, g in sorted(ledger.by_tier.items(), key=lambda kv: -kv[1].estimated_cost_usd):
        lines.append(f"{tier}: ${g.estimated_cost_usd:.4f} ({g.span_count} span(s))")
    if ledger.unknown_tiers:
        lines.append(f"unpriced tiers (0 cost, surfaced): {', '.join(sorted(ledger.unknown_tiers))}")
    return lines


def panel_metrics(events: list[dict], waves: list[dict]) -> list[str]:
    """Every §5 contract number T1-T7 in one glance + a throughput sparkline (trends)."""
    t1, _ = wave_kpi.busy_fraction_from_events(events)
    r = metrics_lib.idle_wave_rates(waves)
    conc = metrics_lib.concurrency_stats(events)
    mix = metrics_lib.model_mix(events)
    rec = metrics_lib.recovery_reliability(events)
    eff = metrics_lib.review_efficiency(events)
    lines = [
        f"T1 busy fraction: {t1:.0%}" if t1 is not None else f"T1 busy fraction: {NODATA}",
        f"T2 idle waves: {r['t2a_rate']:.0%}" if r else f"T2 idle waves: {NODATA}",
        f"T3 concurrency (median): {conc['median']:.1f}" if conc else f"T3 concurrency: {NODATA}",
        f"T4 haiku-eligible share: {mix['ratio']:.0%}" if mix else f"T4 model mix: {NODATA}",
        f"T5 recovery: {rec['ratio']:.0%}" if rec else f"T5 recovery: {NODATA}",
        f"T6 review rework: {eff['rework_rate']:.0%}" if eff else f"T6 review: {NODATA}",
        "T7 rubric: intact, immutable (hard blocker)",
    ]
    series = trends.throughput_series(events, 7)
    trend = trends.classify_trend(series, higher_is_better=True)
    if trend["direction"] == "insufficient":
        lines.append(f"throughput sparkline: {NODATA} (P5 trends trigger-gated)")
    else:
        lines.append(f"throughput {trend['direction']}: {_sparkline(series)} "
                     f"(slope {trend['slope']:+.2f})")
    return lines


def panel_action_console(interrupts_dir: Path) -> list[str]:
    """Action Console: pending interrupt-cards + copy-paste ``resume:<value>`` stubs.

    Lists every ``board/interrupts/<id>.json`` card (schema: interrupts/README.md)
    with its question, options, and a ready-to-copy ``resume:<option>`` line per
    option so the Founder answers in <60s. The design-of-record ``schema.json`` is
    NOT a card and is skipped. Malformed/unreadable cards are annotated, never fatal.
    """
    if not interrupts_dir.is_dir():
        return [ACTION_CONSOLE_EMPTY]
    cards = [c for c in sorted(interrupts_dir.glob("*.json")) if c.name != "schema.json"]
    if not cards:
        return [ACTION_CONSOLE_EMPTY]
    lines = [f"{len(cards)} pending — answer any in <60s by copying its resume: line"]
    for cf in cards:
        try:
            data = json.loads(cf.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            lines.append(f"[{cf.stem}] (unreadable card — skipped)")
            continue
        if not isinstance(data, dict):
            lines.append(f"[{cf.stem}] (malformed card — skipped)")
            continue
        ticket = str(data.get("ticket") or "?")
        by = str(data.get("created_by") or "?")
        opts = data.get("options")
        opts = opts if isinstance(opts, list) else []
        lines.append(f"[{cf.stem}] ticket {ticket} (raised by {by})")
        lines.append(f"   Q: {data.get('question') or '(no question)'}")
        if opts:
            lines.append(f"   options: {' | '.join(str(o) for o in opts)}")
            for o in opts:
                lines.append(f"   answer -> copy: resume:{o}")
        else:
            lines.append("   (no options listed — cannot form an answer stub)")
    return lines


def _render_panel(num: int, title: str, lines: list[str]) -> str:
    head = f"== {num}. {title} " + "=" * max(2, 50 - len(title))
    body = "\n".join(f"   {ln}" for ln in lines)
    return f"{head}\n{body}"


def render(events_path: Path, wave_log: Path, experiments: Path, board: Path,
           mem_store: Path, mem_config: Path, now: datetime,
           interrupts: Path) -> str:
    events = wave_kpi.read_events(str(events_path))
    waves = metrics_lib.read_waves(str(wave_log))
    config: dict = {}
    if yaml is not None and mem_config.is_file():
        try:
            loaded = yaml.safe_load(mem_config.read_text())
        except (OSError, yaml.YAMLError):
            loaded = None
        config = loaded if isinstance(loaded, dict) else {}
    panels = [
        ("Current Wave", panel_current_wave(waves)),
        ("Frontier Health", panel_frontier(waves)),
        ("Quality Health", panel_quality(events)),
        ("GATE-6 Decisions", panel_gate6(experiments, events)),
        ("Risk Escalations", panel_risk(board)),
        ("Memory Health", panel_memory(mem_store, config, now)),
        ("Live Run Feed", panel_run_feed(events)),
        ("Wave Timeline", panel_wave_timeline(waves, events)),
        ("Per-Agent Usage", panel_per_agent(events)),
        ("Per-Tool Usage", panel_per_tool(events)),
        ("Budget Burn", panel_budget_burn(events_path)),
        ("Metrics T1-T7 & Sparklines", panel_metrics(events, waves)),
        ("Action Console", panel_action_console(interrupts)),
    ]
    out = ["DasLab Operator Cockpit v1 (passive · live · shadow mode)", ""]
    out += [_render_panel(i, t, lines) for i, (t, lines) in enumerate(panels, 1)]
    out += [
        "",
        "Trust affordances (operator tools): intent_preview.py (what an agent will do before it runs),",
        "  approval_digest.py (batch low-risk approvals), escalation_context.py (diagnose an escalation).",
        "Proactive (P5, trigger-gated): alerting.py (threshold alerts + Quiet Mode), trends.py (metric trends).",
        "Capstone (P6): loop_controller.py reports loop-promotion eligibility — the loop stays OFF until a human approves.",
        "Tip: `cockpit.py --glossary` explains QONUN-5 / AADL / T1-T7 / GATE-6 in plain English.",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--wave-log", type=Path, default=ROOT / "board" / ".wave-log")
    ap.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    ap.add_argument("--board", type=Path, default=ROOT / "board")
    ap.add_argument("--memory-store", type=Path, default=ROOT / "board" / ".arcrift-outbox.jsonl")
    ap.add_argument("--memory-config", type=Path, default=ROOT / "config" / "memory_governance.yaml")
    ap.add_argument("--interrupts", type=Path, default=ROOT / "board" / "interrupts")
    ap.add_argument("--glossary", action="store_true", help="print the plain-English glossary and exit")
    args = ap.parse_args(argv)

    if args.glossary:
        print("DasLab Cockpit — plain-English glossary\n")
        for term, meaning in GLOSSARY.items():
            print(f"{term}: {meaning}\n")
        return 0

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    print(render(args.events, args.wave_log, args.experiments, args.board,
                 args.memory_store, args.memory_config, now, args.interrupts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
