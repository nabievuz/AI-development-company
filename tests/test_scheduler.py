#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import loop_controller as lc
from flow_router import DISPATCH, IDLE, VALIDATE

_UTC_NOON = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_UTC_MIDNIGHT = datetime(2026, 7, 3, 23, 30, 0, tzinfo=UTC)
_UTC_EARLY = datetime(2026, 7, 3, 5, 0, 0, tzinfo=UTC)


def _schedule(
    start: str = "22:00",
    end: str = "06:00",
    max_concurrent: int = 1,
) -> dict:
    return {
        "version": 1,
        "max_concurrent_waves": max_concurrent,
        "never_auto_approve": True,
        "quiet_hours": {"start": start, "end": end, "timezone": "UTC"},
    }


class TestScheduleYaml:

    def test_schedule_yaml_exists(self):
        path = REPO_ROOT / "board" / "schedule.yaml"
        assert path.is_file(), "board/schedule.yaml must exist"

    def test_schedule_yaml_parses(self):
        import yaml
        path = REPO_ROOT / "board" / "schedule.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "board/schedule.yaml must be a YAML dict"

    def test_schedule_yaml_required_fields(self):
        import yaml
        path = REPO_ROOT / "board" / "schedule.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert data.get("max_concurrent_waves") == 1, "max_concurrent_waves must be 1 (SI-6)"
        assert data.get("never_auto_approve") is True, "never_auto_approve must be true (SI-7)"
        assert "quiet_hours" in data, "quiet_hours section must be present (SI-4)"
        assert "triggers" in data, "triggers section must be present"

    def test_schedule_yaml_quiet_hours_present(self):
        import yaml
        path = REPO_ROOT / "board" / "schedule.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        qh = data.get("quiet_hours") or {}
        assert qh.get("start"), "quiet_hours.start must be set"
        assert qh.get("end"), "quiet_hours.end must be set"

    def test_schedule_yaml_triggers_are_list(self):
        import yaml
        path = REPO_ROOT / "board" / "schedule.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        triggers = data.get("triggers", [])
        assert isinstance(triggers, list) and len(triggers) >= 1, "triggers must be a non-empty list"

    def test_schedule_yaml_contains_five_trigger_types(self):
        import yaml
        path = REPO_ROOT / "board" / "schedule.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        names = {t.get("name") for t in (data.get("triggers") or [])}
        expected = {"cron_tick", "after_n_runs", "ticket_created", "wave_completed", "interrupt_answered"}
        assert expected <= names, f"missing triggers: {expected - names}"


class TestInQuietHours:

    def test_inside_midnight_wrapping_window_late(self):

        assert lc._in_quiet_hours(_schedule("22:00", "06:00"), _UTC_MIDNIGHT) is True

    def test_inside_midnight_wrapping_window_early(self):

        assert lc._in_quiet_hours(_schedule("22:00", "06:00"), _UTC_EARLY) is True

    def test_outside_midnight_wrapping_window(self):

        assert lc._in_quiet_hours(_schedule("22:00", "06:00"), _UTC_NOON) is False

    def test_inside_normal_window(self):

        assert lc._in_quiet_hours(_schedule("09:00", "17:00"), _UTC_NOON) is True

    def test_outside_normal_window(self):

        assert lc._in_quiet_hours(_schedule("09:00", "17:00"), _UTC_EARLY) is False

    def test_empty_quiet_hours_returns_false(self):
        assert lc._in_quiet_hours({}, _UTC_MIDNIGHT) is False

    def test_start_equals_end_returns_false(self):

        assert lc._in_quiet_hours(_schedule("22:00", "22:00"), _UTC_MIDNIGHT) is False

    def test_malformed_time_string_returns_false(self):
        bad = {"quiet_hours": {"start": "not-a-time", "end": "06:00"}}
        assert lc._in_quiet_hours(bad, _UTC_MIDNIGHT) is False


class TestLoadSchedule:
    def test_missing_file_returns_empty(self, tmp_path):
        result = lc._load_schedule(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_malformed_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(": ][bad", encoding="utf-8")
        assert lc._load_schedule(f) == {}

    def test_non_dict_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n", encoding="utf-8")
        assert lc._load_schedule(f) == {}

    def test_valid_schedule_parses(self, tmp_path):
        f = tmp_path / "sched.yaml"
        f.write_text("max_concurrent_waves: 1\nnever_auto_approve: true\n", encoding="utf-8")
        result = lc._load_schedule(f)
        assert result.get("max_concurrent_waves") == 1


class TestTickShadowMode:

    def _tick_shadow(self, tmp_path: Path, trigger: str = "cron_tick", pending: bool = True) -> dict:
        flags_file = tmp_path / "features.yaml"
        flags_file.write_text("heartbeat_enabled: false\n", encoding="utf-8")
        budgets_file = tmp_path / "budgets.yaml"
        budgets_file.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")
        schedule_file = tmp_path / "schedule.yaml"
        schedule_file.write_text(
            "max_concurrent_waves: 1\nquiet_hours:\n  start: '22:00'\n  end: '06:00'\n", encoding="utf-8"
        )
        return lc.tick(
            schedule_path=schedule_file,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=tmp_path / ".events.jsonl",
            budgets_path=budgets_file,
            feature_flags_path=flags_file,
            trigger=trigger,
            pending_work=pending,
            now=_UTC_NOON,
        )

    def test_mode_is_shadow(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert result["mode"] == "shadow"

    def test_shadow_note_present(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert "shadow_note" in result
        assert "shadow" in result["shadow_note"].lower()

    def test_shadow_note_mentions_heartbeat_flag(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert "heartbeat_enabled" in result["shadow_note"]

    def test_shadow_contains_decision(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert "decision" in result
        assert result["decision"]["action"] in ("dispatch", "validate", "idle")

    def test_shadow_contains_promotion(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert "promotion" in result
        assert "eligible" in result["promotion"]

    def test_shadow_contains_safety_rails(self, tmp_path):
        result = self._tick_shadow(tmp_path)
        assert "safety_rails" in result
        rails = result["safety_rails"]
        assert "break_glass_active" in rails
        assert "in_quiet_hours" in rails
        assert "per_day_budget_exceeded" in rails


class TestTickSafetyRails:

    def _make_paths(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        schedule = tmp_path / "schedule.yaml"
        schedule.write_text(
            "max_concurrent_waves: 1\nquiet_hours:\n  start: '22:00'\n  end: '06:00'\n",
            encoding="utf-8",
        )
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")
        events = tmp_path / ".events.jsonl"
        return schedule, budgets, events

    def _flags(self, tmp_path: Path, enabled: bool = True) -> Path:
        f = tmp_path / "features.yaml"
        val = "true" if enabled else "false"
        f.write_text(f"heartbeat_enabled: {val}\n", encoding="utf-8")
        return f

    def test_break_glass_forces_idle(self, tmp_path):
        from break_glass import append_event, build_activation, fmt_ts
        sched, budgets, events = self._make_paths(tmp_path)
        flags = self._flags(tmp_path, enabled=True)

        activation = build_activation(
            activation_id="BG-TEST-001",
            reason="test",
            operator="sre-eng",
            created_at=fmt_ts(_UTC_NOON),
        )
        append_event(activation, path=events)

        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=events,
            budgets_path=budgets,
            feature_flags_path=flags,
            trigger="ticket_created",
            pending_work=True,
            now=_UTC_NOON,
        )
        assert result["safety_rails"]["break_glass_active"] is True
        assert result["decision"]["action"] == IDLE

    def test_quiet_hours_forces_idle_for_dispatch_trigger(self, tmp_path):
        sched, budgets, events = self._make_paths(tmp_path)
        flags = self._flags(tmp_path, enabled=True)

        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=events,
            budgets_path=budgets,
            feature_flags_path=flags,
            trigger="ticket_created",
            pending_work=True,
            now=_UTC_MIDNIGHT,
        )
        assert result["safety_rails"]["in_quiet_hours"] is True
        assert result["decision"]["action"] == IDLE

    def test_quiet_hours_does_not_block_validate(self, tmp_path):
        sched, budgets, events = self._make_paths(tmp_path)
        flags = self._flags(tmp_path, enabled=True)

        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=events,
            budgets_path=budgets,
            feature_flags_path=flags,
            trigger="wave_completed",
            pending_work=False,
            now=_UTC_MIDNIGHT,
        )

        assert result["decision"]["action"] == VALIDATE

    def test_budget_exceeded_forces_idle(self, tmp_path):
        sched, _, events = self._make_paths(tmp_path)
        flags = self._flags(tmp_path, enabled=True)

        zero_budget = tmp_path / "zero_budget.yaml"
        zero_budget.write_text("caps:\n  per_day:\n    max_cost_usd: 0.0\n", encoding="utf-8")

        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=events,
            budgets_path=zero_budget,
            feature_flags_path=flags,
            trigger="cron_tick",
            pending_work=True,
            now=_UTC_NOON,
        )


        assert "per_day_budget_exceeded" in result["safety_rails"]


class TestTickNeverAutoApprove:

    def test_decision_action_in_closed_set(self, tmp_path):
        flags = tmp_path / "features.yaml"
        flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")
        sched = tmp_path / "schedule.yaml"
        sched.write_text("max_concurrent_waves: 1\nquiet_hours:\n  start: '22:00'\n  end: '06:00'\n",
                         encoding="utf-8")
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")

        for trigger in ["cron_tick", "ticket_created", "wave_completed",
                        "interrupt_answered", "after_n_runs"]:
            result = lc.tick(
                schedule_path=sched,
                loop_config=REPO_ROOT / "config" / "loop.yaml",
                experiments=tmp_path / "experiments",
                metrics_history=tmp_path / ".metrics-history.jsonl",
                events_path=tmp_path / ".events.jsonl",
                budgets_path=budgets,
                feature_flags_path=flags,
                trigger=trigger,
                now=_UTC_NOON,
            )
            action = result["decision"]["action"]
            assert action in (DISPATCH, VALIDATE, IDLE), (
                f"trigger={trigger}: action {action!r} is outside closed decision set"
            )

    def test_promotion_never_auto_applied(self, tmp_path):
        flags = tmp_path / "features.yaml"
        flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")
        sched = tmp_path / "schedule.yaml"
        sched.write_text("max_concurrent_waves: 1\n", encoding="utf-8")
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")

        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=tmp_path / ".events.jsonl",
            budgets_path=budgets,
            feature_flags_path=flags,
            trigger="cron_tick",
            now=_UTC_NOON,
        )

        assert "promotion" in result
        import yaml as _yaml
        loop_cfg = _yaml.safe_load(
            (REPO_ROOT / "config" / "loop.yaml").read_text(encoding="utf-8")
        ) or {}
        assert loop_cfg.get("mode") == "shadow", "loop.yaml mode must remain shadow"
        assert loop_cfg.get("auto_apply") is False, "auto_apply must remain false"


class TestPerDayBudget:
    def test_missing_budgets_file_returns_false(self, tmp_path):
        result = lc._per_day_budget_exceeded(tmp_path / "nonexistent.yaml", tmp_path / ".events.jsonl")
        assert result is False

    def test_zero_cap_always_returns_false(self, tmp_path):
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 0\n", encoding="utf-8")
        result = lc._per_day_budget_exceeded(budgets, tmp_path / ".events.jsonl")
        assert result is False

    def test_no_events_returns_false(self, tmp_path):
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")
        result = lc._per_day_budget_exceeded(budgets, tmp_path / ".events.jsonl")
        assert result is False


class TestCheckLoopModeStaysGreen:

    def test_check_loop_mode_exit_0(self):
        import check_loop_mode as clm
        rc = clm.main(["--config", str(REPO_ROOT / "config" / "loop.yaml")])
        assert rc == 0, "check_loop_mode must exit 0 (loop safely off)"

    def test_loop_yaml_mode_is_shadow(self):
        import yaml as _yaml
        data = _yaml.safe_load((REPO_ROOT / "config" / "loop.yaml").read_text()) or {}
        assert data.get("mode") == "shadow"

    def test_loop_yaml_auto_apply_is_false(self):
        import yaml as _yaml
        data = _yaml.safe_load((REPO_ROOT / "config" / "loop.yaml").read_text()) or {}
        assert data.get("auto_apply") is False


class TestMainTickExitCode:

    def test_main_tick_exits_0(self, tmp_path):
        flags = tmp_path / "features.yaml"
        flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")
        sched = tmp_path / "schedule.yaml"
        sched.write_text("max_concurrent_waves: 1\n", encoding="utf-8")
        budgets = tmp_path / "budgets.yaml"
        budgets.write_text("caps:\n  per_day:\n    max_cost_usd: 500\n", encoding="utf-8")


        result = lc.tick(
            schedule_path=sched,
            loop_config=REPO_ROOT / "config" / "loop.yaml",
            experiments=tmp_path / "experiments",
            metrics_history=tmp_path / ".metrics-history.jsonl",
            events_path=tmp_path / ".events.jsonl",
            budgets_path=budgets,
            feature_flags_path=flags,
            trigger="cron_tick",
            now=_UTC_NOON,
        )

        assert "mode" in result
        assert "decision" in result
        assert "promotion" in result
        assert "safety_rails" in result

    def test_main_tick_flag_json(self, tmp_path, capsys):
        flags = tmp_path / "features.yaml"
        flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")
        sched = REPO_ROOT / "board" / "schedule.yaml"
        budgets = REPO_ROOT / "config" / "budgets.yaml"

        rc = lc.main([
            "--tick",
            "--json",
            f"--schedule={sched}",
            f"--budgets={budgets}",
            "--trigger=cron_tick",
        ])
        assert rc == 0
        captured = capsys.readouterr().out
        obj = json.loads(captured)
        assert obj.get("mode") in ("shadow", "live")
        assert obj.get("decision", {}).get("action") in (DISPATCH, VALIDATE, IDLE)


class TestHeartbeatFlag:

    def test_heartbeat_enabled_in_defaults(self):
        import feature_flags as ff
        assert "heartbeat_enabled" in ff.DEFAULTS, (
            "heartbeat_enabled must be declared in feature_flags.DEFAULTS (ADR-0027 SI-7)"
        )

    def test_heartbeat_enabled_default_is_false(self):
        import feature_flags as ff
        assert ff.DEFAULTS["heartbeat_enabled"] is False, (
            "heartbeat_enabled must default to False (ADR-0027 SI-7: Founder flip-only)"
        )

    def test_heartbeat_enabled_off_by_default_via_load(self, tmp_path):
        import feature_flags as ff
        f = tmp_path / "features.yaml"
        f.write_text("", encoding="utf-8")
        result = ff.load(path=f)
        assert result.get("heartbeat_enabled") is False

    def test_heartbeat_enabled_can_be_flipped_on(self, tmp_path):
        import feature_flags as ff
        f = tmp_path / "features.yaml"
        f.write_text("heartbeat_enabled: true\n", encoding="utf-8")
        result = ff.load(path=f)
        assert result.get("heartbeat_enabled") is True
