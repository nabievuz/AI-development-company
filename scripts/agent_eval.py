#!/usr/bin/env python3
"""agent_eval.py — golden-eval harness runner (ORGANISM WS6 GUILD / P19 / DAS-1487).

Measures each agent role's real competence and cost against a curated golden-task
set, so the org can rank roles/models on evidence rather than reputation. This is
GATE-3 (P19) of the ORGANISM WS6 GUILD program.

Layout (a NEW ``evals/`` tree, one dir per golden task)
------------------------------------------------------
::

    evals/<role>/<task-id>/
        task.md          # the task prompt/spec handed to the agent
        fixtures/        # input files/state the task needs (given TO the agent)
        verify.py        # a DETERMINISTIC verifier → fractional credit in [0.0, 1.0]
        submissions/     # recorded sample attempt(s) — the agent's OUTPUT, scored
                         # offline so the harness can grade a role end-to-end WITHOUT
                         # dispatching a live subagent.  Never shown to the agent.

The ``fixtures/`` vs ``submissions/`` split is load-bearing anti-gaming discipline
(inherited from ``scripts/check_metric_gaming.py``): fixtures are inputs the agent
sees; the graded answer key lives ONLY in ``verify.py``.  Putting the answer in
``fixtures/`` would leak verifier internals — forbidden.

Scoring
-------
Each task is scored over ``k`` attempts (default 3).  Every attempt earns
fractional credit in ``[0.0, 1.0]``; the task's accuracy is the mean credit, and a
role's accuracy is the mean over its tasks.  Accuracy is paired with the role's
estimated USD cost pulled from ``scripts/cost/cost_ledger.py`` (the DGO-X span
ledger) to produce one accuracy×cost record per (role, model-tier).

Verifier discipline
-------------------
Verifiers are DETERMINISTIC wherever possible.  A ``verify.py`` exposes either:

* ``def verify(submission: dict, fixtures: Path) -> float`` — a deterministic grader
  (the default, preferred path), OR
* ``RUBRIC = True`` — a soft, rubric-scored task.  The soft path reuses the
  EXISTING ``config/t7_rubric.yaml`` dimensions via ``scripts/check_t7_quality.py``
  (``load_rubric`` + ``check_rubric_integrity`` + ``weighted_score``) — it does NOT
  fork or re-implement a parallel scorer.  The per-dimension scores come from a
  haiku-as-judge pass live, or from the recorded submission's ``judge_scores`` field
  offline.  Haiku-as-judge is allowed ONLY for these soft tasks.

Anti-gaming (inherited from check_metric_gaming.py's Goodhart defence)
--------------------------------------------------------------------
The eval score must not become a new gameable metric.  :func:`gaming_findings`
probes every task with a DEGENERATE (empty) submission and FAILS the task if it
earns any credit — "no reward for empty/degenerate output".  A task that a blank
answer can pass is not a benchmark.

Inert-by-design
---------------
Cost is pulled from the span ledger, which returns ``None`` when no spans exist
yet (the loop-off baseline).  In that state the scorecard reports accuracy with a
``cost = None`` ("n/a") — accuracy is still measurable from recorded submissions
without any live run, exactly like the other DasLab levers ship inert.

Usage::

    python3 scripts/agent_eval.py --role qa-eng --tier sonnet
    python3 scripts/agent_eval.py --all --json
    python3 scripts/agent_eval.py --roster       # print the scorecard markdown table
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import check_t7_quality
from _paths import ROOT
from cost.cost_ledger import aggregate_spans

# ---------------------------------------------------------------------------
# Canonical locations
# ---------------------------------------------------------------------------

DEFAULT_EVALS_ROOT: Path = ROOT / "evals"
DEFAULT_RUBRIC_PATH: Path = ROOT / "config" / "t7_rubric.yaml"
DEFAULT_K: int = 3

#: Release-blocking competence bar (GATE-4). A role whose mean accuracy is at or
#: above this clears the golden-eval gate; below it, the role is flagged and, with
#: ``--enforce``, the run exits non-zero. This is the >=80% mechanism the roster
#: scorecard reports against; owned by QA Lead (GATE-4 accountable — see
#: governance/policies/model-allocation.md).
PASS_BAR: float = 0.80

#: A degenerate/empty submission must earn NO credit — the anti-gaming invariant
#: (Goodhart defence, mirrors check_metric_gaming.py). Anything above this is a
#: gameable task: a blank answer scored a point.
MAX_DEGENERATE_CREDIT: float = 0.0

#: The task.md is the agent-VISIBLE prompt, and a correct one shows ONLY non-answer
#: placeholders (``<int>``, ``<tag>``) — which do not parse as JSON and score nothing.
#: So the guild convention is ZERO overlap: any JSON example that scores ABOVE this
#: through the task's OWN verifier leaked (part of) the graded answer into the prompt,
#: letting an agent copy its own prompt for undeserved credit. Set to 0.0 (strict) —
#: the ORGANISM R-5 review found the full-leak class, and the DAS-1536 guild sweep then
#: found partial (0.2–0.4) coincidental overlaps the empty-probe + a 0.5 bar both miss.
MAX_PROMPT_LEAK_CREDIT: float = 0.0

#: Names under evals/ that are not roles.
_NON_ROLE_ENTRIES = frozenset({"README.md"})


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def clamp01(value: float) -> float:
    """Clamp a numeric credit/score into the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, float(value)))


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class AttemptResult:
    """Fractional credit earned by one attempt at a task."""

    index: int
    credit: float


@dataclass
class TaskResult:
    """Aggregated result of scoring one golden task over k attempts."""

    role: str
    task_id: str
    attempts: list[AttemptResult] = field(default_factory=list)
    rubric: bool = False

    @property
    def accuracy(self) -> float:
        """Mean fractional credit over the scored attempts (0.0 if none)."""
        if not self.attempts:
            return 0.0
        return sum(a.credit for a in self.attempts) / len(self.attempts)

    @property
    def k(self) -> int:
        return len(self.attempts)


@dataclass
class RoleScorecard:
    """One accuracy×cost record for a (role, model-tier) pair."""

    role: str
    tier: str
    tasks: list[TaskResult] = field(default_factory=list)
    cost_usd: float | None = None

    @property
    def accuracy(self) -> float:
        """Mean accuracy over the role's tasks (0.0 when the role has no tasks)."""
        if not self.tasks:
            return 0.0
        return sum(t.accuracy for t in self.tasks) / len(self.tasks)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def meets_bar(self, bar: float = PASS_BAR) -> bool:
        """True when the role's mean accuracy clears the release-blocking bar."""
        return self.accuracy >= bar

    def to_dict(self, bar: float = PASS_BAR) -> dict[str, object]:
        return {
            "role": self.role,
            "tier": self.tier,
            "accuracy": round(self.accuracy, 4),
            "bar": bar,
            "passed": self.meets_bar(bar),
            "cost_usd": None if self.cost_usd is None else round(self.cost_usd, 6),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "rubric": t.rubric,
                    "accuracy": round(t.accuracy, 4),
                    "attempts": [round(a.credit, 4) for a in t.attempts],
                }
                for t in self.tasks
            ],
        }


# ---------------------------------------------------------------------------
# Verifier + submission loading
# ---------------------------------------------------------------------------

class EvalError(Exception):
    """Raised when a golden task is malformed (missing verify.py, bad submission…)."""


def load_verifier(task_dir: Path) -> ModuleType:
    """Import a task's ``verify.py`` as an isolated module.

    The module is loaded under a task-unique name so two tasks named ``verify``
    never collide in ``sys.modules``.  Raises :class:`EvalError` if the file is
    missing or cannot be imported.
    """
    verify_path = task_dir / "verify.py"
    if not verify_path.is_file():
        raise EvalError(f"{task_dir}: no verify.py")
    mod_name = f"_eval_verify_{task_dir.parent.name}_{task_dir.name}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, verify_path)
    if spec is None or spec.loader is None:
        raise EvalError(f"{verify_path}: cannot build import spec")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import error as EvalError
        raise EvalError(f"{verify_path}: import failed: {exc}") from exc
    return module


def load_submissions(task_dir: Path) -> list[dict]:
    """Load a task's recorded sample submissions (the agent's OUTPUT).

    Reads every ``submissions/*.json`` file in sorted order; each file is one
    recorded attempt (a JSON object).  Returns ``[]`` when the directory is
    absent — the caller decides whether that is fatal.
    """
    sub_dir = task_dir / "submissions"
    if not sub_dir.is_dir():
        return []
    submissions: list[dict] = []
    for path in sorted(sub_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvalError(f"{path}: unreadable submission: {exc}") from exc
        if not isinstance(data, dict):
            raise EvalError(f"{path}: submission must be a JSON object")
        submissions.append(data)
    return submissions


# ---------------------------------------------------------------------------
# Scoring a single submission
# ---------------------------------------------------------------------------

def _rubric_credit(rubric: dict, judge_scores: dict) -> float:
    """Score a soft submission by REUSING the T7 rubric (no parallel scorer).

    Reuses ``check_t7_quality`` end-to-end: it verifies the rubric is intact
    (a drifted rubric must never be scored against — same discipline as
    ``check_t7_quality --scores``), then folds the per-dimension judge scores
    through ``weighted_score``.  Each dimension score is clamped to [0,1] first so
    a mis-behaving judge cannot inflate credit above 1.0.
    """
    problems = check_t7_quality.check_rubric_integrity(rubric)
    if problems:
        raise EvalError(f"T7 rubric drift — refusing to score: {problems}")
    clamped = {name: clamp01(score) for name, score in (judge_scores or {}).items()}
    return clamp01(check_t7_quality.weighted_score(rubric, clamped))


def score_submission(
    module: ModuleType,
    submission: dict,
    task_dir: Path,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> float:
    """Score one submission, returning fractional credit in [0.0, 1.0].

    Two paths (chosen by the verify module):

    * ``RUBRIC = True``  → soft task: score the recorded ``judge_scores`` (a
      haiku-as-judge output) through the reused T7 rubric.
    * otherwise          → deterministic task: call
      ``module.verify(submission, fixtures_dir)`` and clamp the result.
    """
    if getattr(module, "RUBRIC", False):
        rubric = check_t7_quality.load_rubric(rubric_path)
        return _rubric_credit(rubric, submission.get("judge_scores", {}))

    verify_fn = getattr(module, "verify", None)
    if not callable(verify_fn):
        raise EvalError(f"{task_dir}: verify.py defines no verify() and is not RUBRIC")
    try:
        credit = verify_fn(submission, task_dir / "fixtures")
    except Exception as exc:  # noqa: BLE001 - a crashing verifier is a task defect
        raise EvalError(f"{task_dir}: verify() raised: {exc}") from exc
    return clamp01(credit)


# ---------------------------------------------------------------------------
# Scoring a task over k attempts
# ---------------------------------------------------------------------------

def score_task(
    task_dir: Path,
    k: int = DEFAULT_K,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> TaskResult:
    """Score one golden task over up to ``k`` recorded attempts.

    Uses the recorded ``submissions/`` fixtures so a role can be graded without
    dispatching a live subagent.  When fewer than ``k`` submissions are recorded,
    all available ones are scored; extras beyond ``k`` are ignored.
    """
    if k < 1:
        raise EvalError(f"k must be >= 1; got {k}")
    module = load_verifier(task_dir)
    is_rubric = bool(getattr(module, "RUBRIC", False))
    submissions = load_submissions(task_dir)
    if not submissions:
        raise EvalError(f"{task_dir}: no recorded submissions to score")

    result = TaskResult(
        role=task_dir.parent.name, task_id=task_dir.name, rubric=is_rubric
    )
    for i, submission in enumerate(submissions[:k]):
        credit = score_submission(module, submission, task_dir, rubric_path)
        result.attempts.append(AttemptResult(index=i, credit=credit))
    return result


# ---------------------------------------------------------------------------
# Anti-gaming probe (Goodhart defence, inherited from check_metric_gaming.py)
# ---------------------------------------------------------------------------

def degenerate_credit(task_dir: Path, rubric_path: Path = DEFAULT_RUBRIC_PATH) -> float:
    """Credit an EMPTY/degenerate submission earns — must be 0 for a real task."""
    module = load_verifier(task_dir)
    return score_submission(module, {}, task_dir, rubric_path)


def gaming_findings(
    evals_root: Path = DEFAULT_EVALS_ROOT,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> list[str]:
    """Return anti-gaming violations across every golden task; [] when clean.

    A task is gameable (violation) when a degenerate empty submission earns more
    than :data:`MAX_DEGENERATE_CREDIT` credit — i.e. an empty/degenerate answer is
    rewarded.  This mirrors the R-9 Goodhart defence in ``check_metric_gaming.py``:
    a metric a blank submission can move is not evidence of competence.
    """
    findings: list[str] = []
    for task_dir in discover_all_tasks(evals_root):
        try:
            credit = degenerate_credit(task_dir, rubric_path)
        except EvalError as exc:
            findings.append(f"{task_dir.parent.name}/{task_dir.name}: {exc}")
            continue
        if credit > MAX_DEGENERATE_CREDIT:
            findings.append(
                f"{task_dir.parent.name}/{task_dir.name}: gameable — a degenerate "
                f"empty submission scored {credit:.4f} (> {MAX_DEGENERATE_CREDIT}); "
                "an empty answer must earn no credit"
            )
    findings.extend(prompt_leak_findings(evals_root, rubric_path))
    return findings


def _json_candidates(text: str) -> list[object]:
    """Every parseable JSON object/array embedded in a markdown text — fenced code
    blocks and balanced ``{…}`` / ``[…]`` spans. A NON-answer placeholder such as
    ``{"cases": [<int>]}`` is not valid JSON and is silently skipped, so only literal
    (answer-shaped) values survive."""
    import re as _re

    out: list[object] = []

    def _try(frag: str) -> None:
        try:
            value = json.loads(frag)
        except (ValueError, TypeError):
            return
        if isinstance(value, dict | list):
            out.append(value)

    for match in _re.finditer(r"```[a-zA-Z0-9]*\n(.*?)```", text, _re.S):
        _try(match.group(1).strip())
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        depth, start = 0, None
        for i, ch in enumerate(text):
            if ch == open_ch:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == close_ch and depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    _try(text[start : i + 1])
                    start = None
    return out


def prompt_leak_findings(
    evals_root: Path = DEFAULT_EVALS_ROOT,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> list[str]:
    """Flag any task whose agent-visible ``task.md`` contains a JSON example that
    scores ABOVE :data:`MAX_PROMPT_LEAK_CREDIT` (0.0 — strict zero-overlap) through
    the task's OWN verifier — i.e. (part of) the graded answer is leaked into the
    prompt. Deterministic tasks only (RUBRIC tasks are judge-scored, not answer-keyed,
    so this probe does not apply)."""
    findings: list[str] = []
    for task_dir in discover_all_tasks(evals_root):
        task_md = task_dir / "task.md"
        if not task_md.is_file():
            continue
        try:
            module = load_verifier(task_dir)
        except EvalError:
            continue
        if getattr(module, "RUBRIC", False):
            continue
        best = 0.0
        for candidate in _json_candidates(task_md.read_text(encoding="utf-8", errors="ignore")):
            try:
                best = max(best, score_submission(module, candidate, task_dir, rubric_path))
            except EvalError:
                continue  # a candidate of the wrong shape simply is not the answer
        if best > MAX_PROMPT_LEAK_CREDIT:
            findings.append(
                f"{task_dir.parent.name}/{task_dir.name}: prompt-leak — a JSON example "
                f"in task.md scores {best:.4f} through the task's own verifier "
                f"(> {MAX_PROMPT_LEAK_CREDIT}); (part of) the graded answer is visible in "
                "the agent-facing prompt. Replace it with a non-answer placeholder."
            )
    return findings


# ---------------------------------------------------------------------------
# Task / role discovery
# ---------------------------------------------------------------------------

def _is_task_dir(path: Path) -> bool:
    return path.is_dir() and (path / "verify.py").is_file()


def discover_roles(evals_root: Path = DEFAULT_EVALS_ROOT) -> list[str]:
    """Return the roles that have at least one golden task, sorted."""
    if not evals_root.is_dir():
        return []
    roles: list[str] = []
    for child in sorted(evals_root.iterdir()):
        if not child.is_dir() or child.name in _NON_ROLE_ENTRIES or child.name.startswith("."):
            continue
        if any(_is_task_dir(t) for t in child.iterdir()):
            roles.append(child.name)
    return roles


def discover_tasks(role: str, evals_root: Path = DEFAULT_EVALS_ROOT) -> list[Path]:
    """Return the task directories for one role, sorted by task id."""
    role_dir = evals_root / role
    if not role_dir.is_dir():
        return []
    return sorted((t for t in role_dir.iterdir() if _is_task_dir(t)), key=lambda p: p.name)


def discover_all_tasks(evals_root: Path = DEFAULT_EVALS_ROOT) -> list[Path]:
    """Return every golden-task directory across all roles, sorted."""
    tasks: list[Path] = []
    for role in discover_roles(evals_root):
        tasks.extend(discover_tasks(role, evals_root))
    return tasks


# ---------------------------------------------------------------------------
# Cost (from the DGO-X span ledger — cost_ledger.py, the single cost source)
# ---------------------------------------------------------------------------

def role_cost(role: str, store_path: Path | str | None = None) -> float | None:
    """Estimated USD cost attributed to ``role`` in the span ledger.

    Delegates to ``cost_ledger.aggregate_spans`` (no re-implemented parsing).
    Returns ``None`` when the ledger is inert (no spans yet — the loop-off
    baseline), ``0.0`` when spans exist but none are attributed to this role.
    """
    ledger = aggregate_spans(store_path)
    if ledger is None:
        return None
    group = ledger.by_agent.get(role)
    return group.estimated_cost_usd if group is not None else 0.0


# ---------------------------------------------------------------------------
# Evaluate a role → one accuracy×cost scorecard
# ---------------------------------------------------------------------------

def evaluate_role(
    role: str,
    tier: str,
    evals_root: Path = DEFAULT_EVALS_ROOT,
    k: int = DEFAULT_K,
    store_path: Path | str | None = None,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> RoleScorecard:
    """Score every golden task for ``role`` and pair accuracy with ledger cost."""
    tasks = [
        score_task(task_dir, k=k, rubric_path=rubric_path)
        for task_dir in discover_tasks(role, evals_root)
    ]
    return RoleScorecard(
        role=role, tier=tier, tasks=tasks, cost_usd=role_cost(role, store_path)
    )


def evaluate_all(
    tier: str = "unspecified",
    evals_root: Path = DEFAULT_EVALS_ROOT,
    k: int = DEFAULT_K,
    store_path: Path | str | None = None,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> list[RoleScorecard]:
    """Score every role that has golden tasks; one scorecard per role."""
    return [
        evaluate_role(role, tier, evals_root, k, store_path, rubric_path)
        for role in discover_roles(evals_root)
    ]


# ---------------------------------------------------------------------------
# Scorecard rendering (feeds docs/AGENT-ROSTER.md)
# ---------------------------------------------------------------------------

def _fmt_cost(cost: float | None) -> str:
    return "n/a (inert)" if cost is None else f"${cost:.4f}"


def scorecard_markdown(scorecards: list[RoleScorecard], bar: float = PASS_BAR) -> str:
    """Render a Markdown accuracy×cost table for the roster scorecard sink.

    The ``Pass`` column reports each role against the release-blocking ``bar``
    (default :data:`PASS_BAR` = 80%) — the >=80% mechanism, made visible per role.
    """
    bar_pct = f"{bar:.0%}"
    lines = [
        f"| Role | Tier | Tasks | Accuracy | Pass (>={bar_pct}) | Est. cost (USD) |",
        "|---|---|---|---|---|---|",
    ]
    for sc in sorted(scorecards, key=lambda s: s.role):
        verdict = "PASS" if sc.meets_bar(bar) else "FAIL"
        lines.append(
            f"| `{sc.role}` | {sc.tier} | {sc.task_count} | "
            f"{sc.accuracy:.2f} | {verdict} | {_fmt_cost(sc.cost_usd)} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--evals", type=Path, default=DEFAULT_EVALS_ROOT, help="evals/ root")
    p.add_argument("--role", default=None, help="score a single role")
    p.add_argument("--tier", default="unspecified", help="model tier being evaluated")
    p.add_argument("--all", action="store_true", help="score every role with tasks")
    p.add_argument("--k", type=int, default=DEFAULT_K, help="attempts per task (default 3)")
    p.add_argument("--events", type=Path, default=None, help="span store for cost")
    p.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC_PATH, help="T7 rubric")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--roster", action="store_true", help="print the scorecard markdown table")
    p.add_argument(
        "--bar", type=float, default=PASS_BAR,
        help=f"release-blocking accuracy bar (default {PASS_BAR:.2f} = 80%%)",
    )
    p.add_argument(
        "--enforce", action="store_true",
        help="exit 1 if any evaluated role's accuracy is below --bar (GATE-4 gate)",
    )
    p.add_argument(
        "--check-gaming",
        action="store_true",
        help="only run the anti-gaming probe over every task (exit 1 if gameable)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.check_gaming:
        findings = gaming_findings(args.evals, args.rubric)
        if findings:
            sys.stderr.write("FAIL: gameable golden task(s):\n")
            for f in findings:
                sys.stderr.write(f"  - {f}\n")
            return 1
        print("OK: no gameable golden tasks.")
        return 0

    # Refuse to score anything if any task is gameable (anti-gaming gate first).
    findings = gaming_findings(args.evals, args.rubric)
    if findings:
        sys.stderr.write("FAIL: gameable golden task(s) — refusing to score:\n")
        for f in findings:
            sys.stderr.write(f"  - {f}\n")
        return 1

    if args.role:
        scorecards = [
            evaluate_role(args.role, args.tier, args.evals, args.k, args.events, args.rubric)
        ]
    elif args.all or args.roster:
        scorecards = evaluate_all(args.tier, args.evals, args.k, args.events, args.rubric)
    else:
        sys.stderr.write("usage: pass --role <role>, --all, or --roster\n")
        return 2

    if not scorecards or all(sc.task_count == 0 for sc in scorecards):
        print("agent_eval: no golden tasks found — nothing to score (inert).")
        return 0

    if args.roster:
        print(scorecard_markdown(scorecards, args.bar))
    elif args.json:
        print(json.dumps([sc.to_dict(args.bar) for sc in scorecards], indent=2))
    else:
        for sc in scorecards:
            verdict = "PASS" if sc.meets_bar(args.bar) else "FAIL"
            print(
                f"{sc.role} [{sc.tier}]: accuracy={sc.accuracy:.3f} "
                f"over {sc.task_count} task(s) [{verdict} @>={args.bar:.2f}], "
                f"cost={_fmt_cost(sc.cost_usd)}"
            )

    if args.enforce:
        below = [sc for sc in scorecards if sc.task_count and not sc.meets_bar(args.bar)]
        if below:
            sys.stderr.write(f"FAIL: role(s) below the {args.bar:.0%} bar:\n")
            for sc in below:
                sys.stderr.write(f"  - {sc.role}: {sc.accuracy:.3f}\n")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
