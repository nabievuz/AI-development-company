from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_import_ban import check, main, scan_imports, scan_manifests


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_real_repo_clean_baseline() -> None:
    hits = check(_REPO_ROOT)
    assert hits == [], "Banned donor lib(s) found in real repo:\n" + "\n".join(hits)


def test_manifest_banned_simple_fails(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "crewai==0.1.0\n")
    hits = scan_manifests(tmp_path)
    assert len(hits) == 1
    assert "crewai" in hits[0]


def test_manifest_banned_hyphen_form_fails(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.in", "agency-swarm>=2.0\n")
    hits = scan_manifests(tmp_path)
    assert hits, "agency-swarm not detected"


def test_manifest_banned_underscore_form_fails(tmp_path: Path) -> None:
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
    _write(
        tmp_path / "requirements.txt",
        "# crewai is banned — do not add it\npyyaml==6.0.2\n",
    )
    assert scan_manifests(tmp_path) == []


def test_manifest_clean_pyyaml_passes(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "pyyaml==6.0.2\n")
    assert scan_manifests(tmp_path) == []


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
    _write(tmp_path / "scripts" / "worker.py", "import agency_swarm\n")
    hits = scan_imports(tmp_path)
    assert hits, "agency_swarm import not detected"


def test_import_comment_line_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "worker.py", "# import crewai  # banned\n")
    assert scan_imports(tmp_path) == []


def test_import_clean_stdlib_passes(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "worker.py",
        "import os\nimport re\nfrom pathlib import Path\n",
    )
    assert scan_imports(tmp_path) == []


def test_word_boundary_no_match_alphanumeric_embed_manifest(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "mycrewaiplugin==1.0\n")
    assert scan_manifests(tmp_path) == []


def test_word_boundary_no_match_underscore_prefix_import(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "worker.py", "import my_langgraph_ext\n")
    assert scan_imports(tmp_path) == []


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


def test_nested_scripts_subdir_banned_import_caught(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "dgox" / "pipeline.py", "import crewai\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "crewai" in hits[0]
    assert "scripts/dgox/pipeline.py" in hits[0]


def test_nested_scripts_deep_subdir_all_banned_caught(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "cache" / "a.py", "import crewai\n")
    _write(tmp_path / "scripts" / "cost" / "b.py", "from agency_swarm import Agent\n")
    _write(tmp_path / "scripts" / "dgox" / "c.py", "import superagi\n")
    _write(tmp_path / "scripts" / "other" / "d.py", "import langgraph\n")
    _write(tmp_path / "scripts" / "other" / "e.py", "import agent_framework\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 5, f"Expected 5 hits, got {hits}"


def test_tests_dir_banned_import_caught(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "helpers" / "util.py", "from crewai import Crew\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "crewai" in hits[0]
    assert "tests/helpers/util.py" in hits[0]


def test_nested_clean_baseline_still_passes(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "dgox" / "ok.py", "import os\nfrom pathlib import Path\n")
    _write(tmp_path / "scripts" / "cache" / "ok.py", "import json\n")
    _write(tmp_path / "tests" / "unit" / "test_ok.py", "import pytest\n")
    assert scan_imports(tmp_path) == []


def test_pyproject_pep621_banned_dep_caught(tmp_path: Path) -> None:
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
    toml_text = (
        '[project]\n'
        'name = "myapp"\n'
        'dependencies = ["agency_swarm>=2.0"]\n'
    )
    _write(tmp_path / "pyproject.toml", toml_text)
    hits = scan_manifests(tmp_path)
    assert hits, "agency_swarm (underscore) in pyproject.toml not detected"


def test_real_repo_pyproject_clean(tmp_path: Path) -> None:
    hits = scan_manifests(_REPO_ROOT)
    pyproject_hits = [h for h in hits if "pyproject.toml" in h]
    assert pyproject_hits == [], (
        "Banned donor lib(s) found in real pyproject.toml:\n"
        + "\n".join(pyproject_hits)
    )


def test_carveout_langgraph_allowed_in_dgox_substrate_zone(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "dgox" / "langgraph_loop.py",
        "from langgraph.graph import StateGraph\n",
    )
    assert scan_imports(tmp_path) == []


def test_carveout_langgraph_bare_and_submodule_allowed_in_dgox(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "dgox" / "a.py", "import langgraph\n")
    _write(tmp_path / "scripts" / "dgox" / "b.py", "import langgraph.graph\n")
    assert scan_imports(tmp_path) == []


def test_carveout_langgraph_still_banned_outside_dgox(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "other" / "smuggle.py", "from langgraph.graph import X\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "langgraph" in hits[0]
    assert "scripts/other/smuggle.py" in hits[0]


def test_carveout_langgraph_still_banned_in_tests_tree(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "helpers" / "u.py", "import langgraph\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 1, f"Expected 1 hit, got {hits}"
    assert "langgraph" in hits[0]


def test_carveout_does_not_extend_to_other_donor_libs_in_dgox(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "dgox" / "c.py", "import crewai\n")
    _write(tmp_path / "scripts" / "dgox" / "d.py", "from agency_swarm import Agent\n")
    _write(tmp_path / "scripts" / "dgox" / "e.py", "import superagi\n")
    _write(tmp_path / "scripts" / "dgox" / "f.py", "import agent_framework\n")
    hits = scan_imports(tmp_path)
    assert len(hits) == 4, f"Expected 4 hits (langgraph excluded), got {hits}"
    assert not any("langgraph" in h for h in hits)


def test_carveout_core_requirements_langgraph_still_banned(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "langgraph==0.1\n")
    hits = scan_manifests(tmp_path)
    assert hits, "langgraph in core requirements.txt must still fail"
    assert any("langgraph" in h for h in hits)
