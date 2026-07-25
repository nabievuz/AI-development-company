"""WS-C live DockerSandbox tests (DAS-1566) — the real per-task isolation smoke.

Two layers, both SKIPPED when no container engine is reachable (absent-by-
default): a fresh checkout / CI stays green with nothing installed.

  CONTRACT PARITY  the same four fail-closed walls the DAS-1565 stub tests
                   assert (host/repo, other-task, unscoped-credential, egress)
                   produce the SAME decisions + messages against DockerSandbox,
                   since it subclasses LocalStubSandbox (ADR-0010 C1).

  LIVE ISOLATION   DAS-1566 acceptance — a real command runs INSIDE the per-task
    (smoke)        container via exec_in_container and the boundary holds: the
                   host and repo are unreachable, the network is off, another
                   task's workdir is invisible, and no unscoped credential is
                   present (a scoped one is).

Run on a host with Docker:  pytest tests/test_ws_c_docker_sandbox.py -v
Drive podman instead:       DASLAB_DOCKER_BIN=podman pytest ...
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import sandbox as sbx  # noqa: E402

Mount = sbx.Mount
ScopedSecret = sbx.ScopedSecret
SandboxScope = sbx.SandboxScope
SandboxEscapeError = sbx.SandboxEscapeError
SandboxHandle = sbx.SandboxHandle
DockerSandbox = sbx.DockerSandbox

requires_docker = pytest.mark.skipif(
    not sbx.docker_available(), reason="no docker/podman engine reachable (absent-by-default)"
)


def _scope(task_id: str, mount_root: Path, **kw) -> SandboxScope:
    return SandboxScope(task_id=task_id, workdir_mounts=[Mount(host_path=str(mount_root))], **kw)


# --------------------------------------------------------------------------- #
# Contract parity — identical wall decisions to the stub
# --------------------------------------------------------------------------- #
@requires_docker
def test_docker_host_wall_rejects_traversal(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="d-h1", scope=_scope("d-h1", tmp_path))
    try:
        r = b.exec(h, ["read", "../secret" + "-value"])
        assert r.ok is False
        assert "host/repo wall" in r.denied_reason
    finally:
        b.close(h)


@requires_docker
def test_docker_confined_write_read(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="d-h3", scope=_scope("d-h3", tmp_path))
    try:
        assert b.exec(h, ["write", "notes.txt", "hello"]).ok is True
        r = b.exec(h, ["read", "notes.txt"])
        assert r.ok is True and r.stdout == "hello"
    finally:
        b.close(h)


def test_docker_open_rejects_scope_task_id_mismatch(tmp_path):
    # No @requires_docker: the inherited open-time wall raises BEFORE any
    # container is launched, so this proves the wall is inherited even with no
    # engine installed (a rejected scope never shells out to docker).
    b = DockerSandbox()
    with pytest.raises(SandboxEscapeError):
        b.open(task_id="d-B", scope=_scope("d-A", tmp_path))  # no container started


@requires_docker
def test_docker_foreign_token_denied(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="d-c2", scope=_scope("d-c2", tmp_path))
    try:
        forged = SandboxHandle(task_id="d-c2", backend="docker", token="not-the-real-token")
        r = b.exec(forged, ["read", "notes.txt"])
        assert r.ok is False and "other-task wall" in r.denied_reason
    finally:
        b.close(h)


@requires_docker
def test_docker_egress_deny_all_by_default(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="d-e6", scope=_scope("d-e6", tmp_path))
    try:
        r = b.exec(h, ["net", "https://anything.example/"])
        assert r.ok is False and "deny-all" in r.denied_reason
    finally:
        b.close(h)


@requires_docker
def test_docker_credentials_empty_by_default(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="d-e1", scope=_scope("d-e1", tmp_path))
    try:
        r = b.exec(h, ["cred", "some-api" + "-key"])
        assert r.ok is False and "credentials empty by default" in r.denied_reason
    finally:
        b.close(h)


# --------------------------------------------------------------------------- #
# Live isolation smoke — real code runs inside the container and cannot escape
# --------------------------------------------------------------------------- #
@requires_docker
def test_live_own_workdir_reachable_but_host_and_repo_are_not(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="live-1", scope=_scope("live-1", tmp_path))
    try:
        # The task's own file (written via the confined write verb) is visible
        # to real in-container code at /work.
        assert b.exec(h, ["write", "mine.txt", "owned"]).ok is True
        ls = b.exec_in_container(h, ["sh", "-c", "ls /work"])
        assert ls.ok is True and "mine.txt" in ls.stdout
        # The host repo is NOT mounted — invisible from inside.
        repo = b.exec_in_container(
            h, ["sh", "-c", "test -e /home/daslab/projects/daslab && echo REACH || echo NONE"]
        )
        assert "NONE" in repo.stdout, repo.stdout
        # A real host file path resolves to nothing in the container.
        passwd_host = b.exec_in_container(
            h, ["sh", "-c", "grep -q daslab /etc/passwd && echo HOSTUSER || echo isolated"]
        )
        assert "isolated" in passwd_host.stdout, passwd_host.stdout
    finally:
        b.close(h)


@requires_docker
def test_live_network_is_off(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="live-2", scope=_scope("live-2", tmp_path))
    try:
        # --network none: no route out even to a raw IP (avoids DNS).
        net = b.exec_in_container(
            h, ["sh", "-c", "wget -T2 -qO- http://1.1.1.1 >/dev/null 2>&1 && echo REACH || echo NONET"]
        )
        assert "NONET" in net.stdout, net.stdout
    finally:
        b.close(h)


@requires_docker
def test_live_unscoped_credential_absent_scoped_present(tmp_path):
    # Default: no credential in the container's env.
    b = DockerSandbox()
    h = b.open(task_id="live-3", scope=_scope("live-3", tmp_path))
    try:
        absent = b.exec_in_container(h, ["sh", "-c", "env | grep -c DASLAB_TEST_SECRET || true"])
        assert absent.stdout.strip() == "0", absent.stdout
    finally:
        b.close(h)

    # Granted + task-scoped: present inside the container (and only there).
    cred = ScopedSecret(name="DASLAB_TEST_SECRET", value="sk-live-777", scope="live-3b", ttl_seconds=60)
    h2 = b.open(task_id="live-3b", scope=_scope("live-3b", tmp_path, credentials=[cred]))
    try:
        present = b.exec_in_container(h2, ["sh", "-c", "printf %s \"$DASLAB_TEST_SECRET\""])
        assert present.stdout == "sk-live-777", present.stdout
    finally:
        b.close(h2)


@requires_docker
def test_live_other_task_workdir_invisible(tmp_path):
    b = DockerSandbox()
    a = b.open(task_id="live-A", scope=_scope("live-A", tmp_path / "a"))
    (tmp_path / "a").mkdir(exist_ok=True)
    bb = b.open(task_id="live-B", scope=_scope("live-B", tmp_path / "b"))
    (tmp_path / "b").mkdir(exist_ok=True)
    try:
        b.exec(a, ["write", "secret.txt", "a-only"])  # in A's workdir only
        # B's container has its own /work — A's file is not there.
        seen = b.exec_in_container(bb, ["sh", "-c", "test -e /work/secret.txt && echo LEAK || echo isolated"])
        assert "isolated" in seen.stdout, seen.stdout
    finally:
        b.close(a)
        b.close(bb)
