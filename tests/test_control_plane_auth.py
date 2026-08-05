from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_app(features_path: Path | None = None):
    pytest.importorskip("fastapi")
    spec = importlib.util.spec_from_file_location(
        "cp_app_auth", ROOT / "tools" / "control_plane" / "app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if features_path is not None:
        mod.FEATURES_PATH = Path(features_path)
    return mod


def _client(mod, raise_server_exceptions: bool = True):
    from fastapi.testclient import TestClient

    return TestClient(mod.app, raise_server_exceptions=raise_server_exceptions)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    tickets = tmp_path / "board" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / "DAS-1-x.md").write_text(
        "---\nid: DAS-1\ntitle: T\nstatus: done\nassignee: ceo\nupdated: 2026-07-21\n---\nbody\n",
        encoding="utf-8",
    )
    rbac = tmp_path / "vault-tokens.json"
    rbac.write_text(
        json.dumps({"tokens": {"tf": {"user": "akmal", "principal": "founder"}}}),
        encoding="utf-8",
    )
    features = tmp_path / "features.yaml"
    features.write_text("ws_h_control_plane: true\n", encoding="utf-8")
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_RBAC", str(rbac))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    return tmp_path


def _audit_lines(root: Path) -> list[dict]:
    path = root / "audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _auth_lines(root: Path) -> list[dict]:
    return [r for r in _audit_lines(root) if r["action"] == "auth"]


NON_ASCII_TOKEN = "tökén-Ω-ÿ"
NON_ASCII_HEADERS = [(b"authorization", ("Bearer " + NON_ASCII_TOKEN).encode("utf-8"))]


def test_non_ascii_bearer_token_is_401_not_500(env):
    client = _client(_load_app())
    resp = client.get("/api/board", headers=NON_ASCII_HEADERS)
    assert resp.status_code == 401


def test_non_ascii_bearer_token_is_audited(env):
    client = _client(_load_app())
    client.get("/api/board", headers=NON_ASCII_HEADERS)
    denies = [r for r in _auth_lines(env) if r["decision"] == "deny"]
    assert len(denies) == 1
    assert denies[0]["reason"] == "unknown bearer token"


def test_match_token_compares_bytes_and_never_raises_on_non_ascii(env):
    mod = _load_app()
    tokens = {"tf": {"user": "akmal", "principal": "founder"}}
    assert mod._match_token(tokens, NON_ASCII_TOKEN) is None
    assert mod._match_token(tokens, "tf") == tokens["tf"]


def test_type_confusion_in_token_map_cannot_defeat_the_compare(env):
    mod = _load_app()
    tokens = {"tf": {"user": "akmal", "principal": "founder"}, 7: {"principal": "founder"}}
    assert mod._match_token(tokens, "7") is None
    assert mod._match_token(tokens, "tf") == tokens["tf"]


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({}, "no authorization header"),
        ({"Authorization": "Bearer "}, "empty bearer token"),
        ({"Authorization": "Basic dXNlcjpwdw=="}, "malformed authorization header"),
        ({"Authorization": "tf"}, "malformed authorization header"),
        ({"Authorization": "Bearer wrong-token"}, "unknown bearer token"),
        (NON_ASCII_HEADERS, "unknown bearer token"),
        ({"Authorization": "Bearer " + "z" * 200_000}, "unknown bearer token"),
    ],
)
def test_every_failed_auth_outcome_is_401_and_writes_exactly_one_audit_deny(env, headers, reason):
    client = _client(_load_app())
    resp = client.get("/api/board", headers=headers)
    assert resp.status_code == 401
    denies = [r for r in _auth_lines(env) if r["decision"] == "deny"]
    assert len(denies) == 1
    assert denies[0]["reason"].startswith(reason)
    assert denies[0]["principal_id"] == "-"


def test_token_mapping_to_an_unknown_principal_is_401_and_audited(env, monkeypatch):
    rbac = env / "vault-tokens.json"
    rbac.write_text(
        json.dumps({"tokens": {"tx": {"user": "ghost", "principal": "bogus-principal"}}}),
        encoding="utf-8",
    )
    client = _client(_load_app())
    assert client.get("/api/board", headers=_h("tx")).status_code == 401
    denies = [r for r in _auth_lines(env) if r["decision"] == "deny"]
    assert len(denies) == 1
    assert denies[0]["reason"] == "token maps to an unusable principal"


def test_successful_auth_is_audited_before_the_response(env):
    client = _client(_load_app())
    assert client.get("/api/board", headers=_h("tf")).status_code == 200
    allows = [r for r in _auth_lines(env) if r["decision"] == "allow"]
    assert len(allows) == 1
    assert allows[0]["principal_id"] == "founder"
    assert allows[0]["principal_kind"] == "founder"


def test_bearer_scheme_is_case_insensitive(env):
    client = _client(_load_app())
    assert client.get("/api/board", headers={"Authorization": "bearer tf"}).status_code == 200


def test_oversized_body_is_413_and_audited(env, monkeypatch):
    monkeypatch.setenv("DASLAB_CP_MAX_REQUEST_BYTES", "2048")
    client = _client(_load_app())
    resp = client.post(
        "/api/goals", headers=_h("tf"), json={"title": "big goal", "body": "x" * 8192}
    )
    assert resp.status_code == 413
    rejects = [r for r in _audit_lines(env) if r["action"] == "request.reject"]
    assert rejects and rejects[-1]["decision"] == "deny"
    assert not (env / "board" / "goal-inbox").exists()


def test_oversized_chunked_body_without_content_length_is_413(env, monkeypatch):
    monkeypatch.setenv("DASLAB_CP_MAX_REQUEST_BYTES", "2048")
    client = _client(_load_app())

    def chunks():
        for _ in range(8):
            yield b"y" * 1024

    resp = client.post(
        "/api/goals",
        headers={**_h("tf"), "Content-Type": "application/json"},
        content=chunks(),
    )
    assert resp.status_code == 413
    assert [r for r in _audit_lines(env) if r["action"] == "request.reject"]


def test_body_within_the_limit_still_works(env, monkeypatch):
    monkeypatch.setenv("DASLAB_CP_MAX_REQUEST_BYTES", "8192")
    client = _client(_load_app())
    resp = client.post("/api/goals", headers=_h("tf"), json={"title": "small goal", "body": "ok"})
    assert resp.status_code == 201


def test_unhandled_error_is_500_and_audited(env, monkeypatch):
    mod = _load_app()

    def _boom() -> dict:
        raise RuntimeError("cockpit exploded")

    monkeypatch.setattr(mod, "board_summary", _boom)
    client = _client(mod, raise_server_exceptions=False)
    resp = client.get("/api/board", headers=_h("tf"))
    assert resp.status_code == 500
    errors = [r for r in _audit_lines(env) if r["action"] == "request.error"]
    assert errors and errors[-1]["decision"] == "error"
    assert errors[-1]["reason"] == "RuntimeError"


def test_healthz_needs_no_token_and_reports_configuration(env):
    client = _client(_load_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["rbac_configured"] is True
    assert _auth_lines(env) == []


def test_healthz_answers_even_when_rbac_is_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.delenv("DASLAB_CP_RBAC", raising=False)
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    client = _client(_load_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["rbac_configured"] is False
