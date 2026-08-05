from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@dataclass(frozen=True)
class ZoneCli:
    script: str
    exit_codes: dict[str, int]


ZONE_CLIS: tuple[ZoneCli, ...] = (
    ZoneCli("check_secrets.py", {"ok": 0, "problem": 1, "usage": 2, "no_data": 3}),
    ZoneCli("doctor.py", {"ok": 0, "problem": 1, "usage": 2}),
    ZoneCli("check_quickstart.py", {"ok": 0, "problem": 1, "usage": 2, "no_data": 3}),
    ZoneCli("wave_kpi.py", {"ok": 0, "problem": 1, "usage": 2, "no_data": 3}),
    ZoneCli("alerting.py", {"ok": 0, "problem": 1, "usage": 2, "no_data": 3}),
    ZoneCli("bootstrap.py", {"ok": 0, "problem": 1, "usage": 2}),
    ZoneCli("trends.py", {"ok": 0, "problem": 1, "usage": 2, "no_data": 3}),
)

_IDS = [c.script for c in ZONE_CLIS]


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


@pytest.mark.parametrize("cli", ZONE_CLIS, ids=_IDS)
def test_help_flag_exits_zero_with_usage(cli: ZoneCli) -> None:
    proc = _run(cli.script, ["--help"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("usage:")
    assert cli.script in proc.stdout


@pytest.mark.parametrize("cli", ZONE_CLIS, ids=_IDS)
def test_help_documents_every_exit_code(cli: ZoneCli) -> None:
    proc = _run(cli.script, ["--help"])
    unwrapped = " ".join(proc.stdout.split())
    assert "exit codes:" in unwrapped
    for code in sorted(set(cli.exit_codes.values())):
        assert f"{code} " in unwrapped, f"{cli.script} --help does not document exit {code}"


@pytest.mark.parametrize("cli", ZONE_CLIS, ids=_IDS)
def test_exit_codes_are_mutually_distinct(cli: ZoneCli) -> None:
    codes = list(cli.exit_codes.values())
    assert len(set(codes)) == len(codes)


@pytest.mark.parametrize("cli", ZONE_CLIS, ids=_IDS)
def test_unknown_flag_is_a_usage_error(cli: ZoneCli) -> None:
    proc = _run(cli.script, ["--definitely-not-a-real-flag"])
    assert proc.returncode == cli.exit_codes["usage"]


@pytest.mark.parametrize("cli", ZONE_CLIS, ids=_IDS)
def test_help_is_never_treated_as_a_positional_path(cli: ZoneCli) -> None:
    proc = _run(cli.script, ["--help"])
    assert "not found" not in proc.stdout.lower()
    assert "no such file" not in proc.stderr.lower()


_NO_DATA_CLIS = [c for c in ZONE_CLIS if "no_data" in c.exit_codes]


def _no_data_args(script: str, tmp_path: Path) -> list[str]:
    if script == "check_secrets.py":
        return ["--events", str(tmp_path / "absent.jsonl"),
                "--experiments", str(tmp_path / "absent-dir")]
    if script == "check_quickstart.py":
        return ["--root", str(tmp_path), "--no-run"]
    if script == "wave_kpi.py":
        return [str(tmp_path / "absent.log")]
    if script == "alerting.py":
        return ["--events", str(tmp_path / "absent.jsonl"),
                "--memory-store", str(tmp_path / "absent-mem.jsonl")]
    if script == "trends.py":
        return ["--events", str(tmp_path / "absent.jsonl")]
    raise AssertionError(script)


@pytest.mark.parametrize("cli", _NO_DATA_CLIS, ids=[c.script for c in _NO_DATA_CLIS])
def test_absent_input_reports_no_data_and_never_success(cli: ZoneCli, tmp_path: Path) -> None:
    proc = _run(cli.script, _no_data_args(cli.script, tmp_path))
    assert proc.returncode == cli.exit_codes["no_data"], proc.stdout + proc.stderr
    assert proc.returncode != cli.exit_codes["ok"]


def test_doctor_json_contract() -> None:
    proc = _run("doctor.py", ["--json"])
    payload = json.loads(proc.stdout)
    assert "checks" in payload
    assert isinstance(payload["required_passed"], bool)
    assert proc.returncode == (0 if payload["required_passed"] else 1)
