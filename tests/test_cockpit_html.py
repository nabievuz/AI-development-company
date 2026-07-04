#!/usr/bin/env python3
"""tests/test_cockpit_html.py — HTML cockpit render (ADR-0028 D-1..D-6)."""
from __future__ import annotations

import datetime as dt
import html as _html_lib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cockpit  # noqa: E402
import cockpit_html  # noqa: E402

# Sentinel reused across tests.
_NOW = dt.datetime(2026, 7, 3, 12, 0, 0)


def _args(tmp_path: Path) -> dict:
    """Return keyword arguments for render_html / write_snapshot using tmp dirs."""
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


# All panel titles cockpit.py's render() emits — HTML must mirror every one (ADR-0028 D-4).
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


# ── D-1 / D-5: pure render, no server ───────────────────────────────────────────


def test_render_html_returns_string_without_server(tmp_path: Path) -> None:
    """render_html() must succeed with no socket bound and no live server."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert isinstance(html, str)
    assert len(html) > 100


def test_render_html_is_valid_html_skeleton(tmp_path: Path) -> None:
    """Rendered output must contain the required HTML5 skeleton elements."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "<head>" in html or "<head" in html
    assert "<body>" in html or "<body" in html
    assert "</body>" in html


def test_render_html_contains_all_panels(tmp_path: Path) -> None:
    """All cockpit panels (matching cockpit.py's render()) must appear in the HTML.

    The HTML surface must be panel-count-parity with cockpit.py — no panel may
    be silently dropped (ADR-0028 D-4; DAS-1482 fix).  This test is intentionally
    kept generic: adding a panel to cockpit.py breaks this test until cockpit_html
    is updated to match, making the divergence immediately visible.

    Panel titles are compared after HTML-escaping because _render_panel_html
    escapes them (e.g. '&' -> '&amp;').
    """
    html = cockpit_html.render_html(**_args(tmp_path))
    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in html, f"Missing panel in HTML: {title!r} (looked for {escaped!r})"


def test_render_html_contains_action_console_and_resume_stubs(tmp_path: Path) -> None:
    """Action Console must appear in the HTML with resume:<value> copy-paste stubs.

    DAS-1479: 'the browser surface lets a Founder answer an interrupt-card in-flow.'
    """
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
    """Generated-at timestamp must appear so stale snapshots are honestly stale (D-5)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "2026-07-03" in html, "Generated-at date not found in HTML output"
    assert "Generated:" in html


def test_render_html_nodata_when_empty_store(tmp_path: Path) -> None:
    """Empty data sources must yield NODATA sentinel — nothing fabricated (D-5)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    # cockpit.NODATA text must appear because all data sources are empty tmp dirs.
    assert cockpit.NODATA in html


# ── D-2: auto-refresh via <meta> only, no JavaScript ────────────────────────────


def test_meta_refresh_present(tmp_path: Path) -> None:
    """HTML must contain <meta http-equiv='refresh'> for auto-refresh (D-2)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert 'http-equiv="refresh"' in html or "http-equiv='refresh'" in html


def test_no_script_tags_in_output(tmp_path: Path) -> None:
    """No <script> tags — zero JavaScript, no build step required (D-2 / D-6)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<script" not in html.lower()


def test_custom_refresh_interval(tmp_path: Path) -> None:
    """The refresh interval must be honoured in the <meta> tag."""
    html = cockpit_html.render_html(**_args(tmp_path), refresh_s=60)
    assert 'content="60"' in html


# ── D-6: self-contained, no external assets ─────────────────────────────────────

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
    """No CDN links, web fonts, remote images, or XHR/fetch calls (D-6)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    html_lower = html.lower()
    for pat in _EXTERNAL_PATTERNS:
        assert pat.lower() not in html_lower, (
            f"External ref found in HTML output: {pat!r}"
        )


def test_inline_css_present(tmp_path: Path) -> None:
    """CSS must be inline (no <link rel='stylesheet'> to an external file — D-6)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert "<style>" in html
    assert "link rel" not in html.lower()


# ── D-1: static snapshot write ──────────────────────────────────────────────────


def test_write_snapshot_creates_file(tmp_path: Path) -> None:
    """write_snapshot() must write an HTML file without binding a socket."""
    out = tmp_path / "cockpit.html"
    result = cockpit_html.write_snapshot(out, **_args(tmp_path))
    assert result == out
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_write_snapshot_creates_parent_dirs(tmp_path: Path) -> None:
    """write_snapshot() must create missing parent directories."""
    out = tmp_path / "nested" / "sub" / "cockpit.html"
    cockpit_html.write_snapshot(out, **_args(tmp_path))
    assert out.is_file()


def test_static_snapshot_readable_as_full_html(tmp_path: Path) -> None:
    """The written snapshot must be a complete, self-contained HTML document."""
    out = tmp_path / "snap.html"
    cockpit_html.write_snapshot(out, **_args(tmp_path))
    content = out.read_text(encoding="utf-8")
    # Must have all structural required elements.
    for marker in ("<!DOCTYPE html>", "<html", "</html>", "<style>", "<body"):
        assert marker in content, f"Missing HTML marker: {marker}"
    # Must have auto-refresh meta.
    assert 'http-equiv="refresh"' in content or "http-equiv='refresh'" in content


# ── D-4: wraps cockpit.py, does not duplicate its logic ─────────────────────────


def test_cockpit_nodata_sentinel_reused(tmp_path: Path) -> None:
    """The NODATA sentinel from cockpit.py must appear verbatim (no re-implementation)."""
    html = cockpit_html.render_html(**_args(tmp_path))
    assert cockpit.NODATA in html


def test_render_html_with_real_repo_state() -> None:
    """render_html() against the real (shadow) repo state must not raise."""
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
    # All panel titles must be present — HTML must be parity with cockpit.py (D-4).
    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in html, f"Missing panel in real-repo HTML: {title!r} (looked for {escaped!r})"


# ── CLI entry point ──────────────────────────────────────────────────────────────


def test_main_writes_snapshot(tmp_path: Path) -> None:
    """main() with --out must write a snapshot and return 0."""
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
    # All panels must appear in the CLI-generated snapshot too.
    for title in _ALL_PANEL_TITLES:
        escaped = _html_lib.escape(title)
        assert escaped in content, f"Missing panel in main() snapshot: {title!r} (looked for {escaped!r})"
