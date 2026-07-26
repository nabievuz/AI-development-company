"""WS-C sandbox adapter tests (ADR-0035 LG-5 / FR-006, DAS-1565).

Covers the design's (`docs/design/ws-c-langgraph-loop.md` §5) four fail-closed
walls plus escape-prevention, against the host-free ``LocalStubSandbox``:

  W1 (host)                path outside the workdir ('..'/absolute) refused
  W2 (repo)                only the task's own worktree is visible — a path
                            escaping into a sibling "repo" area (.git/board/
                            another ticket) is refused the same way
  W3 (other-task)           one sandbox per task_id; a foreign/stale handle,
                            or a scope built for a different task_id, is
                            refused
  W4 (unscoped-credential)  credentials empty by default (ADR-0012); a scoped
                            grant works; a credential's VALUE never lands in
                            an event (Tier-M — only to_event_fields() may);
                            egress is deny-all except an explicit allow-list
  ESC (escape-prevention)   a denied call returns ok=False with no side
                            effect (no file written, no registry mutation)
  FLAG                      ws_c_langgraph_loop OFF by default ⇒ flag_on()
                            is False and nothing changes / import is inert
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Load the package as ONE consistent module graph (`tools.sandbox`) so every
# submodule's internal `from contract import ...` resolves to the same cached
# `contract` module the test uses — avoids the classic "two module objects,
# two classes with the same name" trap that breaks `isinstance`/`pytest.raises`
# when a package's siblings are instead loaded independently by file path.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import sandbox as sbx  # noqa: E402
from tools.sandbox import flag  # noqa: E402

Mount = sbx.Mount
ScopedSecret = sbx.ScopedSecret
ResourceLimits = sbx.ResourceLimits
SandboxScope = sbx.SandboxScope
SandboxEscapeError = sbx.SandboxEscapeError
SandboxHandle = sbx.SandboxHandle
LocalStubSandbox = sbx.LocalStubSandbox


def _scope(task_id: str, mount_root: Path, **kw) -> SandboxScope:
    return SandboxScope(
        task_id=task_id,
        workdir_mounts=[Mount(host_path=str(mount_root))],
        **kw,
    )


# ---------------------------------------------------------------------------
# W1 — host wall
# ---------------------------------------------------------------------------


def test_host_wall_rejects_dotdot_traversal(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-h1", tmp_path)
    handle = backend.open(task_id="task-h1", scope=scope)
    result = backend.exec(handle, ["read", "../secret" + "-value"])
    assert result.ok is False
    assert "host/repo wall" in result.denied_reason


def test_host_wall_rejects_absolute_path(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-h2", tmp_path)
    handle = backend.open(task_id="task-h2", scope=scope)
    result = backend.exec(handle, ["read", "/etc/passwd"])
    assert result.ok is False
    assert "host/repo wall" in result.denied_reason


def test_host_wall_allows_confined_write_and_read(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-h3", tmp_path)
    handle = backend.open(task_id="task-h3", scope=scope)
    w = backend.exec(handle, ["write", "notes.txt", "hello"])
    assert w.ok is True
    r = backend.exec(handle, ["read", "notes.txt"])
    assert r.ok is True
    assert r.stdout == "hello"


# ---------------------------------------------------------------------------
# W2 — repo wall (only the task's own worktree is visible)
# ---------------------------------------------------------------------------


def test_repo_wall_rejects_escape_into_sibling_repo_area(tmp_path):
    # Simulate a repo layout: <root>/worktrees/<task>/  and  <root>/board/
    repo_root = tmp_path / "repo"
    worktree = repo_root / "worktrees" / "task-r1"
    worktree.mkdir(parents=True)
    (repo_root / "board" / "tickets").mkdir(parents=True)
    (repo_root / "board" / "tickets" / "DAS-9999.md").write_text("other ticket")
    (repo_root / ".git").mkdir()

    backend = LocalStubSandbox()
    scope = _scope("task-r1", worktree)
    handle = backend.open(task_id="task-r1", scope=scope)

    for rel in ("../../board/tickets/DAS-9999.md", "../../.git/config"):
        result = backend.exec(handle, ["read", rel])
        assert result.ok is False
        assert "host/repo wall" in result.denied_reason


def test_repo_wall_only_own_worktree_mounted(tmp_path):
    backend = LocalStubSandbox()
    own = tmp_path / "own-worktree"
    own.mkdir()
    scope = _scope("task-r2", own)
    handle = backend.open(task_id="task-r2", scope=scope)
    # Only paths under `own` resolve; nothing else in tmp_path is reachable.
    sibling = tmp_path / "sibling-worktree"
    sibling.mkdir()
    (sibling / "leak.txt").write_text("leak")
    result = backend.exec(handle, ["read", "../sibling-worktree/leak.txt"])
    assert result.ok is False


# ---------------------------------------------------------------------------
# W3 — other-task wall
# ---------------------------------------------------------------------------


def test_other_task_wall_open_rejects_scope_task_id_mismatch(tmp_path):
    backend = LocalStubSandbox()
    scope_for_a = _scope("task-A", tmp_path)
    with pytest.raises(SandboxEscapeError):
        backend.open(task_id="task-B", scope=scope_for_a)


def test_other_task_wall_stale_handle_denied_after_close(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-c1", tmp_path)
    handle = backend.open(task_id="task-c1", scope=scope)
    backend.close(handle)
    result = backend.exec(handle, ["read", "notes.txt"])
    assert result.ok is False
    assert "other-task wall" in result.denied_reason


def test_other_task_wall_foreign_token_denied(tmp_path):
    backend = LocalStubSandbox()
    scope_a = _scope("task-c2", tmp_path / "a")
    (tmp_path / "a").mkdir()
    handle_a = backend.open(task_id="task-c2", scope=scope_a)

    # A forged handle claiming the same task_id but a bogus token must not work.
    forged = SandboxHandle(task_id="task-c2", backend="local-stub", token="not-the-real-token")
    result = backend.exec(forged, ["read", "notes.txt"])
    assert result.ok is False
    assert "other-task wall" in result.denied_reason
    # The legitimate handle still works — proves the deny was token-specific.
    assert backend.exec(handle_a, ["write", "notes.txt", "ok"]).ok is True


def test_other_task_wall_no_shared_mount_across_tasks(tmp_path):
    backend = LocalStubSandbox()
    dir_a = tmp_path / "task-d1-dir"
    dir_b = tmp_path / "task-d2-dir"
    dir_a.mkdir()
    dir_b.mkdir()
    handle_a = backend.open(task_id="task-d1", scope=_scope("task-d1", dir_a))
    handle_b = backend.open(task_id="task-d2", scope=_scope("task-d2", dir_b))
    backend.exec(handle_a, ["write", "secret.txt", "a-only"])
    # task-d2's handle cannot reach task-d1's file even by relative escape.
    leak = backend.exec(handle_b, ["read", "../task-d1-dir/secret.txt"])
    assert leak.ok is False
    assert not (dir_b / "secret.txt").exists()


# ---------------------------------------------------------------------------
# W4 — unscoped-credential wall (+ egress deny-all-except-allow-list)
# ---------------------------------------------------------------------------


def test_credentials_empty_by_default(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-e1", tmp_path)  # no credentials= passed -> default []
    assert scope.credentials == []
    handle = backend.open(task_id="task-e1", scope=scope)
    result = backend.exec(handle, ["cred", "some-api" + "-key"])
    assert result.ok is False
    assert "unscoped-credential wall" in result.denied_reason
    assert "credentials empty by default" in result.denied_reason


def test_scoped_credential_grant_is_usable(tmp_path):
    secret_value = "sk-fake" + "-scoped" + "-value" + "-123"
    cred = ScopedSecret(name="api-key", value=secret_value, scope="task-e2", ttl_seconds=60)
    backend = LocalStubSandbox()
    scope = _scope("task-e2", tmp_path, credentials=[cred])
    handle = backend.open(task_id="task-e2", scope=scope)
    result = backend.exec(handle, ["cred", "api-key"])
    assert result.ok is True
    assert result.stdout == secret_value


def test_open_rejects_credential_scoped_to_a_different_task(tmp_path):
    secret_value = "sk-fake" + "-cross" + "-task" + "-999"
    cred = ScopedSecret(name="api-key", value=secret_value, scope="task-OTHER", ttl_seconds=60)
    backend = LocalStubSandbox()
    scope = _scope("task-e3", tmp_path, credentials=[cred])
    with pytest.raises(SandboxEscapeError, match="unscoped-credential"):
        backend.open(task_id="task-e3", scope=scope)


def test_credential_value_never_lands_in_an_event():
    """Tier-M (ADR-0012): an event built from a ScopedSecret carries only the
    fact-of-grant + scope + ttl — never `.value`."""
    secret_value = "sk-fake" + "-tier-m" + "-guard" + "-777"
    cred = ScopedSecret(name="db-password", value=secret_value, scope="task-e4", ttl_seconds=300)

    event_fields = cred.to_event_fields()

    assert event_fields == {"name": "db-password", "scope": "task-e4", "ttl_seconds": 300}
    assert "value" not in event_fields
    serialized = repr(event_fields)
    assert secret_value not in serialized


def test_egress_denies_non_allowlisted_host(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-e5", tmp_path, egress_profile="research-read", egress_allowlist=["allowed.example"])
    handle = backend.open(task_id="task-e5", scope=scope)
    result = backend.exec(handle, ["net", "https://not-allowed.example/x"])
    assert result.ok is False
    assert "egress wall" in result.denied_reason


def test_egress_deny_all_when_no_profile_configured(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-e6", tmp_path)  # egress_profile="" by default
    handle = backend.open(task_id="task-e6", scope=scope)
    result = backend.exec(handle, ["net", "https://anything.example/"])
    assert result.ok is False
    assert "deny-all" in result.denied_reason


def test_egress_allows_explicit_allowlist_match(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-e7", tmp_path, egress_profile="research-read", egress_allowlist=["allowed.example"])
    handle = backend.open(task_id="task-e7", scope=scope)
    result = backend.exec(handle, ["net", "https://allowed.example/x"])
    assert result.ok is True


# ---------------------------------------------------------------------------
# Escape-prevention (design §5.3) — denied ⇒ no side effect
# ---------------------------------------------------------------------------


def test_escape_attempt_denied_result_has_no_side_effect(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-x1", tmp_path)
    handle = backend.open(task_id="task-x1", scope=scope)
    outside = tmp_path.parent / "escaped.txt"
    result = backend.exec(handle, ["write", "../escaped.txt", "pwned"])
    assert result.ok is False
    assert not outside.exists()


def test_escape_via_unknown_verb_denied_fail_closed(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-x2", tmp_path)
    handle = backend.open(task_id="task-x2", scope=scope)
    result = backend.exec(handle, ["shell", "rm -rf /"])
    assert result.ok is False
    assert "unknown verb" in result.denied_reason


def test_resource_limit_denies_over_cap_sleep(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-x3", tmp_path, resource_limits=ResourceLimits(wallclock_seconds=1.0))
    handle = backend.open(task_id="task-x3", scope=scope)
    result = backend.exec(handle, ["sleep", "999"])
    assert result.ok is False
    assert "resource limit" in result.denied_reason


def test_resource_limit_denies_oversized_write(tmp_path):
    backend = LocalStubSandbox()
    scope = _scope("task-x4", tmp_path, resource_limits=ResourceLimits(max_output_bytes=4))
    handle = backend.open(task_id="task-x4", scope=scope)
    result = backend.exec(handle, ["write", "big.txt", "way too much content"])
    assert result.ok is False
    assert "resource limit" in result.denied_reason
    assert not (tmp_path / "big.txt").exists()


# ---------------------------------------------------------------------------
# GATE-3 red-team residuals (DAS-1564/1565 logs) — routed to DAS-1567 (here).
# ---------------------------------------------------------------------------


def test_host_wall_nul_byte_path_denies_cleanly_not_a_raised_valueerror(tmp_path):
    """SC-005 residual (a): the contract-desired shape for a NUL-byte path is a
    clean `ExecResult(ok=False)`, exactly like every other host-wall escape —
    never an exception escaping `exec()`. Today it raises; this asserts the
    DESIRED contract and is expected to fail until local_stub.py is patched."""
    backend = LocalStubSandbox()
    scope = _scope("task-nul1", tmp_path)
    handle = backend.open(task_id="task-nul1", scope=scope)
    nul_path = "foo" + "\x00" + "bar"

    try:
        result = backend.exec(handle, ["read", nul_path])
    except ValueError:
        # Fail-closed baseline holds REGARDLESS of the denial shape: no path
        # was ever read/written for the NUL-byte candidate.
        assert not any(p.name.startswith("foo") for p in tmp_path.iterdir())
        raise

    # Desired contract shape (contract.py's ExecResult docstring): a denial is
    # a RETURNED ExecResult(ok=False), never a raised exception.
    assert result.ok is False
    assert not any(p.name.startswith("foo") for p in tmp_path.iterdir())


def test_credential_exec_result_stdout_is_not_serialized_into_an_event_by_a_correct_caller(tmp_path):
    """SC-005 residual (b) — caller-side raw-stdout Tier-M assertion: `cred`
    returns the secret VALUE in `ExecResult.stdout` BY DESIGN (the in-sandbox
    task is the intended consumer; see local_stub.py's `_exec_cred` comment).
    The Tier-M guarantee therefore rests entirely on CALLERS: an event MUST be
    built from `ScopedSecret.to_event_fields()`, and raw `stdout` must never be
    serialized into one. This test proves both the leak path a naive caller
    would hit AND that the safe projection never carries the secret."""
    secret_value = "sk-fake" + "-caller" + "-stdout" + "-501"
    cred = ScopedSecret(name="svc-token", value=secret_value, scope="task-tm1", ttl_seconds=120)
    backend = LocalStubSandbox()
    scope = _scope("task-tm1", tmp_path, credentials=[cred])
    handle = backend.open(task_id="task-tm1", scope=scope)

    result = backend.exec(handle, ["cred", "svc-token"])
    assert result.ok is True
    assert result.stdout == secret_value  # intended in-sandbox-consumer path

    # A NAIVE caller that serializes raw stdout into an event WOULD leak it —
    # this is exactly the mistake the design flags callers to avoid.
    naive_event = {"exec_stdout": result.stdout}
    assert secret_value in repr(naive_event)

    # The Tier-M-SAFE caller path never touches raw stdout for the event.
    safe_event = {"credential_grant": cred.to_event_fields()}
    assert secret_value not in repr(safe_event)
    assert "value" not in cred.to_event_fields()


# ---------------------------------------------------------------------------
# Flag-off inert
# ---------------------------------------------------------------------------


def test_flag_off_via_env_override(monkeypatch):
    # The committed config is ON after the 2026-07-26 activation; force the flag
    # OFF explicitly to keep the inert-path coverage deterministic.
    monkeypatch.setenv("DASLAB_WS_C_FLAG", "false")
    monkeypatch.delenv("DASLAB_FEATURES", raising=False)
    assert flag.flag_on() is False


def test_flag_reads_tracked_features_file_as_on(monkeypatch):
    # ACTIVATED 2026-07-26: the tracked config now carries ws_c_langgraph_loop ON.
    monkeypatch.delenv("DASLAB_WS_C_FLAG", raising=False)
    monkeypatch.setenv("DASLAB_FEATURES", str(ROOT / "config" / "features.yaml"))
    assert flag.flag_on() is True


def test_flag_env_override_can_flip_on(monkeypatch):
    monkeypatch.setenv("DASLAB_WS_C_FLAG", "true")
    assert flag.flag_on() is True
    monkeypatch.setenv("DASLAB_WS_C_FLAG", "false")
    assert flag.flag_on() is False


def test_adapter_usable_regardless_of_flag_state(tmp_path, monkeypatch):
    """The adapter itself is a library — it stays importable/usable no matter
    the flag; the flag only gates the (separately flagged-off) WS-C loop that
    would call it. Flag OFF ⇒ no behavior of this module changes."""
    monkeypatch.setenv("DASLAB_WS_C_FLAG", "false")  # force OFF (config is ON after activation)
    assert flag.flag_on() is False
    backend = LocalStubSandbox()
    scope = _scope("task-f1", tmp_path)
    handle = backend.open(task_id="task-f1", scope=scope)
    result = backend.exec(handle, ["write", "ok.txt", "fine"])
    assert result.ok is True
