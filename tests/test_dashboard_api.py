from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

ORG_FIXTURE = """
escalation_ladder:
- ic
- lead
- cxo
- founder
departments:
- key: engineering
  title: Engineering
  manager_role: cto
- key: operations
  title: Operations
  manager_role: coo
roles:
- key: ceo
  dept: governance
  title: CEO
  reports_to: null
- key: cto
  dept: engineering
  title: CTO
  reports_to: ceo
- key: backend-em
  dept: engineering
  title: Backend EM
  reports_to: cto
- key: backend-eng-1
  dept: engineering
  title: Backend Engineer 1
  reports_to: backend-em
- key: coo
  dept: operations
  title: COO
  reports_to: ceo
- key: finance-analyst
  dept: operations
  title: Finance Analyst
  reports_to: coo
"""

TOKENS = {
    "tf": {"user": "akmal", "principal": "founder"},
    "tf-cto": {"user": "akmal", "principal": "founder", "role": "cto"},
    "ta": {"user": "auditor", "principal": "audit-team"},
    "ta-em": {"user": "em", "principal": "audit-team", "role": "backend-em"},
    "ta-eng": {"user": "eng", "principal": "audit-team", "role": "backend-eng-1"},
    "ta-fin": {"user": "fin", "principal": "audit-team", "role": "finance-analyst"},
    "tagent": {"user": "bot", "principal": "agent:backend-eng-1"},
}


def _load_app():
    pytest.importorskip("fastapi")
    spec = importlib.util.spec_from_file_location(
        "cp_app_dashboard", ROOT / "tools" / "control_plane" / "app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _client(mod):
    from fastapi.testclient import TestClient

    return TestClient(mod.app)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir(parents=True)
    (config / "org.yaml").write_text(ORG_FIXTURE, encoding="utf-8")
    (config / "features.yaml").write_text("ws_h_control_plane: true\n", encoding="utf-8")
    (config / "t7_rubric.yaml").write_text("version: 1\n", encoding="utf-8")
    board = tmp_path / "board"
    (board / "tickets").mkdir(parents=True)
    (board / "interrupts").mkdir(parents=True)
    (board / "tickets" / "DAS-9-x.md").write_text(
        "---\nid: DAS-9\ntitle: T\nstatus: blocked\npriority: p0\nupdated: 2026-08-01\n---\n",
        encoding="utf-8",
    )
    (board / "interrupts" / "schema.json").write_text(
        json.dumps(
            {
                "required": ["question", "options", "ticket", "payload", "created_by"],
                "additionalProperties": False,
                "properties": {
                    "question": {},
                    "options": {},
                    "ticket": {},
                    "payload": {},
                    "created_by": {},
                },
            }
        ),
        encoding="utf-8",
    )
    (board / "interrupts" / "GOOD.json").write_text(
        json.dumps(
            {
                "question": "ship?",
                "options": ["yes", "no"],
                "ticket": "DAS-9",
                "payload": {},
                "created_by": "cto",
            }
        ),
        encoding="utf-8",
    )
    (board / "interrupts" / "BAD.json").write_text(
        json.dumps({"question": "flip the flag?", "authorized_by": "founder"}),
        encoding="utf-8",
    )
    rbac = tmp_path / "tokens.json"
    rbac.write_text(json.dumps({"tokens": TOKENS}), encoding="utf-8")
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_RBAC", str(rbac))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("DASLAB_CP_RBAC_CONFIG", raising=False)
    return tmp_path


def _me(client, token: str) -> dict:
    response = client.get("/api/dashboard/me", headers=_h(token))
    assert response.status_code == 200
    return response.json()


def test_tiers_derive_from_the_org_escalation_ladder(env):
    client = _client(_load_app())
    assert _me(client, "tf")["tier"] == "founder"
    assert _me(client, "tf-cto")["tier"] == "cxo"
    assert _me(client, "ta-em")["tier"] == "lead"
    assert _me(client, "ta-eng")["tier"] == "ic"
    assert _me(client, "tf")["ladder"] == ["ic", "lead", "cxo", "founder"]


def test_role_overlay_narrows_and_never_widens(env):
    client = _client(_load_app())
    founder = set(_me(client, "tf")["modules"])
    for token in ("tf-cto", "ta", "ta-em", "ta-eng", "ta-fin", "tagent"):
        assert set(_me(client, token)["modules"]) <= founder


def test_overlay_strips_founder_only_actions(env):
    client = _client(_load_app())
    assert _me(client, "tf")["actions"] == ["gate.approve", "goal.submit", "run.trigger"]
    assert _me(client, "tf-cto")["actions"] == []
    assert _me(client, "ta")["actions"] == []


def test_department_scoping_hides_other_departments(env):
    client = _client(_load_app())
    engineer = set(_me(client, "ta-eng")["modules"])
    assert "engineering.waves" in engineer
    assert "product.board" not in engineer
    assert "operations.cost" not in engineer


def test_cost_module_is_executive_only(env):
    client = _client(_load_app())
    assert client.get("/api/dashboard/cost", headers=_h("tf")).status_code == 200
    assert client.get("/api/dashboard/cost", headers=_h("ta-eng")).status_code == 403
    assert client.get("/api/dashboard/cost", headers=_h("ta-fin")).status_code == 403


def test_agent_principals_hold_no_dashboard_modules(env):
    client = _client(_load_app())
    assert _me(client, "tagent")["modules"] == []
    assert client.get("/api/dashboard/org", headers=_h("tagent")).status_code == 403


def test_every_visible_module_is_backed_by_a_substrate_grant(env):
    mod = _load_app()
    client = _client(mod)
    import sys

    sys.path.insert(0, str(ROOT / "tools" / "control_plane"))
    from dashboard_api import capabilities

    grants = mod.load_grants()
    for token, entry in TOKENS.items():
        principal = entry["principal"]
        for module_id in _me(client, token)["modules"]:
            module = capabilities.MODULES_BY_ID[module_id]
            decision, _ = mod._rbac.decide(principal, module.permission, config=grants)
            assert decision == "allow"


def test_unauthenticated_and_unknown_tokens_are_rejected(env):
    client = _client(_load_app())
    assert client.get("/api/dashboard/me").status_code == 401
    assert client.get("/api/dashboard/me", headers=_h("nope")).status_code == 401
    assert client.get("/api/dashboard/org", headers=_h("")).status_code == 401


def test_dashboard_is_404_when_the_flag_is_off(env, monkeypatch):
    (env / "config" / "features.yaml").write_text("ws_h_control_plane: false\n", encoding="utf-8")
    mod = _load_app()
    mod.FEATURES_PATH = env / "config" / "features.yaml"
    client = _client(mod)
    assert client.get("/api/dashboard/me", headers=_h("tf")).status_code == 404
    assert client.get("/api/dashboard/org", headers=_h("tf")).status_code == 404


def test_dashboard_is_503_when_rbac_is_unconfigured(env, monkeypatch):
    monkeypatch.delenv("DASLAB_CP_RBAC")
    client = _client(_load_app())
    assert client.get("/api/dashboard/me", headers=_h("tf")).status_code == 503


def test_openapi_schema_is_not_served(env):
    client = _client(_load_app())
    assert client.get("/openapi.json").status_code == 404


def test_interrupt_cards_report_schema_divergence(env):
    client = _client(_load_app())
    body = client.get("/api/dashboard/interrupts", headers=_h("tf")).json()
    assert body["total"] == 2
    assert body["schema_divergent"] == 1
    bad = next(c for c in body["cards"] if c["id"] == "BAD")
    good = next(c for c in body["cards"] if c["id"] == "GOOD")
    assert good["schema_valid"] is True
    assert bad["schema_valid"] is False
    assert any("options" in v for v in bad["violations"])
    assert bad["answerable"] is False


def test_a_failing_module_degrades_without_a_500(env, monkeypatch):
    import sys

    sys.path.insert(0, str(ROOT / "tools" / "control_plane"))
    from dashboard_api import readers, router

    def boom() -> dict:
        raise RuntimeError("module exploded")

    assert router._safe(boom)["available"] is False
    assert "module exploded" in router._safe(boom)["reason"]
    monkeypatch.setattr(readers, "org_directory", boom)
    client = _client(_load_app())
    response = client.get("/api/dashboard/org", headers=_h("tf"))
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_reads_are_audited_with_allow_and_deny(env):
    client = _client(_load_app())
    client.get("/api/dashboard/org", headers=_h("tf"))
    client.get("/api/dashboard/cost", headers=_h("ta-eng"))
    lines = [
        json.loads(line)
        for line in (env / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    allows = [r for r in lines if r["action"] == "dashboard.org.directory" and r["decision"] == "allow"]
    denies = [r for r in lines if r["action"] == "dashboard.operations.cost" and r["decision"] == "deny"]
    assert allows
    assert denies


def test_board_reader_surfaces_real_ticket_state(env):
    client = _client(_load_app())
    body = client.get("/api/dashboard/board", headers=_h("tf")).json()
    assert body["available"] is True
    assert body["total"] == 1
    assert body["blocked"] == 1
    assert body["by_priority"]["p0"] == 1


def test_summary_payload_excludes_the_full_role_roster(env):
    client = _client(_load_app())
    body = client.get("/api/dashboard/summary", headers=_h("tf")).json()
    assert "org" in body["panels"]
    assert "roles" not in body["panels"]["org"]
    assert body["panels"]["org"]["totals"]["roles"] == 6
