#!/usr/bin/env python3
"""check_wave_reconciliation.py — GATE-4: the committed dispatch record reconciles.

ORGANISM WS9 HARNESS (ADR-0032). ADR-0031 shipped ``wave_runner.run_wave`` which
co-produces, atomically, TWO committed records per wave: the doubly hash-chained
``metrics/attestations/<run_id>.json`` receipt (verified for completeness by
``scripts/check_attestation.py``) and one append-only, hash-chained line in the
TRACKED ``board/wave-ledger.jsonl`` (ADR-0032 §1). This validator proves those two
committed records — and the board they describe — MUTUALLY AGREE, fail-closed: a
dropped ledger line, a broken/gapped chain, an orphaned attestation, a tampered
``attestation_hash``, a non-terminal recorded ticket, or a post-baseline ``done``
transition with no covering ledger entry each FAILS CI.

The ledger's four INTRINSIC arms — **well-formed**, **no-duplicate
``(run_id, wave)``**, **hash-chain continuity** (append-order ``prev``/``self``),
and **bijection** (ledger ⇄ committed attestations: no orphan either way, each
``attestation_hash`` == the receipt FILE's exact bytes, ``tickets`` / ``wave``
agree, and each receipt itself verifies) — are DELEGATED to the SSOT primitive
:func:`wave_runner.verify_wave_ledger` (ADR-0032 §1, whose docstring names this
gate as a caller). There is exactly ONE implementation of that logic; this gate
CALLS it and folds its returned problems into the gate's failures — never a forked
second copy that could drift on an enforcement path.

On top of that delegated core, this gate adds three arms that reconcile the ledger
against the LIVE BOARD (which ``verify_wave_ledger`` does not see):

- **WAVE CONTIGUITY** — per ``run_id`` the ``wave`` indices must be gap-free
  contiguous ``1..K``. DISTINCT from hash-chain continuity: an excise-and-relink
  (drop wave 2, recompute the chain) leaves an intact hash chain yet a wave gap,
  which the hash chain alone cannot see. A mid-sequence skip (wave 1 then 3, no 2)
  FAILS.
- **TERMINAL** — every ticket named in any committed ledger entry that EXISTS on
  the board is terminal (``done``/``blocked``). (A ledger ticket absent from the live
  board — e.g. the synthetic committed sample, or an archived ticket — cannot be
  proven non-terminal and is not a violation; the harness-forcing teeth live in the
  COVERAGE arm.)
- **BASELINE + COVERAGE** — a committed ``board/.attestation-baseline`` pins the
  HEAD SHA at regime start so PRE-REGIME ``done`` tickets are grandfathered. The
  COVERAGE arm requires a committed ledger entry ONLY for a board ticket that is
  terminal AND carries a ``run_id`` reference (a ``run_id:`` frontmatter field — the
  post-regime marker a wave stamps on tickets it completes). Such a ticket MUST be
  covered by a committed ledger entry whose ``run_id`` matches and whose ``ticket_ids``
  contains it — a post-baseline ``done`` transition with no reconciled receipt FAILS.
  Pre-regime dones (no ``run_id`` field) are grandfathered and never trigger coverage.

Inert-by-design (ADR 0020, mirroring ``check_attestation``): with NO committed ledger
entries, NO committed attestations, no delegated problem, and NO coverage-needing
board ticket, there is nothing to reconcile — exit 0 (a fresh clone before any wave).
The gate BITES the moment any of those exists. It fail-closes on ANY post-baseline
reconciliation gap.

REUSE, never re-implement: the ledger primitives (``LEDGER_PATH`` / ``LEDGER_FIELDS``
/ ``ATTEST_DIR``, the genesis sentinel, the self-hash, the byte-hasher) AND the whole
intrinsic-reconciliation decision come from ``wave_runner`` (the producer's SSOT).
This validator only re-parses the ledger for the three board-facing arms and
cross-checks.

Exit codes: 0 = reconciled OR inert, 1 = a reconciliation gap, 2 = usage/setup error.

Usage:
    python3 scripts/check_wave_reconciliation.py
    python3 scripts/check_wave_reconciliation.py --ledger board/wave-ledger.jsonl \\
        --attest-dir metrics/attestations --board board/tickets \\
        --baseline board/.attestation-baseline
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import wave_runner as wr
from _paths import ROOT

#: Board statuses that count as terminal for a recorded (attested) ticket.
TERMINAL_STATUSES = frozenset({"done", "blocked"})

#: Default committed baseline anchor — HEAD SHA at regime start (ADR-0032 §3).
BASELINE_PATH: Path = ROOT / "board" / ".attestation-baseline"

#: Default board tickets directory the validator reconciles against.
BOARD_TICKETS_DIR: Path = ROOT / "board" / "tickets"


# --------------------------------------------------------------------------- #
# Small readers (tolerant — a malformed input is reported, never crashes)
# --------------------------------------------------------------------------- #


def load_ledger_entries(ledger_path: Path) -> list[dict]:
    """Tolerantly parse the well-formed entries of ``board/wave-ledger.jsonl``.

    Returns only the lines that are valid JSON objects carrying exactly
    :data:`wave_runner.LEDGER_FIELDS` — the shape the board-facing arms (wave
    contiguity, terminal, coverage) need. Malformed / wrong-field lines are SKIPPED
    here, not reported: the reconciliation verdict on well-formedness and every other
    intrinsic arm is owned by :func:`wave_runner.verify_wave_ledger` (the SSOT), so
    re-flagging them here would be a forked second copy of that logic.
    """
    entries: list[dict] = []
    if not ledger_path.is_file():
        return entries
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if tuple(sorted(entry)) != tuple(sorted(wr.LEDGER_FIELDS)):
            continue
        entries.append(entry)
    return entries


def _read_frontmatter(text: str) -> dict[str, str]:
    """Parse a ticket's leading YAML-ish frontmatter into a flat dict (tolerant)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def load_board_index(board_dir: Path) -> dict[str, dict[str, str]]:
    """Return ``{ticket_id: {"status": ..., "run_id": ...}}`` for the live board.

    ``run_id`` is the empty string when the ticket carries no such frontmatter field
    (the pre-regime / grandfathered case).
    """
    index: dict[str, dict[str, str]] = {}
    if not board_dir.is_dir():
        return index
    for path in sorted(board_dir.glob("DAS-*.md")):
        try:
            fm = _read_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        tid = fm.get("id")
        if tid:
            index[tid] = {"status": fm.get("status", ""), "run_id": fm.get("run_id", "")}
    return index


def _baseline_ancestry_error(sha: str, repo_dir: Path) -> str | None:
    """Verify ``sha`` is a REAL commit that is an ancestor of HEAD in ``repo_dir``.

    Returns ``None`` when the anchor is verified OR the check is legitimately
    skipped (the genesis all-zeros sentinel, or a non-git environment — both
    logged, never a crash); a problem string when the baseline names a
    non-existent object or a commit that is NOT an ancestor of HEAD.

    This is what makes the baseline load-bearing instead of decorative: a forged
    or advanced baseline SHA (one that does not exist, or that was moved ahead of
    HEAD to silently grandfather post-regime dones) FAILS the gate.  In a non-git
    checkout the ancestry claim cannot be evaluated, so it is skipped with a note
    rather than fabricating a pass or crashing (ADR 0020 — unmeasured is skipped).
    """
    # The genesis sentinel (all-zeros) is a convention, not a commit — no object
    # to resolve, nothing before it to grandfather; accept without a git lookup.
    if set(sha) == {"0"}:
        return None

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=str(repo_dir),
            capture_output=True, text=True, check=False,
        )

    try:
        inside = _git("rev-parse", "--is-inside-work-tree")
    except (OSError, ValueError) as exc:  # git absent / un-spawnable
        sys.stderr.write(
            f"read_baseline: cannot run git ({type(exc).__name__}: {exc}) — "
            "skipping baseline ancestry check (non-git environment)\n"
        )
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        sys.stderr.write(
            f"read_baseline: {repo_dir} is not a git work tree — "
            "skipping baseline ancestry check (non-git environment)\n"
        )
        return None

    if _git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return (
            f"baseline SHA {sha!r} is not a commit in this repository "
            "(a forged or non-existent baseline anchor)"
        )
    if _git("merge-base", "--is-ancestor", sha, "HEAD").returncode != 0:
        return (
            f"baseline SHA {sha!r} is not an ancestor of HEAD "
            "(an advanced baseline cannot silently grandfather post-regime dones)"
        )
    return None


def read_baseline(baseline_path: Path) -> tuple[str | None, str | None]:
    """Return (sha, error): the committed baseline SHA, or an error string.

    The anchor must be a single committed token — a 40/64-char hex SHA or the
    genesis all-zeros sentinel — AND (when git is available) a real commit that
    is an ancestor of HEAD.  A missing/malformed baseline, or a forged/advanced
    baseline SHA that git does not confirm as an ancestor of HEAD, is a setup
    error (fail-closed): the coverage arm cannot grandfather without a genuine
    cut-line.  In a non-git environment the ancestry check is skipped with a note.
    """
    if not baseline_path.is_file():
        return None, f"missing committed baseline anchor: {baseline_path}"
    raw = baseline_path.read_text(encoding="utf-8").strip()
    token = raw.splitlines()[0].strip() if raw else ""
    if not token or any(c not in "0123456789abcdefABCDEF" for c in token) or len(token) < 7:
        return None, f"malformed baseline SHA in {baseline_path}: {raw!r}"
    anc_err = _baseline_ancestry_error(token, baseline_path.resolve().parent)
    if anc_err:
        return None, anc_err
    return token, None


# --------------------------------------------------------------------------- #
# The board-facing additive arms (the intrinsic arms delegate to wave_runner)
# --------------------------------------------------------------------------- #


def chain_errors(entries: list[dict]) -> list[str]:
    """Additive WAVE-CONTIGUITY arm — per ``run_id`` the wave indices are 1..K gap-free.

    NOT the hash chain: the ``prev``/``self`` hash-chain continuity (and well-formed,
    no-duplicate, bijection) is DELEGATED to :func:`wave_runner.verify_wave_ledger`.
    This retained arm catches what the hash chain alone cannot — an excise-and-relink
    that drops a wave and recomputes the chain leaves an INTACT hash chain yet a wave
    gap. A mid-sequence skip (wave 1 then 3, no 2) is reported here.
    """
    errors: list[str] = []
    waves_by_run: dict[str, list[int]] = {}
    for entry in entries:
        waves_by_run.setdefault(str(entry["run_id"]), []).append(int(entry["wave"]))
    for run_id, waves in sorted(waves_by_run.items()):
        ordered = sorted(waves)
        if len(set(waves)) != len(waves):
            errors.append(f"run_id {run_id!r}: duplicate wave index in {ordered}")
        expected = list(range(1, len(set(waves)) + 1))
        if sorted(set(waves)) != expected:
            errors.append(
                f"run_id {run_id!r}: wave sequence {ordered} is not gap-free 1..K "
                f"(expected {expected}) — a recorded wave was skipped/dropped"
            )
    return errors


def terminal_errors(entries: list[dict], board: dict[str, dict[str, str]]) -> list[str]:
    """Arm (3): every ledger ticket present on the board is terminal."""
    errors: list[str] = []
    for entry in entries:
        for tid in entry["ticket_ids"]:
            info = board.get(tid)
            if info is None:
                continue  # absent from the live board — not provably non-terminal
            if info["status"] not in TERMINAL_STATUSES:
                errors.append(
                    f"ledger run_id {entry['run_id']!r}: recorded ticket {tid} is "
                    f"{info['status']!r} on the board, not terminal (done/blocked)"
                )
    return errors


def coverage_errors(entries: list[dict], board: dict[str, dict[str, str]]) -> list[str]:
    """Arm (4): every post-regime (run_id-bearing) terminal board ticket is covered.

    A board ticket that is terminal AND carries a ``run_id`` frontmatter field is a
    post-regime completion — it MUST be covered by a committed ledger entry whose
    ``run_id`` matches and whose ``ticket_ids`` contains it. Pre-regime dones (no
    ``run_id`` field) are grandfathered by the baseline and never checked here.
    """
    errors: list[str] = []
    # (run_id -> covered ticket ids) from the committed ledger.
    covered: dict[str, set[str]] = {}
    for entry in entries:
        covered.setdefault(str(entry["run_id"]), set()).update(entry["ticket_ids"])

    for tid, info in sorted(board.items()):
        run_id = info["run_id"]
        if not run_id or info["status"] not in TERMINAL_STATUSES:
            continue  # grandfathered (no run_id) or not yet terminal
        if tid not in covered.get(run_id, set()):
            errors.append(
                f"board ticket {tid} is terminal ({info['status']}) and references "
                f"run_id {run_id!r}, but no committed ledger entry covers it "
                "(a wave committed done-ness without a reconciled receipt)"
            )
    return errors


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def reconcile(
    *,
    ledger_path: Path,
    attest_dir: Path,
    board_dir: Path,
    baseline_path: Path,
) -> tuple[int, list[str], bool]:
    """Run all arms. Return (exit_code, messages, inert)."""
    entries = load_ledger_entries(ledger_path)
    board = load_board_index(board_dir)
    attest_files = sorted(attest_dir.glob("*.json")) if attest_dir.is_dir() else []
    coverage_needed = [
        tid
        for tid, info in board.items()
        if info["run_id"] and info["status"] in TERMINAL_STATUSES
    ]

    # Intrinsic reconciliation (well-formed + no-duplicate + hash-chain + bijection)
    # is DELEGATED to the SSOT primitive — one implementation, no fork.
    ledger_problems = wr.verify_wave_ledger(
        ledger_path, attest_dir=attest_dir, reconcile_attestations=True
    )

    # Inert-by-design: nothing committed to reconcile and no coverage obligation.
    # ``ledger_problems`` guards the malformed-but-nonempty ledger case (a corrupt
    # line has no well-formed entry yet must still bite).
    if not entries and not ledger_problems and not attest_files and not coverage_needed:
        return 0, ["check_wave_reconciliation: no committed ledger/attestations and no "
                   "post-baseline done tickets — gate inert (exit 0). It BITES once a "
                   "wave commits a receipt or a run_id-bearing ticket goes terminal."], True

    # Anything to check ⇒ the committed baseline anchor is REQUIRED (fail-closed).
    _sha, base_err = read_baseline(baseline_path)
    problems: list[str] = list(ledger_problems)
    if base_err:
        problems.append(base_err)
    problems += chain_errors(entries)
    problems += terminal_errors(entries, board)
    problems += coverage_errors(entries, board)

    if problems:
        return 1, problems, False
    return 0, [
        f"OK: {len(entries)} committed ledger entr(y/ies) reconcile with "
        f"{len(attest_files)} committed attestation(s) — bijection, chain, terminality, "
        f"and coverage all hold ({len(coverage_needed)} post-baseline ticket(s) covered)."
    ], False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=wr.LEDGER_PATH,
                    help="committed wave-ledger (default: board/wave-ledger.jsonl)")
    ap.add_argument("--attest-dir", type=Path, default=wr.ATTEST_DIR,
                    help="committed attestation directory (default: metrics/attestations)")
    ap.add_argument("--board", type=Path, default=BOARD_TICKETS_DIR,
                    help="board tickets directory (default: board/tickets)")
    ap.add_argument("--baseline", type=Path, default=BASELINE_PATH,
                    help="committed baseline anchor (default: board/.attestation-baseline)")
    args = ap.parse_args(argv)

    code, messages, _inert = reconcile(
        ledger_path=args.ledger,
        attest_dir=args.attest_dir,
        board_dir=args.board,
        baseline_path=args.baseline,
    )
    if code == 0:
        for m in messages:
            print(m)
        return 0

    sys.stderr.write(
        "FAIL: wave-reconciliation gate (GATE-4 / ADR-0032) — the committed dispatch "
        "record does not reconcile:\n"
    )
    for m in messages:
        sys.stderr.write(f"  - {m}\n")
    sys.stderr.write(f"\n{len(messages)} reconciliation problem(s).\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
