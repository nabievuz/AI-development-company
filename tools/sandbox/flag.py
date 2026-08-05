from __future__ import annotations

from pathlib import Path

_FLAG = "ws_c_langgraph_loop"
_DEFAULT_REL = "config/features.yaml"


DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / _DEFAULT_REL


def flag_on(features_path: Path | None = None) -> bool:
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{_FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False
