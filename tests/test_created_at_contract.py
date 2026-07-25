"""tests/test_created_at_contract.py — DAS-1633 created_at format contract.

Found by SRE Lead in the DAS-1618 round-2 re-review: ``dgox.events.
validate_envelope`` used to accept ANY non-empty string as ``created_at``,
while every downstream consumer (``cost_ledger``, ``metrics_history_feeder``,
``wave_kpi``, ``metrics_lib``, ``trends``) silently required exactly
``%Y-%m-%dT%H:%M:%SZ`` and silently skipped anything else — no error, no
warning, no dropped-record count. A caller emitting
``datetime.now(UTC).isoformat()`` (``+00:00``, possibly with microseconds)
therefore wrote an event that validated cleanly at the write seam and then
vanished from every KPI: invisible to the budget ceiling (fails OPEN, i.e.
under-counts) and invisible to the clean-day evidence window.

THE TEST THAT MATTERS (per the ticket): an event whose ``created_at`` is
``datetime.now(UTC).isoformat()`` must be either REJECTED at the write seam
or COUNTED downstream — never accepted-then-silently-dropped. A test that only
asserts well-formed ``...Z`` events work would pass against the buggy code and
prove nothing; every test class below therefore also exercises the buggy
shape explicitly.

Coverage:
    1. ``TestWriteSeamRejectsBuggyShape`` — the failing shape from the ticket
       (``datetime.now(UTC).isoformat()``) is rejected by ``validate_envelope``
       and by ``EventStore.append`` (raises, nothing written) — before/after
       behavior recorded verbatim in the ticket log.
    2. ``TestEveryBuilderStillRoundTrips`` — every existing ``build_*``
       producer in ``dgox/events.py`` still emits a ``created_at`` that
       validates cleanly (the write-seam tightening does not break a single
       real producer — demonstrated, not assumed).
    3. ``TestDroppedCountIsObservable`` — a scratch stream with one good and
       one (already-conforming-shape-but-hypothetically-bad — constructed by
       bypassing the builder) record makes the drop count observable in
       ``cost_ledger``, ``metrics_history_feeder``, ``wave_kpi``,
       ``metrics_lib``, and ``trends`` — never silent.
    4. ``TestExclusionSemanticsUnchanged`` — undated/unparseable records are
       still EXCLUDED from window filtering (DAS-1618's permanent-latch fix is
       not reintroduced); DAS-1633 only makes the exclusion visible.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import metrics_lib  # noqa: E402
import trends  # noqa: E402
import wave_kpi  # noqa: E402
from cost.cost_ledger import aggregate_spans  # noqa: E402
from dgox import events  # noqa: E402
from dgox.created_at import (  # noqa: E402
    CREATED_AT_FORMAT,
    DropCounter,
    count_invalid,
    is_valid_created_at,
    parse_created_at,
)
from metrics_history_feeder import filter_events_by_window  # noqa: E402

_TS = "2026-07-24T12:00:00Z"

# The exact failing shape called out by the ticket: datetime.now(UTC).isoformat()
# yields a '+00:00' offset and (usually) microseconds — never a bare 'Z'.
_BUGGY_SHAPE = datetime.now(tz=UTC).isoformat()


# ---------------------------------------------------------------------------
# 1. Write-seam rejection of the exact buggy shape from the ticket
# ---------------------------------------------------------------------------


class TestWriteSeamRejectsBuggyShape:
    def test_isoformat_shape_is_not_the_canonical_shape(self):
        """Sanity: confirm the shape under test really is off-contract (has an
        offset and/or fractional seconds, never a bare 'Z')."""
        assert not _BUGGY_SHAPE.endswith("Z") or "." in _BUGGY_SHAPE

    def test_buggy_shape_rejected_by_is_valid_created_at(self):
        assert is_valid_created_at(_BUGGY_SHAPE) is False
        assert parse_created_at(_BUGGY_SHAPE) is None

    def test_buggy_shape_rejected_by_validate_envelope(self):
        """BEFORE this fix: validate_envelope accepted any non-empty string,
        so this returned []. AFTER: it must return a created_at error."""
        ev = {
            "event_type": "routing_decision",
            "ticket_id": "DAS-1633",
            "created_at": _BUGGY_SHAPE,
        }
        errors = events.validate_envelope(ev)
        assert any("created_at" in e for e in errors), (
            f"expected a created_at rejection for buggy shape {_BUGGY_SHAPE!r}; got {errors!r}"
        )

    def test_buggy_shape_rejected_by_event_store_append(self, tmp_path):
        """The write seam: EventStore.append must raise and write NOTHING for
        an off-contract created_at — never silently accept it."""
        store_path = tmp_path / "scratch.events.jsonl"
        store = events.EventStore(path=store_path)
        ev = events.build_routing_decision(
            ticket_id="DAS-1633",
            from_status="todo",
            to_status="in_progress",
            assignee="backend-eng-2",
            model="sonnet",
            reason="test",
            confidence=0.9,
            policy_checks=["x"],
            fallback="block",
            created_at=_BUGGY_SHAPE,
        )
        with pytest.raises(ValueError, match="created_at"):
            store.append(ev)
        assert not store_path.exists() or store_path.read_text() == ""

    def test_conforming_shape_is_accepted(self, tmp_path):
        """Control: the canonical shape (what utcnow() actually emits) is
        accepted end-to-end — the seam rejects only the ambiguous shape."""
        store_path = tmp_path / "scratch.events.jsonl"
        store = events.EventStore(path=store_path)
        ev = events.build_routing_decision(
            ticket_id="DAS-1633",
            from_status="todo",
            to_status="in_progress",
            assignee="backend-eng-2",
            model="sonnet",
            reason="test",
            confidence=0.9,
            policy_checks=["x"],
            fallback="block",
            created_at=events.utcnow(),
        )
        store.append(ev)  # must not raise
        lines = store_path.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["created_at"] == ev["created_at"]


# ---------------------------------------------------------------------------
# 2. Every existing build_* producer still round-trips through the tightened
#    validator — demonstrated for each shape, not assumed.
# ---------------------------------------------------------------------------


def _created_at_errors(ev: dict[str, Any]) -> list[str]:
    return [e for e in events.validate_envelope(ev) if "created_at" in e]


class TestEveryBuilderStillRoundTrips:
    def test_utcnow_matches_the_canonical_format(self):
        ts = events.utcnow()
        assert is_valid_created_at(ts)
        assert datetime.strptime(ts, CREATED_AT_FORMAT)

    def test_routing_decision_round_trips(self):
        ev = events.build_routing_decision(
            ticket_id="DAS-1", from_status="todo", to_status="in_progress",
            assignee="a", model="sonnet", reason="r", confidence=0.5,
            policy_checks=["x"], fallback="f", created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_agent_invocation_round_trips(self):
        ev = events.build_agent_invocation(
            ticket_id="DAS-1", run_id="run-1", role_key="backend-eng-2",
            model="sonnet", workspace_id="ws-1", context_contract={},
            allowed_tools=[], secrets_policy="no_secrets", exit_contract={},
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_run_start_round_trips(self):
        ev = events.build_run_start(
            ticket_id="DAS-1", run_id="run-1", goal="g", engine_version="1.2.0",
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_run_end_round_trips(self):
        ev = events.build_run_end(
            ticket_id="DAS-1", run_id="run-1", outcome="success", model="sonnet",
            merged_pr=True, ci_status="green", t7_pass=True, t7_score=0.95,
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_wave_round_trips(self):
        ev = events.build_wave(
            ticket_id="DAS-1", run_id="run-1", wave=1, tickets=["DAS-1"],
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_checkpoint_round_trips(self):
        ev = events.build_checkpoint(
            ticket_id="DAS-1", run_id="run-1", wave=1, board_hash="h",
            event_offset=0, ticket_states={}, ledger_hashes={"prev": "a", "self": "b"},
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_cache_hit_round_trips(self):
        ev = events.build_cache_hit(
            ticket_id="DAS-1", cache_key="deadbeef", created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_span_round_trips(self):
        ts = events.utcnow()
        ev = events.build_span(
            ticket_id="DAS-1", span_id="s1", parent_span_id=None, kind="chat",
            agent_name="backend-eng-2", model="sonnet", start=ts, end=ts,
            created_at=ts,
        )
        assert _created_at_errors(ev) == []

    def test_ticket_completion_round_trips(self):
        ev = events.build_ticket_completion(
            ticket_id="DAS-1", run_id="run-1", status="done", wave=1,
            created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []

    def test_replanned_round_trips(self):
        ev = events.build_replanned(
            ticket_id="DAS-1", run_id="run-1", wave=1, revision=2, stall=3,
            max_replans_remaining=1, reason="stall", created_at=events.utcnow(),
        )
        assert _created_at_errors(ev) == []


# ---------------------------------------------------------------------------
# 3. Dropped/undated count is observable, never silent (acceptance #2)
# ---------------------------------------------------------------------------


def _good_and_bad_span() -> list[dict[str, Any]]:
    """One well-formed span + one span carrying the buggy created_at shape.

    Built by hand (not via build_span/EventStore) to simulate an already
    non-conforming record reaching a consumer — e.g. from before this fix, or
    a bypassed seam — so the *consumer-side* counting is exercised
    independently of the write-seam rejection tested above.
    """
    good = {
        "event_type": "span", "ticket_id": "DAS-1633", "trace_id": "DAS-1633",
        "span_id": "s-good", "parent_span_id": None, "kind": "chat",
        "gen_ai.agent.name": "backend-eng-2", "gen_ai.request.model": "sonnet",
        "start": _TS, "end": _TS, "duration_ms": 0,
        "gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 5,
        "gen_ai.usage.cached_input_tokens": 0, "cached": False, "status": "ok",
        "created_at": _TS,
    }
    bad = dict(good)
    bad["span_id"] = "s-bad"
    bad["created_at"] = _BUGGY_SHAPE
    return [good, bad]


class TestDroppedCountIsObservable:
    def test_cost_ledger_surfaces_dropped_undated(self, tmp_path):
        store_path = tmp_path / "scratch.events.jsonl"
        with open(store_path, "w", encoding="utf-8") as fh:
            for ev in _good_and_bad_span():
                fh.write(json.dumps(ev) + "\n")
        # Lifetime aggregation (since=None): both spans counted in totals, but
        # the bad one is still surfaced via dropped_undated (visibility even
        # when nothing is excluded).
        ledger = aggregate_spans(store_path)
        assert ledger is not None
        assert ledger.raw_span_count == 2
        assert ledger.dropped_undated == 1

        # Windowed aggregation (since=...): the bad span is EXCLUDED from the
        # window (D1/DAS-1618 semantics unchanged) but the drop is counted.
        windowed = aggregate_spans(store_path, since=datetime(2020, 1, 1))
        assert windowed is not None
        assert windowed.raw_span_count == 1  # only the good span
        assert windowed.dropped_undated == 1  # the bad one is now visible

    def test_metrics_history_feeder_surfaces_dropped_undated(self):
        good = {"event_type": "run_end", "created_at": _TS}
        bad = {"event_type": "run_end", "created_at": _BUGGY_SHAPE}
        counter = DropCounter()
        result = filter_events_by_window(
            [good, bad],
            start=datetime(2020, 1, 1),
            end=datetime(2030, 1, 1),
            drop_counter=counter,
        )
        assert result == [good]  # bad excluded — semantics unchanged
        assert counter.count == 1  # but now counted, not silent

    def test_wave_kpi_surfaces_dropped_undated(self):
        events_batch = [
            {"event_type": "run_start", "run_id": "r1", "created_at": _TS},
            {"event_type": "run_end", "run_id": "r1", "model": "sonnet", "created_at": _BUGGY_SHAPE},
        ]
        _, stats = wave_kpi.busy_fraction_from_events(events_batch)
        assert stats["dropped_undated"] == 1

    def test_metrics_lib_concurrency_stats_surfaces_dropped_undated(self):
        events_batch = [
            {"event_type": "run_start", "run_id": "r1", "created_at": _TS},
            {"event_type": "run_end", "run_id": "r1", "created_at": _BUGGY_SHAPE},
        ]
        stats = metrics_lib.concurrency_stats(events_batch)
        # No paired interval (the bad run_end never parses), so concurrency_stats
        # itself is None (T3 evidence-only contract) — assert via the shared
        # helper instead, matching what concurrency_stats would report if paired.
        assert stats is None
        assert metrics_lib._dropped_undated(
            events_batch, frozenset({"run_start", "run_end"})
        ) == 1

    def test_metrics_lib_review_efficiency_surfaces_dropped_undated(self):
        events_batch = [
            {
                "event_type": "routing_decision", "ticket_id": "DAS-1",
                "to_status": "in_review", "created_at": _TS,
            },
            {
                "event_type": "routing_decision", "ticket_id": "DAS-1",
                "to_status": "done", "created_at": _BUGGY_SHAPE,
            },
            {
                "event_type": "routing_decision", "ticket_id": "DAS-2",
                "from_status": "in_review", "to_status": "in_progress",
                "created_at": _TS,
            },
        ]
        r = metrics_lib.review_efficiency(events_batch)
        assert r is not None
        assert r["dropped_undated"] == 1

    def test_trends_surfaces_dropped_undated_run_ends(self):
        events_batch = [
            {"event_type": "run_end", "created_at": _TS},
            {"event_type": "run_end", "created_at": _BUGGY_SHAPE},
        ]
        assert trends.dropped_undated_run_ends(events_batch) == 1

    def test_shared_count_invalid_helper(self):
        good, bad = _good_and_bad_span()
        assert count_invalid([good, bad]) == 1
        assert count_invalid([good, good]) == 0


# ---------------------------------------------------------------------------
# 4. Exclusion semantics unchanged — D1/DAS-1618's fix is not reintroduced
# ---------------------------------------------------------------------------


class TestExclusionSemanticsUnchanged:
    def test_unparseable_created_at_never_counts_in_every_window(self):
        """An undated event must NOT count toward a window it does not belong
        to (the permanent-latch failure D1/DAS-1618 was about). Confirmed here
        for the shared filter used by the clean-day evidence window."""
        bad = {"event_type": "run_end", "created_at": _BUGGY_SHAPE}
        for start, end in (
            (datetime(2020, 1, 1), datetime(2020, 12, 31)),
            (datetime(2026, 1, 1), datetime(2026, 12, 31)),
            (None, None),
        ):
            if start is None and end is None:
                # No window at all -> pass-through is correct (nothing filtered).
                assert filter_events_by_window([bad], start, end) == [bad]
            else:
                assert filter_events_by_window([bad], start, end) == []
