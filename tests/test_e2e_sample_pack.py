#!/usr/bin/env python3

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gateway_compile as gc

E2E_DIR = REPO_ROOT / "evals" / "e2e"
PACK_DIRS = (E2E_DIR / "sample-pack", E2E_DIR / "sample-pack-2")


def _slug_of(pack_dir: Path) -> str:
    manifest = yaml.safe_load((pack_dir / "PROJECT-OS.yaml").read_text(encoding="utf-8"))
    return str(manifest["name"])


def _compile_in_scratch(pack_dir: Path, tmp_path: Path):
    slug = _slug_of(pack_dir)
    scratch_root = tmp_path / "projects" / slug
    shutil.copytree(pack_dir, scratch_root)
    return slug, scratch_root, gc.run_pipeline(scratch_root, projects_dir=tmp_path / "projects")


@pytest.mark.parametrize("pack", PACK_DIRS, ids=lambda p: p.name)
def test_pack_manifest_is_still_complete(pack: Path) -> None:
    manifest_path = pack / "PROJECT-OS.yaml"
    assert manifest_path.is_file()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    for key in gc.REQUIRED_MANIFEST_KEYS:
        assert manifest.get(key) not in (None, ""), f"{pack.name} manifest missing {key}"


@pytest.mark.parametrize("pack", PACK_DIRS, ids=lambda p: p.name)
def test_pack_without_its_doc_tree_is_rejected_not_silently_compiled(
    pack: Path, tmp_path: Path
) -> None:
    _slug, _root, res = _compile_in_scratch(pack, tmp_path)
    assert res.ok is False
    assert res.rejected_stage == "validate"
    assert res.tickets == []


@pytest.mark.parametrize("pack", PACK_DIRS, ids=lambda p: p.name)
def test_rejection_names_the_missing_artifact_and_a_fix(pack: Path, tmp_path: Path) -> None:
    _slug, _root, res = _compile_in_scratch(pack, tmp_path)
    rendered = [str(e) for e in res.errors]
    assert rendered
    assert any("docs/" in text for text in rendered)
    assert all("fix:" in text for text in rendered)


@pytest.mark.parametrize("pack", PACK_DIRS, ids=lambda p: p.name)
def test_rejected_pack_writes_no_board_tickets(pack: Path, tmp_path: Path) -> None:
    _slug, root, res = _compile_in_scratch(pack, tmp_path)
    assert res.ok is False
    assert not (root / "board-tickets").exists()
    assert not (pack / "board-tickets").exists()


def test_no_committed_pack_currently_compiles(tmp_path: Path) -> None:
    compiled = []
    for pack in PACK_DIRS:
        _slug, _root, res = _compile_in_scratch(pack, tmp_path / pack.name)
        if res.ok:
            compiled.append(pack.name)
    assert compiled == [], (
        "a committed pack compiled — this test records the current truth that the "
        "PROJECT-OS packs lost their doc trees, so no pack-driven delivery evidence "
        "can exist; update it deliberately once a pack is whole again"
    )


def test_compiling_packs_never_touches_org_board(tmp_path: Path) -> None:
    before = sorted((REPO_ROOT / "board" / "tickets").glob("DAS-*.md"))
    for pack in PACK_DIRS:
        _compile_in_scratch(pack, tmp_path / pack.name)
    after = sorted((REPO_ROOT / "board" / "tickets").glob("DAS-*.md"))
    assert before == after


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
