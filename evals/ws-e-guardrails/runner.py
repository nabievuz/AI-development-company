#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_BRIDGE_PATH = _ROOT / "tools" / "mcp_bridges" / "promptfoo_tool_bridge.py"


ANTI_GAMING_CASE_NAME = "anti-gaming-probe"


def _load_promptfoo_bridge() -> ModuleType:
    name = "_ws_e_golden_set_promptfoo_tool_bridge"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _BRIDGE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_BRIDGE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_SUMMARY_RE = re.compile(r"^promptfoo: (\d+)/(\d+) passed(?:; failed: (.*))?$")


@dataclass(frozen=True)
class GoldenSetResult:

    passed_count: int
    total_count: int
    failed_names: tuple[str, ...] = field(default_factory=tuple)
    raw_summary: str = ""

    @property
    def all_passed(self) -> bool:
        return self.total_count > 0 and self.passed_count == self.total_count

    @property
    def judge_eligible(self) -> bool:
        return self.all_passed

    @property
    def anti_gaming_probe_failed(self) -> bool:
        return ANTI_GAMING_CASE_NAME in self.failed_names


def run_golden_set(fixture_path: str | Path) -> GoldenSetResult:
    bridge = _load_promptfoo_bridge()
    summary = bridge.run_eval(str(fixture_path))
    match = _SUMMARY_RE.match(summary)
    if not match:
        return GoldenSetResult(0, 0, (), summary)
    passed = int(match.group(1))
    total = int(match.group(2))
    failed_raw = match.group(3) or ""
    failed_names = tuple(n.strip() for n in failed_raw.split(",") if n.strip())
    return GoldenSetResult(passed, total, failed_names, summary)


def gate_is_red(result: GoldenSetResult) -> bool:
    return not result.all_passed


def run_judge_if_eligible(result: GoldenSetResult) -> str:
    if not result.judge_eligible:
        raise RuntimeError(
            "golden-set gate is RED (no full pass) — judge/dashboard MUST NOT "
            "run (ADR-0020 no-false-green, FR-007 golden-set-before-judge)"
        )
    return f"judge-eligible: golden set passed {result.passed_count}/{result.total_count}"
