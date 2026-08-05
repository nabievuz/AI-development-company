
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


PINNED_ROOT_VAR = "DASLAB_ROOT"


PRESERVED_ENV_VARS = frozenset(
    {
        "DASLAB_DOCKER_BIN",
        "DASLAB_DOCKER_GROUP",
    }
)


ENV_PREFIX = "DASLAB_"


def scrubbed_env_vars(environ: dict[str, str] | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    return sorted(
        name
        for name in env
        if name.startswith(ENV_PREFIX)
        and name != PINNED_ROOT_VAR
        and name not in PRESERVED_ENV_VARS
    )


for _name in scrubbed_env_vars():
    del os.environ[_name]
os.environ[PINNED_ROOT_VAR] = str(REPO_ROOT)


@pytest.fixture
def inert_store_path(tmp_path: Path) -> Path:
    return tmp_path / "inert" / ".events.jsonl"
