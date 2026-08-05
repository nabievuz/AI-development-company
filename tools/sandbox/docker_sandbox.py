#!/usr/bin/env python3

from __future__ import annotations

import atexit
import contextlib
import grp
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import (
    ExecResult,
    Mount,
    ResourceLimits,
    SandboxEscapeError,
    SandboxHandle,
    SandboxScope,
    ScopedSecret,
)
from local_stub import LocalStubSandbox

_PINNED_ALPINE = "alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc"
_IMAGE = os.environ.get("DASLAB_SANDBOX_IMAGE", _PINNED_ALPINE)
_DOCKER = os.environ.get("DASLAB_DOCKER_BIN", "docker")
_OP_TIMEOUT = 60
_PULL_TIMEOUT = 300

_SOCKET_GROUP = os.environ.get("DASLAB_DOCKER_GROUP", "docker")

DEFAULT_RUN_AS = "65534:65534"
CONTAINER_NETWORK_MODE = "none"
CONTAINER_NAME_PREFIX = "daslab-sbx-"
SANDBOX_LABEL = "daslab.sandbox=1"

RUNTIME_DIR = "/run/daslab"
PID_DIR = f"{RUNTIME_DIR}/pid"
CREDENTIALS_FILE = f"{RUNTIME_DIR}/credentials.env"

CREDENTIAL_DELIVERY_POSTURE = (
    "credential values are streamed into the container over docker exec stdin and land only in an "
    "in-container tmpfs file created under umask 077; they never appear in docker run argv, never "
    "appear in the container config env that 'docker inspect' prints, and this module never writes "
    "them to any host file"
)

_RUN_AS_PATTERN = re.compile(r"^[1-9][0-9]*:[0-9]+$")
_DIGEST_REFERENCE_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_SETUP_SCRIPT = f"umask 077; mkdir -p {PID_DIR} && cat > {CREDENTIALS_FILE}"


class ImagePinError(RuntimeError):
    pass


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


_LIVE_CONTAINERS: set[str] = set()


def _remove_container(name: str) -> None:
    with contextlib.suppress(Exception):
        _run([_DOCKER, "rm", "-f", name], capture_output=True, timeout=_OP_TIMEOUT)
    _LIVE_CONTAINERS.discard(name)


@atexit.register
def _remove_surviving_containers() -> None:
    for name in sorted(_LIVE_CONTAINERS):
        _remove_container(name)


def _container_name(task_id: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in task_id)
    return f"{CONTAINER_NAME_PREFIX}{safe}-{secrets.token_hex(6)}"


def is_digest_pinned(reference: str) -> bool:
    return bool(_DIGEST_REFERENCE_PATTERN.match(reference))


def _repo_digest(reference: str) -> str | None:
    proc = _run(
        [_DOCKER, "image", "inspect", reference, "--format", "{{index .RepoDigests 0}}"],
        capture_output=True, text=True, timeout=_OP_TIMEOUT,
    )
    if proc.returncode != 0:
        return None
    candidate = (proc.stdout or "").strip()
    return candidate if is_digest_pinned(candidate) else None


def pin_image_reference(reference: str) -> str:
    if is_digest_pinned(reference):
        return reference
    digest = _repo_digest(reference)
    if digest is None:
        _run([_DOCKER, "pull", reference], capture_output=True, text=True, timeout=_PULL_TIMEOUT)
        digest = _repo_digest(reference)
    if digest is None:
        raise ImagePinError(
            f"refusing to start a sandbox from unpinned image {reference!r}: "
            "no sha256 repo digest is available for it"
        )
    return digest


def credential_script(credentials: list[ScopedSecret]) -> str:
    lines = []
    for cred in credentials:
        if not _ENV_NAME_PATTERN.match(cred.name):
            raise SandboxEscapeError(
                f"open() refused: credential name {cred.name!r} is not a shell-safe identifier"
            )
        lines.append(f"export {cred.name}={shlex.quote(cred.value)}\n")
    return "".join(lines)


def build_run_argv(
    *,
    container_name: str,
    image_reference: str,
    workdir: str,
    mount_mode: str,
    limits: ResourceLimits,
    run_as: str = DEFAULT_RUN_AS,
) -> list[str]:
    if not _RUN_AS_PATTERN.match(run_as):
        raise SandboxEscapeError(
            f"run_as {run_as!r} refused: expected 'uid:gid' with a non-root uid"
        )
    if not is_digest_pinned(image_reference):
        raise ImagePinError(f"image reference {image_reference!r} is not pinned to a sha256 digest")
    return [
        _DOCKER, "run", "-d", "--name", container_name,
        "--init",
        "--network", CONTAINER_NETWORK_MODE,
        "--user", run_as,
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
        "--tmpfs", f"{RUNTIME_DIR}:rw,nosuid,nodev,noexec,size=4m,mode=1777",
        "--cpus", str(limits.cpu_limit),
        "--memory", f"{limits.mem_limit_mb}m",
        "--memory-swap", f"{limits.mem_limit_mb}m",
        "--pids-limit", str(limits.pids_limit),
        "--label", SANDBOX_LABEL,
        "-v", f"{workdir}:/work:{mount_mode}",
        "-w", "/work",
        image_reference, "tail", "-f", "/dev/null",
    ]


def build_exec_script(exec_id: str) -> str:
    pid_file = f"{PID_DIR}/{shlex.quote(exec_id)}"
    return (
        f". {CREDENTIALS_FILE}; "
        '"$0" "$@" & _child=$!; '
        f'echo "$$ $_child" > {pid_file}; '
        'wait "$_child"; _status=$?; '
        f"rm -f {pid_file}; "
        'exit "$_status"'
    )


def build_kill_script(exec_id: str) -> str:
    pid_file = f"{PID_DIR}/{shlex.quote(exec_id)}"
    return (
        f"read _shell _child < {pid_file} 2>/dev/null || exit 3; "
        f"rm -f {pid_file}; "
        '[ -n "$_shell" ] || exit 3; '
        'kill -9 -"$_shell" 2>/dev/null; '
        'kill -9 "$_shell" "$_child" 2>/dev/null; '
        "exit 0"
    )


class DockerSandbox(LocalStubSandbox):

    def __init__(self, image: str | None = None, run_as: str = DEFAULT_RUN_AS) -> None:
        super().__init__()
        if not _RUN_AS_PATTERN.match(run_as):
            raise SandboxEscapeError(
                f"DockerSandbox(run_as={run_as!r}) refused: expected 'uid:gid' with a non-root uid"
            )
        self._image = image or _IMAGE
        self._run_as = run_as
        self._pinned_image_reference: str | None = None
        self._containers: dict[str, str] = {}

    def pinned_image(self) -> str:
        if self._pinned_image_reference is None:
            self._pinned_image_reference = pin_image_reference(self._image)
        return self._pinned_image_reference

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        handle = super().open(task_id=task_id, scope=scope)
        reg = self._registry[task_id]

        primary = (scope.workdir_mounts or [Mount(host_path=str(reg.workdir))])[0]
        workdir = primary.host_path
        os.makedirs(workdir, exist_ok=True)
        mount_mode = "ro" if primary.read_only else "rw"
        name = _container_name(task_id)

        try:
            script = credential_script(scope.credentials)
            argv = build_run_argv(
                container_name=name,
                image_reference=self.pinned_image(),
                workdir=workdir,
                mount_mode=mount_mode,
                limits=scope.resource_limits,
                run_as=self._run_as,
            )
            proc = _run(argv, capture_output=True, text=True, timeout=_OP_TIMEOUT)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"DockerSandbox.open failed for {task_id!r}: {(proc.stderr or '').strip()}"
                )
            _LIVE_CONTAINERS.add(name)
            setup = _run(
                [_DOCKER, "exec", "-i", name, "sh", "-c", _SETUP_SCRIPT],
                input=script, capture_output=True, text=True, timeout=_OP_TIMEOUT,
            )
            if setup.returncode != 0:
                raise RuntimeError(
                    f"DockerSandbox.open could not prepare the runtime dir for {task_id!r}: "
                    f"{(setup.stderr or '').strip()}"
                )
        except BaseException:
            _remove_container(name)
            super().close(handle)
            raise

        self._containers[task_id] = name
        return handle

    def close(self, handle: SandboxHandle) -> None:
        name = self._containers.pop(handle.task_id, None)
        if name:
            _remove_container(name)
        super().close(handle)

    def close_all(self) -> None:
        for task_id in list(self._containers):
            name = self._containers.pop(task_id)
            _remove_container(name)

    def container_name(self, handle: SandboxHandle) -> str | None:
        return self._containers.get(handle.task_id)

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
        exec_id = secrets.token_hex(8)
        try:
            proc = _run(
                [_DOCKER, "exec", name, "sh", "-c", build_exec_script(exec_id), *command],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            killed = self._terminate_in_container(name, exec_id)
            outcome = "in-container process killed" if killed else "in-container process not found"
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"resource limit: wallclock timeout ({timeout}s) — {outcome}",
            )
        return ExecResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:cap],
            stderr=(proc.stderr or "")[:cap],
        )

    def _terminate_in_container(self, name: str, exec_id: str) -> bool:
        try:
            proc = _run(
                [_DOCKER, "exec", name, "sh", "-c", build_kill_script(exec_id)],
                capture_output=True, text=True, timeout=_OP_TIMEOUT,
            )
        except Exception:
            return False
        return proc.returncode == 0
