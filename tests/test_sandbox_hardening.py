from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import sandbox as sbx

ds = sys.modules[sbx.DockerSandbox.__module__]

requires_docker = pytest.mark.skipif(
    not sbx.docker_available(), reason="no docker engine reachable"
)

SECRET_VALUE = "sk-" + "or-v1-hardening-probe"

_ZOMBIE_COUNT_SCRIPT = (
    'for _p in /proc/[0-9]*; do '
    'read _pid _comm _state _rest < "$_p/stat" 2>/dev/null || continue; '
    '[ "$_state" = Z ] && echo Z; '
    "done | wc -l"
)


@pytest.fixture(autouse=True)
def _no_leaked_container_registry():
    before = set(ds._LIVE_CONTAINERS)
    yield
    ds._LIVE_CONTAINERS.clear()
    ds._LIVE_CONTAINERS.update(before)


@pytest.fixture
def fake_docker(monkeypatch):
    calls: list[dict] = []

    def _fake_run(argv, **kwargs):
        calls.append({"argv": list(argv), "input": kwargs.get("input")})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ds, "_run", _fake_run)
    return calls


def _scope(task_id: str, workdir: Path, **kw) -> sbx.SandboxScope:
    return sbx.SandboxScope(
        task_id=task_id, workdir_mounts=[sbx.Mount(host_path=str(workdir))], **kw
    )


def _limits() -> sbx.ResourceLimits:
    return sbx.ResourceLimits()


def _argv(tmp_path: Path, **kw) -> list[str]:
    return ds.build_run_argv(
        container_name="daslab-sbx-t-abc",
        image_reference=ds._PINNED_ALPINE,
        workdir=str(tmp_path),
        mount_mode="rw",
        limits=_limits(),
        **kw,
    )


def test_run_argv_drops_all_capabilities(tmp_path):
    assert "--cap-drop=ALL" in _argv(tmp_path)


def test_run_argv_forbids_privilege_escalation(tmp_path):
    assert "--security-opt=no-new-privileges" in _argv(tmp_path)


def test_run_argv_runs_as_non_root_user(tmp_path):
    argv = _argv(tmp_path)
    assert "--user" in argv
    assert argv[argv.index("--user") + 1] == "65534:65534"


def test_run_argv_uses_read_only_rootfs_with_explicit_tmpfs(tmp_path):
    argv = _argv(tmp_path)
    assert "--read-only" in argv
    tmpfs = [argv[i + 1] for i, token in enumerate(argv) if token == "--tmpfs"]
    assert any(spec.startswith("/tmp:") for spec in tmpfs)
    assert any(spec.startswith(f"{ds.RUNTIME_DIR}:") for spec in tmpfs)
    for spec in tmpfs:
        assert "nosuid" in spec and "nodev" in spec


def test_run_argv_states_network_posture_explicitly(tmp_path):
    argv = _argv(tmp_path)
    assert "--network" in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert ds.CONTAINER_NETWORK_MODE == "none"


def test_run_argv_reaps_orphans_with_an_init_process(tmp_path):
    assert "--init" in _argv(tmp_path)


def test_run_argv_caps_memory_and_pids(tmp_path):
    argv = _argv(tmp_path)
    for flag in ("--cpus", "--memory", "--memory-swap", "--pids-limit"):
        assert flag in argv
    assert argv[argv.index("--memory") + 1] == argv[argv.index("--memory-swap") + 1]


def test_run_argv_refuses_a_floating_tag(tmp_path):
    with pytest.raises(ds.ImagePinError):
        ds.build_run_argv(
            container_name="daslab-sbx-t-abc",
            image_reference="alpine:3.20",
            workdir=str(tmp_path),
            mount_mode="rw",
            limits=_limits(),
        )


def test_run_argv_refuses_root_run_as(tmp_path):
    with pytest.raises(sbx.SandboxEscapeError):
        _argv(tmp_path, run_as="0:0")


def test_constructor_refuses_root_run_as():
    with pytest.raises(sbx.SandboxEscapeError):
        sbx.DockerSandbox(run_as="0:0")


def test_default_image_is_digest_pinned():
    assert ds.is_digest_pinned(ds._PINNED_ALPINE)
    assert not ds.is_digest_pinned("alpine:3.20")
    assert not ds.is_digest_pinned("alpine@sha256:tooshort")


def test_container_names_are_namespaced_per_run():
    first = ds._container_name("das-1")
    second = ds._container_name("das-1")
    assert first != second
    assert first.startswith(ds.CONTAINER_NAME_PREFIX)
    assert set("/: ").isdisjoint(ds._container_name("a/b c:d"))


def test_credential_script_quotes_values_and_refuses_hostile_names():
    script = ds.credential_script(
        [sbx.ScopedSecret(name="TOKEN", value="a b'c", scope="t", ttl_seconds=1)]
    )
    assert script == "export TOKEN='a b'\"'\"'c'\n"
    with pytest.raises(sbx.SandboxEscapeError):
        ds.credential_script(
            [sbx.ScopedSecret(name="X; rm -rf /", value="v", scope="t", ttl_seconds=1)]
        )


def test_exec_script_records_pids_and_sources_credentials():
    script = ds.build_exec_script("abc123")
    assert f". {ds.CREDENTIALS_FILE};" in script
    assert f'echo "$$ $_child" > {ds.PID_DIR}/abc123' in script
    assert '"$0" "$@" &' in script


def test_kill_script_signals_the_whole_process_group():
    script = ds.build_kill_script("abc123")
    assert f"read _shell _child < {ds.PID_DIR}/abc123" in script
    assert 'kill -9 -"$_shell"' in script


def test_open_never_puts_credentials_in_docker_run_argv(tmp_path, fake_docker):
    box = sbx.DockerSandbox()
    cred = sbx.ScopedSecret(name="TOKEN", value=SECRET_VALUE, scope="fk-1", ttl_seconds=60)
    box.open(task_id="fk-1", scope=_scope("fk-1", tmp_path, credentials=[cred]))

    run_call = next(c for c in fake_docker if c["argv"][1] == "run")
    assert "-e" not in run_call["argv"]
    assert "--env-file" not in run_call["argv"]
    assert SECRET_VALUE not in " ".join(run_call["argv"])

    setup_call = next(c for c in fake_docker if c["argv"][1] == "exec")
    assert setup_call["input"] == f"export TOKEN={shlex.quote(SECRET_VALUE)}\n"
    assert SECRET_VALUE not in " ".join(setup_call["argv"])


def test_open_writes_no_credential_file_on_the_host(tmp_path, fake_docker):
    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.iterdir())
    box = sbx.DockerSandbox()
    cred = sbx.ScopedSecret(name="TOKEN", value=SECRET_VALUE, scope="fk-2", ttl_seconds=60)
    box.open(task_id="fk-2", scope=_scope("fk-2", tmp_path, credentials=[cred]))
    for path in set(temp_root.iterdir()) - before:
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        assert SECRET_VALUE not in body


def test_open_registers_the_container_and_close_unregisters_it(tmp_path, fake_docker):
    box = sbx.DockerSandbox()
    handle = box.open(task_id="fk-3", scope=_scope("fk-3", tmp_path))
    name = box.container_name(handle)
    assert name in ds._LIVE_CONTAINERS
    box.close(handle)
    assert name not in ds._LIVE_CONTAINERS
    assert box.container_name(handle) is None
    assert any(c["argv"][1:3] == ["rm", "-f"] for c in fake_docker)


def test_open_removes_the_container_when_startup_fails(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def _failing_run(argv, **kwargs):
        calls.append(list(argv))
        if argv[1] == "run":
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ds, "_run", _failing_run)
    box = sbx.DockerSandbox()
    with pytest.raises(RuntimeError):
        box.open(task_id="fk-4", scope=_scope("fk-4", tmp_path))
    assert any(argv[1:3] == ["rm", "-f"] for argv in calls)
    assert not ds._LIVE_CONTAINERS
    assert box._registry["fk-4"].closed is True


def test_open_removes_the_container_when_setup_fails(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def _failing_setup(argv, **kwargs):
        calls.append(list(argv))
        if argv[1] == "exec":
            return SimpleNamespace(returncode=1, stdout="", stderr="no runtime dir")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ds, "_run", _failing_setup)
    box = sbx.DockerSandbox()
    with pytest.raises(RuntimeError):
        box.open(task_id="fk-5", scope=_scope("fk-5", tmp_path))
    assert any(argv[1:3] == ["rm", "-f"] for argv in calls)
    assert not ds._LIVE_CONTAINERS


def test_close_all_removes_every_live_container(tmp_path, fake_docker):
    box = sbx.DockerSandbox()
    a = box.open(task_id="fk-6a", scope=_scope("fk-6a", tmp_path / "a"))
    b = box.open(task_id="fk-6b", scope=_scope("fk-6b", tmp_path / "b"))
    names = {box.container_name(a), box.container_name(b)}
    box.close_all()
    assert names.isdisjoint(ds._LIVE_CONTAINERS)
    removed = {c["argv"][3] for c in fake_docker if c["argv"][1:3] == ["rm", "-f"]}
    assert removed == names


def test_process_exit_cleanup_removes_registered_containers(fake_docker):
    ds._LIVE_CONTAINERS.add("daslab-sbx-orphan-1")
    ds._remove_surviving_containers()
    assert "daslab-sbx-orphan-1" not in ds._LIVE_CONTAINERS
    assert ["rm", "-f", "daslab-sbx-orphan-1"] in [c["argv"][1:] for c in fake_docker]


def _grant(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o777)
    return path


@requires_docker
def test_live_container_runs_unprivileged(tmp_path):
    box = sbx.DockerSandbox()
    handle = box.open(task_id="hard-1", scope=_scope("hard-1", _grant(tmp_path / "w")))
    try:
        assert box.exec_in_container(handle, ["id", "-u"]).stdout.strip() == "65534"
        caps = box.exec_in_container(handle, ["sh", "-c", "grep CapEff /proc/self/status"])
        assert caps.stdout.split()[1].strip("0") == ""
        nnp = box.exec_in_container(handle, ["sh", "-c", "grep NoNewPrivs /proc/self/status"])
        assert nnp.stdout.split()[1] == "1"
    finally:
        box.close(handle)


@requires_docker
def test_live_rootfs_is_read_only_but_tmpfs_is_writable(tmp_path):
    box = sbx.DockerSandbox()
    handle = box.open(task_id="hard-2", scope=_scope("hard-2", _grant(tmp_path / "w")))
    try:
        rootfs = box.exec_in_container(
            handle, ["sh", "-c", "touch /probe 2>/dev/null && echo WRITABLE || echo READONLY"]
        )
        assert rootfs.stdout.strip() == "READONLY"
        scratch = box.exec_in_container(
            handle, ["sh", "-c", "touch /tmp/probe && echo TMPFSOK"]
        )
        assert scratch.stdout.strip() == "TMPFSOK"
    finally:
        box.close(handle)


@requires_docker
def test_live_credentials_are_invisible_to_docker_inspect(tmp_path):
    box = sbx.DockerSandbox()
    cred = sbx.ScopedSecret(name="TOKEN", value=SECRET_VALUE, scope="hard-3", ttl_seconds=60)
    handle = box.open(
        task_id="hard-3", scope=_scope("hard-3", _grant(tmp_path / "w"), credentials=[cred])
    )
    try:
        name = box.container_name(handle)
        inspect = subprocess.run(
            [ds._DOCKER, "inspect", name], capture_output=True, text=True, timeout=60
        )
        assert inspect.returncode == 0
        assert SECRET_VALUE not in inspect.stdout
        seen = box.exec_in_container(handle, ["sh", "-c", 'printf %s "$TOKEN"'])
        assert seen.stdout == SECRET_VALUE
    finally:
        box.close(handle)


@requires_docker
@pytest.mark.parametrize(
    "command", [["sleep", "30"], ["sh", "-c", "sleep 30"], ["sh", "-c", "sh -c 'sleep 30' & wait"]]
)
def test_live_wallclock_timeout_kills_the_in_container_process(tmp_path, command):
    box = sbx.DockerSandbox()
    scope = _scope(
        "hard-4", _grant(tmp_path / "w"), resource_limits=sbx.ResourceLimits(wallclock_seconds=2.0)
    )
    handle = box.open(task_id="hard-4", scope=scope)
    try:
        started = time.monotonic()
        result = box.exec_in_container(handle, command)
        assert result.ok is False
        assert "wallclock timeout" in result.denied_reason
        assert "in-container process killed" in result.denied_reason
        assert time.monotonic() - started < 20
        survivors = box.exec_in_container(
            handle, ["sh", "-c", "ps | grep -c '[s]leep 30' || true"]
        )
        assert survivors.stdout.strip() == "0", survivors.stdout
        zombies = box.exec_in_container(handle, ["sh", "-c", _ZOMBIE_COUNT_SCRIPT])
        assert zombies.stdout.strip() == "0", zombies.stdout
    finally:
        box.close(handle)


@requires_docker
def test_live_leftover_container_does_not_break_the_next_run(tmp_path):
    legacy = "daslab-sbx-hard-5"
    subprocess.run(
        [ds._DOCKER, "run", "-d", "--name", legacy, ds._PINNED_ALPINE, "tail", "-f", "/dev/null"],
        capture_output=True, text=True, timeout=120,
    )
    box = sbx.DockerSandbox()
    try:
        handle = box.open(task_id="hard-5", scope=_scope("hard-5", _grant(tmp_path / "w")))
        try:
            assert box.container_name(handle) != legacy
            assert box.exec_in_container(handle, ["true"]).ok is True
        finally:
            box.close(handle)
    finally:
        subprocess.run([ds._DOCKER, "rm", "-f", legacy], capture_output=True, timeout=60)


@requires_docker
def test_live_close_removes_the_container(tmp_path):
    box = sbx.DockerSandbox()
    handle = box.open(task_id="hard-6", scope=_scope("hard-6", _grant(tmp_path / "w")))
    name = box.container_name(handle)
    probe = [ds._DOCKER, "inspect", name]
    assert subprocess.run(probe, capture_output=True, timeout=60).returncode == 0
    box.close(handle)
    assert subprocess.run(probe, capture_output=True, timeout=60).returncode != 0


@requires_docker
@pytest.mark.skipif(os.getuid() == 0, reason="a root host identity is refused by design")
def test_live_run_as_host_identity_reaches_a_private_workdir(tmp_path):
    workdir = tmp_path / "private"
    workdir.mkdir()
    workdir.chmod(0o700)
    (workdir / "only-mine.txt").write_text("x", encoding="utf-8")
    box = sbx.DockerSandbox(run_as=f"{os.getuid()}:{os.getgid()}")
    handle = box.open(task_id="hard-7", scope=_scope("hard-7", workdir))
    try:
        listing = box.exec_in_container(handle, ["sh", "-c", "ls /work"])
        assert "only-mine.txt" in listing.stdout
    finally:
        box.close(handle)
