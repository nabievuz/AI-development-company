#!/usr/bin/env python3
"""WS-E (DAS-1584) — promptfoo golden-set eval harness: golden-set-before-judge
+ anti-gaming probe, wired into the `evals/` CI path.

FR-007 (``docs/design/ws-e-tenant-hardening.md`` §4.4): promptfoo runs a
**hand-labeled golden set** as the FIRST gate — only if it fully passes does
any LLM-judge / dashboard scoring ever run (ADR-0017/0020 no-false-green); a
**no-pass ⇒ the eval gate is RED**, and the golden set includes an
**anti-gaming probe** case crafted so a model that pattern-matches the eval
surface (rather than actually doing the work) fails it.

"Wired into the evals/ CI path" concretely means: this module is imported by
``tests/test_ws_e_promptfoo_golden_evals.py``, which ``python3 -m pytest``
(the CI step that already runs on every PR) collects and runs — a red golden
set therefore fails the CI job exactly like any other test failure. No CI
workflow file is edited by this ticket; the wiring is the test file itself.

Reuses the ALREADY-ADMITTED promptfoo sidecar
(``tools/mcp_bridges/promptfoo_tool_bridge.run_eval``, admitted through the
ADR-0033 governed MCP edge by WS-D/DAS-1574, granted to ``qa-eng``/``qa-lead``
in ``board/.tool-allowlist.json``) — this module does not re-admit promptfoo,
does not fork a second eval runner, and does not edit the allow-list.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # evals/ws-e-guardrails/ -> repo root
_BRIDGE_PATH = _ROOT / "tools" / "mcp_bridges" / "promptfoo_tool_bridge.py"

#: The designated anti-gaming case name every golden-set fixture this module
#: reads MUST be able to carry (it is not required to be present — a fixture
#: with no such case simply has no probe — but when present it is treated no
#: differently from any other case by the gate itself: the anti-gaming design
#: is that a gaming completion fails the SAME deterministic check every other
#: case does, not a special-cased rule).
ANTI_GAMING_CASE_NAME = "anti-gaming-probe"


def _load_promptfoo_bridge() -> ModuleType:
    name = "_ws_e_golden_set_promptfoo_tool_bridge"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _BRIDGE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover — defensive
        raise ImportError(f"cannot load {_BRIDGE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ``promptfoo_tool_bridge.run_eval`` returns e.g.
#   "promptfoo: 2/3 passed; failed: anti-gaming-probe"
#   "promptfoo: 3/3 passed"
_SUMMARY_RE = re.compile(r"^promptfoo: (\d+)/(\d+) passed(?:; failed: (.*))?$")


@dataclass(frozen=True)
class GoldenSetResult:
    """Outcome of one golden-set run. ``judge_eligible`` is the
    golden-set-before-judge gate: a judge/dashboard step may run ONLY when
    this is True."""

    passed_count: int
    total_count: int
    failed_names: tuple[str, ...] = field(default_factory=tuple)
    raw_summary: str = ""

    @property
    def all_passed(self) -> bool:
        return self.total_count > 0 and self.passed_count == self.total_count

    @property
    def judge_eligible(self) -> bool:
        """FR-007: the judge is consulted ONLY after a full golden-set pass."""
        return self.all_passed

    @property
    def anti_gaming_probe_failed(self) -> bool:
        """True when the designated gaming-probe case is among the failures
        (i.e. the probe correctly caught a gaming completion). If the fixture
        carries no such case this is simply False — no probe, no claim."""
        return ANTI_GAMING_CASE_NAME in self.failed_names


def run_golden_set(fixture_path: str | Path) -> GoldenSetResult:
    """Run the hand-labeled golden set through the reused promptfoo sidecar.

    Fail-closed: a fixture that cannot be read/parsed, or a summary this
    module cannot parse, reports ``0/0`` (which is NOT ``all_passed`` — an
    unreadable golden set can never be silently treated as green)."""
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
    """No golden-set pass ⇒ RED (ADR-0020 no-false-green). Nothing else —
    not a judge score, not a dashboard metric — can turn this green; the
    golden set is the gate."""
    return not result.all_passed


def run_judge_if_eligible(result: GoldenSetResult) -> str:
    """Golden-set-before-judge (ADR-0017/0020): a judge/dashboard scoring
    step may be consulted ONLY when the golden set fully passed. This ticket
    wires no real LLM-judge (out of FR-007's scope) — the stub exists so the
    ORDERING invariant is itself testable: calling this on a RED result must
    refuse, proving a failing golden set can never be rescued downstream."""
    if not result.judge_eligible:
        raise RuntimeError(
            "golden-set gate is RED (no full pass) — judge/dashboard MUST NOT "
            "run (ADR-0020 no-false-green, FR-007 golden-set-before-judge)"
        )
    return f"judge-eligible: golden set passed {result.passed_count}/{result.total_count}"
