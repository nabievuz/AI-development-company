
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pulse_checkpoint as pc
import task_ledger as tl

FIXED_TS = "2026-07-03T12:00:00Z"
REPLAN_TS = "2026-07-03T13:30:00Z"
REPLAN_TS2 = "2026-07-03T14:15:00Z"
RUN_ID = "01J9Z8QK3M7Q0W9E4R5T6Y7U8I"


def _facts() -> tl.Facts:
    return tl.Facts(
        given=["Ship the task-ledger (P7 outer loop)", "Reuse the WS1 run-model"],
        known=["board/runs/<run_id>/ is the run-artifact tree (ADR-0023 §2)"],
        to_look_up=["Whether DAS-1470 needs a JSON view of the ledger"],
        educated_guesses=["The ledger stays gitignored like other run artifacts"],
    )


def _plan() -> list[str]:
    return [
        "Write scripts/task_ledger.py (build / update / read)",
        "Add tests/test_task_ledger.py",
        "Verify: pytest, diagnostics, board_lint, ruff",
    ]


def _runs_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs"


class TestReuseRunModel:
    def test_default_runs_dir_is_pulse_checkpoints(self):
        assert tl.DEFAULT_RUNS_DIR == pc.DEFAULT_RUNS_DIR

    def test_generate_ulid_is_pulse_checkpoints(self):
        assert tl.generate_ulid is pc.generate_ulid

    def test_ledger_path_uses_run_dir_scheme(self, tmp_path):
        rd = _runs_dir(tmp_path)
        p = tl.ledger_path(RUN_ID, rd)
        assert p == rd / RUN_ID / "task-ledger.md"


class TestBuild:
    def test_file_written_at_correct_path(self, tmp_path):
        rd = _runs_dir(tmp_path)
        path = tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            goal="organism-ws2-loom", wave=1, runs_dir=rd,
        )
        assert path == rd / RUN_ID / "task-ledger.md"
        assert path.exists()

    def test_captures_all_four_fact_buckets_and_plan(self, tmp_path):
        rd = _runs_dir(tmp_path)
        path = tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        text = path.read_text(encoding="utf-8")
        for heading in ("### Given", "### Known", "### To look up",
                        "### Educated guesses", "## Plan"):
            assert heading in text
        assert "Ship the task-ledger (P7 outer loop)" in text
        assert "Add tests/test_task_ledger.py" in text

    def test_plan_is_ordered(self, tmp_path):
        rd = _runs_dir(tmp_path)
        path = tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        text = path.read_text(encoding="utf-8")
        assert "1. Write scripts/task_ledger.py (build / update / read)" in text
        assert "3. Verify: pytest, diagnostics, board_lint, ruff" in text

    def test_initial_revision_is_1(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        assert tl.read_task_ledger(RUN_ID, rd)["revision"] == 1

    def test_created_at_equals_updated_at_on_build(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        data = tl.read_task_ledger(RUN_ID, rd)
        assert data["created_at"] == FIXED_TS
        assert data["updated_at"] == FIXED_TS

    def test_accepts_facts_as_dict(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID,
            facts={"given": ["g1"], "known": ["k1"],
                   "to_look_up": ["t1"], "educated_guesses": ["e1"]},
            plan=["p1"], created_at=FIXED_TS, runs_dir=rd,
        )
        facts = tl.read_task_ledger(RUN_ID, rd)["facts"]
        assert facts.given == ["g1"]
        assert facts.educated_guesses == ["e1"]

    def test_creates_run_dir_if_absent(self, tmp_path):
        rd = _runs_dir(tmp_path)
        assert not (rd / RUN_ID).exists()
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        assert (rd / RUN_ID).is_dir()

    def test_empty_facts_bucket_renders_placeholder_and_parses_empty(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID,
            facts=tl.Facts(given=["only given"]),
            plan=[], created_at=FIXED_TS, runs_dir=rd,
        )
        data = tl.read_task_ledger(RUN_ID, rd)
        assert data["facts"].given == ["only given"]
        assert data["facts"].known == []
        assert data["facts"].to_look_up == []
        assert data["plan"] == []


class TestReadRoundTrip:
    def test_round_trip_preserves_facts_and_plan(self, tmp_path):
        rd = _runs_dir(tmp_path)
        facts, plan = _facts(), _plan()
        tl.build_task_ledger(
            run_id=RUN_ID, facts=facts, plan=plan, created_at=FIXED_TS,
            goal="organism-ws2-loom", wave=2, runs_dir=rd,
        )
        data = tl.read_task_ledger(RUN_ID, rd)
        assert data["run_id"] == RUN_ID
        assert data["goal"] == "organism-ws2-loom"
        assert data["wave"] == 2
        assert data["facts"].as_dict() == facts.as_dict()
        assert data["plan"] == plan

    def test_render_parse_are_inverse(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            goal="g", wave=1, runs_dir=rd,
        )
        first = tl.read_task_ledger(RUN_ID, rd)

        rerendered = tl.render_task_ledger(
            run_id=first["run_id"], facts=first["facts"], plan=first["plan"],
            created_at=first["created_at"], updated_at=first["updated_at"],
            revision=first["revision"], goal=first["goal"], wave=first["wave"],
        )
        tl.ledger_path(RUN_ID, rd).write_text(rerendered, encoding="utf-8")
        second = tl.read_task_ledger(RUN_ID, rd)
        assert second["facts"].as_dict() == first["facts"].as_dict()
        assert second["plan"] == first["plan"]
        assert second["goal"] == first["goal"]

    def test_missing_ledger_raises(self, tmp_path):
        rd = _runs_dir(tmp_path)
        try:
            tl.read_task_ledger("NONEXISTENTRUN", rd)
        except FileNotFoundError:
            return
        raise AssertionError("expected FileNotFoundError for missing ledger")


class TestReplanRegeneration:
    def test_facts_update_path_regenerates_facts(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        new_facts = tl.Facts(
            given=["Revised given after replan"],
            known=["New fact discovered"],
            to_look_up=[],
            educated_guesses=["Revised guess"],
        )
        tl.update_task_ledger(
            run_id=RUN_ID, created_at=REPLAN_TS, facts=new_facts, runs_dir=rd,
        )
        data = tl.read_task_ledger(RUN_ID, rd)
        assert data["facts"].given == ["Revised given after replan"]
        assert data["facts"].known == ["New fact discovered"]

        assert data["plan"] == _plan()

    def test_plan_update_path_regenerates_plan(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        new_plan = ["Revised step A", "Revised step B"]
        tl.update_task_ledger(
            run_id=RUN_ID, created_at=REPLAN_TS, plan=new_plan, runs_dir=rd,
        )
        data = tl.read_task_ledger(RUN_ID, rd)
        assert data["plan"] == new_plan

        assert data["facts"].as_dict() == _facts().as_dict()

    def test_replan_replaces_not_appends(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        tl.update_task_ledger(
            run_id=RUN_ID, created_at=REPLAN_TS,
            facts=tl.Facts(given=["only this now"]),
            plan=["only step now"], runs_dir=rd,
        )
        text = tl.ledger_path(RUN_ID, rd).read_text(encoding="utf-8")

        assert text.count("## Facts") == 1
        assert text.count("## Plan") == 1
        assert text.count("### Given") == 1

        assert "Ship the task-ledger (P7 outer loop)" not in text
        assert "Add tests/test_task_ledger.py" not in text
        assert "only this now" in text
        assert "only step now" in text

    def test_replan_bumps_revision_and_advances_updated_at(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(), created_at=FIXED_TS,
            runs_dir=rd,
        )
        tl.update_task_ledger(
            run_id=RUN_ID, created_at=REPLAN_TS, plan=["p"], runs_dir=rd,
        )
        d1 = tl.read_task_ledger(RUN_ID, rd)
        assert d1["revision"] == 2
        assert d1["created_at"] == FIXED_TS
        assert d1["updated_at"] == REPLAN_TS
        tl.update_task_ledger(
            run_id=RUN_ID, created_at=REPLAN_TS2, facts=tl.Facts(), runs_dir=rd,
        )
        d2 = tl.read_task_ledger(RUN_ID, rd)
        assert d2["revision"] == 3
        assert d2["created_at"] == FIXED_TS
        assert d2["updated_at"] == REPLAN_TS2

    def test_update_missing_ledger_raises(self, tmp_path):
        rd = _runs_dir(tmp_path)
        try:
            tl.update_task_ledger(
                run_id="NOPE", created_at=REPLAN_TS, plan=["x"], runs_dir=rd,
            )
        except FileNotFoundError:
            return
        raise AssertionError("expected FileNotFoundError updating a missing ledger")


class TestInjectableTimestamp:
    def test_build_uses_supplied_created_at_verbatim(self, tmp_path):
        rd = _runs_dir(tmp_path)
        tl.build_task_ledger(
            run_id=RUN_ID, facts=_facts(), plan=_plan(),
            created_at="1999-01-01T00:00:00Z", runs_dir=rd,
        )
        assert tl.read_task_ledger(RUN_ID, rd)["created_at"] == "1999-01-01T00:00:00Z"

    def test_no_wallclock_call_in_module_source(self):
        src = (_SCRIPTS / "task_ledger.py").read_text(encoding="utf-8")
        for banned in ("datetime.now", "datetime.utcnow", "time.time("):
            assert banned not in src, f"task_ledger.py must not call {banned}"


class TestGitignore:
    def test_task_ledger_is_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--quiet",
             f"board/runs/{RUN_ID}/task-ledger.md"],
            cwd=_REPO_ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "board/runs/<run_id>/task-ledger.md is NOT gitignored — it is runtime "
            "state and must stay ignored under board/runs/ (ADR-0023 §5)"
        )
