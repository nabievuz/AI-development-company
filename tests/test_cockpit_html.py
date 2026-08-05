#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import html as _html_lib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cockpit
import cockpit_html

_NOW = dt.datetime(2026, 7, 3, 12, 0, 0)


def _args(tmp_path: Path) -> dict:
    return {
        "events_path": tmp_path / "e.jsonl",
        "wave_log": tmp_path / "w.log",
        "experiments": tmp_path / "exp",
        "board": tmp_path / "board",
        "mem_store": tmp_path / "m.jsonl",
        "mem_config": REPO_ROOT / "config" / "memory_governance.yaml",
        "now": _NOW,
        "interrupts": tmp_path / "interrupts",
    }


_ALL_PANEL_TITLES = (
    "Current Wave",
    "Frontier Health",
    "Quality Health",
    "GATE-6 Decisions",
    "Risk Escalations",
    "Memory Health",
    "Live Run Feed",
    "Wave Timeline",
    "Per-Agent Usage",
    "Per-Tool Usage",
    "Budget Burn",
    "Metrics T1-T7 & Sparklines",
    "Action Console",
)


def test_render_html_returns_string_without_server(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert isinstance(html, str)
    assert len(html) > 100


def test_render_html_is_valid_html_skeleton(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "<head>" in html or "<head" in html
    assert "<body>" in html or "<body" in html
    assert "</body>" in html


def test_render_html_contains_all_panels(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in html, f"Missing panel in HTML: {title!r} (looked for {escaped!r})"


def test_render_html_contains_action_console_and_resume_stubs(tmp_path: Path) -> None:
    import json

    interrupts_dir = tmp_path / "interrupts"
    interrupts_dir.mkdir()
    (interrupts_dir / "DAS-1479-1.json").write_text(
        json.dumps({
            "question": "Deploy to prod or roll back?",
            "options": ["deploy", "rollback"],
            "ticket": "DAS-1479",
            "payload": {},
            "created_by": "backend-eng-1",
        }),
        encoding="utf-8",
    )
    args = _args(tmp_path)
    args["interrupts"] = interrupts_dir
    html = cockpit_html.render_html(**args)
    assert "Action Console" in html, "Action Console panel must appear in HTML"
    assert "Deploy to prod or roll back?" in html, "Interrupt question must appear in HTML"
    assert "resume:deploy" in html, "resume:deploy stub must appear in HTML"
    assert "resume:rollback" in html, "resume:rollback stub must appear in HTML"


def test_render_html_contains_generated_at_timestamp(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "2026-07-03" in html, "Generated-at date not found in HTML output"
    assert "Generated:" in html


def test_render_html_nodata_when_empty_store(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))

    assert cockpit.NODATA in html


def test_meta_refresh_present(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert 'http-equiv="refresh"' in html or "http-equiv='refresh'" in html


def test_no_script_tags_in_output(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<script" not in html.lower()


def test_custom_refresh_interval(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path), refresh_s=60)
    assert 'content="60"' in html


_EXTERNAL_PATTERNS = (
    "http://",
    "https://",
    "//cdn",
    "fonts.googleapis",
    "fonts.gstatic",
    "cdnjs",
    "unpkg",
    "jsdelivr",
    "ajax.googleapis",
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "import(",
    "require(",
    "src=http",
    "href=http",
)


def test_no_external_refs_in_output(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    html_lower = html.lower()
    for pat in _EXTERNAL_PATTERNS:
        assert pat.lower() not in html_lower, (
            f"External ref found in HTML output: {pat!r}"
        )


def test_inline_css_present(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<style>" in html
    assert "link rel" not in html.lower()


def test_write_snapshot_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "cockpit.html"
    result = cockpit_html.write_snapshot(out, **_args(tmp_path))
    assert result == out
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_write_snapshot_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "sub" / "cockpit.html"
    cockpit_html.write_snapshot(out, **_args(tmp_path))
    assert out.is_file()


def test_static_snapshot_readable_as_full_html(tmp_path: Path) -> None:
    out = tmp_path / "snap.html"
    cockpit_html.write_snapshot(out, **_args(tmp_path))
    content = out.read_text(encoding="utf-8")

    for marker in ("<!DOCTYPE html>", "<html", "</html>", "<style>", "<body"):
        assert marker in content, f"Missing HTML marker: {marker}"

    assert 'http-equiv="refresh"' in content or "http-equiv='refresh'" in content


def test_cockpit_nodata_sentinel_reused(tmp_path: Path) -> None:
    html = cockpit_html.render_html(**_args(tmp_path))
    assert cockpit.NODATA in html


def test_render_html_with_real_repo_state() -> None:
    now = dt.datetime.now(tz=dt.UTC).replace(tzinfo=None)
    html = cockpit_html.render_html(
        events_path=REPO_ROOT / "board" / ".events.jsonl",
        wave_log=REPO_ROOT / "board" / ".wave-log",
        experiments=REPO_ROOT / "experiments",
        board=REPO_ROOT / "board",
        mem_store=REPO_ROOT / "board" / ".arcrift-outbox.jsonl",
        mem_config=REPO_ROOT / "config" / "memory_governance.yaml",
        now=now,
        interrupts=REPO_ROOT / "board" / "interrupts",
    )
    assert "<!DOCTYPE html>" in html

    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in html, f"Missing panel in real-repo HTML: {title!r} (looked for {escaped!r})"


def test_main_writes_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "out.html"
    rc = cockpit_html.main([
        "--events", str(tmp_path / "e.jsonl"),
        "--wave-log", str(tmp_path / "w.log"),
        "--experiments", str(tmp_path / "exp"),
        "--board", str(tmp_path / "board"),
        "--memory-store", str(tmp_path / "m.jsonl"),
        "--memory-config", str(REPO_ROOT / "config" / "memory_governance.yaml"),
        "--interrupts", str(tmp_path / "interrupts"),
        "--out", str(out),
    ])
    assert rc == 0
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content

    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in content, f"Missing panel in main() snapshot: {title!r} (looked for {escaped!r})"
