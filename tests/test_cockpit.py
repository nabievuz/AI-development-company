#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cockpit

PANELS = ("Current Wave", "Frontier Health", "Quality Health",
          "GATE-6 Decisions", "Risk Escalations", "Memory Health")


def test_glossary_covers_key_terms(capsys):
    assert cockpit.main(["--glossary"]) == 0
    out = capsys.readouterr().out
    for term in ("QONUN-5", "AADL", "T1-T7", "GATE-6", "BREAK-GLASS", "shadow mode"):
        assert term in out


def test_renders_six_panels_with_no_data(tmp_path, capsys):
    rc = cockpit.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--wave-log", str(tmp_path / "w.log"),
        "--experiments", str(tmp_path / "exp"),
        "--board", str(tmp_path / "board"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    for title in PANELS:
        assert title in out
    assert "shadow mode" in out


def test_panel_current_wave_empty_is_nodata():
    assert cockpit.panel_current_wave([]) == [cockpit.NODATA]


def test_panel_memory_with_data(tmp_path):
    store = tmp_path / "m.jsonl"
    store.write_text(
        json.dumps({
            "id": "m1", "content": "x", "project": "p", "provenance": "verified_pr",
            "trust_score": 1.0, "created_at": "2026-06-20T00:00:00Z", "mem_type": "fact",
        }) + "\n",
        encoding="utf-8",
    )
    cfg = {"recall": {"min_trust": 0.3}, "ttl_days": {"fact": 180, "default": 120}, "health": {"decay_per_bad": 0.05}}
    lines = cockpit.panel_memory(store, cfg, dt.datetime(2026, 6, 21))
    assert any("memories: 1" in ln for ln in lines)
    assert any("recallable: 1" in ln for ln in lines)


def test_gate6_panel_shadow_when_empty(tmp_path):
    lines = cockpit.panel_gate6(tmp_path / "nope", [])
    assert any("loop is OFF" in ln for ln in lines)


def test_real_run_exits_0():

    assert cockpit.main([]) == 0


def _render_args(tmp_path, **over):
    args = {
        "events": tmp_path / "e.jsonl", "wave-log": tmp_path / "w.log",
        "experiments": tmp_path / "exp", "board": tmp_path / "board",
        "memory-store": tmp_path / "m.jsonl",
        "memory-config": REPO_ROOT / "config" / "memory_governance.yaml",
    }
    args.update(over)
    out = []
    for k, v in args.items():
        out += [f"--{k}", str(v)]
    return out


def test_survives_unreadable_ticket(tmp_path):

    tickets = tmp_path / "board" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / "DAS-1-ok.md").write_text("---\nid: DAS-1\npriority: p0\nstatus: todo\n---\n", encoding="utf-8")
    (tickets / "DAS-2-bad.md").mkdir()
    assert cockpit.main(_render_args(tmp_path)) == 0


def test_survives_directory_memory_store(tmp_path):
    store_dir = tmp_path / "storedir"
    store_dir.mkdir()
    assert cockpit.main(_render_args(tmp_path, **{"memory-store": store_dir})) == 0


from dgox.events import build_run_end, build_run_start, build_span

NEW_PANELS = ("Live Run Feed", "Wave Timeline", "Per-Agent Usage", "Per-Tool Usage",
              "Budget Burn", "Metrics T1-T7 & Sparklines", "Action Console")


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _span(**over):
    base = {
        "ticket_id": "DAS-1", "span_id": "s1", "parent_span_id": None,
        "kind": "invoke_agent", "agent_name": "backend-eng-1", "model": "sonnet",
        "start": "2026-07-03T00:00:00Z", "end": "2026-07-03T00:00:01Z",
        "created_at": "2026-07-03T00:00:01Z", "input_tokens": 100,
        "output_tokens": 50, "status": "ok",
    }
    base.update(over)
    return build_span(**base)


def test_new_panels_render_with_no_data(tmp_path, capsys):
    rc = cockpit.main(_render_args(tmp_path, interrupts=tmp_path / "nointerrupts"))
    assert rc == 0
    out = capsys.readouterr().out
    for title in (*PANELS, *NEW_PANELS):
        assert title in out

    for tlabel in ("T1", "T2", "T3", "T4", "T5", "T6", "T7"):
        assert tlabel in out
    assert cockpit.NODATA in out


def test_panel_run_feed_empty_is_nodata():
    assert cockpit.panel_run_feed([]) == [cockpit.NODATA]


def test_panel_run_feed_with_runs():
    events = [
        build_run_start(ticket_id="DAS-1", run_id="r1", goal="g",
                        engine_version="1", created_at="2026-07-03T00:00:00Z"),
        build_run_end(ticket_id="DAS-1", run_id="r1", outcome="success", model="sonnet",
                      merged_pr="PR#1", ci_status="green", t7_pass=True, t7_score=0.95,
                      created_at="2026-07-03T00:01:00Z"),
    ]
    lines = cockpit.panel_run_feed(events)
    assert any("runs started: 1" in ln and "completed: 1" in ln for ln in lines)
    assert any("DAS-1" in ln and "success" in ln for ln in lines)


def test_panel_wave_timeline_empty_is_nodata():
    assert cockpit.panel_wave_timeline([], []) == [cockpit.NODATA]


def test_panel_per_agent_empty_is_nodata():
    assert cockpit.panel_per_agent([]) == [cockpit.NODATA]


def test_panel_per_agent_with_spans():
    events = [
        _span(agent_name="backend-eng-1", status="ok", input_tokens=100, output_tokens=40),
        _span(agent_name="backend-eng-1", status="error", input_tokens=10, output_tokens=5),
        _span(agent_name="qa-eng", model="haiku", status="ok"),
    ]
    lines = cockpit.panel_per_agent(events)
    joined = "\n".join(lines)
    assert "backend-eng-1" in joined
    assert "50% ok (1/2)" in joined
    assert "tier sonnet" in joined
    assert "qa-eng" in joined and "tier haiku" in joined


def test_panel_per_tool_empty_is_nodata():
    assert cockpit.panel_per_tool([]) == [cockpit.NODATA]


def test_panel_per_tool_with_data():
    events = [
        {"event_type": "tool_call", "ticket_id": "DAS-1",
         "created_at": "2026-07-03T00:00:00Z", "tool": "Bash"},
        _span(kind="execute_tool"),
        {"event_type": "tool_unavailable", "ticket_id": "DAS-1",
         "created_at": "2026-07-03T00:00:00Z"},
    ]
    lines = cockpit.panel_per_tool(events)
    joined = "\n".join(lines)
    assert "tool Bash: 1 call(s)" in joined
    assert "execute_tool" in joined
    assert "tool_unavailable events: 1" in joined


def test_panel_budget_burn_empty_is_nodata(tmp_path):
    assert cockpit.panel_budget_burn(tmp_path / "none.jsonl") == [cockpit.NODATA]


def test_panel_budget_burn_with_spans(tmp_path):
    events_path = tmp_path / "e.jsonl"
    _write_events(events_path, [
        _span(model="sonnet", input_tokens=1000, output_tokens=500),
        _span(model="haiku", input_tokens=200, output_tokens=100),
    ])
    lines = cockpit.panel_budget_burn(events_path)
    joined = "\n".join(lines)
    assert "spans: 2" in joined
    assert "est cost: $" in joined
    assert "sonnet:" in joined and "haiku:" in joined


def test_panel_metrics_shows_all_t_numbers():
    lines = cockpit.panel_metrics([], [])
    joined = "\n".join(lines)
    for tlabel in ("T1", "T2", "T3", "T4", "T5", "T6", "T7"):
        assert tlabel in joined
    assert "immutable" in joined


def test_sparkline_renders_and_is_empty_safe():
    assert cockpit._sparkline([]) == ""
    bar = cockpit._sparkline([1.0, 2.0, 3.0, 4.0])
    assert len(bar) == 4
    assert cockpit._sparkline([5.0, 5.0, 5.0]) == cockpit._SPARK[0] * 3


def test_action_console_empty(tmp_path):
    (tmp_path / "interrupts").mkdir()
    assert cockpit.panel_action_console(tmp_path / "interrupts") == [cockpit.ACTION_CONSOLE_EMPTY]

    assert cockpit.panel_action_console(tmp_path / "nope") == [cockpit.ACTION_CONSOLE_EMPTY]


def test_action_console_ignores_schema_json(tmp_path):
    d = tmp_path / "interrupts"
    d.mkdir()
    (d / "schema.json").write_text('{"$schema": "x"}', encoding="utf-8")
    assert cockpit.panel_action_console(d) == [cockpit.ACTION_CONSOLE_EMPTY]


def test_action_console_with_card(tmp_path):
    d = tmp_path / "interrupts"
    d.mkdir()
    (d / "DAS-1450-1.json").write_text(json.dumps({
        "question": "Ship now or wait?",
        "options": ["ship", "wait"],
        "ticket": "DAS-1450",
        "payload": {},
        "created_by": "backend-eng-1",
    }), encoding="utf-8")
    lines = cockpit.panel_action_console(d)
    joined = "\n".join(lines)
    assert "1 pending" in joined
    assert "Ship now or wait?" in joined
    assert "resume:ship" in joined and "resume:wait" in joined
    assert "DAS-1450" in joined


def test_action_console_survives_malformed_card(tmp_path):
    d = tmp_path / "interrupts"
    d.mkdir()
    (d / "DAS-1-1.json").write_text("{not valid json", encoding="utf-8")
    (d / "DAS-2-1.json").write_text("[1, 2, 3]", encoding="utf-8")
    lines = cockpit.panel_action_console(d)
    joined = "\n".join(lines)
    assert "unreadable card" in joined
    assert "malformed card" in joined


def test_action_console_surfaced_in_full_render(tmp_path, capsys):
    d = tmp_path / "interrupts"
    d.mkdir()
    (d / "DAS-9-1.json").write_text(json.dumps({
        "question": "Pick a lane", "options": ["a", "b"], "ticket": "DAS-9",
        "payload": {}, "created_by": "frontend-eng-1",
    }), encoding="utf-8")
    rc = cockpit.main(_render_args(tmp_path, interrupts=d))
    assert rc == 0
    out = capsys.readouterr().out
    assert "resume:a" in out and "Pick a lane" in out
