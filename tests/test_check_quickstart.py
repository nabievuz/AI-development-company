from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import check_quickstart
from check_quickstart import (
    EXIT_FAIL,
    EXIT_NO_DATA,
    EXIT_OK,
    UnsafeQuickstartCommand,
    command_argv,
    is_runnable_command,
    main,
    order_problem,
    quickstart_commands,
)

_GOOD = """# X

## Quickstart

```bash
git clone https://example/x.git && cd x
python3 scripts/bootstrap.py     # first-run
python3 scripts/doctor.py        # preflight
claude
#   /daslab-plan "<goal>"
```
"""

_BAD = """# X

## Quickstart

```bash
git clone https://example/x.git && cd x
python3 scripts/doctor.py        # FAILS on a fresh clone — projects/ missing
python3 scripts/bootstrap.py
```
"""


def test_parses_runnable_commands(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(_GOOD)
    cmds = quickstart_commands(tmp_path / "README.md")
    assert cmds == ["python3 scripts/bootstrap.py", "python3 scripts/doctor.py"]


def test_good_order_passes() -> None:
    assert order_problem(["python3 scripts/bootstrap.py", "python3 scripts/doctor.py"]) is None


def test_doctor_before_bootstrap_fails() -> None:
    problem = order_problem(["python3 scripts/doctor.py", "python3 scripts/bootstrap.py"])
    assert problem and "precede" in problem


def test_missing_bootstrap_fails() -> None:
    problem = order_problem(["python3 scripts/doctor.py"])
    assert problem and "bootstrap" in problem


def test_main_order_only_good_and_bad(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(_GOOD)
    assert main(["--root", str(tmp_path), "--no-run"]) == EXIT_OK
    (tmp_path / "README.md").write_text(_BAD)
    assert main(["--root", str(tmp_path), "--no-run"]) == EXIT_FAIL


_INJECTION_LINES = [
    "python3 scripts/bootstrap.py && touch /tmp/daslab-pwned",
    "python3 scripts/bootstrap.py; rm -rf /tmp/daslab-pwned",
    "python3 scripts/bootstrap.py | tee /tmp/daslab-pwned",
    "python3 scripts/bootstrap.py $(touch /tmp/daslab-pwned)",
    "python3 scripts/bootstrap.py > /tmp/daslab-pwned",
    "python3 scripts/../../../bin/sh",
]


@pytest.mark.parametrize("line", _INJECTION_LINES)
def test_injection_line_is_not_a_runnable_command(line: str) -> None:
    assert not is_runnable_command(line)


@pytest.mark.parametrize("line", _INJECTION_LINES)
def test_injection_line_is_never_turned_into_argv(line: str) -> None:
    with pytest.raises(UnsafeQuickstartCommand):
        command_argv(line)


def test_plain_and_flagged_commands_stay_runnable() -> None:
    assert is_runnable_command("python3 scripts/bootstrap.py")
    assert is_runnable_command("python3 scripts/doctor.py --json")
    assert command_argv("python3 scripts/doctor.py --json") == [
        "python3", "scripts/doctor.py", "--json",
    ]


_INJECTED_README = """# X

## Quickstart

```bash
python3 scripts/bootstrap.py && touch {marker}
python3 scripts/doctor.py
```
"""


def test_injected_readme_command_is_dropped_not_executed(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    (tmp_path / "README.md").write_text(_INJECTED_README.format(marker=marker))
    cmds = quickstart_commands(tmp_path / "README.md")
    assert cmds == ["python3 scripts/doctor.py"]
    assert main(["--root", str(tmp_path), "--no-run"]) == EXIT_FAIL
    assert not marker.exists()


def test_run_in_scratch_uses_argv_never_a_shell(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    calls: list[tuple[object, dict]] = []

    class _Done:
        returncode = 0
        stdout = b""
        stderr = ""

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return _Done()

    (tmp_path / "README.md").write_text(_GOOD)
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(check_quickstart.subprocess, "run", fake_run)
    monkeypatch.setattr(check_quickstart.shutil, "copytree", lambda *a, **k: None)
    monkeypatch.setattr(check_quickstart.shutil, "copy2", lambda *a, **k: None)

    check_quickstart.run_in_scratch(tmp_path, ["python3 scripts/bootstrap.py"])

    assert calls
    for argv, kwargs in calls:
        assert isinstance(argv, list)
        assert kwargs.get("shell") is not True


def test_missing_readme_is_no_data_not_a_pass(tmp_path: Path) -> None:
    rc = main(["--root", str(tmp_path), "--no-run"])
    assert rc == EXIT_NO_DATA
    assert rc != EXIT_OK


def test_readme_without_quickstart_is_no_data(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# X\n\nno quickstart here\n")
    assert main(["--root", str(tmp_path), "--no-run"]) == EXIT_NO_DATA
