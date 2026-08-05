#!/usr/bin/env python3


from __future__ import annotations

import argparse
import ast
import functools
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TICKETS_DIR: Path = REPO_ROOT / "board" / "tickets"
TESTS_DIR: Path = REPO_ROOT / "tests"
SCRIPTS_DIR: Path = REPO_ROOT / "scripts"
ORG_PATH: Path = REPO_ROOT / "config" / "org.yaml"
CI_WORKFLOW: Path = REPO_ROOT / ".github" / "workflows" / "ci.yml"


DIMENSIONS: list[tuple[str, str, int]] = [
    ("architecture", "Architecture", 15),
    ("code_quality", "Code-quality", 15),
    ("consistency", "Consistency", 15),
    ("portability", "Portability", 15),
    ("security", "Security", 10),
    ("prose_freedom", "Prose-freedom", 7),
    ("test_suite", "Test-suite", 7),
    ("cli_contracts", "CLI-contracts", 6),
    ("runtime_integrity", "Runtime-integrity", 5),
    ("git_hygiene", "Git-hygiene", 5),
]


_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import board_lint as _board_lint
except Exception:
    _board_lint = None


VALID_STATUS: frozenset[str] = (
    frozenset(_board_lint.VALID_STATUSES) if _board_lint is not None else frozenset()
)


PROSE_MIN_FILES: int = 400
PROSE_COVERAGE_ANCHORS: tuple[str, ...] = (
    "scripts/diagnostics.py",
    "scripts/orchestrator.py",
    "scripts/wave_planner.py",
    "tests/test_diagnostics.py",
    "daslab_sdk/__init__.py",
)

TEST_COUNT_FLOOR: int = 3500

CLI_MIN_COUNT: int = 85
NO_DATA_EXIT: int = 3

EXPECTED_ROLE_COUNT: int = 32
EXPECTED_MODEL_ALLOCATION: dict[str, int] = {"opus": 10, "sonnet": 19, "haiku": 3}

RUNTIME_MODULES: tuple[str, ...] = ("orchestrator", "wave_planner")
REFERENCE_SEARCH_DIRS: tuple[str, ...] = (
    "scripts",
    "tools",
    "daslab_sdk",
    ".github/workflows",
)
REFERENCE_SEARCH_SUFFIXES: frozenset[str] = frozenset({".py", ".yml", ".yaml"})

CI_REQUIRED_STEPS: tuple[str, ...] = (
    "scripts/diagnostics.py",
    "scripts/check_no_prose.py",
    "scripts/orchestrator.py --dry-run",
    "ruff check",
    "pytest",
)


@dataclass(frozen=True)
class NoDataProbe:

    script: str
    args: tuple[str, ...]


NO_DATA_PROBES: tuple[NoDataProbe, ...] = (
    NoDataProbe("check_secrets.py", ("--events", "{tmp}/absent.jsonl", "--experiments", "{tmp}/absent-dir")),
    NoDataProbe("check_quickstart.py", ("--root", "{tmp}/empty", "--no-run")),
    NoDataProbe("wave_kpi.py", ("{tmp}/absent.log",)),
    NoDataProbe("alerting.py", ("--events", "{tmp}/absent.jsonl", "--memory-store", "{tmp}/absent-mem.jsonl")),
    NoDataProbe("trends.py", ("--events", "{tmp}/absent.jsonl")),
    NoDataProbe("check_no_prose.py", ("{tmp}/empty",)),
)

HEALTHY_PROBE_SCRIPT: str = "check_no_prose.py"


@dataclass
class CheckResult:

    name: str
    passed: bool
    detail: str = ""


@dataclass
class DimensionResult:

    key: str
    label: str
    weight: int
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def score(self) -> int:
        return self.weight if self.passed else 0

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "score": self.score,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


def _git(*args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode, proc.stdout
    except Exception as exc:
        return 1, f"git invocation failed: {exc}"


@functools.lru_cache(maxsize=1)
def _tracked_files() -> tuple[str, ...]:
    code, out = _git("ls-files")
    if code != 0:
        return ()
    return tuple(line for line in out.splitlines() if line)


def _tracked_symlinks() -> list[str]:
    code, out = _git("ls-files", "-s")
    if code != 0:
        return []
    links: list[str] = []
    for line in out.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) == 4 and parts[0] == "120000":
            links.append(parts[3])
    return links


def _read_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def _run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / name), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def first_party_sources() -> list[Path]:
    import check_no_prose as _prose

    return _prose.source_files(REPO_ROOT)


def _relative_source_names() -> set[str]:
    return {_rel(path) for path in first_party_sources()}


_SCANNED_RE = re.compile(r"scanned (\d+) \.py files")
_VIOLATIONS_RE = re.compile(r"violations: (\d+)")
_COLLECTED_RE = re.compile(r"(\d+) tests? collected")


def check_prose_freedom() -> list[CheckResult]:
    results: list[CheckResult] = []

    proc = _run_script(
        "check_no_prose.py", str(REPO_ROOT), "--min-files", str(PROSE_MIN_FILES)
    )
    scanned_match = _SCANNED_RE.search(proc.stdout)
    violations_match = _VIOLATIONS_RE.search(proc.stdout)
    scanned = int(scanned_match.group(1)) if scanned_match else -1
    violations = int(violations_match.group(1)) if violations_match else -1

    clean = proc.returncode == 0 and violations == 0
    results.append(
        CheckResult(
            "no-prose-violations",
            clean,
            f"check_no_prose: {violations} violation(s) over {scanned} .py files"
            if violations >= 0
            else f"check_no_prose exit {proc.returncode}: {proc.stderr.strip()[:120]}",
        )
    )

    surface_ok = proc.returncode != NO_DATA_EXIT and scanned >= PROSE_MIN_FILES
    results.append(
        CheckResult(
            "prose-scan-surface",
            surface_ok,
            f"scan surface {scanned} .py files (floor {PROSE_MIN_FILES})"
            if surface_ok
            else f"scan surface collapsed to {scanned} .py files (floor {PROSE_MIN_FILES})",
        )
    )

    try:
        names = _relative_source_names()
    except Exception as exc:
        names = set()
        results.append(
            CheckResult(
                "prose-scan-covers-runtime",
                False,
                f"cannot enumerate the scan surface: {type(exc).__name__}: {exc}",
            )
        )
    else:
        uncovered = [a for a in PROSE_COVERAGE_ANCHORS if a not in names]
        results.append(
            CheckResult(
                "prose-scan-covers-runtime",
                not uncovered,
                "prose scan covers scripts/, tests/ and the SDK"
                if not uncovered
                else f"scan surface excludes: {uncovered}",
            )
        )
    return results


def _test_modules() -> list[Path]:
    if not TESTS_DIR.is_dir():
        return []
    return sorted(TESTS_DIR.rglob("test_*.py"))


def _module_defines_a_test(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test"):
            return True
    return False


def check_test_suite() -> list[CheckResult]:
    results: list[CheckResult] = []

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            str(TESTS_DIR),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    match = _COLLECTED_RE.search(proc.stdout)
    collected = int(match.group(1)) if match else -1

    collection_ok = proc.returncode == 0 and collected >= 0
    results.append(
        CheckResult(
            "test-collection-clean",
            collection_ok,
            f"{collected} tests collected, 0 collection errors"
            if collection_ok
            else f"pytest collection exit {proc.returncode}: "
            f"{(proc.stdout + proc.stderr).strip().splitlines()[-1][:140] if (proc.stdout + proc.stderr).strip() else 'no output'}",
        )
    )

    floor_ok = collected >= TEST_COUNT_FLOOR
    results.append(
        CheckResult(
            "test-count-floor",
            floor_ok,
            f"{collected} tests >= floor {TEST_COUNT_FLOOR}"
            if floor_ok
            else f"test count collapsed to {collected}, floor is {TEST_COUNT_FLOOR}",
        )
    )

    modules = _test_modules()
    empty = [_rel(m) for m in modules if not _module_defines_a_test(m)]
    results.append(
        CheckResult(
            "no-gutted-test-modules",
            bool(modules) and not empty,
            f"all {len(modules)} test modules define at least one test"
            if (modules and not empty)
            else (f"test modules with no test: {empty[:5]}" if modules else "no test modules found"),
        )
    )
    results.append(_suite_actually_passes())
    return results


SUITE_REPORT: Path = REPO_ROOT / "board" / ".pytest-report.xml"
SUITE_REPORT_HINT = (
    "run: python -m pytest --junitxml=board/.pytest-report.xml   (CI does this before the gate)"
)


def _newest_source_mtime() -> float:
    newest = 0.0
    for rel in _tracked_files():
        if not rel.endswith(".py"):
            continue
        path = REPO_ROOT / rel
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest


def _suite_actually_passes() -> CheckResult:
    if not SUITE_REPORT.is_file():
        return CheckResult(
            "suite-passes",
            False,
            f"no test report at {_rel(SUITE_REPORT)}; {SUITE_REPORT_HINT}",
        )
    try:
        root = ElementTree.parse(SUITE_REPORT).getroot()
    except ElementTree.ParseError as exc:
        return CheckResult("suite-passes", False, f"unparseable test report: {exc}")

    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        return CheckResult("suite-passes", False, "test report contains no testsuite element")

    def total(attr: str) -> int:
        return sum(int(s.get(attr, "0") or 0) for s in suites)

    tests, failures, errors = total("tests"), total("failures"), total("errors")
    red = failures + errors

    report_mtime = SUITE_REPORT.stat().st_mtime
    newest_source = _newest_source_mtime()
    if report_mtime < newest_source:
        return CheckResult(
            "suite-passes",
            False,
            f"test report is stale: source changed after the run; {SUITE_REPORT_HINT}",
        )
    if tests < TEST_COUNT_FLOOR:
        return CheckResult(
            "suite-passes",
            False,
            f"test report covers only {tests} tests, floor is {TEST_COUNT_FLOOR}",
        )
    return CheckResult(
        "suite-passes",
        red == 0,
        f"{tests} tests green in the recorded run"
        if red == 0
        else f"recorded run is red: {failures} failed, {errors} errored",
    )


def argparse_clis() -> list[Path]:
    clis: list[Path] = []
    if not SCRIPTS_DIR.is_dir():
        return clis
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "__main__" not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == "argparse" for a in node.names):
                clis.append(path)
                break
            if isinstance(node, ast.ImportFrom) and node.module == "argparse":
                clis.append(path)
                break
    return clis


def _probe_help(path: Path) -> tuple[str, bool, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(path), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
    except subprocess.SubprocessError as exc:
        return path.name, False, f"{type(exc).__name__}"
    if proc.returncode != 0:
        return path.name, False, f"exit {proc.returncode}"
    if not proc.stdout.startswith("usage:"):
        return path.name, False, "no usage: banner on stdout"
    return path.name, True, ""


def check_cli_contracts() -> list[CheckResult]:
    from concurrent.futures import ThreadPoolExecutor

    results: list[CheckResult] = []

    clis = argparse_clis()
    surface_ok = len(clis) >= CLI_MIN_COUNT
    results.append(
        CheckResult(
            "cli-surface",
            surface_ok,
            f"{len(clis)} argparse CLIs in scripts/ (floor {CLI_MIN_COUNT})"
            if surface_ok
            else f"CLI surface collapsed to {len(clis)} (floor {CLI_MIN_COUNT})",
        )
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        probes = list(pool.map(_probe_help, clis))
    broken = [f"{name} ({why})" for name, ok, why in probes if not ok]
    results.append(
        CheckResult(
            "help-contract",
            bool(clis) and not broken,
            f"all {len(clis)} CLIs answer --help with exit 0 and a usage: banner"
            if (clis and not broken)
            else (f"non-conforming --help: {broken[:5]}" if clis else "no CLI found to probe"),
        )
    )

    with tempfile.TemporaryDirectory(prefix="daslab-nodata-") as tmp:
        (Path(tmp) / "empty").mkdir()
        wrong: list[str] = []
        for probe in NO_DATA_PROBES:
            args = [a.replace("{tmp}", tmp) for a in probe.args]
            outcome = _run_script(probe.script, *args)
            if outcome.returncode != NO_DATA_EXIT:
                wrong.append(f"{probe.script} exit {outcome.returncode}")
        healthy = _run_script(HEALTHY_PROBE_SCRIPT, str(REPO_ROOT))

    results.append(
        CheckResult(
            "no-data-never-reads-as-healthy",
            not wrong,
            f"all {len(NO_DATA_PROBES)} no-data probes exit {NO_DATA_EXIT}, never 0"
            if not wrong
            else f"no-data conflated with another state: {wrong[:5]}",
        )
    )
    results.append(
        CheckResult(
            "healthy-distinct-from-no-data",
            healthy.returncode == 0 and healthy.returncode != NO_DATA_EXIT,
            f"{HEALTHY_PROBE_SCRIPT} exits 0 on real data and {NO_DATA_EXIT} on none"
            if healthy.returncode == 0
            else f"{HEALTHY_PROBE_SCRIPT} exits {healthy.returncode} on real data",
        )
    )
    return results


def _org_model():
    import wave_planner as _wp

    return _wp.load_org_model(ORG_PATH)


SYNTHETIC_BOARD: dict[str, str] = {
    "DAS-9001-dispatchable.md": (
        "---\nid: DAS-9001\nstatus: todo\nassignee: cto\nzone: alpha\nauthor: ceo\n---\n\nplan me\n"
    ),
    "DAS-9002-zone-clash.md": (
        "---\nid: DAS-9002\nstatus: todo\nassignee: qa-lead\nzone: alpha\nauthor: ceo\n---\n\nsame zone\n"
    ),
    "DAS-9003-unknown-role.md": (
        "---\nid: DAS-9003\nstatus: todo\nassignee: not-a-real-role\nzone: gamma\nauthor: ceo\n---\n\nno model\n"
    ),
    "DAS-9004-done.md": (
        "---\nid: DAS-9004\nstatus: done\nassignee: cto\nzone: delta\nauthor: ceo\n---\n\nalready shipped\n"
    ),
}

EXPECTED_REFUSALS: dict[str, str] = {
    "DAS-9002": "zone_conflict",
    "DAS-9003": "no_model_for_role",
    "DAS-9004": "not_actionable",
}


def _orchestrator_dry_run(tmp: Path) -> tuple[subprocess.CompletedProcess[str], Path, dict[str, str]]:
    board = tmp / "board"
    board.mkdir(parents=True, exist_ok=True)
    for name, body in SYNTHETIC_BOARD.items():
        (board / name).write_text(body, encoding="utf-8")
    before = {p.name: p.read_text(encoding="utf-8") for p in sorted(board.iterdir())}
    journal = tmp / "must-not-exist.jsonl"
    proc = _run_script(
        "orchestrator.py",
        "--dry-run",
        "--json",
        "--board",
        str(board),
        "--org",
        str(ORG_PATH),
        "--journal",
        str(journal),
        "--goal",
        "release-gate probe",
    )
    return proc, journal, before


def check_runtime_integrity() -> list[CheckResult]:
    results: list[CheckResult] = []

    try:
        org = _org_model()
    except Exception as exc:
        results.append(
            CheckResult("org-model-loads", False, f"{type(exc).__name__}: {exc}")
        )
        org = None
    else:
        results.append(
            CheckResult(
                "org-model-loads",
                True,
                f"{ORG_PATH.name} parsed by wave_planner.load_org_model",
            )
        )

    if org is not None:
        unresolved: list[str] = []
        for role in sorted(org.role_models):
            try:
                org.model_for(role)
            except Exception:
                unresolved.append(role)
        roles_ok = len(org.role_models) == EXPECTED_ROLE_COUNT and not unresolved
        results.append(
            CheckResult(
                "roles-resolve",
                roles_ok,
                f"all {EXPECTED_ROLE_COUNT} roles resolve to a model"
                if roles_ok
                else f"{len(org.role_models)} roles (expected {EXPECTED_ROLE_COUNT}); unresolved: {unresolved[:5]}",
            )
        )

        tally: dict[str, int] = {}
        for model in org.role_models.values():
            tally[model] = tally.get(model, 0) + 1
        allocation_ok = tally == EXPECTED_MODEL_ALLOCATION
        results.append(
            CheckResult(
                "model-allocation",
                allocation_ok,
                f"allocation holds: {EXPECTED_MODEL_ALLOCATION}"
                if allocation_ok
                else f"allocation drifted to {tally}, expected {EXPECTED_MODEL_ALLOCATION}",
            )
        )

    try:
        import orchestrator as _orch

        wired = Path(_orch.DEFAULT_ORG_PATH).resolve() == ORG_PATH.resolve()
        detail = (
            f"orchestrator reads {ORG_PATH.name}"
            if wired
            else f"orchestrator reads {_orch.DEFAULT_ORG_PATH}, not {ORG_PATH}"
        )
    except Exception as exc:
        wired, detail = False, f"cannot import orchestrator: {type(exc).__name__}: {exc}"
    results.append(CheckResult("entrypoint-reads-org-model", wired, detail))

    with tempfile.TemporaryDirectory(prefix="daslab-dryrun-") as raw_tmp:
        tmp = Path(raw_tmp)
        proc, journal, before = _orchestrator_dry_run(tmp)
        board = tmp / "board"
        after = {p.name: p.read_text(encoding="utf-8") for p in sorted(board.iterdir())}
        journal_created = journal.exists()

    plan: dict[str, object] = {}
    parse_error = ""
    if proc.returncode == 0:
        try:
            plan = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)

    dispatch = plan.get("dispatch") if isinstance(plan.get("dispatch"), list) else []
    refused = plan.get("refused") if isinstance(plan.get("refused"), list) else []
    dispatched = {
        str(d.get("ticket_id")): (str(d.get("role")), str(d.get("model")))
        for d in dispatch
        if isinstance(d, dict)
    }
    refusals = {
        str(r.get("ticket_id")): str(r.get("reason")) for r in refused if isinstance(r, dict)
    }

    plan_ok = (
        proc.returncode == 0
        and not parse_error
        and dispatched == {"DAS-9001": ("cto", "opus")}
        and refusals == EXPECTED_REFUSALS
    )
    results.append(
        CheckResult(
            "orchestrator-dry-run-plans",
            plan_ok,
            "orchestrator --dry-run plans a seeded board (1 dispatch, 3 typed refusals)"
            if plan_ok
            else f"exit {proc.returncode}; dispatch={dispatched}; refusals={refusals}; "
            f"{parse_error or proc.stderr.strip()[:120]}",
        )
    )

    inert = not journal_created and before == after
    results.append(
        CheckResult(
            "orchestrator-dry-run-is-inert",
            inert,
            "--dry-run wrote no journal and mutated no ticket"
            if inert
            else f"side effects: journal_created={journal_created}, board_mutated={before != after}",
        )
    )
    return results


def _first_party_reference_files() -> list[Path]:
    files: list[Path] = []
    for rel_dir in REFERENCE_SEARCH_DIRS:
        base = REPO_ROOT / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in REFERENCE_SEARCH_SUFFIXES or not path.is_file():
                continue
            parts = path.relative_to(REPO_ROOT).parts
            if {".vendor", "__pycache__", "tests", ".venv"} & set(parts):
                continue
            if path.name.startswith("test_"):
                continue
            files.append(path)
    return files


def imported_modules(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


SELF_REFERENCE_EXEMPT: frozenset[str] = frozenset({"diagnostics"})


def non_test_references(module_name: str) -> list[str]:
    invocation = f"scripts/{module_name}.py"
    hits: list[str] = []
    for path in _first_party_reference_files():
        if path.stem == module_name or path.stem in SELF_REFERENCE_EXEMPT:
            continue
        if path.suffix == ".py":
            if module_name in imported_modules(path):
                hits.append(_rel(path))
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if invocation in text:
            hits.append(_rel(path))
    return hits


def check_architecture() -> list[CheckResult]:
    results: list[CheckResult] = []

    symlinks = _tracked_symlinks()
    results.append(
        CheckResult(
            "no-tracked-symlinks",
            not symlinks,
            "no tracked symlinks (self-contained)"
            if not symlinks
            else f"{len(symlinks)} tracked symlink(s) not yet materialized",
        )
    )

    shelfware: list[str] = []
    wired: list[str] = []
    for module_name in RUNTIME_MODULES:
        refs = non_test_references(module_name)
        if refs:
            wired.append(f"{module_name}<-{len(refs)}")
        else:
            shelfware.append(module_name)
    results.append(
        CheckResult(
            "no-shelfware-runtime",
            bool(RUNTIME_MODULES) and not shelfware,
            f"every runtime module has a non-test caller ({', '.join(wired)})"
            if not shelfware
            else f"shelfware — only tests reference: {shelfware}",
        )
    )

    iso = _run_script("check_project_isolation.py")
    results.append(
        CheckResult(
            "project-agnostic",
            iso.returncode == 0,
            "engine free of project-specific names"
            if iso.returncode == 0
            else "a project name leaked into the engine",
        )
    )

    dead = _run_script("check_no_dead_runtime.py")
    results.append(
        CheckResult(
            "no-dead-runtime",
            dead.returncode == 0,
            "no dead legacy-runtime endpoint in the active engine"
            if dead.returncode == 0
            else "dead runtime endpoint present",
        )
    )

    attest = _run_script("check_attestation.py")
    results.append(
        CheckResult(
            "attestation-integrity",
            attest.returncode == 0,
            "committed wave attestations complete + hash-chain intact"
            if attest.returncode == 0
            else "a committed attestation is incomplete or tampered",
        )
    )

    reconcile = _run_script("check_wave_reconciliation.py")
    results.append(
        CheckResult(
            "wave-reconciliation",
            reconcile.returncode == 0,
            "committed ledger reconciles with attestations (bijection/chain/terminal/coverage)"
            if reconcile.returncode == 0
            else "the committed dispatch record does not reconcile",
        )
    )
    return results


def debt_constructs() -> list[str]:
    offenders: list[str] = []
    for path in first_party_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        rel = _rel(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(f"{rel}:{node.lineno} bare except")
            if isinstance(node, ast.Raise):
                target = node.exc
                if isinstance(target, ast.Call):
                    target = target.func
                if isinstance(target, ast.Name) and target.id == "NotImplementedError":
                    offenders.append(f"{rel}:{node.lineno} NotImplementedError")
    return offenders


def check_code_quality() -> list[CheckResult]:
    results: list[CheckResult] = []

    scripts_dir = REPO_ROOT / "scripts"
    required_scripts = [
        "board_lint.py",
        "check_import_ban.py",
        "check_no_prose.py",
        "check_agents_sync.py",
        "check_comm_flows.py",
        "check_gates.py",
        "orchestrator.py",
        "wave_planner.py",
        "diagnostics.py",
    ]
    missing_scripts = [s for s in required_scripts if not (scripts_dir / s).is_file()]
    results.append(
        CheckResult(
            "validator-suite-present",
            not missing_scripts,
            "all validators present" if not missing_scripts else f"missing: {missing_scripts}",
        )
    )

    tests_dir = REPO_ROOT / "tests"
    required_tests = [
        "test_board_lint.py",
        "test_check_import_ban.py",
        "test_check_no_prose.py",
        "test_check_agents_sync.py",
        "test_check_comm_flows.py",
        "test_check_gates.py",
        "test_orchestrator.py",
        "test_wave_planner.py",
        "test_diagnostics.py",
        "test_release_gate.py",
    ]
    missing_tests = [t for t in required_tests if not (tests_dir / t).is_file()]
    results.append(
        CheckResult(
            "validator-tests-present",
            tests_dir.is_dir() and not missing_tests,
            "all validator tests present"
            if (tests_dir.is_dir() and not missing_tests)
            else f"missing tests: {missing_tests}",
        )
    )

    try:
        ruff = subprocess.run(
            ["ruff", "check", str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        if ruff.returncode == 0:
            ruff_ok, ruff_detail = True, "ruff: whole tree lint-clean"
        else:
            ruff_ok, ruff_detail = False, "ruff reported lint findings (run `ruff check .`)"
    except FileNotFoundError:
        ruff_ok, ruff_detail = False, "ruff unavailable — lint gate cannot run; install ruff (fail-closed)"
    results.append(CheckResult("ruff-clean", ruff_ok, ruff_detail))

    try:
        offenders = debt_constructs()
    except Exception as exc:
        results.append(
            CheckResult("no-debt-constructs", False, f"{type(exc).__name__}: {exc}")
        )
    else:
        results.append(
            CheckResult(
                "no-debt-constructs",
                not offenders,
                "no bare except / NotImplementedError in first-party source"
                if not offenders
                else f"{len(offenders)} debt construct(s): {offenders[:5]}",
            )
        )

    overlay = _run_script("check_overlay_sections.py", "--strict")
    results.append(
        CheckResult(
            "overlay-contract",
            overlay.returncode == 0,
            "all role overlays carry Mission/Scope/DoD/Escalation"
            if overlay.returncode == 0
            else "a role overlay is missing a contract section",
        )
    )
    return results


def check_consistency() -> list[CheckResult]:
    results: list[CheckResult] = []

    if not TICKETS_DIR.is_dir():
        results.append(CheckResult("tickets-dir", False, f"missing {TICKETS_DIR}"))
        return results

    ticket_files = sorted(TICKETS_DIR.glob("DAS-*.md"))
    if not ticket_files:
        results.append(
            CheckResult("board-valid", True, "live board empty (platform-only); nothing to lint")
        )
        return results

    results.append(
        CheckResult(
            "status-enum-ssot-importable",
            _board_lint is not None,
            "board_lint.VALID_STATUSES imported (single source of truth)"
            if _board_lint is not None
            else "could not import scripts/board_lint.py — status enum "
            "fails closed (empty set) until this is fixed",
        )
    )

    bad_status: list[str] = []
    missing_fields: list[str] = []
    self_review: list[str] = []

    for path in ticket_files:
        try:
            fm = _read_frontmatter(path.read_text(encoding="utf-8"))
        except Exception as exc:
            missing_fields.append(f"{path.name} (unreadable: {exc})")
            continue
        if not {"id", "status", "author"} <= fm.keys():
            missing_fields.append(path.name)
            continue
        if fm.get("status") not in VALID_STATUS:
            bad_status.append(f"{path.name}={fm.get('status')!r}")
        if fm.get("status") == "in_review" and fm.get("assignee") == fm.get("author"):
            self_review.append(path.name)

    results.append(
        CheckResult(
            "frontmatter-fields",
            not missing_fields,
            "all tickets have id/status/author"
            if not missing_fields
            else f"{len(missing_fields)} malformed: {missing_fields[:5]}",
        )
    )
    results.append(
        CheckResult(
            "status-enum",
            not bad_status,
            f"all statuses valid ({len(ticket_files)} tickets)"
            if not bad_status
            else f"bad status: {bad_status[:5]}",
        )
    )
    results.append(
        CheckResult(
            "no-self-review",
            not self_review,
            "no in_review self-reviews"
            if not self_review
            else f"self-review: {self_review[:5]}",
        )
    )

    prec = _run_script("check_precedence.py")
    results.append(
        CheckResult(
            "precedence-enforced",
            prec.returncode == 0,
            "no lower-precedence doc relaxes a board rule"
            if prec.returncode == 0
            else "a charter/overlay relaxes a binding rule",
        )
    )

    clarify = _run_script("check_clarifications.py", "--strict")
    results.append(
        CheckResult(
            "clarify-gate",
            clarify.returncode == 0,
            "no unresolved [NEEDS CLARIFICATION] markers in active tickets"
            if clarify.returncode == 0
            else "an active ticket carries an unresolved clarify marker",
        )
    )

    queue = _run_script("check_approved_goal_queue.py")
    results.append(
        CheckResult(
            "approved-goal-queue",
            queue.returncode == 0,
            "all project goal-queues are Founder-approved"
            if queue.returncode == 0
            else "an unapproved goal-queue exists",
        )
    )

    spec = _run_script("check_spec_consistency.py")
    results.append(
        CheckResult(
            "spec-consistency",
            spec.returncode == 0,
            "SPEC structure + ticket refs consistent"
            if spec.returncode == 0
            else "a SPEC is malformed or a ticket ref is dangling",
        )
    )

    depgraph = _run_script("check_dependency_graph.py")
    results.append(
        CheckResult(
            "dependency-graph",
            depgraph.returncode == 0,
            "ticket depends_on graph acyclic, no dangling refs"
            if depgraph.returncode == 0
            else "a dependency cycle / dangling dep / empty zone exists",
        )
    )
    return results


def check_portability() -> list[CheckResult]:
    results: list[CheckResult] = []

    needle = "/Users/" + "owner"
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel.startswith("board/"):
            continue
        path = REPO_ROOT / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if needle in text:
            offenders.append(rel)

    results.append(
        CheckResult(
            "no-hardcoded-home",
            not offenders,
            f"no {needle} in tracked files (excl board/tickets)"
            if not offenders
            else f"{len(offenders)} file(s) still reference {needle}",
        )
    )

    nohp = _run_script("check_no_hardcoded_paths.py")
    results.append(
        CheckResult(
            "no-hardcoded-paths",
            nohp.returncode == 0,
            "no machine-specific home paths (self-locating root)"
            if nohp.returncode == 0
            else "hardcoded home path(s) present",
        )
    )

    mcp = REPO_ROOT / ".mcp.json"
    if mcp.is_file():
        try:
            mcp_text = mcp.read_text(encoding="utf-8", errors="ignore")
            portable = needle not in mcp_text
        except Exception:
            portable = False
        results.append(
            CheckResult(
                "mcp-portable",
                portable,
                ".mcp.json portable" if portable else ".mcp.json has absolute paths",
            )
        )
    else:
        results.append(CheckResult("mcp-portable", False, ".mcp.json missing"))
    return results


def check_security() -> list[CheckResult]:
    results: list[CheckResult] = []

    nested_git: list[str] = []
    for rel in (
        "engineering",
        "product",
        "design",
        "marketing",
        "operations",
        "governance",
    ):
        dept = REPO_ROOT / rel
        if (dept / ".git").exists():
            nested_git.append(f"{rel}/.git")
    results.append(
        CheckResult(
            "no-nested-git",
            not nested_git,
            "no nested dept .git histories"
            if not nested_git
            else f"nested git: {nested_git}",
        )
    )

    secret_pat = re.compile(
        r"(sk-ant-[a-z]+\d{2}-[A-Za-z0-9_-]{40,}"
        r"|AKIA[0-9A-Z]{16}"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
    )
    leaks: list[str] = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if secret_pat.search(text):
            leaks.append(rel)
    results.append(
        CheckResult(
            "no-committed-secrets",
            not leaks,
            "no secret patterns in tracked files"
            if not leaks
            else f"possible secrets in: {leaks[:5]}",
        )
    )

    import_ban = _run_script("check_import_ban.py")
    results.append(
        CheckResult(
            "no-banned-donor-libs",
            import_ban.returncode == 0,
            "no banned donor libraries in manifests or imports"
            if import_ban.returncode == 0
            else "banned donor library detected (clean-room violation)",
        )
    )

    in_tenant = _run_script("check_in_tenant.py")
    results.append(
        CheckResult(
            "tn1-in-tenant-boundary",
            in_tenant.returncode == 0,
            "all code/IP endpoints in-tenant (model call excepted)"
            if in_tenant.returncode == 0
            else "a code/IP endpoint resolves to an external host",
        )
    )
    return results


def _strip_shell_comments(script: str) -> str:
    kept: list[str] = []
    for line in script.splitlines():
        body, quote = [], None
        for index, char in enumerate(line):
            if quote:
                body.append(char)
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
                body.append(char)
            elif char == "#" and (index == 0 or line[index - 1] in " \t"):
                break
            else:
                body.append(char)
        kept.append("".join(body))
    return "\n".join(kept)


def _ci_run_commands(workflow: Path) -> list[str]:
    if not workflow.is_file():
        return []
    try:
        import yaml

        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(document, dict):
        return []
    commands: list[str] = []
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            script = step.get("run")
            if not isinstance(script, str):
                continue
            if step.get("continue-on-error") is True:
                continue
            commands.append(_strip_shell_comments(script))
    return commands


def check_git_hygiene() -> list[CheckResult]:
    results: list[CheckResult] = []

    version = REPO_ROOT / "VERSION"
    ok_version = False
    detail = "VERSION missing"
    if version.is_file():
        try:
            raw = version.read_text(encoding="utf-8").strip()
            ok_version = bool(re.fullmatch(r"\d+\.\d+\.\d+", raw))
            detail = f"VERSION={raw}" if ok_version else f"VERSION malformed: {raw!r}"
        except Exception as exc:
            detail = f"VERSION unreadable: {exc}"
    results.append(CheckResult("version-file", ok_version, detail))

    gitignore = REPO_ROOT / ".gitignore"
    ignore_ok = False
    detail = ".gitignore missing"
    if gitignore.is_file():
        try:
            body = gitignore.read_text(encoding="utf-8")
            ignore_ok = any(
                line.strip().strip("/") == "projects" for line in body.splitlines()
            )
            detail = (
                ".gitignore keeps projects/ out"
                if ignore_ok
                else ".gitignore does not ignore projects/"
            )
        except Exception as exc:
            detail = f".gitignore unreadable: {exc}"
    results.append(CheckResult("gitignore-sane", ignore_ok, detail))

    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    results.append(
        CheckResult(
            "ci-workflow",
            ci.is_file(),
            "CI workflow present" if ci.is_file() else ".github/workflows/ci.yml missing",
        )
    )

    commands = _ci_run_commands(ci)
    unwired = [step for step in CI_REQUIRED_STEPS if not any(step in c for c in commands)]
    results.append(
        CheckResult(
            "ci-runs-the-gates",
            bool(commands) and not unwired,
            "CI runs diagnostics, the prose law, the orchestrator dry-run, ruff and pytest"
            if (commands and not unwired)
            else (f"CI does not run: {unwired}" if commands else "ci.yml has no run: steps"),
        )
    )

    codeowners = REPO_ROOT / ".github" / "CODEOWNERS"
    results.append(
        CheckResult(
            "codeowners-present",
            codeowners.is_file(),
            "CODEOWNERS present" if codeowners.is_file() else ".github/CODEOWNERS missing",
        )
    )

    co = _run_script("check_codeowners.py")
    results.append(
        CheckResult(
            "codeowners-complete",
            co.returncode == 0,
            "CODEOWNERS covers every area + in sync"
            if co.returncode == 0
            else "CODEOWNERS incomplete or drifted",
        )
    )
    return results


CHECK_FUNCS: dict[str, Callable[[], list[CheckResult]]] = {
    "architecture": check_architecture,
    "code_quality": check_code_quality,
    "consistency": check_consistency,
    "portability": check_portability,
    "security": check_security,
    "prose_freedom": check_prose_freedom,
    "test_suite": check_test_suite,
    "cli_contracts": check_cli_contracts,
    "runtime_integrity": check_runtime_integrity,
    "git_hygiene": check_git_hygiene,
}


def score_dimension(key: str, label: str, weight: int) -> DimensionResult:
    dim = DimensionResult(key=key, label=label, weight=weight)
    func = CHECK_FUNCS[key]
    try:
        dim.checks = func()
        if not dim.checks:
            dim.checks = [CheckResult("no-checks", False, "no checks defined")]
    except Exception as exc:
        dim.checks = [CheckResult("uncaught-error", False, f"{type(exc).__name__}: {exc}")]
    return dim


def run(selected: str) -> list[DimensionResult]:
    if selected == "board":
        selected = "consistency"
    if selected == "all":
        return [score_dimension(k, label, w) for k, label, w in DIMENSIONS]
    for k, label, w in DIMENSIONS:
        if k == selected:
            return [score_dimension(k, label, w)]
    raise SystemExit(f"unknown dimension: {selected!r}")


def render_text(results: list[DimensionResult], total: int, maximum: int) -> str:
    lines: list[str] = []
    for dim in results:
        mark = "PASS" if dim.passed else "FAIL"
        lines.append(f"[{mark}] {dim.label:<18} {dim.score:>3}/{dim.weight:<3}")
        for chk in dim.checks:
            sub = "ok " if chk.passed else "XX "
            lines.append(f"        {sub}{chk.name}: {chk.detail}")
    lines.append("-" * 40)
    lines.append(f"SCORE = {total}/{maximum}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnostics.py",
        description=(
            f"DasLab weighted {len(DIMENSIONS)}-dimension release-gate scorer (100/100). "
            "exit codes: 0 every dimension green, 1 at least one dimension red, 2 usage error."
        ),
    )
    valid = [k for k, _, _ in DIMENSIONS] + ["board", "all"]
    parser.add_argument(
        "--check",
        default="all",
        metavar="DIM",
        help=f"dimension to score: {', '.join(valid)} (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit per-dimension scores as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    valid = {k for k, _, _ in DIMENSIONS} | {"board", "all"}
    if args.check not in valid:
        sys.stderr.write(f"error: --check must be one of {sorted(valid)}\n")
        return 2

    results = run(args.check)
    total = sum(d.score for d in results)
    maximum = sum(d.weight for d in results)

    if args.json:
        payload = {
            "selected": args.check,
            "total": total,
            "maximum": maximum,
            "passed": total == maximum,
            "dimensions": [d.to_dict() for d in results],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(results, total, maximum))

    return 0 if total == maximum else 1


if __name__ == "__main__":
    raise SystemExit(main())
