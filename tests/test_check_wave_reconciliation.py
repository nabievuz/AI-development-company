"""tests/test_check_wave_reconciliation.py — GATE-4 reconciliation gate (DAS-1506).

Proves the committed sample RECONCILES (bijection + chain + terminality + coverage)
and that each tamper class FAILS with teeth: a dropped ledger entry (hash-chain
break), a mid-sequence wave gap, an orphan attestation, an orphan ledger entry, a
tampered ``attestation_hash``, a non-terminal recorded ticket, and an uncovered
post-baseline ``done`` ticket. Fixtures are driven through the production
``wave_runner.run_wave`` (never a hand-rolled payload) so the ledger + attestation
are byte-faithful to what a live wave commits.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_wave_reconciliation as cwr  # noqa: E402
import wave_runner as wr  # noqa: E402

_ROUTING = _REPO_ROOT / "board" / "ROUTING.md"
_GUARDRAILS = _REPO_ROOT / "governance" / "guardrails"

_WAVE_TS = "2026-07-04T12:00:00Z"
_WAVE_TS2 = "2026-07-04T13:00:00Z"
_END_TS = "2026-07-04T12:10:00Z"
_BASELINE_SHA = "02b1f596918234270a2c3967315f04fa4f3e45a3"


# --------------------------------------------------------------------------- #
# Helpers — drive a real receipt + ledger line through run_wave into a tmp tree
# --------------------------------------------------------------------------- #


def _write_ticket(board: Path, ticket_id: str, status: str = "in_progress",
                  run_id: str = "") -> None:
    board.mkdir(parents=True, exist_ok=True)
    run_line = f"run_id: {run_id}\n" if run_id else ""
    (board / f"{ticket_id}-fixture.md").write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: Synthetic fixture\n"
        f"status: {status}\n"
        f"{run_line}"
        "assignee: backend-eng-1\n"
        "author: cto\ndept: engineering\npriority: p1\n"
        "---\n\n## Description\nSynthetic.\n",
        encoding="utf-8",
    )


def _paths(tmp: Path) -> dict[str, Path]:
    return {
        "ledger": tmp / "board" / "wave-ledger.jsonl",
        "attest": tmp / "attest",
        "evidence": tmp / "evidence",
        "guard_board": tmp / "guard-board" / "tickets",
        "baseline": tmp / "board" / ".attestation-baseline",
    }


def _drive(tmp: Path, run_id: str, created_at: str, wave: int = 1) -> wr.WaveAttestation:
    p = _paths(tmp)
    _write_ticket(p["guard_board"], "DAS-9001")
    _write_ticket(p["guard_board"], "DAS-9002")
    common = {
        "outcome": "success", "merged_pr": True, "ci_status": "green",
        "t7_pass": True, "t7_score": 0.95, "start": _WAVE_TS, "end": _END_TS,
        "final_status": "done", "output": "done; tests green.",
    }
    plan = wr.WavePlan(
        run_id=run_id, wave=wave, goal="organism-ws9-harness", engine_version="1.0.0",
        tickets=[wr.TicketPlan("DAS-9001", "backend-eng-1", "opus"),
                 wr.TicketPlan("DAS-9002", "backend-eng-2", "sonnet")],
    )
    results = wr.WaveResults(tickets=[wr.TicketResult(ticket_id="DAS-9001", **common),
                                      wr.TicketResult(ticket_id="DAS-9002", **common)])
    att = wr.run_wave(
        plan, results, created_at=created_at,
        store_path=tmp / "events.jsonl", runs_dir=tmp / "runs",
        attest_dir=p["attest"], ledger_path=p["ledger"], evidence_dir=p["evidence"],
        tickets_dir=p["guard_board"], board_dir=p["guard_board"],
        routing_path=_ROUTING, guardrails_dir=_GUARDRAILS,
    )
    assert att is not None
    return att


def _write_baseline(tmp: Path) -> Path:
    p = _paths(tmp)["baseline"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_BASELINE_SHA + "\n", encoding="utf-8")
    return p


def _recon(tmp: Path, board: Path | None = None) -> int:
    """Run cwr.main against the tmp tree; ``board`` defaults to an empty dir."""
    p = _paths(tmp)
    if board is None:
        board = tmp / "recon-empty-board"
        board.mkdir(parents=True, exist_ok=True)
    return cwr.main([
        "--ledger", str(p["ledger"]), "--attest-dir", str(p["attest"]),
        "--board", str(board), "--baseline", str(p["baseline"]),
    ])


def _read_ledger(tmp: Path) -> list[dict]:
    return [json.loads(x) for x in
            _paths(tmp)["ledger"].read_text(encoding="utf-8").splitlines() if x.strip()]


def _write_ledger(tmp: Path, entries: list[dict]) -> None:
    lines = [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in entries]
    _paths(tmp)["ledger"].write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# The committed sample reconciles; empty regime is inert
# --------------------------------------------------------------------------- #


def test_committed_sample_reconciles(capsys) -> None:
    rc = cwr.main([])  # real defaults: committed ledger + attestations + baseline + board
    out = capsys.readouterr().out
    assert rc == 0
    assert "reconcile" in out


def test_inert_when_empty(tmp_path: Path, capsys) -> None:
    _write_baseline(tmp_path)
    (tmp_path / "board").mkdir(parents=True, exist_ok=True)
    (tmp_path / "attest").mkdir()
    rc = _recon(tmp_path)
    assert rc == 0
    assert "inert" in capsys.readouterr().out


def test_fresh_wave_reconciles(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    assert _recon(tmp_path) == 0


# --------------------------------------------------------------------------- #
# (1) BIJECTION — orphan attestation / orphan ledger / tampered hash
# --------------------------------------------------------------------------- #


def test_orphan_attestation_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    _paths(tmp_path)["ledger"].write_text("", encoding="utf-8")  # drop the only line
    assert _recon(tmp_path) == 1                                 # attestation now orphaned


def test_orphan_ledger_entry_fails(tmp_path: Path) -> None:
    att = _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    att.path.unlink()                                           # drop the attestation file
    assert _recon(tmp_path) == 1                                # ledger entry now orphaned


def test_tampered_attestation_hash_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    entries = _read_ledger(tmp_path)
    entries[0]["attestation_hash"] = "sha256:" + "b" * 64       # a lie about the receipt
    entries[0]["self_hash"] = wr._ledger_self_hash(entries[0])  # keep the line self-consistent
    _write_ledger(tmp_path, entries)
    assert _recon(tmp_path) == 1                                # file bytes hash != recorded


def test_tampered_ticket_set_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    entries = _read_ledger(tmp_path)
    entries[0]["ticket_ids"] = ["DAS-9001"]                     # drop DAS-9002 from the entry
    entries[0]["self_hash"] = wr._ledger_self_hash(entries[0])
    _write_ledger(tmp_path, entries)
    assert _recon(tmp_path) == 1


# --------------------------------------------------------------------------- #
# (2) CHAIN — dropped line breaks the hash chain; wave gap breaks contiguity
# --------------------------------------------------------------------------- #


def test_dropped_ledger_entry_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    _write_baseline(tmp_path)
    entries = _read_ledger(tmp_path)
    assert len(entries) == 2
    _write_ledger(tmp_path, entries[1:])                        # drop the first (genesis) line
    assert _recon(tmp_path) == 1                                # second line's prev != genesis


def test_wave_sequence_gap_fails() -> None:
    def _entry(run_id: str, wave: int, prev: str) -> dict:
        e = {
            "run_id": run_id, "wave": wave, "ticket_ids": ["DAS-1"],
            "attestation_path": f"metrics/attestations/{run_id}.json",
            "attestation_hash": "sha256:" + "a" * 64, "prev_hash": prev,
            "self_hash": "", "created_at": "2026-07-04T00:00:00Z",
        }
        e["self_hash"] = wr._ledger_self_hash(e)
        return e

    e1 = _entry("R", 1, wr._GENESIS_PREV_HASH)
    e3 = _entry("R", 3, e1["self_hash"])                        # wave 2 is missing
    errs = cwr.chain_errors([e1, e3])
    assert any("gap-free" in x or "skipped" in x for x in errs)


def test_intact_chain_has_no_errors(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _drive(tmp_path, "01JWAVE0000000000000000002", _WAVE_TS2)
    assert cwr.chain_errors(_read_ledger(tmp_path)) == []


# --------------------------------------------------------------------------- #
# (3) TERMINAL — a recorded ticket that is non-terminal on the board FAILS
# --------------------------------------------------------------------------- #


def test_nonterminal_recorded_ticket_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    recon_board = tmp_path / "recon-board" / "tickets"
    _write_ticket(recon_board, "DAS-9001", status="in_progress")  # recorded but not terminal
    _write_ticket(recon_board, "DAS-9002", status="done")
    assert _recon(tmp_path, board=recon_board) == 1


def test_terminal_recorded_ticket_passes(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    recon_board = tmp_path / "recon-board" / "tickets"
    _write_ticket(recon_board, "DAS-9001", status="done")
    _write_ticket(recon_board, "DAS-9002", status="blocked")
    assert _recon(tmp_path, board=recon_board) == 0


# --------------------------------------------------------------------------- #
# (4) BASELINE + COVERAGE — post-baseline run_id-bearing done must be covered
# --------------------------------------------------------------------------- #


def test_uncovered_post_baseline_done_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    recon_board = tmp_path / "recon-board" / "tickets"
    # A done ticket that references the run but is NOT in the ledger's ticket set.
    _write_ticket(recon_board, "DAS-7000", status="done", run_id="01JWAVE0000000000000000001")
    assert _recon(tmp_path, board=recon_board) == 1


def test_covered_post_baseline_done_passes(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    recon_board = tmp_path / "recon-board" / "tickets"
    _write_ticket(recon_board, "DAS-9001", status="done", run_id="01JWAVE0000000000000000001")
    assert _recon(tmp_path, board=recon_board) == 0


def test_pre_regime_done_is_grandfathered(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    _write_baseline(tmp_path)
    recon_board = tmp_path / "recon-board" / "tickets"
    # A done ticket with NO run_id field — pre-regime, grandfathered, never checked.
    _write_ticket(recon_board, "DAS-0001", status="done")
    assert _recon(tmp_path, board=recon_board) == 0


def test_missing_baseline_fails(tmp_path: Path) -> None:
    _drive(tmp_path, "01JWAVE0000000000000000001", _WAVE_TS)
    # No baseline written — anything to check ⇒ fail-closed.
    assert _recon(tmp_path) == 1


# --------------------------------------------------------------------------- #
# Malformed ledger line is reported, not crashed
# --------------------------------------------------------------------------- #


def test_corrupt_ledger_line_fails(tmp_path: Path) -> None:
    _write_baseline(tmp_path)
    p = _paths(tmp_path)
    p["ledger"].parent.mkdir(parents=True, exist_ok=True)
    p["ledger"].write_text("{not json\n", encoding="utf-8")
    p["attest"].mkdir(parents=True, exist_ok=True)
    assert _recon(tmp_path) == 1


# --------------------------------------------------------------------------- #
# GAP-2 hardening — read_baseline VERIFIES the baseline is a real git ancestor of
# HEAD (a forged/advanced anchor fails; a genuine committed ancestor passes; a
# non-git environment skips the ancestry check gracefully).
# --------------------------------------------------------------------------- #


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, check=True)


def _init_repo(tmp: Path) -> tuple[Path, str]:
    """Init a real git repo with one commit; return (repo_dir, head_sha)."""
    repo = tmp / "repo"
    (repo / "board").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return repo, head


def test_read_baseline_accepts_committed_ancestor(tmp_path: Path) -> None:
    """A baseline equal to HEAD (a genuine ancestor) verifies."""
    repo, head = _init_repo(tmp_path)
    baseline = repo / "board" / ".attestation-baseline"
    baseline.write_text(head + "\n", encoding="utf-8")
    sha, err = cwr.read_baseline(baseline)
    assert err is None
    assert sha == head


def test_read_baseline_rejects_nonexistent_sha(tmp_path: Path) -> None:
    """A well-formed but non-existent SHA (no such commit) fails the object check."""
    repo, _head = _init_repo(tmp_path)
    baseline = repo / "board" / ".attestation-baseline"
    baseline.write_text("deadbeef" * 5 + "\n", encoding="utf-8")   # 40 hex, not a commit
    sha, err = cwr.read_baseline(baseline)
    assert sha is None
    assert err is not None and "not a commit" in err


def test_read_baseline_rejects_nonancestor_sha(tmp_path: Path) -> None:
    """A real commit that is NOT an ancestor of HEAD (an advanced/divergent
    baseline) fails the merge-base check."""
    repo, _head = _init_repo(tmp_path)
    # A divergent commit reachable only from a side branch, not from HEAD.
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2")
    side = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-q", "-")                              # back to c1 (HEAD)
    baseline = repo / "board" / ".attestation-baseline"
    baseline.write_text(side + "\n", encoding="utf-8")
    sha, err = cwr.read_baseline(baseline)
    assert sha is None
    assert err is not None and "ancestor" in err


def test_read_baseline_skips_ancestry_in_non_git_env(tmp_path: Path) -> None:
    """Outside a git work tree the ancestry check is skipped (not crashed): a
    well-formed SHA still returns cleanly."""
    baseline = tmp_path / "board" / ".attestation-baseline"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(_BASELINE_SHA + "\n", encoding="utf-8")
    sha, err = cwr.read_baseline(baseline)
    assert err is None
    assert sha == _BASELINE_SHA


def test_read_baseline_committed_sample_is_ancestor() -> None:
    """The real committed baseline verifies as an ancestor of HEAD in this repo."""
    if not cwr.BASELINE_PATH.is_file():
        pytest.skip("no committed baseline in this checkout")
    sha, err = cwr.read_baseline(cwr.BASELINE_PATH)
    assert err is None
    assert sha


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
