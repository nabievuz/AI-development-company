"""``SandboxBackend`` contract + shared value types — DasLab WS-C (ADR-0035 LG-5,
`docs/design/ws-c-langgraph-loop.md` §5, DAS-1565, FR-006).

This module has **zero optional/third-party dependencies** — stdlib only — so
it is importable and unit-testable with nothing installed. It defines the
*shape* every sandbox backend (the host-free ``LocalStubSandbox`` built here,
and the live ``DockerSandbox`` scoped to the blocked DAS-1566) must satisfy,
plus the four fail-closed walls' shared vocabulary: ``Mount``, ``ScopedSecret``,
``ResourceLimits``, ``SandboxScope``, ``SandboxHandle``, ``ExecResult``, and the
``SandboxEscapeError`` every wall's refusal path raises or returns.

**Escape-prevention (design §5.3):** any reach the scope did not explicitly
grant is refused, not best-effort allowed. A denied call returns an
``ExecResult`` with ``ok=False`` (never raises for an ordinary policy refusal
inside :meth:`SandboxBackend.exec`) **or** the caller may choose to treat a
refusal as exceptional via :class:`SandboxEscapeError` — both paths guarantee
**no side effect**. This module fixes that vocabulary so DAS-1567's escape
tests are written once, against the stub, and re-run unchanged against
DAS-1566's live backend (design §5.3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class SandboxEscapeError(Exception):
    """Raised when a caller demands a reach the scope did not grant.

    Fail-closed: raising this (or returning a denied :class:`ExecResult`,
    depending on the call site) must never be preceded by the side effect it
    describes — the check always runs *before* any host/repo/network/credential
    action, never after.
    """


@dataclass(frozen=True)
class Mount:
    """One workdir mount the sandbox exposes to the task.

    ``host_path`` is the *only* path an in-sandbox relative path may resolve
    under. ``read_only`` denies writes even inside the mount (host wall,
    design §5.2 item 1) — the stub enforces this at the syscall-analogue layer
    (``open``/``write`` refusal), not just as a hint.
    """

    host_path: str
    read_only: bool = False


@dataclass(frozen=True)
class ScopedSecret:
    """A single gate-approved, ttl'd, task-scoped credential grant.

    Per ADR-0012 (no-secrets-by-default) + Tier-M: only the **fact of grant**
    (``name``, ``scope``, ``ttl_seconds``) is metadata-safe to carry in an
    event. ``value`` is the actual secret material and MUST NEVER be logged,
    serialized into an event, or otherwise leave the process boundary that
    consumes it — callers building an event from a ``ScopedSecret`` must read
    only :meth:`to_event_fields`, never ``value`` directly.
    """

    name: str
    value: str
    scope: str  # e.g. the task_id it is scoped to — never "*"/global
    ttl_seconds: int

    def to_event_fields(self) -> dict[str, object]:
        """Tier-M-safe projection: fact-of-grant + scope + ttl — never ``value``."""
        return {"name": self.name, "scope": self.scope, "ttl_seconds": self.ttl_seconds}


@dataclass(frozen=True)
class ResourceLimits:
    """cpu / mem / pids / wallclock caps — the fork-bomb + runaway guard.

    The stub enforces ``wallclock_seconds`` (a real timeout around ``exec``)
    and ``max_argv_len``/``max_output_bytes`` as host-free approximations of
    what the live backend enforces via cgroups/container limits.
    """

    cpu_limit: float = 1.0
    mem_limit_mb: int = 512
    pids_limit: int = 64
    wallclock_seconds: float = 30.0
    max_output_bytes: int = 1_000_000


@dataclass(frozen=True)
class SandboxScope:
    """The explicit grant a sandbox is opened with — design §5.1.

    Deny-by-default in every field: ``workdir_mounts`` names the ONLY visible
    paths, ``egress_profile`` is empty unless a profile is named,
    ``credentials`` is empty unless explicitly granted. Nothing not named
    here is reachable.
    """

    task_id: str
    workdir_mounts: list[Mount] = field(default_factory=list)
    egress_profile: str = ""
    credentials: list[ScopedSecret] = field(default_factory=list)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    egress_allowlist: list[str] = field(default_factory=list)  # domains for egress_profile


@dataclass(frozen=True)
class SandboxHandle:
    """Opaque handle returned by :meth:`SandboxBackend.open`."""

    task_id: str
    backend: str
    # Backend-private token; the stub uses it to look up its per-task workdir.
    token: str


@dataclass(frozen=True)
class ExecResult:
    """Outcome of one :meth:`SandboxBackend.exec` call.

    A refused call (any wall) returns ``ok=False`` with ``exit_code=-1`` and a
    human-readable, secret-free ``denied_reason`` naming which wall fired —
    never a partial/side-effecting result.
    """

    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    denied_reason: str = ""


@runtime_checkable
class SandboxBackend(Protocol):
    """The contract every sandbox backend implements — design §5.1.

    ``LocalStubSandbox`` (this package) is the host-free reference
    implementation. ``DockerSandbox`` (E2B/OpenHands, real Docker/E2B host) is
    the live implementation — DAS-1566, blocked, not built here. Both must
    enforce the SAME refusal decisions (design §5.3) so a test written against
    one passes unchanged against the other.
    """

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        """Open (or reuse) the one sandbox for ``task_id``. Never shares state
        across ``task_id`` values (other-task wall, design §5.2 item 3)."""
        ...

    def exec(self, handle: SandboxHandle, argv: list[str]) -> ExecResult:
        """Run ``argv`` inside the sandbox named by ``handle``.

        Every wall is checked before any side effect: the working directory
        the command would touch must resolve inside a granted mount (host +
        repo walls), the handle's ``task_id`` must match the scope it was
        opened with (other-task wall), and any credential/egress the command
        implies must be within the granted scope (unscoped-credential wall).
        A refusal returns ``ExecResult(ok=False, ...)`` with no side effect.
        """
        ...

    def close(self, handle: SandboxHandle) -> None:
        """Tear down the sandbox for ``handle``. Idempotent."""
        ...
