from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_no_prose as cnp


def test_shipped_tree_carries_no_comments_or_docstrings() -> None:
    files = cnp.source_files()
    assert len(files) > 400, "the scan surface collapsed — it must cover the whole repo"
    violations: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        tree = cnp.ast.parse(text)
        violations.extend(cnp.docstring_violations(path, tree))
        violations.extend(cnp.comment_violations(path, text))
    assert violations == []


def test_excluded_trees_are_never_scanned() -> None:
    for path in cnp.source_files():
        parts = path.relative_to(cnp.ROOT).parts
        assert not cnp.EXCLUDED_DIR_NAMES.intersection(parts)


def test_a_module_docstring_is_a_violation(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text('"""prose"""\nx = 1\n', encoding="utf-8")
    tree = cnp.ast.parse(src.read_text(encoding="utf-8"))
    assert cnp.docstring_violations(src, tree)


@pytest.mark.parametrize(
    "body",
    [
        'def f():\n    """prose"""\n    return 1\n',
        'class C:\n    """prose"""\n    x = 1\n',
        'async def g():\n    """prose"""\n    return 1\n',
    ],
)
def test_function_and_class_docstrings_are_violations(tmp_path: Path, body: str) -> None:
    src = tmp_path / "m.py"
    src.write_text(body, encoding="utf-8")
    tree = cnp.ast.parse(body)
    assert cnp.docstring_violations(src, tree)


def test_a_comment_is_a_violation_but_the_shebang_is_not(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text(f"{cnp.SHEBANG}\nx = 1  # why\n", encoding="utf-8")
    text = src.read_text(encoding="utf-8")
    violations = cnp.comment_violations(src, text)
    assert len(violations) == 1
    assert "why" in violations[0]


def test_a_data_string_is_not_a_violation(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text('HELP = "run the thing"\nprint(HELP)\n', encoding="utf-8")
    text = src.read_text(encoding="utf-8")
    tree = cnp.ast.parse(text)
    assert cnp.docstring_violations(src, tree) == []
    assert cnp.comment_violations(src, text) == []


def test_cli_exits_zero_on_the_shipped_tree() -> None:
    assert cnp.main([]) == 0


def test_cli_exits_one_when_prose_is_present(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text('"""prose"""\n', encoding="utf-8")
    assert cnp.main([str(tmp_path)]) == 1


def test_cli_accepts_an_explicit_root(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    assert cnp.main([str(tmp_path)]) == 0
