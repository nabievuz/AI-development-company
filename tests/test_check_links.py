from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_links import check, main


def test_detects_broken_relative_link(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("See [the missing doc](does-not-exist.md).\n")
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "does-not-exist.md" in failures[0]
    assert main(["--root", str(tmp_path)]) == 1


def test_passes_when_target_exists(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# Target\n")
    (tmp_path / "a.md").write_text("See [the target](target.md).\n")
    assert check(tmp_path) == []
    assert main(["--root", str(tmp_path)]) == 0


def test_ignores_external_and_anchor_links(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "[web](https://example.com) [mail](mailto:x@y.z) "
        "[anchor](#section) [proto](//cdn.example.com/x)\n"
    )
    assert check(tmp_path) == []


def test_strips_anchor_before_existence_check(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# T\n")
    (tmp_path / "a.md").write_text("[ok](target.md#heading) [bad](nope.md#heading)\n")
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "nope.md#heading" in failures[0]


def test_resolves_relative_to_file_dir(tmp_path: Path) -> None:
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "guide.md").write_text("[up](../README.md)\n")
    (tmp_path / "README.md").write_text("# Root\n")
    assert main(["--root", str(tmp_path)]) == 0

    (sub / "guide.md").write_text("[sib](sibling.md)\n")
    assert main(["--root", str(tmp_path)]) == 1
