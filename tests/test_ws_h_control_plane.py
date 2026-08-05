from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


AGENT_ROLES = [
    "backend-em", "backend-eng-1", "backend-eng-2", "cto", "ceo",
    "security-lead", "senior-pm", "qa-lead", "frontend-em", "sre-lead",
]


_PLANTED_SECRET = "token=sk-ant-" + "api03-" + ("Z" * 44) + " contact=jane@example.com"


def _load_rbac():
    spec = importlib.util.spec_from_file_location("rbac_probe", ROOT / "scripts" / "rbac.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _features(tmp_path: Path, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_h_control_plane: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _load_app(features_path: Path | None = None):
    pytest.importorskip("fastapi")
    spec = importlib.util.spec_from_file_location(
        "cp_app", ROOT / "tools" / "control_plane" / "app.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if features_path is not None:
        mod.FEATURES_PATH = Path(features_path)
    return mod


def _client(mod):
    from fastapi.testclient import TestClient

    return TestClient(mod.app)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    tickets = tmp_path / "board" / "tickets"
    tickets.mkdir(parents=True)
    for tid, status in [("DAS-1", "done"), ("DAS-2", "in_progress"), ("DAS-3", "in_progress")]:
        (tickets / f"{tid}-x.md").write_text(
            f"---\nid: {tid}\ntitle: T {tid}\nstatus: {status}\nassignee: ceo\n"
            f"updated: 2026-07-2{tid[-1]}\n---\nbody\n",
            encoding="utf-8",
        )
    rbac = tmp_path / "vault-tokens.json"
    rbac.write_text(
        json.dumps(
            {
                "tokens": {
                    "tf": {"user": "akmal", "principal": "founder"},
                    "ta": {"user": "team", "principal": "audit-team"},
                    "tg": {"user": "orch", "principal": "orchestrator"},
                    "tb": {"user": "bot", "principal": "agent:backend-em"},
                    "tx": {"user": "ghost", "principal": "bogus-principal"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_RBAC", str(rbac))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    _features(tmp_path, on=True)
    return tmp_path


def _audit_lines(root: Path) -> list[dict]:
    path = root / "audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_founder_only_gate_approve_and_run_trigger_by_construction():
    rbac = _load_rbac()
    grants = rbac.load_grants()
    assert rbac.decide("founder", "gate.approve", config=grants)[0] == "allow"
    assert rbac.decide("founder", "run.trigger", config=grants)[0] == "allow"

    for role in AGENT_ROLES:
        assert rbac.decide(f"agent:{role}", "gate.approve", config=grants)[0] == "deny"
        assert rbac.decide(f"agent:{role}", "run.trigger", config=grants)[0] == "deny"
    assert rbac.decide("audit-team", "gate.approve", config=grants)[0] == "deny"
    assert rbac.decide("orchestrator", "run.trigger", config=grants)[0] == "deny"
    assert rbac.decide("bogus-principal", "audit.read", config=grants)[0] == "deny"


def test_flag_off_is_inert_and_degrades_to_static(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    off = _features(tmp_path, on=False)
    client = _client(_load_app(off))

    assert client.get("/api/board").status_code == 404
    assert client.post("/api/goals", json={"title": "x y z"}).status_code == 404

    assert client.get("/healthz").json()["flag"] is False
    page = client.get("/")
    assert page.status_code == 200 and "read-only cockpit" in page.text

    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "board" / "goal-inbox").exists()


def test_unconfigured_token_map_is_503_and_shell_is_data_free(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.delenv("DASLAB_CP_RBAC", raising=False)
    client = _client(_load_app())
    assert client.get("/api/board").status_code == 503
    health = client.get("/healthz").json()
    assert health["ok"] is True and health["rbac_configured"] is False
    assert "DAS-1" not in client.get("/").text


def test_structurally_invalid_rbac_config_is_503(env, monkeypatch):
    bad = env / "bad-rbac.yaml"
    bad.write_text("grants:\n  agent:\n    gate.approve: allow\n", encoding="utf-8")
    monkeypatch.setenv("DASLAB_CP_RBAC_CONFIG", str(bad))
    client = _client(_load_app())


    assert client.get("/api/board", headers=_h("tf")).status_code == 503
    assert client.get("/healthz").status_code == 200


def test_bad_or_missing_token_is_401_and_audited(env):
    client = _client(_load_app())
    assert client.get("/api/board").status_code == 401
    assert client.get("/api/board", headers=_h("nope")).status_code == 401
    assert client.get("/api/board", headers=_h("tx")).status_code == 401
    denies = [r for r in _audit_lines(env) if r["action"] == "auth" and r["decision"] == "deny"]
    assert denies, "a bad-token 401 must append an audited deny"


def test_founder_reads_board_and_submits_goal_audited(env):
    client = _client(_load_app())
    board = client.get("/api/board", headers=_h("tf"))
    assert board.status_code == 200
    assert board.json()["counts"]["in_progress"] == 2 and board.json()["total"] == 3

    resp = client.post("/api/goals", headers=_h("tf"), json={"title": "Ship WS-H", "body": "detail"})
    assert resp.status_code == 201
    written = env / resp.json()["written"]
    assert written.is_file()
    text = written.read_text(encoding="utf-8")
    assert "status: proposed" in text and "author: akmal" in text and "detail" in text

    submits = [r for r in _audit_lines(env) if r["action"] == "goal.submit"]
    assert submits and submits[-1]["decision"] == "allow"
    assert submits[-1]["principal_id"] == "founder" and submits[-1]["principal_kind"] == "founder"


def test_audit_team_reads_but_cannot_submit_goal_403_audited(env):
    client = _client(_load_app())

    assert client.get("/api/board", headers=_h("ta")).status_code == 200

    denied = client.post("/api/goals", headers=_h("ta"), json={"title": "team goal"})
    assert denied.status_code == 403
    deny = [r for r in _audit_lines(env) if r["action"] == "goal.submit" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "audit-team"
    assert not (env / "board" / "goal-inbox").exists()


def test_agent_principal_denied_unscoped_read_403_audited(env):
    client = _client(_load_app())
    resp = client.get("/api/board", headers=_h("tb"))
    assert resp.status_code == 403
    deny = [r for r in _audit_lines(env) if r["action"] == "board.read" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "agent"


def test_cockpit_endpoint_degrades_honestly(env):
    client = _client(_load_app())
    resp = client.get("/api/cockpit", headers=_h("tf"))
    assert resp.status_code == 200
    assert resp.json()["source"] in {"scripts/cockpit.py", "unavailable"}
    assert resp.json()["text"]


def test_audit_detail_is_redacted_and_record_is_tier_m(env):
    mod = _load_app()
    mod.audit("goal.submit", "founder", "founder", "allow", "granted", _PLANTED_SECRET)
    rec = _audit_lines(env)[-1]

    assert set(rec) == {"ts", "action", "principal_id", "principal_kind", "decision", "reason", "detail"}
    assert "sk-ant-api03" not in rec["detail"] and "jane@example.com" not in rec["detail"]
    assert "[REDACTED:api_key]" in rec["detail"] and "[REDACTED:pii]" in rec["detail"]


def test_html_shell_carries_no_board_data(env):
    client = _client(_load_app())
    page = client.get("/")
    assert page.status_code == 200
    assert "DAS-1" not in page.text


_GATE5 = "gate5_deployment"


def _rbac_ledger(root: Path) -> Path:
    return root / "board" / ".rbac-audit.jsonl"


def test_das1601_non_founder_cannot_emit_gate_approval(tmp_path):
    rbac = _load_rbac()
    ledger = tmp_path / "rbac.jsonl"
    for principal in ["audit-team", "orchestrator", *(f"agent:{r}" for r in AGENT_ROLES)]:
        with pytest.raises(rbac.ApprovalRefused):
            rbac.append_gate_approval(
                principal=principal, ticket_id="DAS-9", category=_GATE5, gate="GATE-5",
                created_at="2026-07-24T00:00:00Z", audit_path=ledger,
            )
    assert not ledger.exists()
    assert rbac.iter_gate_approvals(audit_path=ledger) == []


def test_das1601_forged_frontmatter_claim_leaves_gate_open_founder_event_closes(tmp_path):
    rbac = _load_rbac()
    ledger = tmp_path / "rbac.jsonl"
    closed, _ = rbac.is_gate_closed(
        "DAS-9", _GATE5, approval_claim="human:founder", audit_path=ledger
    )
    assert closed is False
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-9", category=_GATE5, gate="GATE-5",
        created_at="2026-07-24T00:00:00Z", audit_path=ledger,
    )
    closed2, _ = rbac.is_gate_closed("DAS-9", _GATE5, audit_path=ledger)
    assert closed2 is True


def test_das1601_founder_approve_writes_one_attributed_event(tmp_path):
    rbac = _load_rbac()
    ledger = tmp_path / "rbac.jsonl"
    rec = rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-9", category=_GATE5, gate="GATE-5",
        created_at="2026-07-24T00:00:00Z", audit_path=ledger,
    )
    events = rbac.iter_gate_approvals(audit_path=ledger)
    assert len(events) == 1
    assert rec["principal_kind"] == "founder" and rec["event_type"] == "gate_approval"
    assert rec["ticket_id"] == "DAS-9" and rec["category"] == _GATE5


def test_das1601_non_founder_approve_gate_403_no_event(env):
    client = _client(_load_app())
    rbac = _load_rbac()
    for token, kind in [("ta", "audit-team"), ("tb", "agent")]:
        resp = client.post(
            "/api/gates/DAS-9/approve", headers=_h(token),
            json={"category": _GATE5, "gate": "GATE-5"},
        )
        assert resp.status_code == 403
        deny = [
            r for r in _audit_lines(env)
            if r["action"] == "gate.approve" and r["decision"] == "deny"
        ]
        assert deny and deny[-1]["principal_kind"] == kind

    assert rbac.iter_gate_approvals(audit_path=_rbac_ledger(env)) == []


def test_das1601_founder_approve_gate_closes_gate_audited(env):
    client = _client(_load_app())
    rbac = _load_rbac()
    resp = client.post(
        "/api/gates/DAS-9/approve", headers=_h("tf"),
        json={"category": _GATE5, "gate": "GATE-5"},
    )
    assert resp.status_code == 201 and resp.json()["gate_approval"] is True
    assert resp.json()["principal_kind"] == "founder"
    events = rbac.iter_gate_approvals(audit_path=_rbac_ledger(env))
    assert len(events) == 1 and events[0]["principal_kind"] == "founder"
    closed, _ = rbac.is_gate_closed("DAS-9", _GATE5, audit_path=_rbac_ledger(env))
    assert closed is True
    allow = [
        r for r in _audit_lines(env)
        if r["action"] == "gate.approve" and r["decision"] == "allow"
    ]
    assert allow and allow[-1]["principal_id"] == "founder"


def test_das1601_founder_deny_writes_no_event_gate_stays_open(env):
    client = _client(_load_app())
    rbac = _load_rbac()
    resp = client.post(
        "/api/gates/DAS-9/deny", headers=_h("tf"),
        json={"category": _GATE5, "gate": "GATE-5"},
    )
    assert resp.status_code == 201 and resp.json()["gate_approval"] is False

    assert rbac.iter_gate_approvals(audit_path=_rbac_ledger(env)) == []
    closed, _ = rbac.is_gate_closed("DAS-9", _GATE5, audit_path=_rbac_ledger(env))
    assert closed is False
    assert [r for r in _audit_lines(env) if r["action"] == "gate.deny"]


def test_das1601_non_founder_trigger_run_403_audited_no_intent(env):
    client = _client(_load_app())
    resp = client.post("/api/runs", headers=_h("ta"), json={"target": "wave-next"})
    assert resp.status_code == 403
    deny = [
        r for r in _audit_lines(env)
        if r["action"] == "run.trigger" and r["decision"] == "deny"
    ]
    assert deny and deny[-1]["principal_kind"] == "audit-team"
    assert not (env / "board" / "run-inbox").exists()


def test_das1601_founder_trigger_run_queues_intent_never_dispatches(env):
    client = _client(_load_app())
    resp = client.post(
        "/api/runs", headers=_h("tf"), json={"target": "wave-next", "note": "go"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "requested" and body["dispatched"] is False
    intent = env / body["queued"]
    assert intent.is_file()
    text = intent.read_text(encoding="utf-8")
    assert "status: requested" in text and "author: akmal" in text
    assert "dispatches NOTHING" in text.upper() or "dispatch" in text.lower()


    assert not (env / "board" / "runs").exists()
    assert not (env / "board" / "wave-ledger.jsonl").exists()
    submits = [
        r for r in _audit_lines(env)
        if r["action"] == "run.trigger" and r["decision"] == "allow"
    ]
    assert submits and submits[-1]["principal_id"] == "founder"


def test_das1601_gate5_open_stays_machine_blocked_after_trigger(env, monkeypatch):
    client = _client(_load_app())
    rbac = _load_rbac()

    assert client.post("/api/runs", headers=_h("tf"), json={"target": "deploy"}).status_code == 201

    ledger = _rbac_ledger(env)
    closed, _ = rbac.is_gate_closed("DAS-DEPLOY", _GATE5, audit_path=ledger)
    assert closed is False

    monkeypatch.setenv("DASLAB_WS_E_FLAG", "1")
    enforced, _ = rbac.enforce_gate_closed("DAS-DEPLOY", _GATE5, audit_path=ledger)
    assert enforced is False


def test_das1601_flag_off_new_endpoints_are_inert(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    off = _features(tmp_path, on=False)
    client = _client(_load_app(off))
    assert client.post("/api/runs", json={"target": "x"}).status_code == 404
    assert client.post("/api/gates/DAS-9/approve", json={"category": _GATE5}).status_code == 404
    assert client.post("/api/gates/DAS-9/deny", json={"category": _GATE5}).status_code == 404

    assert not (tmp_path / "board" / "run-inbox").exists()
    assert not (tmp_path / "board" / ".rbac-audit.jsonl").exists()


def test_sc001_every_data_and_action_endpoint_fail_closed_503_when_unconfigured(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.delenv("DASLAB_CP_RBAC", raising=False)
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    client = _client(_load_app())
    for path in ("/api/board", "/api/cockpit", "/api/audit"):
        assert client.get(path).status_code == 503, path
    assert client.post("/api/goals", json={"title": "x y z"}).status_code == 503
    assert client.post("/api/runs", json={"target": "x"}).status_code == 503
    assert (
        client.post("/api/gates/DAS-9/approve", json={"category": _GATE5}).status_code == 503
    )
    assert client.post("/api/gates/DAS-9/deny", json={"category": _GATE5}).status_code == 503

    assert client.get("/healthz").status_code == 200
    shell = client.get("/")
    assert shell.status_code == 200 and "DAS-" not in shell.text


    assert not (tmp_path / "audit.jsonl").exists()


def test_r4_denied_trigger_run_never_touches_runs_dir_or_wave_ledger(env):
    client = _client(_load_app())
    resp = client.post("/api/runs", headers=_h("ta"), json={"target": "wave-next"})
    assert resp.status_code == 403
    assert not (env / "board" / "runs").exists()
    assert not (env / "board" / "wave-ledger.jsonl").exists()
    assert not (env / "board" / "run-inbox").exists()


def test_r1_bearer_token_lookup_uses_constant_time_compare():


    source = (ROOT / "tools" / "control_plane" / "app.py").read_text(encoding="utf-8")
    assert "hmac" in source
    assert "compare_digest" in source


def test_r2_principal_resolution_ignores_request_supplied_overrides(env):
    client = _client(_load_app())
    resp = client.post(
        "/api/goals",
        headers={**_h("ta"), "X-Principal": "founder", "X-Kind": "founder"},
        params={"principal": "founder", "kind": "founder"},
        json={"title": "escalate attempt", "principal": "founder", "kind": "founder"},
    )
    assert resp.status_code == 403
    deny = [r for r in _audit_lines(env) if r["action"] == "goal.submit" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "audit-team"


def test_r2_vault_principals_are_already_canonical(env):
    rbac = _load_rbac()
    tokens = json.loads((env / "vault-tokens.json").read_text(encoding="utf-8"))["tokens"]
    for entry in tokens.values():
        principal = entry["principal"]
        if principal == "bogus-principal":
            continue
        assert principal == principal.strip().lower(), f"non-canonical vault principal {principal!r}"
        assert rbac._kind_of(principal) is not None


def test_r3_ci_installs_control_plane_deps_so_endpoint_tests_actually_run():


    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "requirements-control.txt" in ci


def test_sc005_control_plane_app_and_install_are_ruff_clean():
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not on PATH in this environment")
    targets = [str(ROOT / "tools" / "control_plane" / "app.py"), str(ROOT / "tools" / "control_plane" / "install")]
    result = subprocess.run([ruff, "check", *targets], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sc005_ruff_module_invocation_also_clean_when_available():
    if importlib.util.find_spec("ruff") is None:
        pytest.skip("ruff module not importable in this interpreter")
    targets = [str(ROOT / "tools" / "control_plane" / "app.py"), str(ROOT / "tools" / "control_plane" / "install")]
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", *targets], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_env_value_can_open_a_config_off_control_plane(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    off = _features(tmp_path, on=False)
    for value in ("1", "true", "on", "yes"):
        monkeypatch.setenv("DASLAB_WS_H_FLAG", value)
        mod = _load_app(off)
        assert mod.flag_on() is False, value
        client = _client(mod)
        assert client.get("/api/board").status_code == 404, value
        assert client.post("/api/gates/GATE-1/approve", json={}).status_code == 404, value


def test_no_env_value_can_close_a_config_on_control_plane(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    on = _features(tmp_path, on=True)
    for value in ("0", "false", "off", ""):
        monkeypatch.setenv("DASLAB_WS_H_FLAG", value)
        assert _load_app(on).flag_on() is True, value


def test_flag_reads_through_the_canonical_feature_flags_reader(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    sys.path.insert(0, str(ROOT / "scripts"))
    import feature_flags

    mod = _load_app()
    assert mod.FEATURES_PATH is None
    for value in ("1", "0"):
        monkeypatch.setenv("DASLAB_WS_H_FLAG", value)
        assert mod.flag_on() is feature_flags.enabled("ws_h_control_plane"), value
