#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html as _html
import http.server
import socketserver
import sys
from datetime import UTC, datetime
from pathlib import Path

import cockpit
import metrics_lib
import wave_kpi
from _paths import ROOT

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_OUT: Path = ROOT / "board" / ".cockpit.html"
DEFAULT_PORT: int = 8765
DEFAULT_REFRESH: int = 30


_CSS = """\
/* DasLab Cockpit — self-contained inline CSS (ADR-0028 D-6, no external assets) */
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Courier New',Courier,monospace;background:#0d1117;color:#c9d1d9;\
padding:1.5rem;line-height:1.6}
h1{color:#58a6ff;font-size:1.1rem;margin-bottom:.25rem}
.meta{color:#8b949e;font-size:.85rem;margin-bottom:1.5rem}
.panel{border:1px solid #30363d;border-radius:4px;margin-bottom:1rem;padding:1rem}
.panel-title{color:#79c0ff;font-weight:bold;font-size:.95rem;margin-bottom:.5rem;\
border-bottom:1px solid #21262d;padding-bottom:.4rem}
.panel-num{color:#8b949e;font-size:.85rem;margin-right:.4rem}
.panel-line{padding:.15rem 0;color:#c9d1d9}
.nodata{color:#8b949e;font-style:italic}
footer{margin-top:1.5rem;color:#8b949e;font-size:.8rem;\
border-top:1px solid #21262d;padding-top:.75rem}
"""


def _render_panel_html(num: int, title: str, lines: list[str]) -> str:
    rows: list[str] = []
    for ln in lines:
        css = "panel-line nodata" if ln == cockpit.NODATA else "panel-line"
        rows.append(f'    <div class="{css}">{_html.escape(ln)}</div>')
    body = "\n".join(rows)
    return (
        f'<div class="panel">\n'
        f'  <div class="panel-title">'
        f'<span class="panel-num">{num}.</span>{_html.escape(title)}</div>\n'
        f'{body}\n'
        f'</div>'
    )


def render_html(
    events_path: Path,
    wave_log: Path,
    experiments: Path,
    board: Path,
    mem_store: Path,
    mem_config: Path,
    now: datetime,
    interrupts: Path,
    *,
    refresh_s: int = DEFAULT_REFRESH,
) -> str:

    events = wave_kpi.read_events(str(events_path))
    waves = metrics_lib.read_waves(str(wave_log))
    config: dict = {}
    if yaml is not None and mem_config.is_file():
        try:
            loaded = yaml.safe_load(mem_config.read_text())
        except (OSError, yaml.YAMLError):
            loaded = None
        config = loaded if isinstance(loaded, dict) else {}


    panels: list[tuple[str, list[str]]] = [
        ("Current Wave", cockpit.panel_current_wave(waves)),
        ("Frontier Health", cockpit.panel_frontier(waves)),
        ("Quality Health", cockpit.panel_quality(events)),
        ("GATE-6 Decisions", cockpit.panel_gate6(experiments, events)),
        ("Risk Escalations", cockpit.panel_risk(board)),
        ("Memory Health", cockpit.panel_memory(mem_store, config, now)),
        ("Live Run Feed", cockpit.panel_run_feed(events)),
        ("Wave Timeline", cockpit.panel_wave_timeline(waves, events)),
        ("Per-Agent Usage", cockpit.panel_per_agent(events)),
        ("Per-Tool Usage", cockpit.panel_per_tool(events)),
        ("Budget Burn", cockpit.panel_budget_burn(events_path)),
        ("Metrics T1-T7 & Sparklines", cockpit.panel_metrics(events, waves)),
        ("Action Console", cockpit.panel_action_console(interrupts)),
    ]

    panels_html = "\n".join(
        _render_panel_html(i, title, lines)
        for i, (title, lines) in enumerate(panels, 1)
    )


    generated = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f'  <meta http-equiv="refresh" content="{refresh_s}">\n'
        "  <title>DasLab Cockpit</title>\n"
        f"  <style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>DasLab Operator Cockpit v1 &mdash; passive &middot; live"
        " &middot; shadow mode</h1>\n"
        f'  <p class="meta">Generated: {_html.escape(generated)}'
        f" &mdash; auto-refresh every {refresh_s}s</p>\n"
        f"{panels_html}\n"
        "  <footer>\n"
        "    Trust affordances: intent_preview.py &bull; approval_digest.py"
        " &bull; escalation_context.py<br>\n"
        "    Proactive (P5, trigger-gated): alerting.py &bull; trends.py<br>\n"
        "    Capstone (P6): loop_controller.py &mdash; loop stays OFF until"
        " human approves.<br>\n"
        "    Tip: <code>cockpit.py --glossary</code> explains QONUN-5 / AADL"
        " / T1-T7 / GATE-6.\n"
        "  </footer>\n"
        "</body>\n"
        "</html>"
    )


def write_snapshot(
    out: Path,
    events_path: Path,
    wave_log: Path,
    experiments: Path,
    board: Path,
    mem_store: Path,
    mem_config: Path,
    now: datetime,
    interrupts: Path,
    *,
    refresh_s: int = DEFAULT_REFRESH,
) -> Path:
    page = render_html(
        events_path, wave_log, experiments, board, mem_store, mem_config, now,
        interrupts, refresh_s=refresh_s,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def _make_handler(
    events_path: Path,
    wave_log: Path,
    experiments: Path,
    board_path: Path,
    mem_store: Path,
    mem_config: Path,
    interrupts: Path,
    refresh_s: int,
) -> type:

    class _CockpitHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            now = datetime.now(tz=UTC).replace(tzinfo=None)
            try:
                body = render_html(
                    events_path,
                    wave_log,
                    experiments,
                    board_path,
                    mem_store,
                    mem_config,
                    now,
                    interrupts,
                    refresh_s=refresh_s,
                ).encode("utf-8")
            except Exception as exc:
                msg = f"render error: {exc}".encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            sys.stderr.write(f"[cockpit] {fmt % args}\n")

    return _CockpitHandler


def _serve(
    events_path: Path,
    wave_log: Path,
    experiments: Path,
    board_path: Path,
    mem_store: Path,
    mem_config: Path,
    interrupts: Path,
    port: int,
    refresh_s: int,
) -> None:
    handler_cls = _make_handler(
        events_path, wave_log, experiments, board_path, mem_store, mem_config, interrupts, refresh_s
    )
    with socketserver.TCPServer(("127.0.0.1", port), handler_cls) as srv:
        url = f"http://127.0.0.1:{port}/"
        print(f"[cockpit] serving at {url}  (Ctrl-C to stop, loopback only)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n[cockpit] stopped.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description='cockpit_html.py — Zero-infra HTML render of the DasLab cockpit (ADR-0028).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--events", type=Path,
                    default=ROOT / "board" / ".events.jsonl")
    ap.add_argument("--wave-log", type=Path,
                    default=ROOT / "board" / ".wave-log")
    ap.add_argument("--experiments", type=Path,
                    default=ROOT / "experiments")
    ap.add_argument("--board", type=Path, default=ROOT / "board")
    ap.add_argument("--memory-store", type=Path,
                    default=ROOT / "board" / ".arcrift-outbox.jsonl")
    ap.add_argument("--memory-config", type=Path,
                    default=ROOT / "config" / "memory_governance.yaml")
    ap.add_argument("--interrupts", type=Path,
                    default=ROOT / "board" / "interrupts")
    ap.add_argument(
        "--out", type=Path, default=DEFAULT_OUT,
        help="Output path for the static HTML snapshot (default: board/.cockpit.html)",
    )
    ap.add_argument(
        "--refresh", type=int, default=DEFAULT_REFRESH,
        help=f"Auto-refresh interval in seconds (default: {DEFAULT_REFRESH})",
    )
    ap.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port for --serve mode, loopback only (default: {DEFAULT_PORT})",
    )
    ap.add_argument(
        "--serve", action="store_true",
        help="Run optional loopback http.server live mode (foreground, NOT a daemon)",
    )
    args = ap.parse_args(argv)

    if args.serve:
        _serve(
            args.events, args.wave_log, args.experiments, args.board,
            args.memory_store, args.memory_config, args.interrupts, args.port, args.refresh,
        )
        return 0

    now = datetime.now(tz=UTC).replace(tzinfo=None)
    out = write_snapshot(
        args.out,
        args.events, args.wave_log, args.experiments, args.board,
        args.memory_store, args.memory_config,
        now, args.interrupts,
        refresh_s=args.refresh,
    )
    print(f"[cockpit] snapshot written → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
