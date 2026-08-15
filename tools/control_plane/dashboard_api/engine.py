from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    return _PACKAGE_ROOT


def scripts_dir() -> Path:
    return _PACKAGE_ROOT / "scripts"


def _ensure_path() -> None:
    entry = str(scripts_dir())
    if entry not in sys.path:
        sys.path.insert(0, entry)


class EngineUnavailable(RuntimeError):
    def __init__(self, module: str, cause: BaseException) -> None:
        super().__init__(f"engine module {module!r} unavailable: {cause}")
        self.module = module
        self.cause = cause


_CACHE: dict[str, Any] = {}


def load(name: str) -> Any:
    cached = _CACHE.get(name)
    if cached is not None:
        return cached
    _ensure_path()
    try:
        mod = importlib.import_module(name)
    except Exception as exc:
        raise EngineUnavailable(name, exc) from exc
    _CACHE[name] = mod
    return mod


def try_load(name: str) -> tuple[Any | None, str]:
    try:
        return load(name), ""
    except EngineUnavailable as exc:
        return None, str(exc)


def load_file(name: str, relative: str) -> Any:
    cached = _CACHE.get(name)
    if cached is not None:
        return cached
    target = _PACKAGE_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, target)
    if spec is None or spec.loader is None:
        raise EngineUnavailable(name, FileNotFoundError(str(target)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise EngineUnavailable(name, exc) from exc
    _CACHE[name] = module
    return module


def scrub(value: object, cap: int = 0) -> str:
    try:
        mod = load_file("dashboard_redaction", "tools/mcp_bridges/redaction.py")
    except EngineUnavailable:
        return ""
    if cap > 0:
        return str(mod.redact_then_truncate(value, cap))
    return str(mod.safe_scrub(value))


def board() -> Path:
    return root() / "board"


def config_dir() -> Path:
    return root() / "config"


def events_path() -> Path:
    return board() / ".events.jsonl"


def wave_log_path() -> Path:
    return board() / ".wave-log"


def interrupts_dir() -> Path:
    return board() / "interrupts"


def tickets_dir() -> Path:
    return board() / "tickets"


def runs_dir() -> Path:
    return board() / "runs"


def experiments_dir() -> Path:
    return root() / "experiments"


def agent_templates_dir() -> Path:
    return root() / "governance" / "agent-templates"


def dashboard_dist() -> Path:
    return root() / "dashboard" / "dist"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(root()))
    except ValueError:
        return path.name
