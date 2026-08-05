
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _loaded_conftest():
    want = (ROOT / "tests" / "conftest.py").resolve()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve() == want:
            return module
    return None


conftest = _loaded_conftest()

if conftest is None:


    pytest.skip(
        "tests/conftest.py is not loaded (--noconftest?) — the env seam is not in "
        "force, so there is nothing here to guard",
        allow_module_level=True,
    )


def _load_paths():
    spec = importlib.util.spec_from_file_location(
        "_paths_for_conftest_test", ROOT / "scripts" / "_paths.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_conftest_under_test_is_the_one_in_this_tree():


    assert Path(conftest.__file__).resolve() == (ROOT / "tests" / "conftest.py").resolve()
    assert conftest.REPO_ROOT == ROOT


def test_root_is_pinned_to_the_tree_the_tests_live_in():
    assert os.environ[conftest.PINNED_ROOT_VAR] == str(ROOT)

    assert _load_paths().ROOT == ROOT


def test_no_policy_var_is_visible_to_a_test_by_default():
    leftover = [
        name
        for name in os.environ
        if name.startswith(conftest.ENV_PREFIX)
        and name != conftest.PINNED_ROOT_VAR
        and name not in conftest.PRESERVED_ENV_VARS
    ]
    assert leftover == [], f"ambient policy config reached the suite: {leftover}"


def test_scrub_is_deny_by_default_so_a_new_policy_var_needs_no_edit_here():
    env = {
        "PATH": "/usr/bin",
        "DASLAB_ROOT": "/somewhere/else",
        "DASLAB_WS_E_FLAG": "false",
        "DASLAB_A_KNOB_ADDED_LATER": "1",
        "DASLAB_DOCKER_BIN": "podman",
    }
    assert conftest.scrubbed_env_vars(env) == ["DASLAB_A_KNOB_ADDED_LATER", "DASLAB_WS_E_FLAG"]


def test_documented_engine_knobs_survive_the_scrub():


    assert "DASLAB_DOCKER_BIN" in conftest.PRESERVED_ENV_VARS
    assert conftest.scrubbed_env_vars({"DASLAB_DOCKER_BIN": "podman"}) == []


def test_the_sandbox_image_is_scrubbed_because_it_can_mask_an_escape():


    assert "DASLAB_SANDBOX_IMAGE" not in conftest.PRESERVED_ENV_VARS
    assert conftest.scrubbed_env_vars({"DASLAB_SANDBOX_IMAGE": "thin:latest"}) == [
        "DASLAB_SANDBOX_IMAGE"
    ]


def test_hostile_ambient_env_cannot_reach_a_suite(tmp_path):
    hostile = {
        **os.environ,
        "DASLAB_ROOT": str(tmp_path),
        "DASLAB_WS_E_FLAG": "false",
        "DASLAB_INFRA_MCP": "mcp__playwright",
    }


    target = [
        "-m",
        "pytest",
        "tests/test_check_attestation.py",
        "tests/test_ws_e_health_check.py",
        "tests/test_ws_a_tool_bridge.py",
        "tests/test_ws_e_rbac_audit_export.py",
        "-q",
        "-p",
        "no:cacheprovider",
    ]

    with_seam = subprocess.run(
        [sys.executable, *target], cwd=ROOT, env=hostile, capture_output=True, text=True
    )
    assert with_seam.returncode == 0, with_seam.stdout[-3000:]


    without_seam = subprocess.run(
        [sys.executable, *target, "--noconftest"],
        cwd=ROOT,
        env=hostile,
        capture_output=True,
        text=True,
    )
    assert without_seam.returncode != 0, (
        "the control passed: this suite no longer depends on the ambient environment, "
        "so the proof above is vacuous and this test needs a different target"
    )
