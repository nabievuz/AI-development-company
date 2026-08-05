#!/usr/bin/env python3


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


DEFAULT_EVALS_ROOT: Path = ROOT / "evals"
DEFAULT_RUBRIC_PATH: Path = ROOT / "config" / "t7_rubric.yaml"
DEFAULT_K: int = 3


PASS_BAR: float = 0.80


MAX_DEGENERATE_CREDIT: float = 0.0


MAX_PROMPT_LEAK_CREDIT: float = 0.0


_NON_ROLE_ENTRIES = frozenset({"README.md", "e2e"})


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class AttemptResult:

    index: int
    credit: float


@dataclass
class TaskResult:

    role: str
    task_id: str
    attempts: list[AttemptResult] = field(default_factory=list)
    rubric: bool = False

    @property
    def accuracy(self) -> float:
        if not self.attempts:
            return 0.0
        return sum(a.credit for a in self.attempts) / len(self.attempts)

    @property
    def k(self) -> int:
        return len(self.attempts)


@dataclass
class RoleScorecard:

    role: str
    tier: str
    tasks: list[TaskResult] = field(default_factory=list)
    cost_usd: float | None = None

    @property
    def accuracy(self) -> float:
        if not self.tasks:
            return 0.0
        return sum(t.accuracy for t in self.tasks) / len(self.tasks)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def meets_bar(self, bar: float = PASS_BAR) -> bool:
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


class EvalError(Exception):
    pass


def load_verifier(task_dir: Path) -> ModuleType:
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
    except Exception as exc:
        raise EvalError(f"{verify_path}: import failed: {exc}") from exc
    return module


def load_submissions(task_dir: Path) -> list[dict]:
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


def _rubric_credit(rubric: dict, judge_scores: dict) -> float:
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
    if getattr(module, "RUBRIC", False):
        rubric = check_t7_quality.load_rubric(rubric_path)
        return _rubric_credit(rubric, submission.get("judge_scores", {}))

    verify_fn = getattr(module, "verify", None)
    if not callable(verify_fn):
        raise EvalError(f"{task_dir}: verify.py defines no verify() and is not RUBRIC")
    try:
        credit = verify_fn(submission, task_dir / "fixtures")
    except Exception as exc:
        raise EvalError(f"{task_dir}: verify() raised: {exc}") from exc
    return clamp01(credit)


def score_task(
    task_dir: Path,
    k: int = DEFAULT_K,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> TaskResult:
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


def degenerate_credit(task_dir: Path, rubric_path: Path = DEFAULT_RUBRIC_PATH) -> float:
    module = load_verifier(task_dir)
    return score_submission(module, {}, task_dir, rubric_path)


def gaming_findings(
    evals_root: Path = DEFAULT_EVALS_ROOT,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> list[str]:
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
                continue
        if best > MAX_PROMPT_LEAK_CREDIT:
            findings.append(
                f"{task_dir.parent.name}/{task_dir.name}: prompt-leak — a JSON example "
                f"in task.md scores {best:.4f} through the task's own verifier "
                f"(> {MAX_PROMPT_LEAK_CREDIT}); (part of) the graded answer is visible in "
                "the agent-facing prompt. Replace it with a non-answer placeholder."
            )
    return findings


def _is_task_dir(path: Path) -> bool:
    return path.is_dir() and (path / "verify.py").is_file()


def discover_roles(evals_root: Path = DEFAULT_EVALS_ROOT) -> list[str]:
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
    role_dir = evals_root / role
    if not role_dir.is_dir():
        return []
    return sorted((t for t in role_dir.iterdir() if _is_task_dir(t)), key=lambda p: p.name)


def discover_all_tasks(evals_root: Path = DEFAULT_EVALS_ROOT) -> list[Path]:
    tasks: list[Path] = []
    for role in discover_roles(evals_root):
        tasks.extend(discover_tasks(role, evals_root))
    return tasks


def role_cost(role: str, store_path: Path | str | None = None) -> float | None:
    ledger = aggregate_spans(store_path)
    if ledger is None:
        return None
    group = ledger.by_agent.get(role)
    return group.estimated_cost_usd if group is not None else 0.0


def evaluate_role(
    role: str,
    tier: str,
    evals_root: Path = DEFAULT_EVALS_ROOT,
    k: int = DEFAULT_K,
    store_path: Path | str | None = None,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
) -> RoleScorecard:
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
    return [
        evaluate_role(role, tier, evals_root, k, store_path, rubric_path)
        for role in discover_roles(evals_root)
    ]


def _fmt_cost(cost: float | None) -> str:
    return "n/a (inert)" if cost is None else f"${cost:.4f}"


def scorecard_markdown(scorecards: list[RoleScorecard], bar: float = PASS_BAR) -> str:
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


DELIVERY_SCHEMA: str = "daslab.delivery_scorecard.v1"


DELIVERY_EVALS_ROOT: Path = ROOT / "evals" / "e2e"


ED1_DIMENSIONS: tuple[str, ...] = (
    "aadl_gates_closed",
    "merged_pr_green_ci",
    "wave_attestation",
    "diagnostics_100",
    "golden_eval",
    "anti_gaming_probe",
)


_PASS, _FAIL, _SKIP = "pass", "fail", "skipped"


_SUITE_TIMEOUT_S: int = 60


@dataclass
class DimensionResult:

    dimension: str
    status: str
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


def _read_json_artifact(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _dim_aadl_gates_closed(fixtures: Path) -> DimensionResult:
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
    name, ref = "merged_pr_green_ci", "fixtures/counted-tickets.json"
    events = _read_json_artifact(fixtures / "counted-tickets.json")
    if events is None:
        return DimensionResult(name, _SKIP, None, "no counted-tickets.json — unmeasured")
    if not isinstance(events, list) or not events:
        return DimensionResult(name, _FAIL, ref, "counted-tickets.json is empty/malformed")
    try:
        import snapshot_evidence
    except ImportError as exc:
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
    except ImportError as exc:
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


def _mutate_source(src: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            node.body = [ast.Return(value=ast.Constant(value=None))]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _run_suite(workdir: Path) -> bool | None:
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


    stderr = proc.stderr or ""
    unmeasurable = ("ModuleNotFoundError", "ImportError", "SyntaxError", "IndentationError")
    if any(marker in stderr for marker in unmeasurable):
        return None
    return False


def mutation_probe(delivery_dir: Path) -> DimensionResult:
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

        (base / "impl.py").write_text(impl_src, encoding="utf-8")
        (base / "test_impl.py").write_text(test_src, encoding="utf-8")
        baseline = _run_suite(base)
        if baseline is not True:
            reason = "baseline suite is not green" if baseline is False else "suite is un-runnable"
            return DimensionResult(name, _SKIP, None, f"{reason} — cannot measure test tension")

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


def _ws_g_enabled(enabled: bool | None) -> bool:
    if enabled is not None:
        return enabled
    try:
        from feature_flags import enabled as flag_enabled
        return flag_enabled("ws_g_proof")
    except Exception:
        return False


def score_delivery(delivery_dir: Path | str, *, enabled: bool | None = None) -> DeliveryScorecard:
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
    findings: list[str] = []
    card = score_delivery(delivery_dir, enabled=enabled)
    d6 = next((d for d in card.dimensions if d.dimension == "anti_gaming_probe"), None)
    if d6 is not None and d6.status == _FAIL:
        findings.append(f"{card.proof}: anti-gaming probe FAILED — {d6.detail}")

    if card.dimensions and card.passed and all(d.status == _PASS for d in card.dimensions):
        pass
    return findings


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='agent_eval.py — golden-eval harness runner (ORGANISM WS6 GUILD / P19 / DAS-1487).')
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
