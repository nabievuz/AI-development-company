
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import stall_drill as sd
from dgox.events import iter_events, validate_replanned

_REAL_BOARD = _REPO_ROOT / "board"


def _board_fingerprint() -> dict[str, int]:
    if not _REAL_BOARD.exists():
        return {}
    return {
        str(p.relative_to(_REAL_BOARD)): p.stat().st_size
        for p in _REAL_BOARD.rglob("*")
        if p.is_file()
    }


class TestStallDrill:
    def test_drill_replans_pauses_and_resumes(self, tmp_path: Path) -> None:
        before = _board_fingerprint()

        summary = sd.run_stall_drill(tmp_path / "run", max_replans=2)


        assert summary["replanned_count"] >= 1, summary
        assert summary["replanned_count"] == summary["max_replans"], summary
        store_path = Path(summary["board_untouched_paths"]["store_path"])
        events = list(iter_events(store_path, event_type="replanned"))
        assert len(events) == summary["replanned_count"], events
        for ev in events:
            assert validate_replanned(ev) == [], ev
            assert ev["ticket_id"] == summary["anchor"]
            assert ev["run_id"] == summary["run_id"]


        assert summary["paused"] is True, summary
        card_path = Path(summary["card_path"])
        assert card_path.is_file(), card_path
        interrupts_dir = Path(summary["board_untouched_paths"]["interrupts_dir"])
        assert interrupts_dir in card_path.parents, card_path
        card = json.loads(card_path.read_text(encoding="utf-8"))
        assert set(card) == {"question", "options", "ticket", "payload", "created_by"}, card
        assert card["ticket"] == summary["anchor"]
        assert card["options"], "interrupt card must offer answer options"
        assert card["payload"]["run_id"] == summary["run_id"]


        assert summary["resumed"] is True, summary
        assert summary["resume_value"] in card["options"]
        assert summary["injection_chars"] > 0
        assert summary["events_validated"] is True


        assert _board_fingerprint() == before, "drill mutated the real board/"

    def test_drill_writes_nothing_under_real_board(self, tmp_path: Path) -> None:
        before = _board_fingerprint()
        summary = sd.run_stall_drill(tmp_path / "run", max_replans=1)
        after = _board_fingerprint()
        assert after == before, "drill must never write under the real board/"


        for key, path in summary["board_untouched_paths"].items():
            assert str(tmp_path) in path, f"{key} escaped scratch: {path}"
        assert str(tmp_path) in summary["card_path"], summary["card_path"]

    def test_single_replan_budget_still_replans_then_pauses(self, tmp_path: Path) -> None:
        summary = sd.run_stall_drill(tmp_path / "run", max_replans=1)
        assert summary["replanned_count"] == 1, summary
        assert summary["actions"][-1] == "paused", summary["actions"]

        assert summary["revision"] == 2, summary

    def test_invalid_max_replans_rejected(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(sd.DrillError):
            sd.run_stall_drill(tmp_path / "run", max_replans=0)


class TestCli:
    def test_smoke_cli_passes(self) -> None:
        assert sd.main(["--smoke"]) == 0

    def test_cli_rejects_bad_budget(self) -> None:
        assert sd.main(["--max-replans", "0"]) == 2
