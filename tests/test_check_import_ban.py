"""tests/test_check_import_ban.py — pytest for check_import_ban.py.

Hermetic: builds synthetic manifest + scripts directories under tmp_path.
Proves:
  (a) the real repo baseline is clean (no banned donor libs present)
  (b) a banned distribution name in a requirements manifest fails
  (c) a banned Python import statement in scripts/ fails
  (d) word-boundary-safe matching: embeddings without separators do NOT trigger
  (e) comment lines in manifests are skipped
  (f) comment lines in Python source are skipped
  (g) CLI exit codes match pass/fail state
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_import_ban import check, main, scan_imports, scan_manifests  # noqa: E402


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# ---------------------------------------------------------------------------
# Clean-baseline: the real repo must have zero violations
# ---------------------------------------------------------------------------


def test_real_repo_clean_baseline() -> None:
    """The actual repo contains no banned donor libraries (GATE-4 baseline)."""
    hits = check(_REPO_ROOT)
    assert hits == [], "Banned donor lib(s) found in real repo:\n" + "\n".join(hits)


# ---------------------------------------------------------------------------
# Manifest hits
# ---------------------------------------------------------------------------


def test_manifest_banned_simple_fails(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "crewai==0.1.0\n")
    hits = scan_manifests(tmp_path)
    assert len(hits) == 1
    assert "crewai" in hits[0]


def test_manifest_banned_hyphen_form_fails(tmp_path: Path) -> None:
    """agency-swarm (hyphen form) is detected."""
    _write(tmp_path / "requirements.in", "agency-swarm>=2.0\n")
    hits = scan_manifests(tmp_path)
    assert hits, "agency-swarm not detected"


def test_manifest_banned_underscore_form_fails(tmp_path: Path) -> None:
    """agency_swarm (underscore form, PEP 508 equivalent) is also detected."""
    _write(tmp_path / "requirements.in", "agency_swarm>=2.0\n")
    hits = scan_manifests(tmp_path)
    assert hits, "agency_swarm not detected"


def test_manifest_banned_case_insensitive(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "LangGraph==0.9\n")
    hits = scan_manifests(tmp_path)
    assert hits, "LangGraph (mixed case) not detected"


def test_manifest_all_five_banned_detected(tmp_path: Path) -> None:
    content = (
        "langgraph==0.1\n"
        "agent-framework==1.0\n"
        "crewai==0.5\n"
        "agency-swarm==2.0\n"
        "superagi==3.0\n"
    )
    _write(tmp_path / "requirements.txt", content)
    hits = scan_manifests(tmp_path)
    assert len(hits) == 5, f"Expected 5 hits, got {len(hits)}: {hits}"


def test_manifest_comment_line_skipped(tmp_path: Path) -> None:
    """A comment line mentioning a banned name must NOT be flagged."""
    _write(
        tmp_path / "requirements.txt",
        "# crewai is banned — do not add it\npyyaml==6.0.2\n",
    )
    assert scan_manifests(tmp_path) == []


def test_manifest_clean_pyyaml_passes(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "pyyaml==6.0.2\n")
    assert scan_manifests(tmp_path) == []


# ---------------------------------------------------------------------------
# Import hits
# ---------------------------------------------------------------------------


def test_import_bare_import_fails(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "worker.py", "import crewai\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1
    assert "crewai" in hits[0]


def test_import_from_form_fails(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "worker.py", "from langgraph import StateGraph\n")
    hits = scan_imports(tmp_path)
    assert hits, "from-import not detected"


def test_import_submodule_form_fails(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "worker.py", "import langgraph.graph\n")
    hits = scan_imports(tmp_path)
    assert hits, "submodule import not detected"


def test_import_agency_swarm_normalised(tmp_path: Path) -> None:
    """agency_swarm (underscore, the typical import name) is detected."""
    _write(tmp_path / "scripts" / "worker.py", "import agency_swarm\n")
    hits = scan_imports(tmp_path)
    assert hits, "agency_swarm import not detected"


def test_import_comment_line_skipped(tmp_path: Path) -> None:
    """A commented-out import line must NOT be flagged."""
    _write(tmp_path / "scripts" / "worker.py", "# import crewai  # banned\n")
    assert scan_imports(tmp_path) == []


def test_import_clean_stdlib_passes(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "worker.py",
        "import os\nimport re\nfrom pathlib import Path\n",
    )
    assert scan_imports(tmp_path) == []


# ---------------------------------------------------------------------------
# Word-boundary safety (the key correctness requirement)
# ---------------------------------------------------------------------------


def test_word_boundary_no_match_alphanumeric_embed_manifest(tmp_path: Path) -> None:
    """A package name that embeds a banned name WITHOUT a word-separator is not matched.

    "mycrewaiplugin" has no boundary around "crewai" (all alphanumeric) so
    \\b does not fire and the line is NOT a hit.
    """
    _write(tmp_path / "requirements.txt", "mycrewaiplugin==1.0\n")
    assert scan_manifests(tmp_path) == []


def test_word_boundary_no_match_underscore_prefix_import(tmp_path: Path) -> None:
    """An import whose name has underscores surrounding the banned token is not matched.

    "my_langgraph_ext": underscores are word characters (\\w), so \\b does not
    fire around "langgraph" here — the substring is NOT a hit.
    """
    _write(tmp_path / "scripts" / "worker.py", "import my_langgraph_ext\n")
    assert scan_imports(tmp_path) == []


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_main_returns_0_on_clean_tree(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "pyyaml==6.0.2\n")
    _write(tmp_path / "scripts" / "ok.py", "import os\n")
    assert main(["--root", str(tmp_path)]) == 0


def test_main_returns_1_on_manifest_hit(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "superagi==1.0\n")
    assert main(["--root", str(tmp_path)]) == 1


def test_main_returns_1_on_import_hit(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "bad.py", "import crewai\n")
    assert main(["--root", str(tmp_path)]) == 1


# ---------------------------------------------------------------------------
# Scope-widening: nested scripts/ subdirectories are scanned (FIX-C)
# ---------------------------------------------------------------------------


def test_nested_scripts_subdir_banned_import_caught(tmp_path: Path) -> None:
    """A banned import inside a nested scripts/ subdirectory is detected.

    Previously scan_imports used glob("*.py") (top-level only); the fix uses
    rglob("*.py") so scripts/dgox/, scripts/cache/, etc. are covered. Uses
    crewai (a non-sanctioned lib) so the nested-scan assertion is independent of
    the ADR-0035 langgraph carve-out for scripts/dgox/.
    """
    _write(tmp_path / "scripts" / "dgox" / "pipeline.py", "import crewai\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "crewai" in hits[0]
    assert "scripts/dgox/pipeline.py" in hits[0]


def test_nested_scripts_deep_subdir_all_banned_caught(tmp_path: Path) -> None:
    """All 5 banned libs are caught when spread across nested scripts subdirs."""
    _write(tmp_path / "scripts" / "cache" / "a.py", "import crewai\n")
    _write(tmp_path / "scripts" / "cost" / "b.py", "from agency_swarm import Agent\n")
    _write(tmp_path / "scripts" / "dgox" / "c.py", "import superagi\n")
    _write(tmp_path / "scripts" / "other" / "d.py", "import langgraph\n")
    _write(tmp_path / "scripts" / "other" / "e.py", "import agent_framework\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 5, f"Expected 5 hits, got {hits}"


def test_tests_dir_banned_import_caught(tmp_path: Path) -> None:
    """A banned import inside tests/ is detected (scope expansion to tests/ tree)."""
    _write(tmp_path / "tests" / "helpers" / "util.py", "from crewai import Crew\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "crewai" in hits[0]
    assert "tests/helpers/util.py" in hits[0]


def test_nested_clean_baseline_still_passes(tmp_path: Path) -> None:
    """Clean nested tree (no banned libs) produces zero hits."""
    _write(tmp_path / "scripts" / "dgox" / "ok.py", "import os\nfrom pathlib import Path\n")
    _write(tmp_path / "scripts" / "cache" / "ok.py", "import json\n")
    _write(tmp_path / "tests" / "unit" / "test_ok.py", "import pytest\n")
    assert scan_imports(tmp_path) == []


# ---------------------------------------------------------------------------
# Scope-widening: pyproject.toml dependency tables are scanned (FIX-C)
# ---------------------------------------------------------------------------


def test_pyproject_pep621_banned_dep_caught(tmp_path: Path) -> None:
    """A banned lib in [project.dependencies] (PEP 621) is detected."""
    toml_text = (
        '[project]\n'
        'name = "myapp"\n'
        'dependencies = [\n'
        '    "crewai>=0.5",\n'
        '    "requests>=2.0",\n'
        ']\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    hits = scan_manifests(tmp_path)
    assert hits, "crewai in [project.dependencies] not detected"
    assert any("crewai" in h for h in hits)
    assert any("[project.dependencies]" in h for h in hits)


def test_pyproject_poetry_banned_dep_caught(tmp_path: Path) -> None:
    """A banned lib in [tool.poetry.dependencies] is detected."""
    toml_text = (
        '[tool.poetry]\n'
        'name = "myapp"\n'
        '\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.11"\n'
        'langgraph = "^0.1"\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    hits = scan_manifests(tmp_path)
    assert hits, "langgraph in [tool.poetry.dependencies] not detected"
    assert any("langgraph" in h for h in hits)
    assert any("[tool.poetry.dependencies]" in h for h in hits)


def test_pyproject_all_five_banned_detected(tmp_path: Path) -> None:
    """All 5 banned libs spread across pep621 + poetry tables are caught."""
    toml_text = (
        '[project]\n'
        'name = "evil"\n'
        'dependencies = ["langgraph==0.1", "agent-framework==1.0", "crewai==0.5"]\n'
        '\n'
        '[tool.poetry.dependencies]\n'
        'python = "^3.11"\n'
        'agency-swarm = "^2.0"\n'
        'superagi = "^3.0"\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    hits = scan_manifests(tmp_path)
    assert len(hits) == 5, f"Expected 5 hits, got {len(hits)}: {hits}"


def test_pyproject_clean_no_project_deps_passes(tmp_path: Path) -> None:
    """A pyproject.toml with only tool config (no deps) passes cleanly."""
    toml_text = (
        '[tool.ruff]\n'
        'line-length = 100\n'
        '\n'
        '[tool.pytest.ini_options]\n'
        'testpaths = ["tests"]\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    assert scan_manifests(tmp_path) == []


def test_pyproject_hyphen_underscore_normalised(tmp_path: Path) -> None:
    """PEP 508 normalisation: agency_swarm (underscore) in pyproject deps is caught."""
    toml_text = (
        '[project]\n'
        'name = "myapp"\n'
        'dependencies = ["agency_swarm>=2.0"]\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    hits = scan_manifests(tmp_path)
    assert hits, "agency_swarm (underscore) in pyproject.toml not detected"


def test_real_repo_pyproject_clean(tmp_path: Path) -> None:
    """The real repo pyproject.toml contains no banned donor libraries."""
    hits = scan_manifests(_REPO_ROOT)
    pyproject_hits = [h for h in hits if "pyproject.toml" in h]
    assert pyproject_hits == [], (
        "Banned donor lib(s) found in real pyproject.toml:\n"
        + "\n".join(pyproject_hits)
    )


# ---------------------------------------------------------------------------
# ADR-0035 sanctioned-substrate carve-out: langgraph is allowed ONLY inside the
# DGO-X substrate zone scripts/dgox/, and only for langgraph — never elsewhere,
# never for the other four donor libs. (GATE-4, CTO-ratified 2026-07-24.)
# ---------------------------------------------------------------------------


def test_carveout_langgraph_allowed_in_dgox_substrate_zone(tmp_path: Path) -> None:
    """The natural idiomatic import in scripts/dgox/ is ALLOWED (ADR-0035)."""
    _write(
        tmp_path / "scripts" / "dgox" / "langgraph_loop.py",
        "from langgraph.graph import StateGraph\n",
    )
    assert scan_imports(tmp_path) == []


def test_carveout_langgraph_bare_and_submodule_allowed_in_dgox(tmp_path: Path) -> None:
    """Both `import langgraph` and `import langgraph.graph` are allowed in scripts/dgox/."""
    _write(tmp_path / "scripts" / "dgox" / "a.py", "import langgraph\n")
    _write(tmp_path / "scripts" / "dgox" / "b.py", "import langgraph.graph\n")
    assert scan_imports(tmp_path) == []


def test_carveout_langgraph_still_banned_outside_dgox(tmp_path: Path) -> None:
    """langgraph in any non-substrate path is STILL a violation (scoped, not global, unban)."""
    _write(tmp_path / "scripts" / "other" / "smuggle.py", "from langgraph.graph import X\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "langgraph" in hits[0]
    assert "scripts/other/smuggle.py" in hits[0]


def test_carveout_langgraph_still_banned_in_tests_tree(tmp_path: Path) -> None:
    """The carve-out is scripts/dgox/ only — langgraph in tests/ still fails."""
    _write(tmp_path / "tests" / "helpers" / "u.py", "import langgraph\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "langgraph" in hits[0]


def test_carveout_does_not_extend_to_other_donor_libs_in_dgox(tmp_path: Path) -> None:
    """Only langgraph is carved out; the other four stay banned even inside scripts/dgox/."""
    _write(tmp_path / "scripts" / "dgox" / "c.py", "import crewai\n")
    _write(tmp_path / "scripts" / "dgox" / "d.py", "from agency_swarm import Agent\n")
    _write(tmp_path / "scripts" / "dgox" / "e.py", "import superagi\n")
    _write(tmp_path / "scripts" / "dgox" / "f.py", "import agent_framework\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 4, f"Expected 4 hits (langgraph excluded), got {hits}"
    assert not any("langgraph" in h for h in hits)


def test_carveout_core_requirements_langgraph_still_banned(tmp_path: Path) -> None:
    """langgraph in the CORE root requirements.txt is STILL banned (opt-in extra only)."""
    _write(tmp_path / "requirements.txt", "langgraph==0.1\n")
    hits = scan_manifests(tmp_path)
    assert hits, "langgraph in core requirements.txt must still fail"
    assert any("langgraph" in h for h in hits)
