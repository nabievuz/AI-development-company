#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import wave_runner as wr
from _paths import ROOT


TERMINAL_STATUSES = frozenset({"done", "blocked"})


BASELINE_PATH: Path = ROOT / "board" / ".attestation-baseline"


BOARD_TICKETS_DIR: Path = ROOT / "board" / "tickets"


def load_ledger_entries(ledger_path: Path) -> list[dict]:
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


    if set(sha) == {"0"}:
        return None

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=str(repo_dir),
            capture_output=True, text=True, check=False,
        )

    try:
        inside = _git("rev-parse", "--is-inside-work-tree")
    except (OSError, ValueError) as exc:
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


def chain_errors(entries: list[dict]) -> list[str]:
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
    errors: list[str] = []
    for entry in entries:
        for tid in entry["ticket_ids"]:
            info = board.get(tid)
            if info is None:
                continue
            if info["status"] not in TERMINAL_STATUSES:
                errors.append(
                    f"ledger run_id {entry['run_id']!r}: recorded ticket {tid} is "
                    f"{info['status']!r} on the board, not terminal (done/blocked)"
                )
    return errors


def coverage_errors(entries: list[dict], board: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []

    covered: dict[str, set[str]] = {}
    for entry in entries:
        covered.setdefault(str(entry["run_id"]), set()).update(entry["ticket_ids"])

    for tid, info in sorted(board.items()):
        run_id = info["run_id"]
        if not run_id or info["status"] not in TERMINAL_STATUSES:
            continue
        if tid not in covered.get(run_id, set()):
            errors.append(
                f"board ticket {tid} is terminal ({info['status']}) and references "
                f"run_id {run_id!r}, but no committed ledger entry covers it "
                "(a wave committed done-ness without a reconciled receipt)"
            )
    return errors


def reconcile(
    *,
    ledger_path: Path,
    attest_dir: Path,
    board_dir: Path,
    baseline_path: Path,
) -> tuple[int, list[str], bool]:
    entries = load_ledger_entries(ledger_path)
    board = load_board_index(board_dir)
    attest_files = sorted(attest_dir.glob("*.json")) if attest_dir.is_dir() else []
    coverage_needed = [
        tid
        for tid, info in board.items()
        if info["run_id"] and info["status"] in TERMINAL_STATUSES
    ]


    ledger_problems = wr.verify_wave_ledger(
        ledger_path, attest_dir=attest_dir, reconcile_attestations=True
    )


    if not entries and not ledger_problems and not attest_files and not coverage_needed:
        return 0, ["check_wave_reconciliation: no committed ledger/attestations and no "
                   "post-baseline done tickets — gate inert (exit 0). It BITES once a "
                   "wave commits a receipt or a run_id-bearing ticket goes terminal."], True


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
    ap = argparse.ArgumentParser(description='check_wave_reconciliation.py — GATE-4: the committed dispatch record reconciles.')
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
