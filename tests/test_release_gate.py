from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTICS = REPO_ROOT / "scripts" / "diagnostics.py"

RETIRED_MARKDOWN_ARTIFACTS = (
    "docs/README.md",
    "docs/adr",
    "CHANGELOG.md",
    "pull_request_template.md",
    "0004-project-agnostic-engine.md",
)

INTACT_DIMENSION_WEIGHTS = {
    "code_quality": 15,
    "consistency": 15,
    "portability": 15,
    "security": 10,
}

REPLACEMENT_DIMENSIONS = ("prose_freedom", "test_suite", "cli_contracts", "runtime_integrity")


@pytest.fixture
def gate() -> Iterator[object]:
    spec = importlib.util.spec_from_file_location("diagnostics_release_gate", DIAGNOSTICS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _named(checks: list, name: str):
    found = [c for c in checks if c.name == name]
    assert found, f"no check named {name!r} in {[c.name for c in checks]}"
    return found[0]


def test_weights_sum_to_exactly_100(gate) -> None:
    assert sum(w for _, _, w in gate.DIMENSIONS) == 100


def test_dimension_keys_are_unique_and_all_wired(gate) -> None:
    keys = [k for k, _, _ in gate.DIMENSIONS]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(gate.CHECK_FUNCS)


def test_intact_dimensions_keep_their_weight(gate) -> None:
    weights = {k: w for k, _, w in gate.DIMENSIONS}
    for key, weight in INTACT_DIMENSION_WEIGHTS.items():
        assert weights[key] == weight


def test_replacement_dimensions_carry_the_retired_weight(gate) -> None:
    weights = {k: w for k, _, w in gate.DIMENSIONS}
    assert set(REPLACEMENT_DIMENSIONS) <= set(weights)
    assert all(weights[k] > 0 for k in REPLACEMENT_DIMENSIONS)
    assert sum(weights[k] for k in REPLACEMENT_DIMENSIONS) == 25


def test_retired_markdown_artifacts_are_no_longer_scored() -> None:
    source = DIAGNOSTICS.read_text(encoding="utf-8")
    for artifact in RETIRED_MARKDOWN_ARTIFACTS:
        assert artifact not in source


def test_dimension_score_is_all_or_nothing(gate) -> None:
    passing = gate.DimensionResult(key="x", label="X", weight=9)
    passing.checks = [gate.CheckResult("a", True), gate.CheckResult("b", True)]
    assert passing.score == 9

    mixed = gate.DimensionResult(key="x", label="X", weight=9)
    mixed.checks = [gate.CheckResult("a", True), gate.CheckResult("b", False)]
    assert mixed.score == 0


def test_a_dimension_with_no_checks_never_scores(gate) -> None:
    empty = gate.DimensionResult(key="x", label="X", weight=9)
    assert empty.passed is False
    assert empty.score == 0


def test_score_dimension_replaces_an_empty_check_list_with_a_failure(gate) -> None:
    gate.CHECK_FUNCS["git_hygiene"] = lambda: []
    dim = gate.score_dimension("git_hygiene", "Git-hygiene", 5)
    assert dim.score == 0
    assert [c.name for c in dim.checks] == ["no-checks"]


def test_an_exploding_check_scores_zero_instead_of_crashing(gate) -> None:
    def boom() -> list:
        raise RuntimeError("check exploded")

    gate.CHECK_FUNCS["git_hygiene"] = boom
    dim = gate.score_dimension("git_hygiene", "Git-hygiene", 5)
    assert dim.score == 0
    assert dim.checks[0].name == "uncaught-error"


def test_failing_dimension_lowers_the_total_and_the_exit_code(
    gate, capsys: pytest.CaptureFixture[str]
) -> None:
    gate.CHECK_FUNCS["git_hygiene"] = lambda: [gate.CheckResult("seeded", True)]
    assert gate.main(["--check", "git_hygiene", "--json"]) == 0
    green = json.loads(capsys.readouterr().out)
    assert green["total"] == green["maximum"] == 5
    assert green["passed"] is True

    gate.CHECK_FUNCS["git_hygiene"] = lambda: [gate.CheckResult("seeded", False, "seeded defect")]
    assert gate.main(["--check", "git_hygiene", "--json"]) == 1
    red = json.loads(capsys.readouterr().out)
    assert red["total"] == 0
    assert red["maximum"] == 5
    assert red["passed"] is False
    assert red["total"] < green["total"]


def test_json_shape_is_stable(gate, capsys: pytest.CaptureFixture[str]) -> None:
    gate.main(["--check", "git_hygiene", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"selected", "total", "maximum", "passed", "dimensions"}
    assert payload["selected"] == "git_hygiene"
    for dim in payload["dimensions"]:
        assert set(dim) == {"key", "label", "weight", "score", "passed", "checks"}
        assert dim["checks"]
        for check in dim["checks"]:
            assert set(check) == {"name", "passed", "detail"}
            assert isinstance(check["passed"], bool)


def test_unknown_dimension_is_a_usage_error(gate) -> None:
    assert gate.main(["--check", "not-a-dimension"]) == 2


def test_help_exits_zero_with_a_usage_banner() -> None:
    proc = subprocess.run(
        [sys.executable, str(DIAGNOSTICS), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("usage:")
    assert "exit codes:" in " ".join(proc.stdout.split())


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_prose_dimension_is_green_on_the_real_tree(gate) -> None:
    checks = gate.check_prose_freedom()
    assert all(c.passed for c in checks), [c.detail for c in checks if not c.passed]


def test_prose_dimension_goes_red_on_a_single_comment(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "pkg" / "mod.py", "x = 1\n")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "PROSE_MIN_FILES", 1)
    monkeypatch.setattr(gate, "PROSE_COVERAGE_ANCHORS", ("pkg/mod.py",))
    assert all(c.passed for c in gate.check_prose_freedom())

    _write(tmp_path / "pkg" / "mod.py", "# a comment sneaks back in\nx = 1\n")
    checks = gate.check_prose_freedom()
    assert _named(checks, "no-prose-violations").passed is False


def test_prose_dimension_goes_red_when_the_scan_surface_collapses(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "PROSE_MIN_FILES", 1)
    checks = gate.check_prose_freedom()
    assert _named(checks, "prose-scan-surface").passed is False


def test_prose_dimension_goes_red_when_runtime_files_are_excluded(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "pkg" / "mod.py", "x = 1\n")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "PROSE_MIN_FILES", 1)
    checks = gate.check_prose_freedom()
    assert _named(checks, "prose-scan-covers-runtime").passed is False


def test_test_suite_structural_checks_are_green_on_the_real_tree(gate) -> None:
    structural = {"test-collection-clean", "test-count-floor", "no-gutted-test-modules"}
    checks = [c for c in gate.check_test_suite() if c.name in structural]
    assert len(checks) == len(structural)
    assert all(c.passed for c in checks), [c.detail for c in checks if not c.passed]


def _junit(tests: int, failures: int = 0, errors: int = 0) -> str:
    return (
        f'<testsuite name="pytest" tests="{tests}" '
        f'failures="{failures}" errors="{errors}"></testsuite>\n'
    )


def _suite_passes_check(gate, report: Path):
    original = gate.SUITE_REPORT
    gate.SUITE_REPORT = report
    try:
        return gate._suite_actually_passes()
    finally:
        gate.SUITE_REPORT = original


def test_suite_passes_is_red_when_no_report_exists(gate, tmp_path: Path) -> None:
    result = _suite_passes_check(gate, tmp_path / "absent.xml")
    assert result.passed is False
    assert "no test report" in result.detail


def test_suite_passes_is_red_when_the_recorded_run_failed(gate, tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(_junit(gate.TEST_COUNT_FLOOR + 10, failures=1), encoding="utf-8")
    result = _suite_passes_check(gate, report)
    assert result.passed is False
    assert "red" in result.detail


def test_suite_passes_is_red_when_the_report_covers_too_few_tests(gate, tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(_junit(10), encoding="utf-8")
    result = _suite_passes_check(gate, report)
    assert result.passed is False
    assert "floor" in result.detail


def test_suite_passes_is_red_on_an_unparseable_report(gate, tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text("not xml at all", encoding="utf-8")
    result = _suite_passes_check(gate, report)
    assert result.passed is False


def test_suite_passes_is_green_on_a_fresh_clean_report(gate, tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(_junit(gate.TEST_COUNT_FLOOR + 10), encoding="utf-8")
    os.utime(report, (time.time() + 60, time.time() + 60))
    result = _suite_passes_check(gate, report)
    assert result.passed is True, result.detail


def test_suite_passes_is_red_when_the_report_predates_the_sources(gate, tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(_junit(gate.TEST_COUNT_FLOOR + 10), encoding="utf-8")
    os.utime(report, (0, 0))
    result = _suite_passes_check(gate, report)
    assert result.passed is False
    assert "stale" in result.detail


def test_test_count_floor_catches_deleted_tests(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "test_one.py", "def test_one() -> None:\n    assert True\n")
    monkeypatch.setattr(gate, "TESTS_DIR", tmp_path)
    checks = gate.check_test_suite()
    assert _named(checks, "test-collection-clean").passed is True
    assert _named(checks, "test-count-floor").passed is False
    assert str(gate.TEST_COUNT_FLOOR) in _named(checks, "test-count-floor").detail


def test_gutted_test_module_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "test_one.py", "def test_one() -> None:\n    assert True\n")
    _write(tmp_path / "test_gutted.py", "PLACEHOLDER = 1\n")
    monkeypatch.setattr(gate, "TESTS_DIR", tmp_path)
    checks = gate.check_test_suite()
    assert _named(checks, "no-gutted-test-modules").passed is False
    assert "test_gutted.py" in _named(checks, "no-gutted-test-modules").detail


def test_collection_error_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "test_boom.py", "import definitely_not_a_module\n")
    monkeypatch.setattr(gate, "TESTS_DIR", tmp_path)
    checks = gate.check_test_suite()
    assert _named(checks, "test-collection-clean").passed is False


CONFORMING_CLI = (
    "import argparse\n"
    "import sys\n"
    "def main(argv=None):\n"
    "    p = argparse.ArgumentParser(prog='fake')\n"
    "    p.parse_args(argv)\n"
    "    return 0\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)

HELP_HOSTILE_CLI = (
    "import argparse\n"
    "import sys\n"
    "def main(argv=None):\n"
    "    print('doing real work instead of printing help')\n"
    "    return 1\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)

HEALTHY_ON_ABSENT_INPUT_CLI = (
    "import argparse\n"
    "def main(argv=None):\n"
    "    p = argparse.ArgumentParser(prog='fake')\n"
    "    p.add_argument('--events')\n"
    "    p.parse_args(argv)\n"
    "    return 0\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)

NEVER_HEALTHY_CLI = (
    "import argparse\n"
    "def main(argv=None):\n"
    "    p = argparse.ArgumentParser(prog='fake')\n"
    "    p.add_argument('root', nargs='?')\n"
    "    p.parse_args(argv)\n"
    "    return 3\n"
    "if __name__ == '__main__':\n"
    "    raise SystemExit(main())\n"
)


def test_cli_contracts_are_green_on_the_real_tree(gate) -> None:
    checks = gate.check_cli_contracts()
    assert all(c.passed for c in checks), [c.detail for c in checks if not c.passed]


def test_a_cli_that_ignores_help_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "good_cli.py", CONFORMING_CLI)
    _write(tmp_path / "rude_cli.py", HELP_HOSTILE_CLI)
    monkeypatch.setattr(gate, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(gate, "CLI_MIN_COUNT", 2)
    monkeypatch.setattr(gate, "NO_DATA_PROBES", ())
    monkeypatch.setattr(gate, "HEALTHY_PROBE_SCRIPT", "good_cli.py")
    checks = gate.check_cli_contracts()
    assert _named(checks, "cli-surface").passed is True
    assert _named(checks, "help-contract").passed is False
    assert "rude_cli.py" in _named(checks, "help-contract").detail


def test_a_collapsed_cli_surface_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "good_cli.py", CONFORMING_CLI)
    monkeypatch.setattr(gate, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(gate, "NO_DATA_PROBES", ())
    monkeypatch.setattr(gate, "HEALTHY_PROBE_SCRIPT", "good_cli.py")
    checks = gate.check_cli_contracts()
    assert _named(checks, "cli-surface").passed is False


def test_a_cli_that_calls_no_data_healthy_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "good_cli.py", CONFORMING_CLI)
    _write(tmp_path / "liar_cli.py", HEALTHY_ON_ABSENT_INPUT_CLI)
    monkeypatch.setattr(gate, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(gate, "CLI_MIN_COUNT", 1)
    monkeypatch.setattr(gate, "HEALTHY_PROBE_SCRIPT", "good_cli.py")
    monkeypatch.setattr(
        gate,
        "NO_DATA_PROBES",
        (gate.NoDataProbe("liar_cli.py", ("--events", "{tmp}/absent.jsonl")),),
    )
    checks = gate.check_cli_contracts()
    assert _named(checks, "no-data-never-reads-as-healthy").passed is False
    assert "liar_cli.py exit 0" in _named(checks, "no-data-never-reads-as-healthy").detail


def test_a_cli_that_can_never_report_healthy_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "never_healthy.py", NEVER_HEALTHY_CLI)
    monkeypatch.setattr(gate, "SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(gate, "CLI_MIN_COUNT", 1)
    monkeypatch.setattr(gate, "NO_DATA_PROBES", ())
    monkeypatch.setattr(gate, "HEALTHY_PROBE_SCRIPT", "never_healthy.py")
    checks = gate.check_cli_contracts()
    assert _named(checks, "healthy-distinct-from-no-data").passed is False


def _org_yaml(tmp_path: Path, mutate) -> Path:
    import yaml

    data = yaml.safe_load((REPO_ROOT / "config" / "org.yaml").read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "org.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_runtime_integrity_is_green_on_the_real_tree(gate) -> None:
    checks = gate.check_runtime_integrity()
    assert all(c.passed for c in checks), [c.detail for c in checks if not c.passed]


def test_a_missing_org_model_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "ORG_PATH", tmp_path / "absent.yaml")
    checks = gate.check_runtime_integrity()
    assert _named(checks, "org-model-loads").passed is False
    assert _named(checks, "entrypoint-reads-org-model").passed is False


def test_a_dropped_role_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def drop_a_role(data: dict) -> None:
        data["roles"] = [r for r in data["roles"] if r["key"] != "tech-writer"]

    monkeypatch.setattr(gate, "ORG_PATH", _org_yaml(tmp_path, drop_a_role))
    checks = gate.check_runtime_integrity()
    assert _named(checks, "org-model-loads").passed is True
    assert _named(checks, "roles-resolve").passed is False
    assert _named(checks, "model-allocation").passed is False


def test_model_allocation_drift_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def upgrade_a_haiku_role(data: dict) -> None:
        for role in data["roles"]:
            if role["key"] == "tech-writer":
                role["model"] = "opus"

    monkeypatch.setattr(gate, "ORG_PATH", _org_yaml(tmp_path, upgrade_a_haiku_role))
    checks = gate.check_runtime_integrity()
    assert _named(checks, "roles-resolve").passed is True
    assert _named(checks, "model-allocation").passed is False
    assert "haiku" in _named(checks, "model-allocation").detail


def test_a_role_without_an_allocation_breaks_the_dry_run_plan(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def drop_the_dispatched_role(data: dict) -> None:
        data["roles"] = [r for r in data["roles"] if r["key"] != "cto"]

    monkeypatch.setattr(gate, "ORG_PATH", _org_yaml(tmp_path, drop_the_dispatched_role))
    checks = gate.check_runtime_integrity()
    assert _named(checks, "orchestrator-dry-run-plans").passed is False
    assert _named(checks, "orchestrator-dry-run-is-inert").passed is True


def test_dispatch_mode_writes_the_journal_that_dry_run_leaves_untouched(
    gate, tmp_path: Path
) -> None:
    proc, journal, _ = gate._orchestrator_dry_run(tmp_path)
    assert proc.returncode == 0
    assert journal.exists() is False

    invoker_dir = tmp_path / "invoker"
    invoker_dir.mkdir()
    _write(
        invoker_dir / "probe_invoker.py",
        "def invoke(request):\n    return 'ok'\n",
    )
    env = dict(os.environ, PYTHONPATH=str(invoker_dir))
    dispatched = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "orchestrator.py"),
            "--dispatch",
            "--json",
            "--board",
            str(tmp_path / "board"),
            "--org",
            str(REPO_ROOT / "config" / "org.yaml"),
            "--journal",
            str(journal),
            "--run-id",
            "release-gate-probe",
            "--invoker",
            "probe_invoker:invoke",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert dispatched.returncode == 0, dispatched.stderr
    assert journal.exists() is True


def test_orchestrator_has_a_non_test_caller(gate) -> None:
    refs = gate.non_test_references("orchestrator")
    assert ".github/workflows/ci.yml" in refs


def test_the_scorer_does_not_count_itself_as_a_caller(gate) -> None:
    for module in gate.RUNTIME_MODULES:
        assert "scripts/diagnostics.py" not in gate.non_test_references(module)


def test_shelfware_runtime_module_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "scripts" / "orchestrator.py", "VALUE = 1\n")
    _write(tmp_path / "scripts" / "unrelated.py", "OTHER = 2\n")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert gate.non_test_references("orchestrator") == []
    checks = gate.check_architecture()
    assert _named(checks, "no-shelfware-runtime").passed is False


def test_a_module_referenced_only_by_tests_still_counts_as_shelfware(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "scripts" / "orchestrator.py", "VALUE = 1\n")
    _write(tmp_path / "tests" / "test_orchestrator.py", "import orchestrator\n")
    _write(tmp_path / "scripts" / "test_helper.py", "import orchestrator\n")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert gate.non_test_references("orchestrator") == []


def test_a_string_mention_is_not_a_caller(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "scripts" / "orchestrator.py", "VALUE = 1\n")
    _write(
        tmp_path / "scripts" / "mentions.py",
        "PATHS = ['scripts/orchestrator.py']\nNEEDLE = 'import orchestrator'\n",
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert gate.non_test_references("orchestrator") == []

    _write(tmp_path / "scripts" / "caller.py", "import orchestrator\n")
    assert gate.non_test_references("orchestrator") == ["scripts/caller.py"]


def test_a_workflow_invocation_counts_as_a_caller(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "scripts" / "orchestrator.py", "VALUE = 1\n")
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  validate:\n    steps:\n      - run: python3 scripts/orchestrator.py --dry-run\n",
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert gate.non_test_references("orchestrator") == [".github/workflows/ci.yml"]


def test_bare_except_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _write(tmp_path / "clean.py", "x = 1\n")
    assert gate.debt_constructs() == []

    _write(tmp_path / "debt.py", "try:\n    x = 1\nexcept:\n    x = 2\n")
    offenders = gate.debt_constructs()
    assert any("bare except" in o for o in offenders)


def test_not_implemented_error_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _write(tmp_path / "stub.py", "def f():\n    raise NotImplementedError('later')\n")
    offenders = gate.debt_constructs()
    assert any("NotImplementedError" in o for o in offenders)


def test_debt_constructs_fail_the_code_quality_dimension(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "debt.py", "try:\n    x = 1\nexcept:\n    x = 2\n")
    monkeypatch.setattr(gate, "first_party_sources", lambda: [tmp_path / "debt.py"])
    checks = gate.check_code_quality()
    assert _named(checks, "no-debt-constructs").passed is False


def test_ci_wires_every_gate_the_scorer_depends_on(gate) -> None:
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for step in gate.CI_REQUIRED_STEPS:
        assert step in ci_text, step


def test_ci_without_the_orchestrator_step_is_caught(
    gate, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    body = "\n".join(
        f"      - run: {step}" for step in gate.CI_REQUIRED_STEPS if "orchestrator" not in step
    )
    _write(workflow, "name: CI\njobs:\n  validate:\n    steps:\n" + body + "\n")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    checks = gate.check_git_hygiene()
    assert _named(checks, "ci-runs-the-gates").passed is False
    assert "orchestrator" in _named(checks, "ci-runs-the-gates").detail


def test_git_hygiene_is_green_on_the_real_tree(gate) -> None:
    checks = gate.check_git_hygiene()
    assert all(c.passed for c in checks), [c.detail for c in checks if not c.passed]
