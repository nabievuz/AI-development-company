#!/usr/bin/env python3
"""``DockerSandbox`` — the live per-task sandbox backend, DasLab WS-C (DAS-1566).

The real counterpart to ``LocalStubSandbox``: it enforces the SAME four
fail-closed walls with the SAME refusal decisions and messages (so the DAS-1565
contract tests pass unchanged against it), and ADDS a genuine kernel/namespace
isolation boundary — one Docker container per ``task_id`` with the task workdir
bind-mounted at ``/work``, ``--network none`` (egress deny-all), cgroup
cpu/mem/pids limits, a read-only root filesystem (+ tmpfs ``/tmp``), and only
gate-approved, task-scoped credentials injected as environment.

Absent-by-default (ADR-0033 TB-1 / WS-A pattern): imported only where a Docker
engine exists. It shells out to the ``docker`` CLI — **no python dependency**;
set ``DASLAB_DOCKER_BIN=podman`` to drive a rootless podman instead.
:func:`docker_available` is the presence probe the WS-C loop and the live tests
use to skip when no engine is installed.

Design (ADR-0010 C1 — consume, don't rebuild): it SUBCLASSES
``LocalStubSandbox`` so every wall decision, message string, temp-workdir and
token issuance is inherited verbatim. ``open``/``close`` additionally manage the
container lifecycle, and :meth:`exec_in_container` is the REAL untrusted-code
path the DAS-1566 live isolation smoke drives — the thing the stub cannot do
(run actual code) and must not let escape (host / repo / other-task / unscoped
credential / network all unreachable from inside).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import ExecResult, Mount, SandboxHandle, SandboxScope  # noqa: E402
from local_stub import LocalStubSandbox  # noqa: E402

_IMAGE = os.environ.get("DASLAB_SANDBOX_IMAGE", "alpine:3.20")
_DOCKER = os.environ.get("DASLAB_DOCKER_BIN", "docker")
_OP_TIMEOUT = 60


def docker_available() -> bool:
    """True iff the configured container CLI is on PATH and its daemon answers.

    ``DASLAB_DOCKER_BIN`` selects the binary (``docker`` default, or ``podman``).
    Used to skip every live path/test when no engine is installed — the whole
    point of absent-by-default.
    """
    if shutil.which(_DOCKER) is None:
        return False
    try:
        proc = subprocess.run([_DOCKER, "info"], capture_output=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


def _container_name(task_id: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in task_id)
    return f"daslab-sbx-{safe}"


class DockerSandbox(LocalStubSandbox):
    """Live backend — inherits every wall decision, adds a real container.

    The inherited (host-free) file verbs act on the per-task temp workdir, which
    is ALSO the container's bind-mounted ``/work`` — so a file written through
    the ``write`` verb is visible to real in-container code, while nothing the
    scope did not grant (the host, the repo, another task, the network, an
    unscoped credential) is reachable from inside.
    """

    def __init__(self, image: str | None = None) -> None:
        super().__init__()
        self._image = image or _IMAGE
        self._containers: dict[str, str] = {}  # task_id -> container name

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        # Reuse ALL of the stub's fail-closed OPEN-time validation (empty
        # task_id, scope.task_id mismatch, cross-task credential) + temp workdir
        # + token issuance. These raise SandboxEscapeError BEFORE any container
        # is created — a rejected scope never starts a container.
        handle = super().open(task_id=task_id, scope=scope)
        reg = self._registry[task_id]
        # Bind-mount the SAME directory the inherited file verbs resolve against
        # (the scope's granted worktree; the stub's temp workdir only when no
        # mount was granted) so host-side writes and in-container code agree on
        # /work. A read_only mount maps to a :ro bind.
        primary = (scope.workdir_mounts or [Mount(host_path=str(reg.workdir))])[0]
        workdir = primary.host_path
        os.makedirs(workdir, exist_ok=True)
        mount_mode = "ro" if primary.read_only else "rw"
        name = _container_name(task_id)
        # Idempotent: clear any stale container of this name first.
        subprocess.run([_DOCKER, "rm", "-f", name], capture_output=True, timeout=_OP_TIMEOUT)
        rl = scope.resource_limits
        argv = [
            _DOCKER, "run", "-d", "--name", name,
            "--network", "none",
            "--cpus", str(rl.cpu_limit),
            "--memory", f"{rl.mem_limit_mb}m",
            "--pids-limit", str(rl.pids_limit),
            "--read-only", "--tmpfs", "/tmp",
            "-v", f"{workdir}:/work:{mount_mode}", "-w", "/work",
        ]
        # Gate-approved, task-scoped credentials → env inside the container ONLY
        # (never on the host, never in an event — ADR-0012 / Tier-M). open()
        # already refused any credential whose scope != task_id.
        for cred in scope.credentials:
            argv += ["-e", f"{cred.name}={cred.value}"]
        # Keep the container alive without relying on `sleep infinity` (not
        # supported by every busybox); `tail -f /dev/null` is universal.
        argv += [self._image, "tail", "-f", "/dev/null"]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=_OP_TIMEOUT)
        if proc.returncode != 0:
            # Fail-closed: no live container ⇒ tear the registration down too, so
            # a caller can never hold a handle to a half-open sandbox.
            super().close(handle)
            raise RuntimeError(f"DockerSandbox.open failed for {task_id!r}: {proc.stderr.strip()}")
        self._containers[task_id] = name
        return handle

    def close(self, handle: SandboxHandle) -> None:
        name = self._containers.pop(handle.task_id, None)
        if name:
            subprocess.run([_DOCKER, "rm", "-f", name], capture_output=True, timeout=_OP_TIMEOUT)
        super().close(handle)

    # -- the REAL untrusted-code path (DAS-1566 live isolation smoke) --------- #
    def exec_in_container(self, handle: SandboxHandle, command: list[str]) -> ExecResult:
        """Run *command* INSIDE the task's container via ``docker exec`` — the
        genuine isolation boundary the stub cannot provide. Still gated by the
        other-task wall: a stale/foreign handle (token mismatch, closed, or no
        live container) is refused with no side effect."""
        reg = self._registry.get(handle.task_id)
        if reg is None or reg.closed or getattr(reg, "token", None) != handle.token:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason="other-task wall: no live sandbox / handle token mismatch",
            )
        name = self._containers.get(handle.task_id)
        if not name:
            return ExecResult(ok=False, exit_code=-1, denied_reason="other-task wall: no live container")
        if not command:
            return ExecResult(ok=False, exit_code=-1, denied_reason="empty command refused")
        cap = reg.scope.resource_limits.max_output_bytes
        timeout = reg.scope.resource_limits.wallclock_seconds or 30.0
        try:
            proc = subprocess.run(
                [_DOCKER, "exec", name, *command],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"resource limit: wallclock timeout ({timeout}s) — command killed",
            )
        return ExecResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:cap],
            stderr=(proc.stderr or "")[:cap],
        )
