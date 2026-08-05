#!/usr/bin/env python3

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


SCHEDULER_FILES: list[Path] = [
    SCRIPTS / "loop_controller.py",
    SCRIPTS / "flow_router.py",
    SCRIPTS / "check_loop_mode.py",
    SCRIPTS / "metrics_history_feeder.py",
    SCRIPTS / "run_workspace.py",
]


class Violation(NamedTuple):
    file: str
    line: int
    kind: str
    detail: str


_THREADING_DAEMON_ATTRS: frozenset[str] = frozenset({"Timer", "Thread"})


_ASYNCIO_LOOP_ATTRS: frozenset[str] = frozenset(
    {"get_event_loop", "new_event_loop", "get_running_loop"}
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _scan_while_true(tree: ast.Module, rel: str) -> list[Violation]:
    found: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.While):
            continue
        test = node.test


        is_literal_true = isinstance(test, ast.Constant) and test.value is True
        if is_literal_true:
            found.append(Violation(
                rel, node.lineno, "while_true",
                "while True loop — would keep the process alive indefinitely "
                "(SI-1 requires one-shot execution only)",
            ))
    return found


def _scan_threading_daemon(tree: ast.Module, rel: str) -> list[Violation]:
    found: list[Violation] = []
    for node in ast.walk(tree):

        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in _THREADING_DAEMON_ATTRS
                and isinstance(func.value, ast.Name)
                and func.value.id == "threading"
            ):
                found.append(Violation(
                    rel, node.lineno, "threading_daemon",
                    f"threading.{func.attr}() — spawns a background thread or timer "
                    "(SI-1: no background threads in the scheduler code)",
                ))

        if isinstance(node, ast.ImportFrom) and node.module == "threading":
            for alias in node.names:
                if alias.name in _THREADING_DAEMON_ATTRS:
                    found.append(Violation(
                        rel, node.lineno, "threading_daemon_import",
                        f"from threading import {alias.name} — imports a daemon "
                        "constructor; use is presumed (SI-1)",
                    ))
    return found


def _scan_sched_module(tree: ast.Module, rel: str) -> list[Violation]:
    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sched" or alias.name.startswith("sched."):
                    found.append(Violation(
                        rel, node.lineno, "sched_import",
                        f"import {alias.name} — the sched module is an in-process "
                        "event scheduler; cadence must live in the OS (SI-1)",
                    ))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "sched" or mod.startswith("sched."):
                found.append(Violation(
                    rel, node.lineno, "sched_import",
                    f"from {mod} import ... — the sched module is an in-process "
                    "event scheduler; cadence must live in the OS (SI-1)",
                ))
    return found


def _scan_asyncio_loop(tree: ast.Module, rel: str) -> list[Violation]:
    found: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue


        if (
            func.attr in _ASYNCIO_LOOP_ATTRS
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
        ):
            found.append(Violation(
                rel, node.lineno, "asyncio_loop",
                f"asyncio.{func.attr}() — obtains a persistent event loop; "
                "use asyncio.run() for one-shot async calls (SI-1)",
            ))


        if func.attr == "run_forever":
            found.append(Violation(
                rel, node.lineno, "asyncio_loop",
                ".run_forever() call — runs an event loop indefinitely (SI-1: one-shot only)",
            ))
    return found


class _SleepInLoopVisitor(ast.NodeVisitor):

    def __init__(self, rel: str) -> None:
        self._rel = rel
        self._depth = 0
        self.violations: list[Violation] = []

    def visit_While(self, node: ast.While) -> None:
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_For(self, node: ast.For) -> None:
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self._depth > 0:
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "sleep"
                and isinstance(func.value, ast.Name)
                and func.value.id == "time"
            ):
                self.violations.append(Violation(
                    self._rel, node.lineno, "sleep_in_loop",
                    "time.sleep() inside a loop — polling / busy-wait pattern "
                    "(SI-1: the process must exit, not spin)",
                ))
        self.generic_visit(node)


def _scan_sleep_in_loop(tree: ast.Module, rel: str) -> list[Violation]:
    v = _SleepInLoopVisitor(rel)
    v.visit(tree)
    return v.violations


def scan_file(path: Path) -> list[Violation]:
    tree = _parse(path)
    rel = path.name
    return (
        _scan_while_true(tree, rel)
        + _scan_threading_daemon(tree, rel)
        + _scan_sched_module(tree, rel)
        + _scan_asyncio_loop(tree, rel)
        + _scan_sleep_in_loop(tree, rel)
    )


class TestSchedulerFilesPresent:

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_file_exists(self, path: Path) -> None:
        assert path.is_file(), (
            f"SI-1 scanner target missing: {path}\n"
            "If the file was renamed or removed, update SCHEDULER_FILES "
            "in tests/test_no_daemon.py to keep the scanner aware."
        )


class TestNoDaemonPatterns:

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_no_while_true(self, path: Path) -> None:
        if not path.is_file():
            pytest.skip(f"{path.name} not present — existence guard is in TestSchedulerFilesPresent")
        bad = [v for v in scan_file(path) if v.kind == "while_true"]
        assert not bad, (
            f"SI-1 VIOLATION — while True loop(s) in {path.name}:\n"
            + "\n".join(f"  line {v.line}: {v.detail}" for v in bad)
        )

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_no_threading_timer_or_thread(self, path: Path) -> None:
        if not path.is_file():
            pytest.skip(f"{path.name} not present")
        bad = [v for v in scan_file(path) if v.kind.startswith("threading_daemon")]
        assert not bad, (
            f"SI-1 VIOLATION — threading.Timer/Thread in {path.name}:\n"
            + "\n".join(f"  line {v.line}: {v.detail}" for v in bad)
        )

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_no_sched_module(self, path: Path) -> None:
        if not path.is_file():
            pytest.skip(f"{path.name} not present")
        bad = [v for v in scan_file(path) if v.kind == "sched_import"]
        assert not bad, (
            f"SI-1 VIOLATION — sched module imported in {path.name}:\n"
            + "\n".join(f"  line {v.line}: {v.detail}" for v in bad)
        )

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_no_asyncio_event_loop(self, path: Path) -> None:
        if not path.is_file():
            pytest.skip(f"{path.name} not present")
        bad = [v for v in scan_file(path) if v.kind == "asyncio_loop"]
        assert not bad, (
            f"SI-1 VIOLATION — asyncio event-loop usage in {path.name}:\n"
            + "\n".join(f"  line {v.line}: {v.detail}" for v in bad)
        )

    @pytest.mark.parametrize("path", SCHEDULER_FILES, ids=lambda p: p.name)
    def test_no_time_sleep_in_loop(self, path: Path) -> None:
        if not path.is_file():
            pytest.skip(f"{path.name} not present")
        bad = [v for v in scan_file(path) if v.kind == "sleep_in_loop"]
        assert not bad, (
            f"SI-1 VIOLATION — time.sleep() inside a loop in {path.name}:\n"
            + "\n".join(f"  line {v.line}: {v.detail}" for v in bad)
        )


class TestScannerCanary:

    def test_canary_while_true(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text("while True:\n    pass\n", encoding="utf-8")
        kinds = {v.kind for v in scan_file(src)}
        assert "while_true" in kinds, "Scanner missed while True — canary FAILED"

    def test_canary_threading_timer(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import threading\nt = threading.Timer(60, lambda: None)\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "threading_daemon" in kinds, "Scanner missed threading.Timer — canary FAILED"

    def test_canary_threading_thread(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import threading\nt = threading.Thread(target=lambda: None)\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "threading_daemon" in kinds, "Scanner missed threading.Thread — canary FAILED"

    def test_canary_threading_import(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "from threading import Timer\nt = Timer(60, lambda: None)\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "threading_daemon_import" in kinds, (
            "Scanner missed from threading import Timer — canary FAILED"
        )

    def test_canary_sched_import(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text("import sched\n", encoding="utf-8")
        kinds = {v.kind for v in scan_file(src)}
        assert "sched_import" in kinds, "Scanner missed import sched — canary FAILED"

    def test_canary_asyncio_get_event_loop(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import asyncio\nloop = asyncio.get_event_loop()\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "asyncio_loop" in kinds, (
            "Scanner missed asyncio.get_event_loop() — canary FAILED"
        )

    def test_canary_asyncio_new_event_loop(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import asyncio\nloop = asyncio.new_event_loop()\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "asyncio_loop" in kinds, (
            "Scanner missed asyncio.new_event_loop() — canary FAILED"
        )

    def test_canary_run_forever(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import asyncio\nloop = asyncio.new_event_loop()\nloop.run_forever()\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "asyncio_loop" in kinds, (
            "Scanner missed loop.run_forever() — canary FAILED"
        )

    def test_canary_sleep_in_while_loop(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import time\nwhile True:\n    time.sleep(1)\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "sleep_in_loop" in kinds, (
            "Scanner missed time.sleep() in while loop — canary FAILED"
        )

    def test_canary_sleep_in_for_loop(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import time\nfor i in range(10):\n    time.sleep(0.5)\n",
            encoding="utf-8",
        )
        kinds = {v.kind for v in scan_file(src)}
        assert "sleep_in_loop" in kinds, (
            "Scanner missed time.sleep() in for loop — canary FAILED"
        )

    def test_canary_sleep_outside_loop_allowed(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "import time\ndef startup():\n    time.sleep(0.1)  # one-shot delay\n",
            encoding="utf-8",
        )
        bad = [v for v in scan_file(src) if v.kind == "sleep_in_loop"]
        assert not bad, (
            "Scanner wrongly flagged time.sleep() outside a loop — false-positive"
        )

    def test_canary_docstring_mention_not_flagged(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            '"""Module docstring: while True, threading.Timer, import sched example."""\n'
            'def f():\n'
            '    """while True in docstring is fine."""\n'
            '    pass\n',
            encoding="utf-8",
        )
        violations = scan_file(src)
        assert not violations, (
            f"Scanner wrongly flagged docstring content as violations: {violations}"
        )

    def test_canary_comment_not_flagged(self, tmp_path: Path) -> None:
        src = tmp_path / "canary.py"
        src.write_text(
            "# while True  threading.Timer  import sched  asyncio.get_event_loop\n"
            "x = 1\n",
            encoding="utf-8",
        )
        violations = scan_file(src)
        assert not violations, (
            f"Scanner wrongly flagged comment content as violations: {violations}"
        )
