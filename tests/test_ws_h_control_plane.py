"""WS-H control-plane PoC tests (ADR-0039): fail-closed, RBAC, governed goal write, audit."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _load_app():
    spec = importlib.util.spec_from_file_location(
        "cp_app", ROOT / "tools" / "control_plane" / "app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A synthetic repo root + RBAC file with one token per role."""
    tickets = tmp_path / "board" / "tickets"
    tickets.mkdir(parents=True)
    for tid, status in [("DAS-1", "done"), ("DAS-2", "in_progress"), ("DAS-3", "in_progress")]:
        (tickets / f"{tid}-x.md").write_text(
            f"---\nid: {tid}\ntitle: T {tid}\nstatus: {status}\nassignee: ceo\n"
            f"updated: 2026-07-2{tid[-1]}\n---\nbody\n",
            encoding="utf-8",
        )
    rbac = tmp_path / "rbac.json"
    rbac.write_text(
        json.dumps(
            {
                "tokens": {
                    "tv": {"user": "vera", "role": "viewer"},
                    "to": {"user": "omar", "role": "operator"},
                    "tf": {"user": "akmal", "role": "founder"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_RBAC", str(rbac))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    return tmp_path


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_fail_closed_without_rbac(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.delenv("DASLAB_CP_RBAC", raising=False)
    client = TestClient(_load_app().app)
    assert client.get("/api/board").status_code == 503
    assert client.get("/healthz").json() == {"ok": True, "rbac_configured": False}


def test_bad_token_401(env):
    client = TestClient(_load_app().app)
    assert client.get("/api/board", headers=_h("nope")).status_code == 401
    assert client.get("/api/board").status_code == 401


def test_viewer_reads_but_cannot_write(env):
    client = TestClient(_load_app().app)
    board = client.get("/api/board", headers=_h("tv"))
    assert board.status_code == 200
    assert board.json()["counts"]["in_progress"] == 2
    assert board.json()["total"] == 3
    denied = client.post("/api/goals", headers=_h("tv"), json={"title": "New goal"})
    assert denied.status_code == 403


def test_operator_submits_goal_file_and_audit(env):
    client = TestClient(_load_app().app)
    resp = client.post(
        "/api/goals", headers=_h("to"), json={"title": "Ship WS-H!", "body": "detail"}
    )
    assert resp.status_code == 201
    written = env / resp.json()["written"]
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    assert "status: proposed" in text and "author: omar" in text and "detail" in text
    audit_lines = (env / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"goal.submit"' in line and '"allow"' in line for line in audit_lines)


def test_founder_outranks_operator(env):
    client = TestClient(_load_app().app)
    assert client.post("/api/goals", headers=_h("tf"), json={"title": "Founder goal"}).status_code == 201
    audit = client.get("/api/audit", headers=_h("tf"))
    assert audit.status_code == 200 and audit.json()["entries"]


def test_cockpit_endpoint_degrades_honestly(env):
    client = TestClient(_load_app().app)
    resp = client.get("/api/cockpit", headers=_h("tv"))
    assert resp.status_code == 200
    assert resp.json()["source"] in {"scripts/cockpit.py", "unavailable"}
    assert resp.json()["text"]


def test_html_shell_carries_no_data(env):
    client = TestClient(_load_app().app)
    page = client.get("/")
    assert page.status_code == 200
    assert "DAS-1" not in page.text  # shell only; data needs a token (CP-2)
