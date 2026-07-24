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
import ast
import importlib.util
import json
import subprocess
import sys
import tempfile
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

#: Names under evals/ that are not roles. ``e2e`` is the end-to-end *subject* tree
#: (WS7 gateway packs + the WS-G proof-delivery fixture, DAS-1591) — it is graded by
#: dedicated harnesses (``test_e2e_sample_pack.py`` / :func:`score_delivery`), never as a
#: role golden-task set. Excluding it keeps a ``verify.py`` living under
#: ``evals/e2e/<x>/`` (a delivery fixture) out of role discovery, the degenerate probe,
#: and the roster scorecard.
_NON_ROLE_ENTRIES = frozenset({"README.md", "e2e"})


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


# ===========================================================================
# WS-G delivery scorecard (FR-003 / ED-3 / DAS-1591) — a THIRD subject on this
# same substrate: a *delivery* scored against the six ED-1 completion-contract
# dimensions. This is an EXTENSION of the harness above (ADR-0029 extend-vs-new),
# NOT a parallel harness: it reuses ``load_verifier``/``clamp01``, the
# ``fixtures/`` vs ``submissions/`` anti-gaming boundary, the degenerate/prompt-leak
# defence, and the deterministic-verifier discipline verbatim, and adds one new
# subject + a SWE-bench-style mutation probe. Everything here is behind the
# ``ws_g_proof`` flag (config/features.yaml, DEFAULT OFF): with the flag OFF
# :func:`score_delivery` is inert and none of this runs, so dispatch is
# byte-identical to pre-merge (SC-003).
# ---------------------------------------------------------------------------

#: The machine-readable delivery-scorecard schema (design §1.5; owned here).
DELIVERY_SCHEMA: str = "daslab.delivery_scorecard.v1"

#: Where a proof-DELIVERY golden fixture lives — the same ``evals/e2e/`` subject tree
#: the WS7 gateway packs occupy (design §1.1). ``e2e`` is excluded from role discovery.
DELIVERY_EVALS_ROOT: Path = ROOT / "evals" / "e2e"

#: The six ED-1 "finished" dimensions, in canonical order (ADR-0037 ED-1; design §1.2).
#: The verdict is CONJUNCTIVE — ``passed`` iff ALL six are ``pass`` (design §1.4); there
#: is no averaging and no partial credit, and a ``skipped`` dimension NEVER counts green.
ED1_DIMENSIONS: tuple[str, ...] = (
    "aadl_gates_closed",
    "merged_pr_green_ci",
    "wave_attestation",
    "diagnostics_100",
    "golden_eval",
    "anti_gaming_probe",
)

#: The tri-state a dimension may report. ``skipped`` = unmeasured/unmeasurable and is
#: NEVER a pass (ADR-0020 — the load-bearing "no false-green" rule, design §1.4).
_PASS, _FAIL, _SKIP = "pass", "fail", "skipped"

#: Feed the delivery's own test suite through this mutation probe with a hard wall-clock
#: cap so a runaway/hanging suite cannot stall the harness.
_SUITE_TIMEOUT_S: int = 60


@dataclass
class DimensionResult:
    """One ED-1 dimension's honest tri-state over a committed artifact (design §1.2)."""

    dimension: str
    status: str  # _PASS | _FAIL | _SKIP
    evidence_ref: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "status": self.status,
            "evidence_ref": self.evidence_ref,
            "detail": self.detail,
        }


@dataclass
class DeliveryScorecard:
    """Delivery scored against the six ED-1 dimensions — analogous to :class:`RoleScorecard`.

    ``passed`` is CONJUNCTIVE and fail-closed: ``True`` only when every one of the six
    dimensions is present AND ``pass``. Any ``fail``, any ``skipped``, a short dimension
    list, or an inert (flag-OFF) card denies green — the completion contract is "AND of
    all six", never "average of six" (design §1.4, ADR-0020).
    """

    proof: str
    dimensions: list[DimensionResult] = field(default_factory=list)
    inert: bool = False

    @property
    def passed(self) -> bool:
        if self.inert:
            return False
        if len(self.dimensions) != len(ED1_DIMENSIONS):
            return False
        return all(d.status == _PASS for d in self.dimensions)

    @property
    def verdict(self) -> str:
        """``complete`` iff :attr:`passed`, else ``incomplete`` (design §2.2)."""
        return "complete" if self.passed else "incomplete"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_SCHEMA,
            "proof": self.proof,
            "inert": self.inert,
            "passed": self.passed,
            "verdict": self.verdict,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


# --- the six deterministic dimension verifiers (each reads a committed artifact) ------
# A missing/unreadable artifact ⇒ SKIPPED (never green); a present-but-invalid artifact
# ⇒ FAIL; a present-and-valid artifact ⇒ PASS. None of them ever trusts a prose claim.

def _read_json_artifact(path: Path) -> object | None:
    """Return parsed JSON, or ``None`` when the file is absent/unreadable (⇒ SKIPPED)."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _dim_aadl_gates_closed(fixtures: Path) -> DimensionResult:
    """D1 — all six AADL gates closed on the proof project's stage-board."""
    name, ref = "aadl_gates_closed", "fixtures/stage-board.md"
    board = fixtures / "stage-board.md"
    if not board.is_file():
        return DimensionResult(name, _SKIP, None, "no stage-board.md — unmeasured")
    text = board.read_text(encoding="utf-8", errors="ignore").lower()
    open_gates = [g for g in range(1, 7) if f"gate-{g}: closed" not in text]
    if open_gates:
        return DimensionResult(
            name, _FAIL, ref, f"gate(s) not marked closed: {open_gates}"
        )
    return DimensionResult(name, _PASS, ref + "#stage-board", "all six AADL gates closed")


def _dim_merged_pr_green_ci(fixtures: Path) -> DimensionResult:
    """D2 — a merged PR + green CI (R-9 counted completion) per delivered ticket.

    Reuses ``snapshot_evidence.counted_run_ids``/``completed_run_ids`` verbatim (design
    §1.2 — "never re-derived"): PASS iff there is ≥1 completion and EVERY completion
    clears the counted bar (merged PR + green CI + T7).
    """
    name, ref = "merged_pr_green_ci", "fixtures/counted-tickets.json"
    events = _read_json_artifact(fixtures / "counted-tickets.json")
    if events is None:
        return DimensionResult(name, _SKIP, None, "no counted-tickets.json — unmeasured")
    if not isinstance(events, list) or not events:
        return DimensionResult(name, _FAIL, ref, "counted-tickets.json is empty/malformed")
    try:
        import snapshot_evidence
    except ImportError as exc:  # pragma: no cover - snapshot_evidence is a repo module
        return DimensionResult(name, _SKIP, None, f"snapshot_evidence unavailable: {exc}")
    completed = snapshot_evidence.completed_run_ids(events)
    counted = snapshot_evidence.counted_run_ids(events)
    if not completed:
        return DimensionResult(name, _FAIL, ref, "no completion events with a run_id")
    uncounted = sorted(completed - counted)
    if uncounted:
        return DimensionResult(
            name, _FAIL, ref, f"completion(s) not counted (missing merged PR/green CI/T7): {uncounted}"
        )
    return DimensionResult(name, _PASS, f"counted_run_ids:{len(counted)}", "every completion is counted")


def _dim_wave_attestation(fixtures: Path) -> DimensionResult:
    """D3 — a committed hash-chained wave attestation whose mechanics fired.

    Reuses ``check_attestation``'s required-mechanics tuple + digest-shape check (design
    §1.2). The full cross-file chain WALK is DAS-1592's composing gate; here we assert the
    single committed receipt is complete and its ``attest_chain`` digests are well-formed.
    """
    name, ref = "wave_attestation", "fixtures/wave-attestation.json"
    payload = _read_json_artifact(fixtures / "wave-attestation.json")
    if payload is None:
        return DimensionResult(name, _SKIP, None, "no wave-attestation.json — unmeasured")
    if not isinstance(payload, dict):
        return DimensionResult(name, _FAIL, ref, "attestation is not a JSON object")
    try:
        import check_attestation
        required = check_attestation._REQUIRED_MECHANICS
        digest_ok = check_attestation._digest_ok
    except ImportError as exc:  # pragma: no cover - check_attestation is a repo module
        return DimensionResult(name, _SKIP, None, f"check_attestation unavailable: {exc}")
    mech = payload.get("mechanics")
    if not isinstance(mech, dict):
        return DimensionResult(name, _FAIL, ref, "mechanics block missing/malformed")
    unfired = [m for m in required if mech.get(m) is not True]
    if unfired:
        return DimensionResult(name, _FAIL, ref, f"mechanics did not fire: {unfired}")
    chain = payload.get("attest_chain")
    if not isinstance(chain, dict) or not digest_ok(chain.get("self")) or not digest_ok(chain.get("prev")):
        return DimensionResult(name, _FAIL, ref, "attest_chain.prev/self are not well-formed sha256 digests")
    return DimensionResult(name, _PASS, ref, "attestation complete + chain digests well-formed")


def _dim_diagnostics_100(fixtures: Path) -> DimensionResult:
    """D4 — diagnostics 100/100 on a CLEAN tree (uncommitted drift denies green)."""
    name, ref = "diagnostics_100", "fixtures/diagnostics.json"
    data = _read_json_artifact(fixtures / "diagnostics.json")
    if data is None:
        return DimensionResult(name, _SKIP, None, "no diagnostics.json — unmeasured")
    if not isinstance(data, dict):
        return DimensionResult(name, _FAIL, ref, "diagnostics.json is not a JSON object")
    score, maximum, clean = data.get("score"), data.get("max"), data.get("clean_tree")
    if score != maximum or score != 100:
        return DimensionResult(name, _FAIL, ref, f"diagnostics {score}/{maximum} != 100/100")
    if clean is not True:
        return DimensionResult(name, _FAIL, ref, "working tree is not clean (uncommitted drift)")
    return DimensionResult(name, _PASS, "diagnostics:100/100 clean", "100/100 on a clean tree")


def _dim_golden_eval(fixtures: Path) -> DimensionResult:
    """D5 — the proof delivery's own golden-set score clears the release bar."""
    name, ref = "golden_eval", "fixtures/golden-eval.json"
    data = _read_json_artifact(fixtures / "golden-eval.json")
    if data is None:
        return DimensionResult(name, _SKIP, None, "no golden-eval.json — unmeasured")
    if not isinstance(data, dict) or not isinstance(data.get("accuracy"), int | float):
        return DimensionResult(name, _FAIL, ref, "golden-eval.json missing a numeric accuracy")
    bar = data.get("bar", PASS_BAR)
    acc = float(data["accuracy"])
    if acc < float(bar):
        return DimensionResult(name, _FAIL, ref, f"accuracy {acc:.3f} < bar {float(bar):.3f}")
    return DimensionResult(name, _PASS, ref, f"accuracy {acc:.3f} >= bar {float(bar):.3f}")


# --- D6: the SWE-bench-style mutation anti-gaming probe (design §1.3) ------------------

def _mutate_source(src: str) -> str:
    """Return ``src`` with every function/method body replaced by ``return None``.

    This is the deterministic "gut the implementation" mutant: a suite with real test
    tension must turn RED against it; a suite that stays green (``assert True`` /
    hard-coded / all-skipped) proves nothing and fails the probe.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            node.body = [ast.Return(value=ast.Constant(value=None))]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _run_suite(workdir: Path) -> bool | None:
    """Run ``test_impl.py``'s ``test_*`` functions in ``workdir``; return green/red/None.

    ``True`` = every test passed (green), ``False`` = at least one raised (red),
    ``None`` = the suite could not be executed at all (import/collection error) — an
    UNMEASURABLE suite, reported as SKIPPED by the caller, never green.
    """
    runner = (
        "import importlib\n"
        "m = importlib.import_module('test_impl')\n"
        "for _n in sorted(dir(m)):\n"
        "    if _n.startswith('test_'):\n"
        "        getattr(m, _n)()\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=_SUITE_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode == 0:
        return True
    # Distinguish a real test failure (AssertionError) from an un-runnable suite
    # (ModuleNotFoundError / SyntaxError / collection error → unmeasurable).
    stderr = proc.stderr or ""
    unmeasurable = ("ModuleNotFoundError", "ImportError", "SyntaxError", "IndentationError")
    if any(marker in stderr for marker in unmeasurable):
        return None
    return False


def mutation_probe(delivery_dir: Path) -> DimensionResult:
    """D6 — the delivery's own suite must exercise its implementation (SWE-bench spirit).

    Gut ``fixtures/impl.py`` (bodies → ``return None``) and re-run the delivery's own
    ``fixtures/test_impl.py``. A real suite turns RED (PASS the probe); a suite that stays
    GREEN against the gutted implementation is gaming and FAILS the probe. An absent /
    non-green-baseline / un-runnable suite is SKIPPED (never green — ADR-0020, §1.4).
    """
    name, ref = "anti_gaming_probe", "fixtures/{impl.py,test_impl.py}"
    fixtures = delivery_dir / "fixtures"
    impl, test = fixtures / "impl.py", fixtures / "test_impl.py"
    if not impl.is_file() or not test.is_file():
        return DimensionResult(name, _SKIP, None, "no impl.py/test_impl.py to mutate — unmeasured")

    with tempfile.TemporaryDirectory(prefix="ws_g_mutation_") as tmp:
        base = Path(tmp) / "base"
        mutant = Path(tmp) / "mutant"
        base.mkdir()
        mutant.mkdir()
        impl_src = impl.read_text(encoding="utf-8")
        test_src = test.read_text(encoding="utf-8")
        # Baseline: the suite must be green against the REAL implementation first.
        (base / "impl.py").write_text(impl_src, encoding="utf-8")
        (base / "test_impl.py").write_text(test_src, encoding="utf-8")
        baseline = _run_suite(base)
        if baseline is not True:
            reason = "baseline suite is not green" if baseline is False else "suite is un-runnable"
            return DimensionResult(name, _SKIP, None, f"{reason} — cannot measure test tension")
        # Mutant: gut the implementation; a REAL suite must now turn red.
        try:
            mutated = _mutate_source(impl_src)
        except SyntaxError as exc:
            return DimensionResult(name, _SKIP, None, f"impl.py does not parse: {exc}")
        (mutant / "impl.py").write_text(mutated, encoding="utf-8")
        (mutant / "test_impl.py").write_text(test_src, encoding="utf-8")
        mutant_green = _run_suite(mutant)

    if mutant_green is None:
        return DimensionResult(name, _SKIP, None, "mutant suite un-runnable — cannot measure")
    if mutant_green:
        return DimensionResult(
            name, _FAIL, ref,
            "gaming: the suite stayed GREEN against a gutted implementation — it proves nothing",
        )
    return DimensionResult(name, _PASS, ref, "suite turned RED under mutation — real test tension")


# --- the runner: score a whole delivery into a DeliveryScorecard ----------------------

def _ws_g_enabled(enabled: bool | None) -> bool:
    """Resolve the ``ws_g_proof`` flag (explicit override wins; else read the flag)."""
    if enabled is not None:
        return enabled
    try:
        from feature_flags import enabled as flag_enabled
        return flag_enabled("ws_g_proof")
    except Exception:  # noqa: BLE001 - a missing/broken flag file ⇒ treat as OFF (fail-safe)
        return False


def score_delivery(delivery_dir: Path | str, *, enabled: bool | None = None) -> DeliveryScorecard:
    """Score a proof delivery against the six ED-1 dimensions → a :class:`DeliveryScorecard`.

    Flag-gated: with ``ws_g_proof`` OFF the card is INERT (``inert=True``, ``passed=False``,
    no dimensions run) so the surface does not exist and dispatch is byte-identical to
    pre-merge (SC-003). Pass ``enabled=True`` to score explicitly (tests, an ON wave).
    """
    delivery_dir = Path(delivery_dir)
    proof = delivery_dir.name
    if not _ws_g_enabled(enabled):
        return DeliveryScorecard(proof=proof, dimensions=[], inert=True)
    fixtures = delivery_dir / "fixtures"
    dims = [
        _dim_aadl_gates_closed(fixtures),
        _dim_merged_pr_green_ci(fixtures),
        _dim_wave_attestation(fixtures),
        _dim_diagnostics_100(fixtures),
        _dim_golden_eval(fixtures),
        mutation_probe(delivery_dir),
    ]
    return DeliveryScorecard(proof=proof, dimensions=dims)


def delivery_gaming_findings(delivery_dir: Path | str, *, enabled: bool = True) -> list[str]:
    """Anti-gaming violations for a delivery; ``[]`` when clean (design §1.3).

    Extends the task-level Goodhart defence to a DELIVERY: (a) an empty/degenerate
    delivery (no committed artifacts) must NOT pass — an all-``skipped`` card is not green;
    (b) the D6 mutation probe must not FAIL (a suite that stays green against a gutted
    implementation is gaming).
    """
    findings: list[str] = []
    card = score_delivery(delivery_dir, enabled=enabled)
    d6 = next((d for d in card.dimensions if d.dimension == "anti_gaming_probe"), None)
    if d6 is not None and d6.status == _FAIL:
        findings.append(f"{card.proof}: anti-gaming probe FAILED — {d6.detail}")
    # A delivery whose every dimension is skipped/absent must never read as green.
    if card.dimensions and card.passed and all(d.status == _PASS for d in card.dimensions):
        pass  # a genuinely all-pass delivery is legitimate — not a finding
    return findings


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
    p.add_argument(
        "--delivery",
        type=Path,
        default=None,
        help="score a proof DELIVERY dir (WS-G, DAS-1591) and print its DeliveryScorecard "
        "(inert unless ws_g_proof is ON; --delivery-enforce exits 1 unless verdict complete)",
    )
    p.add_argument(
        "--delivery-enforce",
        action="store_true",
        help="with --delivery: exit 1 unless the delivery verdict is 'complete' (all six ED-1 pass)",
    )
    return p


def _run_delivery(args: argparse.Namespace) -> int:
    """Score a proof delivery (``--delivery``) → print the DeliveryScorecard JSON.

    Inert (prints a notice, exit 0) when ``ws_g_proof`` is OFF — the WS-G surface does
    not exist with the flag OFF (SC-003). With ``--delivery-enforce``, a non-``complete``
    verdict exits 1 (a ``skipped``/``fail`` dimension denies green — ADR-0020).
    """
    card = score_delivery(args.delivery)
    if card.inert:
        print("agent_eval: ws_g_proof OFF — delivery scorecard inert (nothing scored).")
        return 0
    print(json.dumps(card.to_dict(), indent=2))
    if args.delivery_enforce and not card.passed:
        sys.stderr.write(
            f"FAIL: delivery '{card.proof}' verdict={card.verdict} — not all six ED-1 dimensions pass.\n"
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.delivery is not None:
        return _run_delivery(args)

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
