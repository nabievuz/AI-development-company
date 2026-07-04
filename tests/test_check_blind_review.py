#!/usr/bin/env python3
"""tests/test_check_blind_review.py — Blind review + rotation (T6 anti-drift)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_blind_review as cbr  # noqa: E402  (import after path manipulation)


def _review(tid="DAS-1", author="eng-1", reviewer="eng-2", blind=True) -> dict:
    return {"event_type": "review", "ticket_id": tid, "author": author,
            "reviewer": reviewer, "blind": blind, "created_at": "2026-06-21T10:00:00Z"}


def _events(tmp_path, events) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


def test_clean_blind_reviews_pass():
    assert cbr.violations([_review(), _review(tid="DAS-2", author="eng-3")]) == []


def test_non_blind_review_flagged():
    assert any("not blind" in p for p in cbr.violations([_review(blind=False)]))


def test_self_review_flagged():
    assert any("self-review" in p for p in cbr.violations([_review(author="eng-1", reviewer="eng-1")]))


def test_over_pairing_flagged():
    # same reviewer/author pair more than max_same_pair times -> rotation violation
    reviews = [_review(tid=f"DAS-{i}", author="eng-1", reviewer="eng-9") for i in range(4)]
    assert any("rotate" in p for p in cbr.violations(reviews, max_same_pair=3))


def test_rotation_ok_within_limit():
    reviews = [_review(tid=f"DAS-{i}", author="eng-1", reviewer="eng-9") for i in range(3)]
    assert cbr.violations(reviews, max_same_pair=3) == []


def test_string_blind_false_is_not_blind():
    # a non-blind review with blind serialized as the string "false" must NOT pass
    for val in ("false", "no", "0", "FALSE"):
        assert any("not blind" in p for p in cbr.violations([_review(blind=val)]))


def test_case_insensitive_self_review():
    assert any("self-review" in p for p in cbr.violations([_review(author="Eng-1", reviewer="eng-1 ")]))


def test_case_split_over_pairing_still_caught():
    # eng-9 and Eng-9 are the same human reviewing eng-1 four times -> still over-paired
    reviews = ([_review(tid=f"a{i}", author="eng-1", reviewer="eng-9") for i in range(2)]
               + [_review(tid=f"b{i}", author="eng-1", reviewer="Eng-9") for i in range(2)])
    assert any("rotate" in p for p in cbr.violations(reviews, max_same_pair=3))


def test_missing_identity_flagged():
    assert any("missing reviewer/author" in p for p in cbr.violations([{"event_type": "review", "ticket_id": "DAS-1", "blind": True}]))


def test_non_string_identity_does_not_crash():
    # a list/dict identity must not raise (unhashable key) — coerced to str
    assert cbr.violations([_review(author=["x"], reviewer={"y": 1})]) is not None


def test_cli_inert(tmp_path):
    assert cbr.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_cli_clean_exit_0(tmp_path):
    assert cbr.main(["--events", str(_events(tmp_path, [_review()]))]) == 0


def test_cli_non_blind_exit_1(tmp_path):
    assert cbr.main(["--events", str(_events(tmp_path, [_review(blind=False)]))]) == 1
