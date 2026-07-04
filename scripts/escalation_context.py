#!/usr/bin/env python3
"""escalation_context.py — Escalation Context Package.

When an agent escalates, attach the decision TRACE (the ticket's routing
transitions), the recent recallable MEMORY, and the ERROR context, so the operator
can diagnose confidently instead of staring at a black box. Inert/empty when there
is no event/memory data yet (the package renders with explicit "(none)" sections).

Usage:
    python3 scripts/escalation_context.py --ticket DAS-1311
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import memory_lib
import wave_kpi
from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


def _load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
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


def build_package(ticket_id: str, events: list[dict], memories: list[dict],
                  config: dict, now: datetime) -> dict:
    tid = str(ticket_id)
    trace = sorted(
        [e for e in events if str(e.get("ticket_id")) == tid and e.get("event_type") == "routing_decision"],
        key=lambda e: str(e.get("created_at", "")),
    )
    escalations = [e for e in events if str(e.get("ticket_id")) == tid and e.get("event_type") == "escalation"]
    recent = memory_lib.recallable(memories, now, config)[-5:]
    return {
        "ticket": tid,
        "decision_trace": [
            {"from": t.get("from_status"), "to": t.get("to_status"),
             "reason": t.get("reason"), "at": t.get("created_at")}
            for t in trace
        ],
        "escalations": [{"reason": e.get("reason"), "error": e.get("error"), "at": e.get("created_at")} for e in escalations],
        "recent_memory": [{"id": m.get("id"), "trust": m.get("trust_score"), "content": m.get("content")} for m in recent],
    }


def render_package(pkg: dict) -> str:
    lines = [f"Escalation context — {pkg['ticket']}", f"  decision trace ({len(pkg['decision_trace'])} step(s)):"]
    for s in pkg["decision_trace"]:
        lines.append(f"    {s['from']} -> {s['to']}  {s.get('reason') or ''}")
    if not pkg["decision_trace"]:
        lines.append("    (no transitions recorded yet)")
    lines.append(f"  error context ({len(pkg['escalations'])}):")
    for e in pkg["escalations"]:
        lines.append(f"    {e.get('reason') or ''} | {e.get('error') or ''}")
    if not pkg["escalations"]:
        lines.append("    (no escalation event recorded)")
    lines.append(f"  recent memory ({len(pkg['recent_memory'])}):")
    for m in pkg["recent_memory"]:
        lines.append(f"    [{m['trust']}] {m['id']}: {str(m['content'])[:60]}")
    if not pkg["recent_memory"]:
        lines.append("    (no memory store yet)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--memory-store", type=Path, default=ROOT / "board" / ".arcrift-outbox.jsonl")
    ap.add_argument("--memory-config", type=Path, default=ROOT / "config" / "memory_governance.yaml")
    args = ap.parse_args(argv)

    config: dict = {}
    if args.memory_config.is_file():
        try:
            loaded = yaml.safe_load(args.memory_config.read_text())
        except (OSError, yaml.YAMLError):
            loaded = None
        config = loaded if isinstance(loaded, dict) else {}
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    pkg = build_package(args.ticket, wave_kpi.read_events(str(args.events)),
                        _load_jsonl(args.memory_store), config, now)
    print(render_package(pkg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
