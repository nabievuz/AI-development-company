from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class SandboxEscapeError(Exception):
    pass


@dataclass(frozen=True)
class Mount:

    host_path: str
    read_only: bool = False


@dataclass(frozen=True)
class ScopedSecret:

    name: str
    value: str
    scope: str
    ttl_seconds: int

    def to_event_fields(self) -> dict[str, object]:
        return {"name": self.name, "scope": self.scope, "ttl_seconds": self.ttl_seconds}


@dataclass(frozen=True)
class ResourceLimits:

    cpu_limit: float = 1.0
    mem_limit_mb: int = 512
    pids_limit: int = 64
    wallclock_seconds: float = 30.0
    max_output_bytes: int = 1_000_000


@dataclass(frozen=True)
class SandboxScope:

    task_id: str
    workdir_mounts: list[Mount] = field(default_factory=list)
    egress_profile: str = ""
    credentials: list[ScopedSecret] = field(default_factory=list)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    egress_allowlist: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SandboxHandle:

    task_id: str
    backend: str

    token: str


@dataclass(frozen=True)
class ExecResult:

    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    denied_reason: str = ""


@runtime_checkable
class SandboxBackend(Protocol):

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        ...

    def exec(self, handle: SandboxHandle, argv: list[str]) -> ExecResult:
        ...

    def close(self, handle: SandboxHandle) -> None:
        ...
