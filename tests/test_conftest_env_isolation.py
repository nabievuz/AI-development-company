"""Guards ``tests/conftest.py``: the ambient environment must not reach the suite.

The seam exists because two couplings used to decide verdicts from outside the
test files — a ``DASLAB_ROOT`` pointing at a different tree than the one under
test (40 failures across six health-check suites), and ``DASLAB_*`` policy vars
that some modules read ahead of the argument a test passes them (11 more, some of
which inverted a deny/allow assertion rather than erroring).

A conftest is invisible plumbing, so it is proven rather than trusted: the last
test here runs a formerly-broken suite under a hostile environment and requires
it to pass, with ``--noconftest`` as the control that must fail.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _loaded_conftest():
    """The conftest instance pytest actually loaded, found by ``__file__``.

    Taken from ``sys.modules`` rather than re-imported: a second import would
    re-run the module-level scrub, and asserting against a freshly executed copy
    would prove nothing about the one in force. Matched on the resolved path
    rather than a module name because the name depends on the import mode
    (``tests.conftest`` under rootdir insertion, ``conftest`` under a plain
    ``prepend`` with no ``tests/__init__.py``).
    """
    want = (ROOT / "tests" / "conftest.py").resolve()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve() == want:
            return module
    return None


conftest = _loaded_conftest()

if conftest is None:
    # Reached under `pytest --noconftest`, where the seam is genuinely off. Skip
    # rather than assert: a module-level assert turns that debug mode into a
    # collection error for the whole run instead of skipping these six guards.
    pytest.skip(
        "tests/conftest.py is not loaded (--noconftest?) — the env seam is not in "
        "force, so there is nothing here to guard",
        allow_module_level=True,
    )


def _load_paths():
    """Load ``scripts/_paths.py`` the way every script does."""
    spec = importlib.util.spec_from_file_location(
        "_paths_for_conftest_test", ROOT / "scripts" / "_paths.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_conftest_under_test_is_the_one_in_this_tree():
    # Guards the other tests here: if `import conftest` ever resolved elsewhere,
    # they would assert against a stranger and pass for the wrong reason.
    assert Path(conftest.__file__).resolve() == (ROOT / "tests" / "conftest.py").resolve()
    assert conftest.REPO_ROOT == ROOT


def test_root_is_pinned_to_the_tree_the_tests_live_in():
    assert os.environ[conftest.PINNED_ROOT_VAR] == str(ROOT)
    # The seam's whole point: the scripts' root and the test files' root agree.
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
    # tests/test_ws_c_docker_sandbox.py's docstring advertises DASLAB_DOCKER_BIN;
    # scrubbing it would silently disable a documented workflow. These select the
    # engine, not what a policy permits.
    assert "DASLAB_DOCKER_BIN" in conftest.PRESERVED_ENV_VARS
    assert conftest.scrubbed_env_vars({"DASLAB_DOCKER_BIN": "podman"}) == []


def test_the_sandbox_image_is_scrubbed_because_it_can_mask_an_escape():
    # It looks like an engine knob but is not one: the isolation probes shell out
    # to tools inside the image, so a thinner image turns a probe into a pass. With
    # `--network none` swapped for `bridge` in docker_sandbox.py — a real escape —
    # alpine:3.20 fails the network test while an image without wget passes it.
    assert "DASLAB_SANDBOX_IMAGE" not in conftest.PRESERVED_ENV_VARS
    assert conftest.scrubbed_env_vars({"DASLAB_SANDBOX_IMAGE": "thin:latest"}) == [
        "DASLAB_SANDBOX_IMAGE"
    ]


def test_hostile_ambient_env_cannot_reach_a_suite(tmp_path):
    """Proof with a control: same command, same hostile env, seam on vs seam off."""
    hostile = {
        **os.environ,
        "DASLAB_ROOT": str(tmp_path),  # a real dir that is NOT this tree
        "DASLAB_WS_E_FLAG": "false",  # read ahead of rbac.py's features_path=
        "DASLAB_INFRA_MCP": "mcp__playwright",
    }
    # One target per hostile setting, so the proof covers the SCRUB and not just
    # the root pin: test_ws_e_health_check alone is insensitive to both policy
    # vars, which would leave a seam that scrubbed nothing looking green here.
    #
    # test_check_attestation is the load-bearing one for WHEN the seam runs. It
    # does `import check_attestation` at module level, so its root is resolved
    # during collection; the other three load their modules lazily inside tests,
    # which an autouse fixture would still be early enough for. Without this
    # target, moving the seam out of import scope into a fixture passes every
    # guard here while taking the full suite to "4 errors during collection".
    target = [
        "-m",
        "pytest",
        "tests/test_check_attestation.py",  # resolves the root at IMPORT time
        "tests/test_ws_e_health_check.py",  # needs the pinned root
        "tests/test_ws_a_tool_bridge.py",  # sensitive to DASLAB_INFRA_MCP
        "tests/test_ws_e_rbac_audit_export.py",  # sensitive to DASLAB_WS_E_FLAG
        "-q",
        "-p",
        "no:cacheprovider",
    ]

    with_seam = subprocess.run(
        [sys.executable, *target], cwd=ROOT, env=hostile, capture_output=True, text=True
    )
    assert with_seam.returncode == 0, with_seam.stdout[-3000:]

    # Control: without the conftest the same run must fail, so the assertion above
    # cannot be passing for some unrelated reason.
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
