"""tests/test_wave_runner.py — the CRITICAL end-to-end seam test (DAS-1499).

ADR-0031 §6(a): a synthetic ``(plan, results)`` is driven through the REAL
:func:`wave_runner.run_wave` against a ``tmp_path`` store/runs/attest/evidence
tree, and then the event-based invariants are asserted WITH TEETH — through the
same production validators CI runs, on the fixture data the runner produced:

  * ``check_spans`` reports 100% coverage REALLY (not the inert empty-store path);
  * the emitted ``run_end`` fields match ``metrics_lib`` exactly (fed through
    ``model_mix`` / ``gaming_violations``);
  * ``check_metric_gaming`` passes given the committed evidence the runner wrote;
  * the progress-ledger validates via ``check_ledger.validate_ledger``;
  * the ``WaveAttestation`` is well-formed and its hash-chain is intact, and a
    second wave chains onto the first.

Plus the ADR-0025 shadow rule is proven BY PROPERTY (no allowlist entry): the
runner never calls an event-store READ primitive and never opens a
``.events.jsonl`` literal in read mode, and the ``organism_emit`` gate makes it a
byte-clean no-op when off.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_ledger  # noqa: E402
import check_metric_gaming  # noqa: E402
import check_spans  # noqa: E402
import metrics_lib  # noqa: E402
import wave_kpi  # noqa: E402
import wave_runner as wr  # noqa: E402
from dgox.events import RUN_END_METRICS_FIELDS  # noqa: E402

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"

_WAVE_TS = "2026-07-04T12:00:00Z"
_WAVE_TS2 = "2026-07-04T13:00:00Z"


# --------------------------------------------------------------------------- #
# Fixture builders — a synthetic wave the orchestrator "already decided/observed"
# --------------------------------------------------------------------------- #


def _write_ticket(board_dir: Path, ticket_id: str, assignee: str) -> None:
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / f"{ticket_id}-synthetic.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic wave-runner fixture\n"
        "status: in_progress\n"
        f"assignee: {assignee}\n"
        "author: cto\n"
        "dept: engineering\n"
        "priority: p1\n"
        "---\n\n"
        "## Description\nSynthetic ticket for the wave_runner end-to-end test.\n",
        encoding="utf-8",
    )


def _plan(run_id: str) -> wr.WavePlan:
    return wr.WavePlan(
        run_id=run_id,
        wave=1,
        goal="organism-ws8-attest",
        engine_version="1.0.0",
        tickets=[
            wr.TicketPlan("DAS-9001", role="backend-eng-1", model="opus"),
            wr.TicketPlan("DAS-9002", role="backend-eng-2", model="sonnet"),
        ],
    )


def _results() -> wr.WaveResults:
    common = {
        "outcome": "success", "merged_pr": True, "ci_status": "green",
        "t7_pass": True, "t7_score": 0.95, "start": _WAVE_TS, "end": "2026-07-04T12:10:00Z",
        "final_status": "done", "output": "Implemented the change; all tests green.",
    }
    return wr.WaveResults(
        tickets=[
            wr.TicketResult(ticket_id="DAS-9001", **common),
            wr.TicketResult(ticket_id="DAS-9002", **common),
        ],
        request_satisfied=True,
        in_loop=False,
        progress_being_made=True,
        next_tickets=[],
        instruction="",
    )


def _drive(tmp: Path, run_id: str, created_at: str) -> wr.WaveAttestation:
    board = tmp / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    att = wr.run_wave(
        _plan(run_id),
        _results(),
        created_at=created_at,
        store_path=tmp / "events.jsonl",
        runs_dir=tmp / "runs",
        attest_dir=tmp / "attest",
        ledger_path=tmp / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def test_run_wave_omitted_guardrails_dir_does_not_crash(tmp_path: Path) -> None:
    """Regression (DAS-1501 finding): run_wave must NOT AttributeError when the
    caller omits ``guardrails_dir``. The default now resolves to the same source
    ``guardrail_dispatch`` uses (``guardrails.runner.DEFAULT_GUARDRAILS_DIR``).
    The crash was at arg-defaulting, BEFORE the ``run_guardrails`` gate, so
    ``run_guardrails=False`` still exercises the previously-broken default path
    (and keeps this test hermetic — no real guardrail modules run)."""
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    att = wr.run_wave(
        _plan("01KWS8ATTEST00000000000009"),
        _results(),
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        run_guardrails=False,
        # guardrails_dir deliberately OMITTED — exercises the (was-broken) default.
    )
    assert att is not None
    # The full mechanics ran (no crash at the guardrails_dir default): the
    # committed attestation for this run_id exists on disk.
    assert (tmp_path / "attest" / "01KWS8ATTEST00000000000009.json").exists()


# --------------------------------------------------------------------------- #
# THE end-to-end test — all six mechanics fired, asserted with teeth
# --------------------------------------------------------------------------- #


def test_run_wave_end_to_end_all_mechanics_have_teeth(tmp_path: Path, capsys) -> None:
    run_id = "01JWAVE0000000000000000001"
    att = _drive(tmp_path, run_id, _WAVE_TS)
    store = tmp_path / "events.jsonl"
    evidence_dir = tmp_path / "evidence"

    # --- TEETH 1: check_spans reports 100% coverage REALLY (not the inert path) ---
    rc = check_spans.main(["--events", str(store)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "coverage 100%" in out
    assert "2 dispatch(es)" in out and "2 span(s)" in out  # real fixture, not "no events"

    # --- TEETH 2: emitted run_end fields match metrics_lib EXACTLY ---
    events = wave_kpi.read_events(str(store))
    run_ends = [e for e in events if e.get("event_type") == "run_end"]
    assert len(run_ends) == 2
    for e in run_ends:
        assert set(e) >= RUN_END_METRICS_FIELDS, "run_end missing a metrics-contract field"
    mix = metrics_lib.model_mix(events)
    assert mix == {"ratio": 0.0, "low_cost": 0, "total": 2}  # opus + sonnet, no haiku
    gaming = metrics_lib.gaming_violations(events)
    assert gaming == {"completions": 2, "violations": []}
    assert att.payload["counts"] == {"dispatched": 2, "counted_completions": 2}

    # --- TEETH 3: check_metric_gaming passes GIVEN the committed evidence ---
    rc = check_metric_gaming.main(["--events", str(store), "--evidence-dir", str(evidence_dir)])
    assert rc == 0
    for rid in att.payload["evidence"]["run_ids"]:
        assert (evidence_dir / f"{rid}.json").is_file()

    # --- TEETH 4: the progress-ledger validates via check_ledger ---
    ledger = json.loads(check_ledger.progress_ledger_path(run_id, tmp_path / "runs").read_text())
    assert check_ledger.validate_ledger(ledger) == []

    # --- TEETH 5: attestation well-formed + hash-chain intact ---
    assert att.payload["schema"] == wr.ATTESTATION_SCHEMA
    assert att.payload["mechanics"] == {
        "checkpoint_open": True,
        "guardrails_run": True,
        "events_emitted": {"run_start": 2, "run_end": 2, "span": 2},
        "ledger_written": True,
        "evidence_written": True,
        "checkpoint_close": True,
    }
    assert att.payload["guardrail_verdicts"] == {"DAS-9001": "passed", "DAS-9002": "passed"}
    assert wr.verify_attestation(att.payload) == []       # recomputed self-hash matches
    assert att.prev_hash == wr._GENESIS_PREV_HASH         # first receipt → genesis
    assert wr.load_attestation(att.path) == att.payload   # committed to disk verbatim


def test_attestation_chain_links_across_waves(tmp_path: Path) -> None:
    """A second run's attest_chain.prev links to the first run's self-hash."""
    first = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    second = _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    assert wr.verify_attestation(second.payload) == []
    assert second.prev_hash == first.self_hash            # chain is intact and ordered
    assert second.self_hash != first.self_hash


# --------------------------------------------------------------------------- #
# ADR-0032 §1 — the co-produced, committed, hash-chained wave-ledger
# --------------------------------------------------------------------------- #

_LEDGER_FIELDS = {
    "run_id", "wave", "ticket_ids", "attestation_path",
    "attestation_hash", "prev_hash", "self_hash", "created_at",
}


def _read_ledger(ledger_path: Path) -> list[dict]:
    """Parse the committed wave-ledger into its ordered entries."""
    lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_run_wave_co_produces_chain_linked_ledger_entry(tmp_path: Path) -> None:
    """A single wave writes BOTH the attestation AND one chain-linked ledger entry.

    The entry carries exactly the eight ADR-0032 fields, its self-hash recomputes
    over the self-excluded preimage, prev links to genesis (first entry), ticket_ids
    equals the attestation's ticket set, and attestation_hash is the SHA-256 of the
    committed attestation FILE's exact bytes.
    """
    run_id = "01JWAVE0000000000000000001"
    att = _drive(tmp_path, run_id, _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"

    # BOTH artifacts landed.
    assert att.path.is_file()
    assert ledger_path.is_file()

    entries = _read_ledger(ledger_path)
    assert len(entries) == 1
    entry = entries[0]

    # exactly the eight fields — no more, no less.
    assert set(entry) == _LEDGER_FIELDS
    assert entry["run_id"] == run_id
    assert entry["wave"] == att.payload["wave"] == 1
    assert entry["created_at"] == _WAVE_TS

    # ticket set agrees with the attestation (both sorted).
    assert entry["ticket_ids"] == att.payload["tickets"] == ["DAS-9001", "DAS-9002"]

    # attestation_hash binds the exact committed attestation bytes.
    assert entry["attestation_hash"] == wr._sha256_bytes(att.path.read_bytes())
    assert entry["attestation_path"].endswith(f"{run_id}.json")

    # chain: first entry links to genesis; self-hash recomputes over its preimage.
    assert entry["prev_hash"] == wr._GENESIS_PREV_HASH
    assert entry["self_hash"] == wr._ledger_self_hash(entry)
    assert entry["self_hash"] != wr._GENESIS_PREV_HASH


def test_two_wave_run_writes_two_chain_linked_ledger_entries(tmp_path: Path) -> None:
    """Two waves append two entries whose ledger chain links AND whose
    attestation_hash matches each committed attestation file (ADR-0032 §1)."""
    first = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    second = _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"

    entries = _read_ledger(ledger_path)
    assert len(entries) == 2
    e1, e2 = entries

    # the ledger's OWN chain: entry 2's prev links to entry 1's self (append order).
    assert e1["prev_hash"] == wr._GENESIS_PREV_HASH
    assert e2["prev_hash"] == e1["self_hash"]
    assert e1["self_hash"] == wr._ledger_self_hash(e1)
    assert e2["self_hash"] == wr._ledger_self_hash(e2)
    assert e1["self_hash"] != e2["self_hash"]

    # each entry's attestation_hash matches ITS committed attestation file's bytes.
    assert e1["attestation_hash"] == wr._sha256_bytes(first.path.read_bytes())
    assert e2["attestation_hash"] == wr._sha256_bytes(second.path.read_bytes())
    assert {e1["run_id"], e2["run_id"]} == {first.run_id, second.run_id}


# --------------------------------------------------------------------------- #
# ADR-0032 §1 — verify_wave_ledger: the SSOT reconciliation primitive (DAS-1507)
# the kill-drill and the check_wave_reconciliation gate both reconcile THROUGH.
# --------------------------------------------------------------------------- #


def test_verify_wave_ledger_reconciles_a_clean_two_wave_run(tmp_path: Path) -> None:
    """A clean two-wave run's ledger reconciles: empty problem list."""
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    assert wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest") == []


def test_verify_wave_ledger_empty_or_absent_is_inert(tmp_path: Path) -> None:
    """An absent ledger is inert-by-design (reconciles, no attestations required)."""
    assert wr.verify_wave_ledger(tmp_path / "board" / "wave-ledger.jsonl") == []


def test_verify_wave_ledger_detects_tampered_attestation_hash(tmp_path: Path) -> None:
    """Reformatting the committed attestation FILE (same payload, new bytes) is
    caught: the ledger's attestation_hash no longer matches the file bytes."""
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    # Rewrite the receipt with different bytes (indent) — payload unchanged, so it
    # still verifies, but its file hash differs from the ledger's attestation_hash.
    payload = wr.load_attestation(att.path)
    att.path.write_text(json.dumps(payload, indent=4, sort_keys=True) + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("attestation_hash mismatch" in p for p in problems), problems


def test_verify_wave_ledger_detects_dropped_line_as_chain_gap(tmp_path: Path) -> None:
    """A dropped ledger line breaks the append-order hash chain (a GAP)."""
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # Drop the FIRST entry: the survivor's prev_hash no longer links to genesis.
    ledger_path.write_text(lines[1] + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("broken chain" in p for p in problems), problems


def test_verify_wave_ledger_detects_duplicate_entry(tmp_path: Path) -> None:
    """A duplicated ledger line is caught (duplicate (run_id, wave) + chain break)."""
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    line = ledger_path.read_text(encoding="utf-8").strip()
    ledger_path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("duplicate ledger entry" in p for p in problems), problems


def test_verify_wave_ledger_detects_orphan_attestation(tmp_path: Path) -> None:
    """A committed attestation with no ledger entry is an orphan (fail-closed)."""
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    ledger_path = tmp_path / "board" / "wave-ledger.jsonl"
    # An extra committed receipt that no ledger line accounts for.
    (tmp_path / "attest" / "01JWAVEORPHAN00000000000099.json").write_text(
        json.dumps({"schema": wr.ATTESTATION_SCHEMA, "run_id": "orphan"}), encoding="utf-8"
    )
    problems = wr.verify_wave_ledger(ledger_path, attest_dir=tmp_path / "attest")
    assert any("orphan attestation" in p for p in problems), problems


def test_verify_wave_ledger_reconciles_the_committed_repo_sample() -> None:
    """The committed board/wave-ledger.jsonl reconciles against the repo's
    committed attestations — the shipped sample is tamper-/gap-free."""
    if not wr.LEDGER_PATH.exists():
        pytest.skip("no committed wave-ledger sample in this checkout")
    assert wr.verify_wave_ledger(wr.LEDGER_PATH, attest_dir=wr.ATTEST_DIR) == []


def test_organism_emit_off_is_a_byte_clean_noop(tmp_path: Path) -> None:
    """flag-off: run_wave writes nothing and returns None (flag-on == flag-off)."""
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    _write_ticket(board, "DAS-9002", "backend-eng-2")
    before = {p.name: p.read_text(encoding="utf-8") for p in board.glob("DAS-*.md")}
    store = tmp_path / "events.jsonl"
    attest = tmp_path / "attest"
    ledger = tmp_path / "board" / "wave-ledger.jsonl"
    result = wr.run_wave(
        _plan("01JWAVE0000000000000000009"),
        _results(),
        created_at=_WAVE_TS,
        store_path=store,
        runs_dir=tmp_path / "runs",
        attest_dir=attest,
        ledger_path=ledger,
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        guardrails_dir=_GUARDRAILS,
        organism_emit=False,
    )
    assert result is None
    assert not store.exists()                              # zero events appended
    assert not attest.exists()                             # zero receipts committed
    assert not ledger.exists()                             # zero ledger entries appended
    # flag-off stamps NOTHING: the ticket frontmatter is byte-identical, no run_id.
    after = {p.name: p.read_text(encoding="utf-8") for p in board.glob("DAS-*.md")}
    assert after == before
    assert all("run_id:" not in text for text in after.values())


# --------------------------------------------------------------------------- #
# GAP-1 hardening — run_wave STAMPS run_id into ticket frontmatter (the coverage
# arm of check_wave_reconciliation has real subjects; a forged run_id is caught).
# --------------------------------------------------------------------------- #


def test_run_wave_stamps_run_id_into_each_ticket(tmp_path: Path) -> None:
    """A flag-on wave writes ``run_id: <run_id>`` into every planned ticket file."""
    run_id = "01JWAVE0000000000000000001"
    _drive(tmp_path, run_id, _WAVE_TS)
    board = tmp_path / "board" / "tickets"
    for tid in ("DAS-9001", "DAS-9002"):
        match = sorted(board.glob(f"{tid}-*.md"))[0]
        fm = match.read_text(encoding="utf-8")
        assert f"run_id: {run_id}" in fm
        assert fm.count("run_id:") == 1                    # stamped exactly once


def test_stamp_run_id_frontmatter_is_idempotent(tmp_path: Path) -> None:
    """Stamping the same run_id twice is a byte no-op; a different run_id REPLACES
    (never duplicates) the field, and the frontmatter stays parseable."""
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    path = sorted(board.glob("DAS-9001-*.md"))[0]

    changed1 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000001")
    text1 = path.read_text(encoding="utf-8")
    changed2 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000001")
    text2 = path.read_text(encoding="utf-8")
    assert changed1 is True                                # first stamp writes
    assert changed2 is False                               # second is a byte no-op
    assert text1 == text2
    assert text2.count("run_id:") == 1
    assert "run_id: 01JRUNID000000000000000001" in text2

    changed3 = wr._stamp_run_id_frontmatter(path, "01JRUNID000000000000000002")
    text3 = path.read_text(encoding="utf-8")
    assert changed3 is True                                # a new value rewrites
    assert text3.count("run_id:") == 1                     # replaced, not duplicated
    assert "run_id: 01JRUNID000000000000000002" in text3
    assert "01JRUNID000000000000000001" not in text3


def test_run_wave_missing_ticket_file_does_not_crash_the_wave(tmp_path: Path) -> None:
    """Failure isolation: a planned ticket absent from board_dir is logged and
    skipped — the load-bearing attestation + ledger still commit."""
    run_id = "01JWAVE0000000000000000005"
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    # DAS-9002 deliberately NOT written to board_dir — stamping must not crash.
    att = wr.run_wave(
        _plan(run_id),
        _results(),
        created_at=_WAVE_TS,
        store_path=tmp_path / "events.jsonl",
        runs_dir=tmp_path / "runs",
        attest_dir=tmp_path / "attest",
        ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
        evidence_dir=tmp_path / "evidence",
        tickets_dir=board,
        board_dir=board,
        routing_path=_ROUTING,
        guardrails_dir=_GUARDRAILS,
        run_guardrails=False,
    )
    assert att is not None
    assert (tmp_path / "attest" / f"{run_id}.json").is_file()
    # The present ticket still got stamped; the absent one simply left no file.
    present = sorted(board.glob("DAS-9001-*.md"))[0].read_text(encoding="utf-8")
    assert f"run_id: {run_id}" in present
    assert sorted(board.glob("DAS-9002-*.md")) == []


def test_shadow_rule_holds_by_property(tmp_path: Path) -> None:
    """ADR-0025 §(d): wave_runner never READS the event store, so it is not a
    reader-vs-router violation regardless of what it writes — no allowlist entry.

    This mirrors the discriminator in tests/test_dgox_phase1_shadow.py::P1 and
    asserts the property directly on wave_runner.py's AST.
    """
    tree = ast.parse((_SCRIPTS / "wave_runner.py").read_text(encoding="utf-8"))
    called: set[str] = set()
    events_literal_in_call = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        called.add(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", ""))
        # A ".events.jsonl" literal passed INTO a call (a read) — docstrings excluded.
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and ".events.jsonl" in arg.value:
                events_literal_in_call = True
    read_primitives = {"read_events", "iter_events", "group_runs", "replay_run"}
    assert not (read_primitives & called), "wave_runner must not read the event store"
    assert not events_literal_in_call, "wave_runner must not open a .events.jsonl literal"


def test_missing_result_for_planned_ticket_raises(tmp_path: Path) -> None:
    """A plan ticket with no collected result is a caller error (fail loud)."""
    board = tmp_path / "board" / "tickets"
    _write_ticket(board, "DAS-9001", "backend-eng-1")
    plan = wr.WavePlan(
        run_id="01JWAVE0000000000000000003", wave=1, goal="g", engine_version="1.0.0",
        tickets=[wr.TicketPlan("DAS-9001", "backend-eng-1", "opus"),
                 wr.TicketPlan("DAS-9099", "backend-eng-2", "sonnet")],
    )
    results = wr.WaveResults(tickets=[wr.TicketResult(
        "DAS-9001", outcome="success", merged_pr=True, ci_status="green",
        t7_pass=True, t7_score=0.9, start=_WAVE_TS, end="2026-07-04T12:05:00Z",
        output="done")])
    with pytest.raises(ValueError, match="DAS-9099"):
        wr.run_wave(plan, results, created_at=_WAVE_TS, store_path=tmp_path / "e.jsonl",
                    runs_dir=tmp_path / "runs", attest_dir=tmp_path / "att",
                    ledger_path=tmp_path / "board" / "wave-ledger.jsonl",
                    evidence_dir=tmp_path / "ev", tickets_dir=board, board_dir=board,
                    routing_path=_ROUTING, guardrails_dir=_GUARDRAILS, run_guardrails=False)
