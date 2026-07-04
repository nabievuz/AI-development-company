#!/usr/bin/env python3
"""
tests/test_wave_kpi.py — unit tests for scripts/wave_kpi.py

Covers:
 - wave header parse
 - idle-marker parse (end timestamp + idle_decl)
 - dispatch row parse + model-mix tally
 - busy-fraction + throughput math (via main() output capture)
 - empty-log path (no waves found)
 - nothing-actionable path
 - missing-file error path
 - back-compat: LIVE_LOG / LEGACY_LOG constants exist
"""
import datetime as dt
import io
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Import the module under test from scripts/
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wave_kpi  # noqa: E402  (import after path manipulation)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_log(tmp_path: Path, content: str) -> Path:
    """Write a .wave-log fixture and return its path."""
    log = tmp_path / ".wave-log"
    log.write_text(textwrap.dedent(content), encoding="utf-8")
    return log


def run_main(log_path: str) -> str:
    """Call wave_kpi.main() with sys.argv pointing at log_path and capture stdout."""
    with mock.patch("sys.argv", ["wave_kpi.py", log_path]):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            wave_kpi.main()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Wave header parse
# ---------------------------------------------------------------------------

class TestWaveParse:
    def test_single_wave_header_parsed(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 08:00:00 =====
        """)
        waves = wave_kpi.parse(str(log))
        assert len(waves) == 1
        w = waves[0]
        assert w["date"] == "2026-06-19"
        assert w["start"] == dt.datetime(2026, 6, 19, 8, 0, 0)
        assert w["end"] is None

    def test_two_consecutive_waves(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 08:00:00 =====
            | DAS-1300 some-ticket  todo → in_progress  sre-eng  sonnet |
            [idle 30s before next wave — 08:03:00]
            ===== wave 2026-06-19 08:03:30 =====
            | DAS-1301 other-ticket  todo → in_progress  qa-eng  haiku |
            [idle 45s before next wave — 08:07:00]
        """)
        waves = wave_kpi.parse(str(log))
        assert len(waves) == 2
        assert waves[0]["start"] == dt.datetime(2026, 6, 19, 8, 0, 0)
        assert waves[1]["start"] == dt.datetime(2026, 6, 19, 8, 3, 30)


# ---------------------------------------------------------------------------
# 2. Idle-marker parse
# ---------------------------------------------------------------------------

class TestIdleParse:
    def test_idle_sets_end_and_idle_decl(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            [idle 120s before next wave — 10:05:00]
        """)
        waves = wave_kpi.parse(str(log))
        w = waves[0]
        assert w["idle_decl"] == 120
        assert w["end"] == dt.datetime(2026, 6, 19, 10, 5, 0)

    def test_idle_midnight_rollover(self, tmp_path):
        """end time before start → advance by one day."""
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 23:59:00 =====
            [idle 90s before next wave — 00:01:00]
        """)
        waves = wave_kpi.parse(str(log))
        w = waves[0]
        # end should be 2026-06-20 00:01:00
        assert w["end"] == dt.datetime(2026, 6, 20, 0, 1, 0)

    def test_no_idle_marker_leaves_end_none(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 09:00:00 =====
            | DAS-1300 ticket  todo → in_progress  sre-eng  sonnet |
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["end"] is None


# ---------------------------------------------------------------------------
# 3. Dispatch row parse + model-mix tally
# ---------------------------------------------------------------------------

class TestDispatchParse:
    def test_sonnet_row_captured(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 some-ticket  todo → in_progress  sre-eng  sonnet |
            [idle 10s before next wave — 10:01:00]
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["disp"] == ["sonnet"]

    def test_opus_row_captured(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 ticket  in_review → done  sre-lead  opus |
            [idle 10s before next wave — 10:02:00]
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["disp"] == ["opus"]

    def test_haiku_row_captured(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 ticket  todo → in_progress  some-role  haiku |
            [idle 10s before next wave — 10:01:30]
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["disp"] == ["haiku"]

    def test_model_mix_multi_row(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 ticket-a  todo → in_progress  sre-eng  sonnet |
            | DAS-1301 ticket-b  todo → in_progress  qa-lead  opus   |
            | DAS-1302 ticket-c  todo → in_progress  bot-role  haiku |
            [idle 60s before next wave — 10:10:00]
        """)
        waves = wave_kpi.parse(str(log))
        disp = waves[0]["disp"]
        assert disp.count("sonnet") == 1
        assert disp.count("opus") == 1
        assert disp.count("haiku") == 1

    def test_row_without_model_not_counted(self, tmp_path):
        """A blocked/skipped row without → + model should be ignored."""
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 blocked ticket (no arrow, no model) |
            [idle 10s before next wave — 10:01:00]
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["disp"] == []

    def test_case_insensitive_model_match(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 ticket  todo → in_progress  sre-eng  Sonnet |
            [idle 10s before next wave — 10:01:00]
        """)
        waves = wave_kpi.parse(str(log))
        assert waves[0]["disp"] == ["sonnet"]


# ---------------------------------------------------------------------------
# 4. Busy-fraction + throughput math (via main() output)
# ---------------------------------------------------------------------------

class TestKpiMath:
    def _make_log(self, tmp_path) -> str:
        """Two waves, known active durations, returns log path string."""
        # Wave 1: 10:00 → idle at 10:10 = 600 s active, 2 dispatched
        # Wave 2: 10:15 → idle at 10:20 = 300 s active, 1 dispatched
        # Total active = 900 s = 0.25 h
        # Total span = 10:20 - 10:00 = 1200 s = 0.333... h
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 10:00:00 =====
            | DAS-1300 ticket-a  todo → in_progress  sre-eng  sonnet |
            | DAS-1301 ticket-b  todo → in_progress  qa-lead  opus   |
            [idle 300s before next wave — 10:10:00]
            ===== wave 2026-06-19 10:15:00 =====
            | DAS-1302 ticket-c  todo → in_progress  sre-eng  sonnet |
            [idle 60s before next wave — 10:20:00]
        """)
        return str(log)

    def test_dispatched_count(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        assert "Tickets dispatched ...... 3" in out

    def test_model_mix_line(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        assert "opus 1" in out
        assert "sonnet 2" in out
        assert "haiku 0" in out

    def test_busy_fraction_present(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        # Busy fraction = 900 / 1200 = 75.0%
        assert "Busy fraction" in out
        assert "75.0%" in out

    def test_throughput_active_present(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        # 3 tickets / 0.25 h = 12.0 dispatched-tickets / active-hour
        assert "Throughput (active)" in out
        assert "12.0" in out

    def test_throughput_elapsed_present(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        # 3 / (1200/3600) = 3 / 0.3333 = 9.0 dispatched-tickets / elapsed-hour
        assert "Throughput (elapsed)" in out
        assert "9.0" in out or "9.00" in out

    def test_wave_count_summary(self, tmp_path):
        out = run_main(self._make_log(tmp_path))
        assert "Waves logged ............ 2" in out


# ---------------------------------------------------------------------------
# 5. Empty-log path (no wave headers in file)
# ---------------------------------------------------------------------------

class TestEmptyLog:
    def test_empty_file_prints_no_waves(self, tmp_path):
        log = tmp_path / ".wave-log"
        log.write_text("", encoding="utf-8")
        out = run_main(str(log))
        assert "No waves found" in out

    def test_file_with_only_comments_prints_no_waves(self, tmp_path):
        log = write_log(tmp_path, """\
            # this is a comment
            # another comment
        """)
        out = run_main(str(log))
        assert "No waves found" in out


# ---------------------------------------------------------------------------
# 6. Nothing-actionable path
# ---------------------------------------------------------------------------

class TestNothingActionable:
    def test_nothing_actionable_counted(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 09:00:00 =====
            nothing actionable — 2026-06-19 09:00:01
            [idle 30s before next wave — 09:00:31]
        """)
        waves = wave_kpi.parse(str(log))
        assert len(waves) == 1
        assert waves[0]["disp"] == []
        # confirm the text is captured in the wave's txt list
        assert any("nothing actionable" in line for line in waves[0]["txt"])

    def test_nothing_actionable_note_in_output(self, tmp_path):
        log = write_log(tmp_path, """\
            ===== wave 2026-06-19 09:00:00 =====
            nothing actionable — 2026-06-19 09:00:01
            [idle 30s before next wave — 09:00:31]
        """)
        out = run_main(str(log))
        assert "nothing actionable" in out


# ---------------------------------------------------------------------------
# 7. Missing-file error path
# ---------------------------------------------------------------------------

class TestMissingFile:
    def test_missing_live_log_prints_help(self, tmp_path):
        missing = str(tmp_path / "nonexistent.log")
        out = run_main(missing)
        assert "Log not found" in out

    def test_missing_default_log_gives_wave_log_hint(self):
        """When no path arg is given and board/.wave-log is absent, hint is shown."""
        with mock.patch("sys.argv", ["wave_kpi.py"]):
            # Temporarily ensure board/.wave-log does not exist in cwd
            orig = os.getcwd()
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    wave_kpi.main()
                os.chdir(orig)
        out = buf.getvalue()
        assert "Log not found" in out
        assert "board/.wave-log" in out


# ---------------------------------------------------------------------------
# 8. Back-compat: LIVE_LOG and LEGACY_LOG constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_live_log_constant(self):
        assert wave_kpi.LIVE_LOG == "board/.wave-log"

    def test_legacy_log_constant(self):
        assert wave_kpi.LEGACY_LOG == "board/.night-waves.log"


class TestBusyFractionFromEventsModelMix:
    """F-2 regression: busy_fraction_from_events must tally model_mix from the
    ``run_end`` completion (which carries ``model``), NOT ``run_start`` (which does
    not) — the bug that zeroed model_mix on real opus/sonnet evidence."""

    @staticmethod
    def _run(rid: str, model: str, start: str, end: str) -> list[dict]:
        # run_start deliberately carries NO model (matches build_run_start).
        return [
            {"event_type": "run_start", "run_id": rid, "created_at": start,
             "goal": "g", "engine_version": "1"},
            {"event_type": "run_end", "run_id": rid, "created_at": end,
             "model": model, "outcome": "success"},
        ]

    def test_model_counted_from_run_end(self):
        evs = self._run("R1", "opus", "2026-07-04T10:00:00Z", "2026-07-04T10:10:00Z")
        _, stats = wave_kpi.busy_fraction_from_events(evs)
        assert stats["model_mix"] == {"opus": 1, "sonnet": 0, "haiku": 0}

    def test_model_on_run_start_is_ignored(self):
        # Even if a run_start erroneously carried a model, it must not be tallied
        # (the tally source is run_end only).
        evs = self._run("R1", "sonnet", "2026-07-04T10:00:00Z", "2026-07-04T10:10:00Z")
        evs[0]["model"] = "haiku"  # stray model on run_start
        _, stats = wave_kpi.busy_fraction_from_events(evs)
        assert stats["model_mix"] == {"opus": 0, "sonnet": 1, "haiku": 0}

    def test_multi_run_tally(self):
        evs = (
            self._run("R1", "opus", "2026-07-04T10:00:00Z", "2026-07-04T10:05:00Z")
            + self._run("R2", "haiku", "2026-07-04T11:00:00Z", "2026-07-04T11:02:00Z")
        )
        _, stats = wave_kpi.busy_fraction_from_events(evs)
        assert stats["model_mix"] == {"opus": 1, "sonnet": 0, "haiku": 1}

    def test_incomplete_run_no_end_not_tallied(self):
        # A run_start with no run_end contributes nothing to model_mix.
        evs = [{"event_type": "run_start", "run_id": "R1",
                "created_at": "2026-07-04T10:00:00Z", "goal": "g", "engine_version": "1"}]
        _, stats = wave_kpi.busy_fraction_from_events(evs)
        assert stats["model_mix"] == {"opus": 0, "sonnet": 0, "haiku": 0}
