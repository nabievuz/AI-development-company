#!/usr/bin/env python3
"""tests/test_replay_qa.py — Replay-QA / recovery-drill harness (T5 / RFC-003)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import replay_qa as rq  # noqa: E402  (import after path manipulation)


def _t(frm, to, minute, run="r1") -> dict:
    return {"event_type": "routing_decision", "run_id": run, "ticket_id": "DAS-1",
            "from_status": frm, "to_status": to, "created_at": f"2026-06-21T10:{minute:02d}:00Z"}


def _events(tmp_path, events) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


def test_clean_chain_replays():
    r = rq.replay_run([_t("todo", "in_progress", 0), _t("in_progress", "in_review", 1), _t("in_review", "done", 2)])
    assert r["replayable"] is True and r["corrupted"] is False and r["final_status"] == "done"


def test_broken_chain_is_corrupted():
    r = rq.replay_run([_t("todo", "in_progress", 0), _t("done", "in_review", 1)])
    assert r["corrupted"] is True


def test_invalid_status_is_corrupted():
    r = rq.replay_run([_t("todo", "frobnicate", 0)])
    assert r["corrupted"] is True


def test_drill_counts():
    evs = [
        _t("todo", "in_progress", 0, run="a"), _t("in_progress", "done", 1, run="a"),
        _t("todo", "in_progress", 0, run="b"), _t("done", "in_review", 1, run="b"),  # b corrupted
    ]
    d = rq.drill(evs)
    assert d["runs"] == 2 and d["replayable"] == 1 and d["corrupted"] == ["b"]


def test_cli_inert(tmp_path):
    assert rq.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_cli_clean_exit_0(tmp_path):
    p = _events(tmp_path, [_t("todo", "in_progress", 0), _t("in_progress", "done", 1)])
    assert rq.main(["--events", str(p)]) == 0


def test_cli_corrupted_exit_1(tmp_path):
    p = _events(tmp_path, [_t("todo", "in_progress", 0), _t("done", "done", 1)])
    assert rq.main(["--events", str(p)]) == 1


def test_none_to_status_before_break_is_corrupted():
    # a None to_status must not reset the chain check and let a later break pass
    middle = {"event_type": "routing_decision", "from_status": "in_progress",
              "to_status": None, "created_at": "2026-06-21T10:01:00Z"}
    r = rq.replay_run([_t("todo", "in_progress", 0), middle, _t("done", "blocked", 2)])
    assert r["corrupted"] is True


def test_invalid_from_status_is_corrupted():
    assert rq.replay_run([_t("ZZZ", "in_progress", 0)])["corrupted"] is True


def test_emit_writes_recovery_drills(tmp_path):
    p = _events(tmp_path, [_t("todo", "in_progress", 0), _t("in_progress", "done", 1)])
    emit = tmp_path / "drills.jsonl"
    rq.main(["--events", str(p), "--emit", str(emit)])
    drills = [json.loads(x) for x in emit.read_text().splitlines() if x.strip()]
    assert drills and drills[0]["event_type"] == "recovery_drill" and drills[0]["outcome"] == "success"
