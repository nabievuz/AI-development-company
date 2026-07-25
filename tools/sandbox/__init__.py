"""Per-task sandbox adapter — DasLab WS-C (ADR-0035 LG-5 / FR-006, DAS-1565).

Public surface: :class:`SandboxBackend` (the contract every backend implements),
:class:`LocalStubSandbox` (the host-free reference/stub backend built here), and
the shared value types (:class:`SandboxScope`, :class:`Mount`, :class:`ScopedSecret`,
:class:`ResourceLimits`, :class:`ExecResult`, :class:`SandboxHandle`,
:class:`SandboxEscapeError`).

The LIVE backend (``DockerSandbox`` — a real per-task Docker/podman container)
lives in ``docker_sandbox.py`` (DAS-1566). It is **absent-by-default**: the
driver shells out to the ``docker`` CLI (no third-party dependency), so this
package still ships importable + unit-testable with nothing installed —
:func:`docker_available` reports whether an engine is actually reachable, and
``LocalStubSandbox`` is used until one is, exactly the WS-A pattern
(``tools/mcp_bridges``). The live isolation smoke on a real host is DAS-1566.

Feature-flagged: behind ``ws_c_langgraph_loop`` (default OFF, see
``config/features.yaml``). With the flag OFF, :func:`flag_on` returns
``False`` and nothing in this package changes dispatch — the module is inert
until imported and used explicitly by the (also flagged-off) WS-C loop.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contract import (  # noqa: E402
    ExecResult,
    Mount,
    ResourceLimits,
    SandboxBackend,
    SandboxEscapeError,
    SandboxHandle,
    SandboxScope,
    ScopedSecret,
)
from flag import flag_on  # noqa: E402
from local_stub import LocalStubSandbox  # noqa: E402
from docker_sandbox import DockerSandbox, docker_available  # noqa: E402

__all__ = [
    "DockerSandbox",
    "ExecResult",
    "LocalStubSandbox",
    "Mount",
    "ResourceLimits",
    "SandboxBackend",
    "SandboxEscapeError",
    "SandboxHandle",
    "SandboxScope",
    "ScopedSecret",
    "docker_available",
    "flag_on",
]
