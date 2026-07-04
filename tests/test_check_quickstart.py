"""tests/test_check_quickstart.py — pytest for check_quickstart.py.

Hermetic: synthetic READMEs prove the parser extracts the commands and the order
guard fails a doctor-first Quickstart while passing a bootstrap-first one.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_quickstart import main, order_problem, quickstart_commands  # noqa: E402

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
    assert main(["--root", str(tmp_path), "--no-run"]) == 0
    (tmp_path / "README.md").write_text(_BAD)
    assert main(["--root", str(tmp_path), "--no-run"]) == 1
