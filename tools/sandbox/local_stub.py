"""``LocalStubSandbox`` — the host-free reference/stub backend, DasLab WS-C
(ADR-0035 LG-5, `docs/design/ws-c-langgraph-loop.md` §5, DAS-1565).

Satisfies :class:`tools.sandbox.contract.SandboxBackend` by running against a
**temporary, per-task working directory** with the mount / egress / credential
/ resource-limit checks enforced **in-process**, deny-by-default. It proves the
*contract shape and refusal logic* — it is explicitly **not** a security
boundary for real untrusted code (no kernel/namespace isolation; see design
§5.1). The live `DockerSandbox` (DAS-1566, blocked) provides that.

Zero third-party dependencies — stdlib only (``tempfile``, ``pathlib``,
``time``, ``secrets``, ``urllib.parse``) — so this module is importable and
testable with nothing installed (WS-A pattern: absent optional deps ⇒ the
*live* sandbox does not exist, but the stub always works).

Supported ``argv`` verbs (an internal, safe operation set — deliberately NOT a
generic subprocess passthrough, since shelling out to the real OS would defeat
"host-free": a subprocess's cwd does not, by itself, stop an absolute-path or
``..`` escape from reaching the real host filesystem):

  ``["read", <relpath>]``            — read a file inside a granted mount
  ``["write", <relpath>, <content>]`` — write a file inside a (writable) mount
  ``["exists", <relpath>]``          — existence probe inside a granted mount
  ["net", <url>]                    — egress decision only (no real request)
  ["cred", <name>]                  — fetch a scoped credential's value
  ["sleep", <seconds>]              — resource-limit probe (wallclock cap)

Any other verb is refused (unknown-verb ⇒ fail-closed deny, not best-effort).
"""
from __future__ import annotations

import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import urlparse

# Sibling-module import that works whether this file is imported as part of
# the ``tools.sandbox`` package (``-m pytest`` from repo root) or loaded
# directly by file path (as the WS-A tests load ``tools/mcp_bridges/*.py``) —
# same pattern as ``audit_external_tool.py``'s ``redaction`` import.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contract import (  # noqa: E402
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
    """Confine *rel* to *mount_root*. ``None`` on any escape attempt.

    Rejects: absolute paths, any ``..`` path component, and (defense in
    depth against symlink tricks) a resolved path that lands outside the
    mount root even after traversal-free joining.
    """
    if not rel:
        return None
    candidate_raw = Path(rel)
    if candidate_raw.is_absolute():
        return None
    if ".." in candidate_raw.parts:
        return None
    root = mount_root.resolve()
    candidate = (mount_root / candidate_raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


class LocalStubSandbox(SandboxBackend):
    """Host-free reference backend. One temp workdir per ``task_id``.

    An instance holds its own in-memory registry — ``task_id`` isolation is
    per-instance, matching the design's "one sandbox per task_id": two
    :meth:`open` calls with different ``task_id`` values never share a mount,
    and a handle from one registration can never be used to reach another's
    workdir, even via a crafted path (caught by :func:`_resolve_within`).
    """

    def __init__(self) -> None:
        self._registry: dict[str, _Registration] = {}

    # -- SandboxBackend -----------------------------------------------------

    def open(self, *, task_id: str, scope: SandboxScope) -> SandboxHandle:
        if not task_id:
            raise SandboxEscapeError("open() refused: empty task_id")
        if scope.task_id != task_id:
            # Unscoped-credential / other-task wall at construction time: a
            # scope built for one task_id can never be used to open another's
            # sandbox — fail closed before any workdir/credential exists.
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
        reg.token = token  # type: ignore[attr-defined]  # last-issued token wins
        return SandboxHandle(task_id=task_id, backend="local-stub", token=token)

    def exec(self, handle: SandboxHandle, argv: list[str]) -> ExecResult:
        reg = self._registry.get(handle.task_id)
        if reg is None or reg.closed:
            return ExecResult(
                ok=False, exit_code=-1,
                denied_reason=f"other-task wall: no live sandbox for task_id {handle.task_id!r}",
            )
        if getattr(reg, "token", None) != handle.token:
            # A stale/foreign handle claiming this task_id — deny, no side effect.
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

    # -- internal verb handlers ----------------------------------------------

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
        # Host-free: this is a decision only — the stub never performs a real
        # network I/O call, matching "not a security boundary for real
        # untrusted code" (design §5.1). No side effect either way.
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
                # The VALUE is returned to the in-sandbox caller (the task's own
                # process), which is the intended consumer. It must never be
                # copied into an ExecResult field other than stdout by any
                # caller building an event — see ScopedSecret.to_event_fields().
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
