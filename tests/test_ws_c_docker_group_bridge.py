"""WS-C DockerSandbox group-stale self-heal (DAS-1566 hardening).

A real container backend must never *silently* degrade to the stub just because
THIS session started before the operator was added to the ``docker`` group. On
such a *group-stale login* the membership is permanent in ``/etc/group`` but the
running process's credentials lack the gid (a kernel rule — no supplementary
group can be granted to a live process from outside). ``sg <group> -c`` bridges
it with no password and no re-login. These tests pin that decision table without
needing an actual stale session or a Docker engine — every probe is monkeypatched
so a fresh checkout / CI stays deterministic and green.
"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sandbox import docker_sandbox as ds  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_cache():
    """The group prefix is cached module-wide; clear it around every test."""
    ds._GROUP_PREFIX_CACHE = None
    yield
    ds._GROUP_PREFIX_CACHE = None


# --------------------------------------------------------------------------- #
# _group_stale — the exact "member but gid not active" condition
# --------------------------------------------------------------------------- #
def _fake_group(gid: int, members: list[str]):
    return SimpleNamespace(gr_gid=gid, gr_mem=members)


def test_group_stale_true_when_member_but_gid_inactive(monkeypatch):
    monkeypatch.setattr(ds.grp, "getgrnam", lambda n: _fake_group(983, ["daslab"]))
    monkeypatch.setattr(ds.os, "getgroups", lambda: [1000, 4, 27])  # no 983
    monkeypatch.setenv("USER", "daslab")
    assert ds._group_stale() is True


def test_group_stale_false_when_gid_already_active(monkeypatch):
    monkeypatch.setattr(ds.grp, "getgrnam", lambda n: _fake_group(983, ["daslab"]))
    monkeypatch.setattr(ds.os, "getgroups", lambda: [1000, 983])  # already active
    monkeypatch.setenv("USER", "daslab")
    assert ds._group_stale() is False


def test_group_stale_false_when_not_a_member(monkeypatch):
    monkeypatch.setattr(ds.grp, "getgrnam", lambda n: _fake_group(983, ["someoneelse"]))
    monkeypatch.setattr(ds.os, "getgroups", lambda: [1000])
    monkeypatch.setenv("USER", "daslab")
    assert ds._group_stale() is False


def test_group_stale_false_when_group_absent(monkeypatch):
    def _boom(_n):
        raise KeyError("docker")

    monkeypatch.setattr(ds.grp, "getgrnam", _boom)
    assert ds._group_stale() is False


# --------------------------------------------------------------------------- #
# _compute_group_prefix — the decision table
# --------------------------------------------------------------------------- #
def test_prefix_empty_when_cli_absent(monkeypatch):
    monkeypatch.setattr(ds.shutil, "which", lambda b: None)
    assert ds._compute_group_prefix() == []


def test_prefix_empty_when_daemon_answers_directly(monkeypatch):
    monkeypatch.setattr(ds.shutil, "which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(ds, "_daemon_ok", lambda argv: True)  # direct info OK
    # Even if the session were stale, a direct answer means no bridge is needed.
    monkeypatch.setattr(ds, "_group_stale", lambda: True)
    assert ds._compute_group_prefix() == []


def test_prefix_bridges_when_group_stale(monkeypatch):
    monkeypatch.setattr(ds.shutil, "which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(ds, "_group_stale", lambda: True)
    seen = []

    def _daemon_ok(argv):
        seen.append(argv)
        return argv[0] == "sg"  # direct fails, sg-wrapped succeeds

    monkeypatch.setattr(ds, "_daemon_ok", _daemon_ok)
    assert ds._compute_group_prefix() == ["sg", ds._SOCKET_GROUP, "-c"]
    # It probed the DIRECT form first, then the sg-wrapped form.
    assert seen[0] == [ds._DOCKER, "info"]
    assert seen[-1] == ["sg", ds._SOCKET_GROUP, "-c", shlex.join([ds._DOCKER, "info"])]


def test_prefix_empty_when_stale_but_sg_bridge_also_fails(monkeypatch):
    monkeypatch.setattr(ds.shutil, "which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(ds, "_group_stale", lambda: True)
    monkeypatch.setattr(ds, "_daemon_ok", lambda argv: False)  # nothing works
    assert ds._compute_group_prefix() == []


def test_prefix_empty_when_stale_but_no_sg(monkeypatch):
    monkeypatch.setattr(ds.shutil, "which", lambda b: None if b == "sg" else f"/usr/bin/{b}")
    monkeypatch.setattr(ds, "_group_stale", lambda: True)
    monkeypatch.setattr(ds, "_daemon_ok", lambda argv: argv[0] == "sg")
    assert ds._compute_group_prefix() == []


# --------------------------------------------------------------------------- #
# _group_prefix cache + _run wrapping
# --------------------------------------------------------------------------- #
def test_group_prefix_probes_at_most_once(monkeypatch):
    calls = {"n": 0}

    def _compute():
        calls["n"] += 1
        return ["sg", "docker", "-c"]

    monkeypatch.setattr(ds, "_compute_group_prefix", _compute)
    assert ds._group_prefix() == ["sg", "docker", "-c"]
    assert ds._group_prefix() == ["sg", "docker", "-c"]
    assert calls["n"] == 1  # cached — the (up to 10s) probe never repeats


def test_run_passes_argv_through_when_no_prefix(monkeypatch):
    monkeypatch.setattr(ds, "_group_prefix", lambda: [])
    captured = {}
    monkeypatch.setattr(ds.subprocess, "run", lambda argv, **kw: captured.setdefault("argv", argv))
    ds._run([ds._DOCKER, "rm", "-f", "daslab-sbx-x"], capture_output=True)
    assert captured["argv"] == [ds._DOCKER, "rm", "-f", "daslab-sbx-x"]


def test_run_wraps_argv_when_bridged(monkeypatch):
    monkeypatch.setattr(ds, "_group_prefix", lambda: ["sg", "docker", "-c"])
    captured = {}
    monkeypatch.setattr(ds.subprocess, "run", lambda argv, **kw: captured.setdefault("argv", argv))
    inner = [ds._DOCKER, "exec", "daslab-sbx-x", "sh", "-c", "echo hi; wget x"]
    ds._run(inner, capture_output=True, text=True)
    # Whole inner argv becomes ONE safely-quoted shell string under sg.
    assert captured["argv"] == ["sg", "docker", "-c", shlex.join(inner)]
    # And every original token round-trips through the quoting.
    assert shlex.split(captured["argv"][-1]) == inner
