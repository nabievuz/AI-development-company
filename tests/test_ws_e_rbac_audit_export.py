from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


ROLE_KEYS = [
    "backend-em", "backend-eng-1", "backend-eng-2", "board-member", "cdo", "ceo",
    "chairman", "cmo", "content-lead", "coo", "cpo", "cto", "design-lead",
    "finance-analyst", "frontend-em", "frontend-eng-1", "frontend-eng-2",
    "growth-marketer", "legal-analyst", "product-analyst", "product-designer",
    "qa-eng", "qa-lead", "security-eng", "security-lead", "senior-pm",
    "seo-specialist", "sre-eng", "sre-lead", "support-lead", "tech-writer",
    "ux-researcher",
]


def _load(rel: str, name: str):
    import sys

    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rbac = _load("scripts/rbac.py", "rbac")
siem = _load("scripts/rbac_siem_export.py", "rbac_siem_export")

TS = "2026-07-24T12:00:00Z"


def _flag_on(tmp_path: Path, on: bool = True) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_e_tenant_hardening: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _subdir(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tenant_config(tmp_path: Path, audit_url: str) -> Path:
    p = tmp_path / "tenant_boundary.yaml"
    p.write_text(
        "version: 1\n"
        "accepted_external_roles:\n  - model\n"
        "endpoints:\n"
        "  - name: claude_model\n    role: model\n    carries_code_ip: true\n"
        "    url: https://api.anthropic.com\n"
        "  - name: audit_store\n    role: audit\n    carries_code_ip: true\n"
        f"    url: {audit_url}\n",
        encoding="utf-8",
    )
    return p


def test_every_agent_role_denied_founder_only_permissions():
    for role in ROLE_KEYS:
        principal = f"agent:{role}"
        for perm in ("gate.approve", "run.trigger", "config.edit.security"):
            decision, _ = rbac.decide(principal, perm)
            assert decision == "deny", f"{principal} must be denied {perm}"


def test_agent_denied_routing_mutation():
    assert rbac.decide("agent:backend-em", "board.mutate.routing")[0] == "deny"


def test_agent_board_work_scoped_to_own_ticket():
    assert rbac.decide("agent:backend-em", "board.work")[0] == "deny"
    assert rbac.decide("agent:backend-em", "board.work", scope=True)[0] == "allow"


def test_audit_team_is_read_only():
    assert rbac.decide("audit-team", "audit.read")[0] == "allow"
    for perm in (
        "gate.approve",
        "run.trigger",
        "board.mutate.routing",
        "board.work",
        "config.edit.security",
    ):
        assert rbac.decide("audit-team", perm)[0] == "deny", f"audit-team must not hold {perm}"


def test_orchestrator_routes_but_cannot_originate_approval_or_trigger():
    assert rbac.decide("orchestrator", "board.mutate.routing")[0] == "allow"
    assert rbac.decide("orchestrator", "gate.approve")[0] == "deny"
    assert rbac.decide("orchestrator", "run.trigger")[0] == "deny"
    assert rbac.decide("orchestrator", "config.edit.security")[0] == "deny"


def test_founder_is_the_only_gate_approver():
    assert rbac.decide("founder", "gate.approve")[0] == "allow"
    assert rbac.decide("founder", "config.edit.security")[0] == "allow"


    grants = rbac.load_grants()
    for perm in ("gate.approve", "config.edit.security"):
        holders = [kind for kind, perms in grants.items() if perm in perms]
        assert holders == ["founder"], f"{perm} holders must be [founder]; got {holders}"


def test_unknown_or_forged_principal_holds_nothing():
    for principal in ("", "not-a-kind", "backend-em", "human:founder", "founder-ish"):
        for perm in ("gate.approve", "audit.read", "board.work"):
            assert rbac.decide(principal, perm)[0] == "deny", f"{principal!r}/{perm} must deny"


def test_load_refuses_founder_only_permission_granted_to_agent(tmp_path):
    bad = tmp_path / "rbac.yaml"
    bad.write_text(
        "version: 1\ngrants:\n  founder:\n    gate.approve: allow\n"
        "  agent:\n    gate.approve: allow\n",
        encoding="utf-8",
    )
    with pytest.raises(rbac.RbacConfigError):
        rbac.load_grants(config_path=bad)


def test_missing_config_grants_nothing(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    assert rbac.load_grants(config_path=missing) == {}
    assert rbac.decide("founder", "gate.approve", config_path=missing)[0] == "deny"


def test_shipped_rbac_config_loads_and_is_structurally_valid():
    grants = rbac.load_grants()
    assert grants["founder"]["gate.approve"] == "allow"
    assert "gate.approve" not in grants.get("agent", {})
    assert grants["audit-team"] == {"audit.read": "allow"}


def test_every_qonun5_category_maps_to_founder():
    cfg = ROOT / "config" / "rbac.yaml"
    import yaml

    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    authority = data["gate_approval_authority"]
    assert set(authority) == set(rbac.QONUN5_CATEGORIES)
    assert all(role == "founder" for role in authority.values())


def test_forged_frontmatter_claim_closes_no_gate(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    closed, reason = rbac.is_gate_closed(
        "DAS-1586", "gate5_deployment", approval_claim="human:founder", audit_path=ledger
    )
    assert closed is False
    assert "forged" in reason.lower() or "not closed" in reason.lower()


def test_matching_founder_event_closes_the_gate(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder",
        ticket_id="DAS-1586",
        category="gate5_deployment",
        gate="GATE-5",
        created_at=TS,
        audit_path=ledger,
    )
    closed, _ = rbac.is_gate_closed("DAS-1586", "gate5_deployment", audit_path=ledger)
    assert closed is True


    assert rbac.is_gate_closed("DAS-9999", "gate5_deployment", audit_path=ledger)[0] is False
    assert rbac.is_gate_closed("DAS-1586", "security_sensitive", audit_path=ledger)[0] is False


def test_agent_cannot_emit_founder_gate_approval(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    for principal in ("agent:backend-em", "agent:cto", "audit-team", "orchestrator", "founder-ish"):
        with pytest.raises(rbac.ApprovalRefused):
            rbac.append_gate_approval(
                principal=principal,
                ticket_id="DAS-1586",
                category="gate5_deployment",
                gate="GATE-5",
                created_at=TS,
                audit_path=ledger,
            )

    assert rbac.iter_gate_approvals(ledger) == []
    assert rbac.is_gate_closed("DAS-1586", "gate5_deployment", audit_path=ledger)[0] is False


def test_appended_record_is_stamped_founder_kind_by_runtime(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    rec = rbac.append_gate_approval(
        principal="founder",
        ticket_id="DAS-1586",
        category="gate5_deployment",
        gate="GATE-5",
        created_at=TS,
        audit_path=ledger,
    )
    assert rec["principal_kind"] == "founder"
    assert rec["principal_id"] == "founder"
    assert rec["event_type"] == "gate_approval"


def test_audit_ledger_is_append_only(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    for i in range(3):
        rbac.append_gate_approval(
            principal="founder",
            ticket_id=f"DAS-160{i}",
            category="security_sensitive",
            gate="GATE-3",
            created_at=TS,
            audit_path=ledger,
        )
    recs = rbac.iter_gate_approvals(ledger)
    assert len(recs) == 3
    assert [r["ticket_id"] for r in recs] == ["DAS-1600", "DAS-1601", "DAS-1602"]

    assert len([ln for ln in ledger.read_text().splitlines() if ln.strip()]) == 3


def test_gate_approval_record_carries_no_secret_field(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    rec = rbac.append_gate_approval(
        principal="founder",
        ticket_id="DAS-1586",
        category="gate5_deployment",
        gate="GATE-5",
        created_at=TS,
        attestation_ref="a1b2c3",
        audit_path=ledger,
    )
    for forbidden in ("secret", "token", "prompt", "completion", "source", "diff", "password"):
        assert forbidden not in rec


def test_export_inert_when_flag_off(tmp_path):
    features = _flag_on(tmp_path, on=False)
    res = siem.export_audit(features_path=features)
    assert res.ran is False
    assert res.target is None
    assert res.read == 0 and res.exported == 0


def test_rbac_enforcement_inert_when_flag_off(tmp_path):
    features = _flag_on(tmp_path, on=False)
    ledger = tmp_path / ".rbac-audit.jsonl"
    closed, reason = rbac.enforce_gate_closed(
        "DAS-1586", "gate5_deployment", audit_path=ledger, features_path=features
    )
    assert closed is True
    assert "inert" in reason.lower()


def test_ambient_env_cannot_disable_enforcement_that_the_config_commits(tmp_path, monkeypatch):
    features = _flag_on(tmp_path, on=True)
    ledger = tmp_path / ".rbac-audit.jsonl"
    for value in ("false", "0", "off", "no", "", "true", "1", "garbage"):
        monkeypatch.setenv("DASLAB_WS_E_FLAG", value)
        assert rbac.is_enabled(features) is True, value
        closed, reason = rbac.enforce_gate_closed(
            "DAS-1586", "gate5_deployment", audit_path=ledger, features_path=features
        )
        assert closed is False, value
        assert "inert" not in reason.lower(), value


def test_explicit_features_path_outranks_any_environment_value(tmp_path, monkeypatch):
    off = _flag_on(_subdir(tmp_path, "off_dir"), on=False)
    on = _flag_on(_subdir(tmp_path, "on_dir"), on=True)
    for value in ("true", "1", "false", "0"):
        monkeypatch.setenv("DASLAB_WS_E_FLAG", value)
        assert rbac.is_enabled(off) is False, value
        assert rbac.is_enabled(on) is True, value


def test_flag_reader_consults_no_environment_variable_at_all(tmp_path, monkeypatch):
    features = _flag_on(tmp_path, on=True)
    monkeypatch.setenv("DASLAB_ROOT", str(_subdir(tmp_path, "elsewhere")))
    for name in ("DASLAB_WS_E_FLAG", "DASLAB_WS_E_TENANT_HARDENING_FLAG", "DASLAB_FEATURES"):
        monkeypatch.setenv(name, "false")
    assert rbac.is_enabled(features) is True
    assert rbac.is_enabled(_flag_on(_subdir(tmp_path, "off_dir"), on=False)) is False


def test_flag_stays_fail_safe_to_off_when_the_file_cannot_be_read(tmp_path, monkeypatch):


    monkeypatch.setenv("DASLAB_WS_E_FLAG", "true")
    assert rbac.is_enabled(tmp_path / "does-not-exist.yaml") is False
    other = tmp_path / "unrelated.yaml"
    other.write_text("some_other_flag: true\n", encoding="utf-8")
    assert rbac.is_enabled(other) is False


def test_export_is_readonly_otel_json_and_never_writes_back(tmp_path):
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "file:///var/lib/daslab/audit")
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder",
        ticket_id="DAS-1586",
        category="gate5_deployment",
        gate="GATE-5",
        created_at=TS,
        audit_path=ledger,
    )
    before = ledger.read_bytes()

    captured: list[tuple[str, dict]] = []
    res = siem.export_audit(
        audit_path=ledger,
        config_path=config,
        features_path=features,
        transport=lambda t, p: captured.append((t, p)),
        post=True,
    )
    assert res.ran is True
    assert res.exported == 1 and res.dropped == 0

    assert ledger.read_bytes() == before

    assert not (tmp_path / ".events.jsonl").exists()


    assert res.posted is True
    target, payload = captured[0]
    assert "resourceLogs" in payload
    body = json.dumps(payload)
    assert "gate_approval" in body


    assert not hasattr(siem, "write_back")
    assert not hasattr(siem, "append")


def test_redaction_probe_over_exported_record(tmp_path):
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "file:///var/lib/daslab/audit")
    ledger = tmp_path / ".rbac-audit.jsonl"

    api_key = "sk-ant-" + "api03-" + "A" * 40
    bearer = "Bearer " + "z" * 40
    dsn = "postgres://user:" + "pw" * 8 + "@db.internal/app"
    email = "alice.founder" + "@example.com"

    record = {
        "event_type": "gate_approval",
        "ticket_id": "DAS-1586",
        "principal_id": "founder",
        "principal_kind": "founder",
        "category": "gate5_deployment",
        "gate": "GATE-5",
        "ts": TS,
        "note": f"leak {api_key} {bearer} {dsn} {email}",
    }
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    captured: list[tuple[str, dict]] = []
    res = siem.export_audit(
        audit_path=ledger,
        config_path=config,
        features_path=features,
        transport=lambda t, p: captured.append((t, p)),
        post=True,
    )
    assert res.exported == 1
    body = json.dumps(captured[0][1])

    for raw in (api_key, bearer.split(" ", 1)[1], "user:" + "pw" * 8, email):
        assert raw not in body, f"raw secret leaked into export: {raw[:12]}..."
    assert "[REDACTED:" in body

    assert "DAS-1586" in body and "gate5_deployment" in body


def test_hosted_siem_sink_blocks_the_export(tmp_path):
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "https://siem.public-vendor.example.com")
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-1586", category="gate5_deployment",
        gate="GATE-5", created_at=TS, audit_path=ledger,
    )
    with pytest.raises(siem.BoundaryError) as exc:
        siem.export_audit(audit_path=ledger, config_path=config, features_path=features, post=True)
    assert "EXTERNAL" in str(exc.value) or "not intact" in str(exc.value)


def test_model_call_is_the_sole_accepted_external_exception(tmp_path):
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "http://127.0.0.1:9200")
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-1586", category="gate5_deployment",
        gate="GATE-5", created_at=TS, audit_path=ledger,
    )
    res = siem.export_audit(audit_path=ledger, config_path=config, features_path=features)
    assert res.ran is True
    assert res.target == "http://127.0.0.1:9200/v1/logs"
