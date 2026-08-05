from __future__ import annotations

from pathlib import Path

TENANT_HARDENING_FLAG = "ws_e_tenant_hardening"
OPENWEIGHT_EJECTPATH_FLAG = "ws_e_openweight_ejectpath"

_DEFAULT_REL = "config/features.yaml"
_TRUE = {"1", "true", "on", "yes"}


DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / _DEFAULT_REL


def _read_flag(flag: str, features_path: Path | None = None) -> bool:
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{flag}:"):
                return raw.split(":", 1)[1].strip().lower() in _TRUE
    except OSError:
        return False
    return False


def tenant_hardening_on(features_path: Path | None = None) -> bool:
    return _read_flag(TENANT_HARDENING_FLAG, features_path)


def openweight_ejectpath_on(features_path: Path | None = None) -> bool:
    return _read_flag(TENANT_HARDENING_FLAG, features_path) and _read_flag(
        OPENWEIGHT_EJECTPATH_FLAG, features_path
    )
