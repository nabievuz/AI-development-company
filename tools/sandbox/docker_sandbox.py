#!/usr/bin/env python3

from __future__ import annotations

import grp
import os
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import ExecResult, Mount, SandboxHandle, SandboxScope
from local_stub import LocalStubSandbox

_IMAGE = os.environ.get("DASLAB_SANDBOX_IMAGE", "alpine:3.20")
_DOCKER = os.environ.get("DASLAB_DOCKER_BIN", "docker")
_OP_TIMEOUT = 60

_SOCKET_GROUP = os.environ.get("DASLAB_DOCKER_GROUP", "docker")


def _daemon_ok(argv: list[str]) -> bool:
    try:
        return subprocess.run(argv, capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def _group_stale() -> bool:
    try:
        gr = grp.getgrnam(_SOCKET_GROUP)
    except (KeyError, OSError):
        return False
    if gr.gr_gid in os.getgroups():
        return False
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    return bool(user) and user in gr.gr_mem


def _compute_group_prefix() -> list[str]:
    if shutil.which(_DOCKER) is None:
        return []
    if _daemon_ok([_DOCKER, "info"]):
        return []
    if _group_stale() and shutil.which("sg"):
        prefix = ["sg", _SOCKET_GROUP, "-c"]
        if _daemon_ok(prefix + [shlex.join([_DOCKER, "info"])]):
            return prefix
    return []


_GROUP_PREFIX_CACHE: list[str] | None = None


def _group_prefix() -> list[str]:
    global _GROUP_PREFIX_CACHE
    if _GROUP_PREFIX_CACHE is None:
        _GROUP_PREFIX_CACHE = _compute_group_prefix()
    return _GROUP_PREFIX_CACHE


def _run(argv: list[str], **kwargs):
    prefix = _group_prefix()
    if prefix:
        argv = [*prefix, shlex.join(argv)]
    return subprocess.run(argv, **kwargs)


def docker_available() -> bool:
    if shutil.which(_DOCKER) is None:
        return False
    try:
        return _run([_DOCKER, "info"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def _container_name(task_id: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in task_id)
    return f"daslab-sbx-{safe}"


class DockerSandbox(LocalStubSandbox):

    def __init__(self, image: str | None = None) -> None:
        super().__init__()
        self._image = image or _IMAGE
        self._containers: dict[str, str] = {}

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:


        handle = super().open(task_id=task_id, scope=scope)
        reg = self._registry[task_id]


        primary = (scope.workdir_mounts or [Mount(host_path=str(reg.workdir))])[0]
        workdir = primary.host_path
        os.makedirs(workdir, exist_ok=True)
        mount_mode = "ro" if primary.read_only else "rw"
        name = _container_name(task_id)

        _run([_DOCKER, "rm", "-f", name], capture_output=True, timeout=_OP_TIMEOUT)
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


        for cred in scope.credentials:
            argv += ["-e", f"{cred.name}={cred.value}"]


        argv += [self._image, "tail", "-f", "/dev/null"]
        proc = _run(argv, capture_output=True, text=True, timeout=_OP_TIMEOUT)
        if proc.returncode != 0:


            super().close(handle)
            raise RuntimeError(f"DockerSandbox.open failed for {task_id!r}: {proc.stderr.strip()}")
        self._containers[task_id] = name
        return handle

    def close(self, handle: SandboxHandle) -> None:
        name = self._containers.pop(handle.task_id, None)
        if name:
            _run([_DOCKER, "rm", "-f", name], capture_output=True, timeout=_OP_TIMEOUT)
        super().close(handle)


    def exec_in_container(self, handle: SandboxHandle, command: list[str]) -> ExecResult:
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
            proc = _run(
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
