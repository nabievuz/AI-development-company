from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_project_isolation import engine_files, offenders

DENY = {"acme"}


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_detects_project_name_in_engine_script(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "x.py", "ROUTE = 'acme/runtime'\n")
    found = offenders(tmp_path, deny=DENY)
    assert len(found) == 1 and "x.py" in found[0]


def test_clean_engine_passes(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "x.py", "from _paths import ROOT\n")
    _write(tmp_path / "AGENTS.md", "# Generic umbrella spec\n")
    assert offenders(tmp_path, deny=DENY) == []


def test_non_engine_areas_out_of_scope(tmp_path: Path) -> None:

    _write(tmp_path / "docs" / "report.md", "acme shipped\n")
    _write(tmp_path / "board" / "archive" / "old.md", "acme ticket\n")
    _write(tmp_path / "projects" / "acme" / "app.py", "print('acme')\n")
    assert offenders(tmp_path, deny=DENY) == []


def test_engine_surface_excludes_self_and_docs(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "check_project_isolation.py", "deny = 'acme'\n")
    _write(tmp_path / "scripts" / "real.py", "x = 1\n")
    files = engine_files(tmp_path)
    assert "scripts/check_project_isolation.py" not in files
    assert "scripts/real.py" in files


def test_default_denylist_derives_from_projects_dir(tmp_path: Path) -> None:

    (tmp_path / "projects" / "acme").mkdir(parents=True)
    (tmp_path / "projects" / "acme" / "app.py").write_text("print('acme')\n")

    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0004.md").write_text("acme extraction\n")
    assert offenders(tmp_path) == []

    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "gen.py").write_text('PROJECT = "acme"\n')
    found = offenders(tmp_path)
    assert len(found) == 1 and "scripts/gen.py" in found[0]
