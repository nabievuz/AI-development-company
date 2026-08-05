#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

import yaml
from _paths import ROOT

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

DASLAB_SDK_DIR = ROOT / "daslab_sdk"
BUDGETS_PATH = ROOT / "config" / "budgets.yaml"


_SEAM_MODULE = "wave_runner"
_SEAM_FUNC = "run_wave"


_REQUIRED_CAP_FIELDS = ("max_input_tokens", "max_output_tokens", "max_cost_usd")
_REQUIRED_PLAN_KEYS = ("pro", "max_5x", "max_20x")


def _load_wave_runner():
    spec = importlib.util.spec_from_file_location("_ws_b_health_wave_runner", _HERE / "wave_runner.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _iter_python_files(directory: Path):
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _count_run_wave_call_sites(directory: Path) -> dict[str, list[str]]:
    base = directory.parent
    hits: dict[str, list[str]] = {}
    for path in _iter_python_files(directory):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        found: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == _SEAM_FUNC:
                found.append(f"line {node.lineno}")
        if found:
            try:
                key = str(path.relative_to(base))
            except ValueError:
                key = str(path)
            hits[key] = found
    return hits


def check_dispatch_equivalence_drift() -> dict:
    call_sites = _count_run_wave_call_sites(DASLAB_SDK_DIR)
    total_calls = sum(len(v) for v in call_sites.values())
    files_with_calls = len(call_sites)

    if total_calls == 0:
        return {
            "ok": False,
            "detail": f"no {_SEAM_FUNC}() call found under daslab_sdk/ — runner is no longer "
            f"wired to the single post-decision seam (dispatch path broken, not just drifted)",
        }
    if files_with_calls > 1 or total_calls > 1:
        detail = "; ".join(f"{f}: {', '.join(v)}" for f, v in sorted(call_sites.items()))
        return {
            "ok": False,
            "detail": f"multiple {_SEAM_FUNC}() call sites under daslab_sdk/ ({total_calls} total "
            f"across {files_with_calls} file(s)) — a second producer path would break the "
            f"flag-on == flag-off DECISIONS invariant: {detail}",
        }

    wr = _load_wave_runner()
    problems = wr.verify_wave_ledger(wr.LEDGER_PATH, attest_dir=wr.ATTEST_DIR)
    if problems:
        return {
            "ok": False,
            "detail": f"wave ledger does not reconcile ({len(problems)} problem(s)): "
            f"{'; '.join(str(p) for p in problems[:5])}",
        }
    (only_file,) = call_sites.keys()
    return {
        "ok": True,
        "detail": f"single {_SEAM_FUNC}() caller ({only_file}); ledger reconciles clean (0 problems)",
    }


def check_budget_ceiling_drift(path: Path | None = None) -> dict:
    budgets_path = Path(path) if path is not None else BUDGETS_PATH
    if not budgets_path.exists():
        return {"ok": False, "detail": f"{budgets_path} is missing"}
    try:
        doc = yaml.safe_load(budgets_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {"ok": False, "detail": f"budgets.yaml failed to parse: {exc}"}

    mustaqil = doc.get("mustaqil")
    if not isinstance(mustaqil, dict):
        return {"ok": False, "detail": "budgets.yaml has no top-level `mustaqil:` block"}

    findings: list[str] = []

    caps = mustaqil.get("caps")
    if not isinstance(caps, dict):
        findings.append("mustaqil.caps missing")
    else:
        for window in ("per_run", "per_day"):
            window_caps = caps.get(window)
            if not isinstance(window_caps, dict):
                findings.append(f"mustaqil.caps.{window} missing")
                continue
            for field in _REQUIRED_CAP_FIELDS:
                if field not in window_caps:
                    findings.append(f"mustaqil.caps.{window}.{field} missing")

    ceiling = mustaqil.get("monthly_credit_ceiling")
    if not isinstance(ceiling, dict):
        findings.append("mustaqil.monthly_credit_ceiling missing")
    else:
        plan_credit = ceiling.get("plan_credit_usd")
        if not isinstance(plan_credit, dict):
            findings.append("mustaqil.monthly_credit_ceiling.plan_credit_usd missing")
        else:
            for key in _REQUIRED_PLAN_KEYS:
                if key not in plan_credit:
                    findings.append(f"mustaqil.monthly_credit_ceiling.plan_credit_usd.{key} missing")
        if ceiling.get("on_exhaustion") != "sanctioned_pause":
            findings.append(
                f"mustaqil.monthly_credit_ceiling.on_exhaustion changed to "
                f"{ceiling.get('on_exhaustion')!r} (expected 'sanctioned_pause')"
            )


        overflow = ceiling.get("metered_overflow", "__absent__")
        if overflow is not False:
            findings.append(
                f"mustaqil.monthly_credit_ceiling.metered_overflow is {overflow!r}, expected "
                f"literal false — a flip to true (or a removed key) silently re-enables metered spend"
            )

    if findings:
        return {"ok": False, "detail": "; ".join(findings)}
    return {"ok": True, "detail": "mustaqil: SI-5 caps + monthly-credit ceiling intact, metered_overflow: false"}


def run() -> dict:
    equivalence = check_dispatch_equivalence_drift()
    budget = check_budget_ceiling_drift()
    healthy = equivalence["ok"] and budget["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "dispatch_equivalence_drift": equivalence,
            "budget_ceiling_drift": budget,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ws_b_health_check.py — WS-B runner Maintenance health/eval (GATE-6, DAS-1559)')
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("WS-B runner health check (GATE-6 Maintenance, DAS-1559)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
