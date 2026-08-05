from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIR_NAMES = {".venv", "venv", ".vendor", "projects", ".git", "__pycache__", "node_modules"}
SHEBANG = "#!/usr/bin/env python3"


def source_files(root: Path | None = None) -> list[Path]:
    root = root or ROOT
    return sorted(
        p for p in root.rglob("*.py")
        if not EXCLUDED_DIR_NAMES.intersection(p.relative_to(root).parts)
    )


DOCSTRING_BEARING_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def docstring_violations(path: Path, tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, DOCSTRING_BEARING_NODES):
            continue
        if ast.get_docstring(node) is None:
            continue
        name = getattr(node, "name", "<module>")
        out.append(f"{path}:{getattr(node, 'lineno', 1)}: docstring on {name}")
    return out


def comment_violations(path: Path, text: str) -> list[str]:
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT and tok.string.strip() != SHEBANG:
            out.append(f"{path}:{tok.start[0]}: comment {tok.string.strip()[:60]!r}")
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else ROOT
    files = source_files(root)
    violations: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            violations.append(f"{path}: unparseable ({exc})")
            continue
        violations.extend(docstring_violations(path, tree))
        try:
            violations.extend(comment_violations(path, text))
        except tokenize.TokenError as exc:
            violations.append(f"{path}: untokenizable ({exc})")
    print(f"scanned {len(files)} .py files under {root}")
    for v in violations:
        print(v)
    print(f"violations: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
