from __future__ import annotations

import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import (
    ExecResult,
    Mount,
    SandboxBackend,
    SandboxEscapeError,
    SandboxHandle,
    SandboxScope,
)

_KNOWN_VERBS = frozenset({"read", "write", "exists", "net", "cred", "sleep"})


@dataclass
class _Registration:
    task_id: str
    scope: SandboxScope
    workdir: Path
    opened_at: float = field(default_factory=time.monotonic)
    closed: bool = False


def _resolve_within(mount_root: Path, rel: str) -> Path | None:
    if not rel:
        return None
    try:
        candidate_raw = Path(rel)
        if candidate_raw.is_absolute():
            return None
        if ".." in candidate_raw.parts:
            return None
        root = mount_root.resolve()
        candidate = (mount_root / candidate_raw).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):


        return None
    return candidate


class LocalStubSandbox(SandboxBackend):

    def __init__(self) -> None:
        self._registry: dict[str, _Registration] = {}


    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        if not task_id:
            raise SandboxEscapeError("open() refused: empty task_id")
        if scope.task_id != task_id:


            raise SandboxEscapeError(
                f"open() refused: scope.task_id {scope.task_id!r} != task_id {task_id!r}"
            )
        for cred in scope.credentials:
            if cred.scope != task_id:
                raise SandboxEscapeError(
                    f"open() refused: credential {cred.name!r} scoped to "
                    f"{cred.scope!r}, not this task {task_id!r} (unscoped-credential wall)"
                )
        if task_id in self._registry and not self._registry[task_id].closed:
            reg = self._registry[task_id]
        else:
            workdir = Path(mkdtemp(prefix=f"daslab-sandbox-{task_id}-"))
            reg = _Registration(task_id=task_id, scope=scope, workdir=workdir)
            self._registry[task_id] = reg
        token = secrets.token_hex(16)
        reg.token = token
        return SandboxHandle(task_id=task_id, backend="local-stub", token=token)

    def exec(self, handle: SandboxHandle, argv: list[str]) -> ExecResult:
        reg = self._registry.get(handle.task_id)
        if reg is None or reg.closed:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"other-task wall: no live sandbox for task_id {handle.task_id!r}",
            )
        if getattr(reg, "token", None) != handle.token:

            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason="other-task wall: handle token does not match live registration",
            )
        if not argv:
            return ExecResult(ok=False, exit_code=-1, denied_reason="empty argv refused")

        verb, *args = argv
        if verb not in _KNOWN_VERBS:
            return ExecResult(ok=False, exit_code=-1, denied_reason=f"unknown verb {verb!r} refused (fail-closed)")

        if verb == "sleep":
            return self._exec_sleep(reg, args)
        if verb == "net":
            return self._exec_net(reg, args)
        if verb == "cred":
            return self._exec_cred(reg, args)
        return self._exec_fileop(reg, verb, args)

    def close(self, handle: SandboxHandle) -> None:
        reg = self._registry.get(handle.task_id)
        if reg is not None:
            reg.closed = True


    def _mounts(self, reg: _Registration) -> list[Mount]:
        return reg.scope.workdir_mounts or [Mount(host_path=str(reg.workdir))]

    def _exec_fileop(self, reg: _Registration, verb: str, args: list[str]) -> ExecResult:
        if not args:
            return ExecResult(ok=False, exit_code=-1, denied_reason=f"{verb} requires a path argument")
        rel = args[0]
        want_write = verb == "write"
        target = None
        chosen_mount = None
        for mount in self._mounts(reg):
            root = Path(mount.host_path)
            resolved = _resolve_within(root, rel)
            if resolved is not None:
                target = resolved
                chosen_mount = mount
                break
        if target is None:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=(
                    f"host/repo wall: path {rel!r} escapes every granted workdir mount "
                    "(absolute path, '..' traversal, or outside the task's own worktree)"
                ),
            )
        if want_write and chosen_mount is not None and chosen_mount.read_only:
            return ExecResult(ok=False, exit_code=-1, denied_reason=f"mount {chosen_mount.host_path!r} is read-only")

        if verb == "read":
            if not target.is_file():
                return ExecResult(ok=False, exit_code=1, stderr=f"no such file: {rel}")
            return ExecResult(ok=True, exit_code=0, stdout=target.read_text(encoding="utf-8", errors="replace"))
        if verb == "exists":
            return ExecResult(ok=True, exit_code=0, stdout="true" if target.exists() else "false")
        if verb == "write":
            content = args[1] if len(args) > 1 else ""
            limit = reg.scope.resource_limits.max_output_bytes
            if len(content.encode("utf-8")) > limit:
                return ExecResult(ok=False, exit_code=-1, denied_reason=f"resource limit: write exceeds max_output_bytes={limit}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ExecResult(ok=True, exit_code=0, stdout=f"wrote {len(content)} bytes")
        return ExecResult(ok=False, exit_code=-1, denied_reason=f"unhandled fileop verb {verb!r}")

    def _exec_net(self, reg: _Registration, args: list[str]) -> ExecResult:
        if not args:
            return ExecResult(ok=False, exit_code=-1, denied_reason="net requires a url argument")
        url = args[0]
        host = (urlparse(url).hostname or "").strip().lower()
        profile = reg.scope.egress_profile
        allowlist = [d.strip().lower() for d in reg.scope.egress_allowlist]
        if not host or not profile or not allowlist:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"unscoped-credential/egress wall: deny-all — no profile/allow-list grants {url!r}",
            )
        matched = any(host == d or host.endswith("." + d.removeprefix("*.")) for d in allowlist)
        if not matched:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"egress wall: host {host!r} not in allow-list for profile {profile!r}",
            )


        return ExecResult(ok=True, exit_code=0, stdout=f"egress allowed: {host} (profile={profile})")

    def _exec_cred(self, reg: _Registration, args: list[str]) -> ExecResult:
        if not args:
            return ExecResult(ok=False, exit_code=-1, denied_reason="cred requires a name argument")
        name = args[0]
        for cred in reg.scope.credentials:
            if cred.name == name:
                if cred.scope != reg.task_id:
                    return ExecResult(
                        ok=False, exit_code=-1,
                        denied_reason=f"unscoped-credential wall: {name!r} not scoped to task {reg.task_id!r}",
                    )


                return ExecResult(ok=True, exit_code=0, stdout=cred.value)
        return ExecResult(
            ok=False, exit_code=-1,
            denied_reason=f"unscoped-credential wall: {name!r} not granted — credentials empty by default (ADR-0012)",
        )

    def _exec_sleep(self, reg: _Registration, args: list[str]) -> ExecResult:
        if not args:
            return ExecResult(ok=False, exit_code=-1, denied_reason="sleep requires a seconds argument")
        try:
            seconds = float(args[0])
        except ValueError:
            return ExecResult(ok=False, exit_code=-1, denied_reason=f"invalid seconds {args[0]!r}")
        limit = reg.scope.resource_limits.wallclock_seconds
        if seconds > limit:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"resource limit: requested sleep {seconds}s exceeds wallclock cap {limit}s (no sleep performed)",
            )
        return ExecResult(ok=True, exit_code=0, stdout=f"slept {seconds}s (within {limit}s cap)")
