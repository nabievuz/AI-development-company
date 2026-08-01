"""Test-suite bootstrap: pin the repo root, scrub ambient DasLab policy config.

Two ambient-environment couplings used to decide test verdicts, and both were
invisible from the test files themselves.

**1. Two different repo roots.** Each test file derives its own root from
``Path(__file__).resolve().parents[1]``, while every script under ``scripts/``
takes ``ROOT`` from ``scripts/_paths.py``, which resolves ``DASLAB_ROOT`` first
and falls back to ``git rev-parse`` against the *process* CWD (LAW A: the root is
resolved at runtime, never written down). When those two disagree, the tests
assert against one tree while the code under test reads another. Setting the
documented ``DASLAB_ROOT`` knob — its stated purpose is "explicit override / CI /
containers" — made 40 tests across six health-check suites fail:

    DASLAB_ROOT=<empty dir> pytest tests/test_ws_{a,b,c,d,e,h}*health_check.py
    -> 2 + 4 + 7 + 2 + 14 + 11 failures

Tests in this tree must test *this* tree, so the root is pinned here, once, to
the directory holding this file. Pinning happens at import time because
``_paths.ROOT`` is a module-level constant: by the time a fixture could run, the
scripts have already been imported and the wrong root is baked in.

**2. Ambient policy vars beating the fixtures.** Several modules read a
``DASLAB_*`` setting *before* the argument a test passes them — e.g.
``scripts/rbac.py`` reads ``DASLAB_WS_E_FLAG`` ahead of its own ``features_path=``
— so an operator's shell could silently invert a security assertion rather than
merely erroring:

    DASLAB_INFRA_MCP=mcp__playwright         -> 5 deny/allow assertions flip
    DASLAB_WS_E_FLAG=false                   -> 4 failures
    DASLAB_BROWSER_ACTION_GRANTS=click,...   -> 2 failures

So policy configuration is scrubbed: a test that wants a flag, an allow-list or a
path must declare it (``monkeypatch.setenv``/``features_path=``), never inherit
it. The scrub is deny-by-default — a newly added ``DASLAB_*`` policy var is
removed without this file needing an update — with a short, explicit preserve
list for the knobs that select the *environment* rather than the policy.

Guarded by ``tests/test_conftest_env_isolation.py``, which proves the seam holds
by running a formerly-broken suite under a hostile environment, with
``--noconftest`` as the control.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Resolved to the tree these tests live in, overriding any ambient value.
PINNED_ROOT_VAR = "DASLAB_ROOT"

#: Ambient ``DASLAB_*`` names that survive the scrub: documented operator knobs
#: that select *which container engine* runs the sandbox. Removing them would
#: silently disable a documented workflow —
#: ``tests/test_ws_c_docker_sandbox.py``'s module docstring advertises
#: ``DASLAB_DOCKER_BIN=podman pytest ...`` — and an unusable value degrades to a
#: skip (``DASLAB_DOCKER_BIN=no-such-engine`` → ``1 passed, 10 skipped``), never
#: to a quietly weaker assertion.
#:
#: ``DASLAB_SANDBOX_IMAGE`` deliberately does NOT belong here, though it looks
#: like the same kind of knob. The isolation probes shell out to tools inside the
#: image, so a thinner image turns a probe into a pass: with ``--network none``
#: swapped for ``bridge`` in ``docker_sandbox.py`` — a real escape — the default
#: alpine:3.20 catches it (``1 failed``) while an image without ``wget`` reports
#: ``1 passed``. An ambient value that can mask an escape is policy, not
#: environment. (Unlike the other two it also hard-fails rather than skipping when
#: the image is unpullable.)
PRESERVED_ENV_VARS = frozenset(
    {
        "DASLAB_DOCKER_BIN",
        "DASLAB_DOCKER_GROUP",
    }
)

#: Prefix that marks configuration owned by the engine.
ENV_PREFIX = "DASLAB_"


def scrubbed_env_vars(environ: dict[str, str] | None = None) -> list[str]:
    """Return the ``DASLAB_*`` names this module removes, for a given environment.

    Pure helper (no mutation) so the policy can be asserted directly.
    """
    env = os.environ if environ is None else environ
    return sorted(
        name
        for name in env
        if name.startswith(ENV_PREFIX)
        and name != PINNED_ROOT_VAR
        and name not in PRESERVED_ENV_VARS
    )


# Applied at import: pytest loads this file before any test module, so the
# scripts under test see the pinned root and a policy-free environment when
# their module-level constants are evaluated.
for _name in scrubbed_env_vars():
    del os.environ[_name]
os.environ[PINNED_ROOT_VAR] = str(REPO_ROOT)
