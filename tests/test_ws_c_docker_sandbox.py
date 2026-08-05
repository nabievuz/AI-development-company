from __future__ import annotations

import getpass
import os
import shlex
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import sandbox as sbx

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


def _grant_sandbox_user_access(mount_root: Path) -> Path:
    mount_root.mkdir(parents=True, exist_ok=True)
    mount_root.chmod(0o777)
    return mount_root


_NO_PROBE = "NOPROBE"


def _guarded_probe(tool: str, script: str) -> str:
    return f"command -v {tool} >/dev/null 2>&1 || {{ echo {_NO_PROBE}; exit 0; }}; {script}"


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


    b = DockerSandbox()
    with pytest.raises(SandboxEscapeError):
        b.open(task_id="d-B", scope=_scope("d-A", tmp_path))


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


@requires_docker
def test_live_own_workdir_reachable_but_host_and_repo_are_not(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="live-1", scope=_scope("live-1", _grant_sandbox_user_access(tmp_path)))
    try:


        assert b.exec(h, ["write", "mine.txt", "owned"]).ok is True
        ls = b.exec_in_container(h, ["sh", "-c", "ls /work"])
        assert ls.ok is True and "mine.txt" in ls.stdout


        repo = b.exec_in_container(
            h, ["sh", "-c", f"test -e {shlex.quote(str(ROOT))} && echo REACH || echo NONE"]
        )
        assert "NONE" in repo.stdout, repo.stdout


        sentinel = tmp_path.parent / f"daslab-host-sentinel-{tmp_path.name}"
        sentinel.write_text("host-only", encoding="utf-8")
        probe = f"test -e {shlex.quote(str(sentinel))} && echo HOSTREACH || echo isolated"
        host_only = b.exec_in_container(h, ["sh", "-c", probe])
        assert "isolated" in host_only.stdout, host_only.stdout
    finally:
        b.close(h)


@requires_docker
@pytest.mark.skipif(
    os.getuid() < 1000,
    reason="system-account uid: a stock image carries this account name too, so the probe "
    "could not tell host /etc from the image's own",
)
def test_live_host_etc_is_not_exposed(tmp_path):


    b = DockerSandbox()
    h = b.open(task_id="live-1b", scope=_scope("live-1b", tmp_path))
    try:
        user = getpass.getuser()
        probe = _guarded_probe(
            "grep", f"grep -q {shlex.quote(user)} /etc/passwd && echo HOSTETC || echo isolated"
        )
        etc = b.exec_in_container(h, ["sh", "-c", probe])
        assert _NO_PROBE not in etc.stdout, "image lacks grep — the /etc probe cannot run"
        assert "isolated" in etc.stdout, etc.stdout
    finally:
        b.close(h)


@requires_docker
def test_live_network_is_off(tmp_path):
    b = DockerSandbox()
    h = b.open(task_id="live-2", scope=_scope("live-2", tmp_path))
    try:

        net = b.exec_in_container(
            h,
            [
                "sh",
                "-c",
                _guarded_probe(
                    "wget",
                    "wget -T2 -qO- http://1.1.1.1 >/dev/null 2>&1 && echo REACH || echo NONET",
                ),
            ],
        )
        assert _NO_PROBE not in net.stdout, "image lacks wget — the egress probe cannot run"
        assert "NONET" in net.stdout, net.stdout
    finally:
        b.close(h)


@requires_docker
def test_live_unscoped_credential_absent_scoped_present(tmp_path):

    b = DockerSandbox()
    h = b.open(task_id="live-3", scope=_scope("live-3", tmp_path))
    try:
        absent = b.exec_in_container(h, ["sh", "-c", "env | grep -c DASLAB_TEST_SECRET || true"])
        assert absent.stdout.strip() == "0", absent.stdout
    finally:
        b.close(h)


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
    a = b.open(task_id="live-A", scope=_scope("live-A", _grant_sandbox_user_access(tmp_path / "a")))
    bb = b.open(task_id="live-B", scope=_scope("live-B", _grant_sandbox_user_access(tmp_path / "b")))
    try:
        b.exec(a, ["write", "secret.txt", "a-only"])

        seen = b.exec_in_container(bb, ["sh", "-c", "test -e /work/secret.txt && echo LEAK || echo isolated"])
        assert "isolated" in seen.stdout, seen.stdout
    finally:
        b.close(a)
        b.close(bb)
