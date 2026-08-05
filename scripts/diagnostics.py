#!/usr/bin/env python3


from __future__ import annotations

import argparse
import functools
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TICKETS_DIR: Path = REPO_ROOT / "board" / "tickets"


DIMENSIONS: list[tuple[str, str, int]] = [
    ("docs", "Docs", 20),
    ("architecture", "Architecture", 20),
    ("code_quality", "Code-quality", 15),
    ("consistency", "Consistency", 15),
    ("portability", "Portability", 15),
    ("security", "Security", 10),
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


def _is_substantive_doc(path: Path, min_chars: int = 200) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return len(text.strip()) >= min_chars and any(
        line.lstrip().startswith("#") for line in text.splitlines()
    )


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


def check_docs() -> list[CheckResult]:
    results: list[CheckResult] = []

    readme = REPO_ROOT / "README.md"
    results.append(
        CheckResult("root-readme", readme.is_file(), str(readme.relative_to(REPO_ROOT)))
    )

    docs_index = REPO_ROOT / "docs" / "README.md"
    results.append(
        CheckResult(
            "docs-index",
            docs_index.is_file(),
            "docs/README.md present" if docs_index.is_file() else "docs/README.md missing",
        )
    )

    adr_dir = REPO_ROOT / "docs" / "adr"
    expected_adrs = [
        "0001-status-handoff-protocol.md",
        "0002-enforcement-as-code.md",
        "0003-self-locating-root.md",
        "0004-project-agnostic-engine.md",
        "0005-worktree-per-ticket-dispatch-ownership.md",
    ]


    missing = [
        name
        for name in expected_adrs
        if not (adr_dir / name).is_file() and not (adr_dir / name).is_symlink()
    ]


    weak = [
        name
        for name in expected_adrs
        if (adr_dir / name).is_file()
        and not (adr_dir / name).is_symlink()
        and not _is_substantive_doc(adr_dir / name)
    ]
    adr_ok = not missing and not weak
    results.append(
        CheckResult(
            "adr-set-complete",
            adr_ok,
            "all 5 ADRs present and substantive"
            if adr_ok
            else (f"missing ADRs: {missing}" if missing else f"empty/stub ADRs: {weak}"),
        )
    )

    adr_index = adr_dir / "README.md"
    results.append(
        CheckResult(
            "adr-index",
            adr_index.is_file() or adr_index.is_symlink(),
            "docs/adr/README.md present"
            if (adr_index.is_file() or adr_index.is_symlink())
            else "docs/adr/README.md missing",
        )
    )


    import subprocess

    links = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_links.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "links-resolve",
            links.returncode == 0,
            "no broken relative links"
            if links.returncode == 0
            else "broken relative links present",
        )
    )

    qs = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_quickstart.py"), "--no-run"],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "quickstart-order",
            qs.returncode == 0,
            "README Quickstart runs bootstrap before doctor"
            if qs.returncode == 0
            else "README Quickstart boot order is wrong",
        )
    )
    return results


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


    arch_adr = REPO_ROOT / "docs" / "adr" / "0004-project-agnostic-engine.md"
    documented = arch_adr.is_file() or arch_adr.is_symlink()
    results.append(
        CheckResult(
            "architecture-documented",
            documented,
            "project-agnostic-engine ADR present"
            if documented
            else "architecture ADR missing",
        )
    )


    import subprocess

    iso = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_project_isolation.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "project-agnostic",
            iso.returncode == 0,
            "engine free of project-specific names"
            if iso.returncode == 0
            else "a project name leaked into the engine",
        )
    )

    dead = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_no_dead_runtime.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "no-dead-runtime",
            dead.returncode == 0,
            "no dead legacy-runtime endpoint in the active engine"
            if dead.returncode == 0
            else "dead runtime endpoint present",
        )
    )


    attest = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_attestation.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "attestation-integrity",
            attest.returncode == 0,
            "committed wave attestations complete + hash-chain intact"
            if attest.returncode == 0
            else "a committed attestation is incomplete or tampered (ADR-0031)",
        )
    )


    reconcile = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_wave_reconciliation.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "wave-reconciliation",
            reconcile.returncode == 0,
            "committed ledger ⇄ attestations reconcile (bijection/chain/terminal/coverage)"
            if reconcile.returncode == 0
            else "the committed dispatch record does not reconcile (ADR-0032)",
        )
    )
    return results


def check_code_quality() -> list[CheckResult]:
    results: list[CheckResult] = []

    scripts_dir = REPO_ROOT / "scripts"
    required_scripts = [
        "board_lint.py",
        "check_import_ban.py",
        "check_links.py",
        "check_agents_sync.py",
        "check_comm_flows.py",
        "check_gates.py",
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
        "test_check_links.py",
        "test_check_agents_sync.py",
        "test_check_comm_flows.py",
        "test_check_gates.py",
        "test_diagnostics.py",
    ]
    missing_tests = [
        t for t in required_tests if not (tests_dir / t).is_file()
    ]
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
            ["ruff", "check", str(REPO_ROOT / "scripts"), str(REPO_ROOT / "tests")],
            capture_output=True,
            text=True,
        )
        if ruff.returncode == 0:
            ruff_ok, ruff_detail = True, "ruff: scripts + tests lint-clean"
        else:
            ruff_ok, ruff_detail = False, "ruff reported lint findings (run `ruff check scripts tests`)"
    except FileNotFoundError:
        ruff_ok, ruff_detail = False, "ruff unavailable — lint gate cannot run; install ruff (fail-closed, ADR-0021)"
    results.append(CheckResult("ruff-clean", ruff_ok, ruff_detail))


    overlay = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_overlay_sections.py"), "--strict"],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "overlay-contract",
            overlay.returncode == 0,
            "all role overlays carry Mission/Scope/DoD/Escalation"
            if overlay.returncode == 0
            else "a role overlay is missing a contract section (ADR-0018)",
        )
    )
    return results


def check_consistency() -> list[CheckResult]:
    results: list[CheckResult] = []

    if not TICKETS_DIR.is_dir():
        results.append(
            CheckResult("tickets-dir", False, f"missing {TICKETS_DIR}")
        )
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


    prec = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_precedence.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "precedence-enforced",
            prec.returncode == 0,
            "no lower-precedence doc relaxes a board rule"
            if prec.returncode == 0
            else "a charter/overlay relaxes a binding rule",
        )
    )


    clarify = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_clarifications.py"), "--strict"],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "clarify-gate",
            clarify.returncode == 0,
            "no unresolved [NEEDS CLARIFICATION] markers in active tickets"
            if clarify.returncode == 0
            else "an active ticket carries an unresolved clarify marker",
        )
    )


    queue = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_approved_goal_queue.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "approved-goal-queue",
            queue.returncode == 0,
            "all project goal-queues are Founder-approved"
            if queue.returncode == 0
            else "an unapproved goal-queue exists (QONUN-3)",
        )
    )


    spec = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_spec_consistency.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "spec-consistency",
            spec.returncode == 0,
            "SPEC.md structure + ticket refs consistent"
            if spec.returncode == 0
            else "a SPEC.md is malformed or a ticket ref is dangling (ADR-0015)",
        )
    )


    depgraph = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_dependency_graph.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "dependency-graph",
            depgraph.returncode == 0,
            "ticket depends_on graph acyclic, no dangling refs"
            if depgraph.returncode == 0
            else "a dependency cycle / dangling dep / empty zone exists (ADR-0016)",
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


    import subprocess

    nohp = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_no_hardcoded_paths.py")],
        capture_output=True,
        text=True,
    )
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


    import subprocess

    import_ban = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_import_ban.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "no-banned-donor-libs",
            import_ban.returncode == 0,
            "no banned donor libraries in manifests or imports"
            if import_ban.returncode == 0
            else "banned donor library detected (GATE-4 clean-room violation)",
        )
    )


    in_tenant = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_in_tenant.py")],
        capture_output=True,
        text=True,
    )
    results.append(
        CheckResult(
            "tn1-in-tenant-boundary",
            in_tenant.returncode == 0,
            "all code/IP endpoints in-tenant (model call excepted)"
            if in_tenant.returncode == 0
            else "a code/IP endpoint resolves to an external host (TN-1 breach)",
        )
    )
    return results


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

    changelog = REPO_ROOT / "CHANGELOG.md"
    results.append(
        CheckResult(
            "changelog-file",
            changelog.is_file(),
            "CHANGELOG.md present" if changelog.is_file() else "CHANGELOG.md missing",
        )
    )

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

    templates = [".github/CODEOWNERS", ".github/pull_request_template.md"]
    missing_templates = [p for p in templates if not (REPO_ROOT / p).is_file()]
    results.append(
        CheckResult(
            "repo-templates",
            not missing_templates,
            "CODEOWNERS + PR template present"
            if not missing_templates
            else f"missing: {missing_templates}",
        )
    )

    co = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_codeowners.py")],
        capture_output=True,
        text=True,
    )
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
    "docs": check_docs,
    "architecture": check_architecture,
    "code_quality": check_code_quality,
    "consistency": check_consistency,
    "portability": check_portability,
    "security": check_security,
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
        lines.append(f"[{mark}] {dim.label:<13} {dim.score:>3}/{dim.weight:<3}")
        for chk in dim.checks:
            sub = "ok " if chk.passed else "XX "
            lines.append(f"        {sub}{chk.name}: {chk.detail}")
    lines.append("-" * 40)
    lines.append(f"SCORE = {total}/{maximum}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnostics.py",
        description="DasLab weighted 7-dimension release-gate scorer (100/100).",
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
