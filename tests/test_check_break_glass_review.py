#!/usr/bin/env python3
"""tests/test_check_break_glass_review.py — 24h post-incident review gate (R-8 / ADR-008)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import break_glass as bg  # noqa: E402  (import after path manipulation)
import check_break_glass_review as cr  # noqa: E402

T0 = "2026-06-22T10:00:00Z"
DEADLINE = "2026-06-23T10:00:00Z"  # T0 + 24h


def _act(aid: str = "BG-1", created: str = T0) -> dict:
    return bg.build_activation(activation_id=aid, reason="x", operator="cto", created_at=created)


def _review(aid: str = "BG-1", created: str = "2026-06-22T12:00:00Z", status: str = "closed") -> dict:
    return {
        "event_type": bg.REVIEW_EVENT,
        "ticket_id": "DAS-BREAK-GLASS",
        "created_at": created,
        "review_for": aid,
        "status": status,
    }


def _store(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


def test_missing_store_is_clean(tmp_path):
    assert cr.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_no_activations_is_clean(tmp_path):
    p = _store(tmp_path, [{"event_type": "routing_decision", "ticket_id": "DAS-1", "created_at": T0}])
    assert cr.main(["--events", str(p)]) == 0


def test_timely_review_passes(tmp_path):
    p = _store(tmp_path, [_act(), _review(created="2026-06-22T12:00:00Z")])
    assert cr.main(["--events", str(p), "--now", "2026-06-25T00:00:00Z"]) == 0


def test_overdue_without_review_fails(tmp_path):
    p = _store(tmp_path, [_act()])
    assert cr.main(["--events", str(p), "--now", "2026-06-23T11:00:00Z"]) == 1


def test_pending_within_24h_is_ok(tmp_path):
    p = _store(tmp_path, [_act()])
    assert cr.main(["--events", str(p), "--now", "2026-06-22T12:00:00Z"]) == 0


def test_late_review_fails(tmp_path):
    p = _store(tmp_path, [_act(), _review(created="2026-06-23T11:00:00Z")])  # 25h later
    assert cr.main(["--events", str(p), "--now", "2026-06-25T00:00:00Z"]) == 1


def test_open_review_does_not_satisfy(tmp_path):
    p = _store(tmp_path, [_act(), _review(created="2026-06-22T12:00:00Z", status="open")])
    assert cr.main(["--events", str(p), "--now", "2026-06-23T11:00:00Z"]) == 1


def test_bad_now_exit_2(tmp_path):
    p = _store(tmp_path, [_act()])
    assert cr.main(["--events", str(p), "--now", "garbage"]) == 2


def test_find_problems_unit():
    overdue = bg.parse_ts("2026-06-23T11:00:00Z")
    assert cr.find_problems([_act()], [], overdue)
    assert cr.find_problems([_act()], [_review()], overdue) == []


# --- review-found blocker/major regression tests ---

def test_duplicate_activation_id_each_needs_own_review(tmp_path):
    # two DISTINCT activations share an id; one review covers only the first
    a1 = _act(aid="BG-dup", created="2026-06-22T10:00:00Z")
    a2 = _act(aid="BG-dup", created="2026-06-25T09:00:00Z")
    r1 = _review(aid="BG-dup", created="2026-06-22T10:30:00Z")  # in a1's window only
    p = _store(tmp_path, [a1, a2, r1])
    assert cr.main(["--events", str(p), "--now", "2026-06-30T00:00:00Z"]) == 1


def test_duplicate_id_both_reviewed_passes(tmp_path):
    a1 = _act(aid="BG-dup", created="2026-06-22T10:00:00Z")
    a2 = _act(aid="BG-dup", created="2026-06-25T09:00:00Z")
    r1 = _review(aid="BG-dup", created="2026-06-22T10:30:00Z")
    r2 = _review(aid="BG-dup", created="2026-06-25T09:30:00Z")
    p = _store(tmp_path, [a1, a2, r1, r2])
    assert cr.main(["--events", str(p), "--now", "2026-06-30T00:00:00Z"]) == 0


def test_predated_review_does_not_satisfy(tmp_path):
    a1 = _act(created="2026-06-22T10:00:00Z")
    r1 = _review(created="2020-01-01T00:00:00Z")  # years before the incident
    p = _store(tmp_path, [a1, r1])
    assert cr.main(["--events", str(p), "--now", "2026-06-25T00:00:00Z"]) == 1


def test_overlapping_windows_pass_regardless_of_review_order(tmp_path):
    # a perfect assignment exists (a1<-r_a1only, a2<-r_shared); a max-matching gate
    # must PASS in either event order, never false-fail on greedy order dependence.
    a1 = _act(aid="BG-y", created="2026-06-22T10:00:00Z")
    a2 = _act(aid="BG-y", created="2026-06-22T10:30:00Z")
    r_shared = _review(aid="BG-y", created="2026-06-22T10:45:00Z")  # valid for both
    r_a1only = _review(aid="BG-y", created="2026-06-22T10:15:00Z")  # valid for a1 only
    now = "2026-06-25T00:00:00Z"
    for order in ([a1, a2, r_a1only, r_shared], [a1, a2, r_shared, r_a1only]):
        f = tmp_path / "ev.jsonl"
        f.write_text("".join(json.dumps(e) + "\n" for e in order), encoding="utf-8")
        assert cr.main(["--events", str(f), "--now", now]) == 0
