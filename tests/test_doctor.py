from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import doctor


def test_pyyaml_is_a_required_dependency() -> None:
    assert any(d.module == "yaml" for d in doctor.REQUIRED_RUNTIME_DEPENDENCIES)


def test_dependency_probe_passes_when_importable() -> None:
    result = doctor.check_runtime_dependency(doctor.RuntimeDependency("PyYAML", "yaml"))
    assert result.passed
    assert result.required


def test_dependency_probe_fails_loudly_when_missing() -> None:
    result = doctor.check_runtime_dependency(
        doctor.RuntimeDependency("Nonexistent", "daslab_missing_dependency_probe")
    )
    assert not result.passed
    assert result.required
    assert result.status == "FAIL"
    assert "requirements.txt" in result.detail


def test_run_checks_includes_the_dependency_probe() -> None:
    names = [r.name for r in doctor.run_checks()]
    assert "Python dep: PyYAML" in names


def test_missing_pyyaml_makes_doctor_exit_nonzero(monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    real_import_module = doctor.importlib.import_module

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(doctor.importlib, "import_module", blocked)
    rc = doctor.main([])
    monkeypatch.undo()

    assert rc == doctor.EXIT_REQUIRED_FAILED
    captured = capsys.readouterr()
    assert "PyYAML" in captured.err
    assert "doctor: FAIL" in captured.err


def test_json_output_marks_required_failure(monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    real_import_module = doctor.importlib.import_module

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ImportError("No module named 'yaml'")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(doctor.importlib, "import_module", blocked)
    rc = doctor.main(["--json"])
    out = capsys.readouterr().out
    monkeypatch.undo()

    assert rc == doctor.EXIT_REQUIRED_FAILED
    payload = json.loads(out)
    assert payload["required_passed"] is False
    dep = next(c for c in payload["checks"] if c["name"] == "Python dep: PyYAML")
    assert dep["tier"] == "required"
    assert dep["passed"] is False


def test_repo_root_markers_do_not_reference_deleted_markdown() -> None:
    assert not any(marker.endswith(".md") for marker in doctor.REPO_ROOT_MARKERS)
    assert doctor.check_repo_root().passed


def test_healthy_environment_exit_code_is_zero() -> None:
    results = doctor.run_checks()
    if all(r.passed for r in results if r.required):
        assert doctor.main([]) == doctor.EXIT_OK
