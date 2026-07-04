#!/usr/bin/env python3
"""tests/test_break_glass.py — BREAK-GLASS override mechanism (R-8 / ADR-008).

Proves: 60-min auto-expiry, single-rollback scope enforcement, the 24h review
deadline stamp, append-only logging to the audit store, and the CLI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import break_glass as bg  # noqa: E402  (import after path manipulation)

T0 = "2026-06-22T10:00:00Z"


def _activate(store: Path, created: str = T0, aid: str = "BG-1") -> None:
    bg.append_event(
        bg.build_activation(activation_id=aid, reason="incident", operator="cto", created_at=created),
        store,
    )


# --------------------------------------------------------------------------- #
# Builder: expiry, review deadline, scope
# --------------------------------------------------------------------------- #

def test_activation_expiry_is_60_minutes():
    ev = bg.build_activation(activation_id="BG-1", reason="x", operator="cto", created_at=T0)
    assert ev["expires_at"] == "2026-06-22T11:00:00Z"
    assert ev["window_minutes"] == 60
    assert ev["scope"] == "single_rollback"


def test_review_deadline_is_24h():
    ev = bg.build_activation(activation_id="BG-1", reason="x", operator="cto", created_at=T0)
    assert ev["review_required_by"] == "2026-06-23T10:00:00Z"


def test_scope_must_be_single_rollback():
    with pytest.raises(ValueError, match="single_rollback"):
        bg.build_activation(
            activation_id="BG-1", reason="x", operator="cto", created_at=T0, scope="full_access"
        )


def test_bad_timestamp_rejected():
    with pytest.raises(ValueError):
        bg.build_activation(activation_id="BG-1", reason="x", operator="cto", created_at="not-a-time")


# --------------------------------------------------------------------------- #
# Append-only log + auto-expiry
# --------------------------------------------------------------------------- #

def test_append_is_append_only(tmp_path):
    store = tmp_path / ".events.jsonl"
    _activate(store, aid="BG-1")
    _activate(store, aid="BG-2")
    events = bg.read_events(str(store))
    assert [e["activation_id"] for e in events] == ["BG-1", "BG-2"]


def test_active_within_window(tmp_path):
    store = tmp_path / ".events.jsonl"
    _activate(store)
    assert bg.is_active(bg.parse_ts("2026-06-22T10:30:00Z"), store) is True


def test_auto_expires_at_60_min(tmp_path):
    store = tmp_path / ".events.jsonl"
    _activate(store)
    assert bg.is_active(bg.parse_ts("2026-06-22T11:00:00Z"), store) is False
    assert bg.is_active(bg.parse_ts("2026-06-22T11:00:01Z"), store) is False


def test_not_active_before_start(tmp_path):
    store = tmp_path / ".events.jsonl"
    _activate(store)
    assert bg.is_active(bg.parse_ts("2026-06-22T09:59:00Z"), store) is False


def test_no_store_means_inactive(tmp_path):
    assert bg.is_active(bg.parse_ts(T0), tmp_path / "nope.jsonl") is False


def test_forged_expires_at_is_ignored(tmp_path):
    # liveness is recomputed from created_at + 60min, NOT a forged expires_at
    store = tmp_path / ".events.jsonl"
    ev = bg.build_activation(activation_id="BG-1", reason="x", operator="cto", created_at=T0)
    ev["expires_at"] = "2126-06-22T10:00:00Z"  # forged far-future expiry
    bg.append_event(ev, store)
    assert bg.is_active(bg.parse_ts("2026-06-22T12:00:00Z"), store) is False


def test_non_single_rollback_scope_never_active(tmp_path):
    store = tmp_path / ".events.jsonl"
    ev = bg.build_activation(activation_id="BG-1", reason="x", operator="cto", created_at=T0)
    ev["scope"] = "full_access"  # tampered scope in the log
    bg.append_event(ev, store)
    assert bg.is_active(bg.parse_ts("2026-06-22T10:30:00Z"), store) is False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_activate_logs_event(tmp_path):
    store = tmp_path / ".events.jsonl"
    rc = bg.main(
        ["activate", "--reason", "prod down", "--operator", "cto", "--id", "BG-9", "--store", str(store)]
    )
    assert rc == 0
    events = bg.read_events(str(store))
    assert len(events) == 1
    assert events[0]["event_type"] == bg.ACTIVATION_EVENT
    assert events[0]["activation_id"] == "BG-9"


def test_cli_status_runs(tmp_path):
    assert bg.main(["status", "--store", str(tmp_path / "nope.jsonl")]) == 0
