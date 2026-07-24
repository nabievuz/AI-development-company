"""WS-E RBAC + audit + SIEM export tests (TN-3 / TN-4 / FR-001 / FR-002, DAS-1582).

Positive + negative coverage for the Founder-gate RBAC model and the read-only one-way
SIEM audit export (design ``docs/design/ws-e-tenant-hardening.md`` §1-2). These are the
DAS-1582 unit tests; the formal negative-test suite SC-001/SC-002 is folded into DAS-1585
against the SAME surfaces.

  RBAC (TN-3 / FR-001, §1)
    * agent identity (every one of the 32 roles) denied gate.approve / run.trigger /
      config.edit.security — structural, fail-closed
    * non-Founder human (audit-team) is READ-ONLY: audit.read allow; approve/trigger/
      routing/config-edit all deny (mutate nothing)
    * orchestrator is a mechanism: routing allow, but cannot ORIGINATE approve/trigger
    * founder is the ONLY principal holding gate.approve and config.edit.security
    * unknown/forged principal holds nothing (deny-all)
    * load_grants REFUSES a tampered rbac.yaml that grants a founder-only permission to a
      non-founder kind (structural QONUN-5 exclusion at load time)
    * a forged `approval: human:founder` frontmatter with NO backing Founder-identity
      event closes NO gate; a matching Founder-identity event DOES close it
    * an agent cannot emit a gate_approval stamped principal_kind: founder (write refused)
    * every QONUN-5 category maps to the human-only founder role

  Audit + SIEM export (TN-4 / FR-002, §2)
    * the audit ledger is append-only (records accrete, never rewritten)
    * a gate_approval record is Tier-M by construction (no secret/prompt/completion/source)
    * the SIEM export is read-only OTel/JSON and NEVER writes back to the ledger/board
    * a redaction probe over an exported record: planted secrets/PII do not survive
    * a hosted audit sink BLOCKS the export (in-tenant boundary reuse)
    * flag OFF ⇒ export is inert and RBAC enforcement is inert
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The 32 org role keys (.claude/agents/<key>.md) — the agent-exclusion is asserted for ALL.
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
    import sys  # noqa: PLC0415

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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _flag_on(tmp_path: Path, on: bool = True) -> Path:
    """Write a minimal features.yaml with ws_e_tenant_hardening on/off; return its path."""
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_e_tenant_hardening: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _tenant_config(tmp_path: Path, audit_url: str) -> Path:
    """Write a tenant_boundary.yaml with the audit sink pointed at *audit_url*."""
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


# --------------------------------------------------------------------------- #
# RBAC — agent structural exclusion (SC-001)
# --------------------------------------------------------------------------- #
def test_every_agent_role_denied_founder_only_permissions():
    """No agent role — none of the 32 — holds gate.approve / run.trigger / config.edit.security."""
    for role in ROLE_KEYS:
        principal = f"agent:{role}"
        for perm in ("gate.approve", "run.trigger", "config.edit.security"):
            decision, _ = rbac.decide(principal, perm)
            assert decision == "deny", f"{principal} must be denied {perm}"


def test_agent_denied_routing_mutation():
    assert rbac.decide("agent:backend-em", "board.mutate.routing")[0] == "deny"


def test_agent_board_work_scoped_to_own_ticket():
    """An agent works its OWN ticket only — board.work denies without ownership scope,
    allows with it."""
    assert rbac.decide("agent:backend-em", "board.work")[0] == "deny"
    assert rbac.decide("agent:backend-em", "board.work", scope=True)[0] == "allow"


# --------------------------------------------------------------------------- #
# RBAC — audit-team read-only (SC-001)
# --------------------------------------------------------------------------- #
def test_audit_team_is_read_only():
    """audit-team may READ the trail and mutate NOTHING."""
    assert rbac.decide("audit-team", "audit.read")[0] == "allow"
    for perm in (
        "gate.approve",
        "run.trigger",
        "board.mutate.routing",
        "board.work",
        "config.edit.security",
    ):
        assert rbac.decide("audit-team", perm)[0] == "deny", f"audit-team must not hold {perm}"


# --------------------------------------------------------------------------- #
# RBAC — orchestrator mechanism (cannot originate approve/trigger)
# --------------------------------------------------------------------------- #
def test_orchestrator_routes_but_cannot_originate_approval_or_trigger():
    assert rbac.decide("orchestrator", "board.mutate.routing")[0] == "allow"
    assert rbac.decide("orchestrator", "gate.approve")[0] == "deny"
    assert rbac.decide("orchestrator", "run.trigger")[0] == "deny"
    assert rbac.decide("orchestrator", "config.edit.security")[0] == "deny"


# --------------------------------------------------------------------------- #
# RBAC — founder is the sole approver (SC-001)
# --------------------------------------------------------------------------- #
def test_founder_is_the_only_gate_approver():
    assert rbac.decide("founder", "gate.approve")[0] == "allow"
    assert rbac.decide("founder", "config.edit.security")[0] == "allow"

    # Founder is the ONLY principal kind holding gate.approve and config.edit.security.
    grants = rbac.load_grants()
    for perm in ("gate.approve", "config.edit.security"):
        holders = [kind for kind, perms in grants.items() if perm in perms]
        assert holders == ["founder"], f"{perm} holders must be [founder]; got {holders}"


def test_unknown_or_forged_principal_holds_nothing():
    for principal in ("", "not-a-kind", "backend-em", "human:founder", "founder-ish"):
        for perm in ("gate.approve", "audit.read", "board.work"):
            assert rbac.decide(principal, perm)[0] == "deny", f"{principal!r}/{perm} must deny"


# --------------------------------------------------------------------------- #
# RBAC — structural load refusal of a tampered config (§1.3)
# --------------------------------------------------------------------------- #
def test_load_refuses_founder_only_permission_granted_to_agent(tmp_path):
    """A tampered rbac.yaml that grants gate.approve to the agent kind is REFUSED at load —
    the founder-only permission is structurally unrepresentable for a non-founder kind."""
    bad = tmp_path / "rbac.yaml"
    bad.write_text(
        "version: 1\ngrants:\n  founder:\n    gate.approve: allow\n"
        "  agent:\n    gate.approve: allow\n",
        encoding="utf-8",
    )
    with pytest.raises(rbac.RbacConfigError):
        rbac.load_grants(config_path=bad)


def test_missing_config_grants_nothing(tmp_path):
    """An ABSENT rbac.yaml grants nothing (every decide denies) — fail-closed, not a crash."""
    missing = tmp_path / "does-not-exist.yaml"
    assert rbac.load_grants(config_path=missing) == {}
    assert rbac.decide("founder", "gate.approve", config_path=missing)[0] == "deny"


def test_shipped_rbac_config_loads_and_is_structurally_valid():
    """The tracked config/rbac.yaml loads clean (no structural violation)."""
    grants = rbac.load_grants()
    assert grants["founder"]["gate.approve"] == "allow"
    assert "gate.approve" not in grants.get("agent", {})
    assert grants["audit-team"] == {"audit.read": "allow"}


def test_every_qonun5_category_maps_to_founder():
    """Every never-auto-approve category maps to the human-only founder role (FR-001)."""
    cfg = ROOT / "config" / "rbac.yaml"
    import yaml  # noqa: PLC0415

    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    authority = data["gate_approval_authority"]
    assert set(authority) == set(rbac.QONUN5_CATEGORIES)
    assert all(role == "founder" for role in authority.values())


# --------------------------------------------------------------------------- #
# RBAC — approval is an attributed EVENT, not a frontmatter string (SC-001 crux)
# --------------------------------------------------------------------------- #
def test_forged_frontmatter_claim_closes_no_gate(tmp_path):
    """A ticket carrying `approval: human:founder` with NO backing Founder-identity event
    is a forged claim — the gate stays OPEN."""
    ledger = tmp_path / ".rbac-audit.jsonl"  # empty ledger — no backing event
    closed, reason = rbac.is_gate_closed(
        "DAS-1586", "gate5_deployment", approval_claim="human:founder", audit_path=ledger
    )
    assert closed is False
    assert "forged" in reason.lower() or "not closed" in reason.lower()


def test_matching_founder_event_closes_the_gate(tmp_path):
    """A matching Founder-identity gate_approval event DOES close the gate."""
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

    # But a DIFFERENT ticket/category is still not closed by that event.
    assert rbac.is_gate_closed("DAS-9999", "gate5_deployment", audit_path=ledger)[0] is False
    assert rbac.is_gate_closed("DAS-1586", "security_sensitive", audit_path=ledger)[0] is False


def test_agent_cannot_emit_founder_gate_approval(tmp_path):
    """An agent principal cannot emit a gate_approval at all — the write is refused, so it
    can never stamp principal_kind: founder."""
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
    # Nothing was written — the forged attempts left the ledger empty, so the gate is open.
    assert rbac.iter_gate_approvals(ledger) == []
    assert rbac.is_gate_closed("DAS-1586", "gate5_deployment", audit_path=ledger)[0] is False


def test_appended_record_is_stamped_founder_kind_by_runtime(tmp_path):
    """The runtime stamps principal_kind from the authenticated principal (not caller input)."""
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


# --------------------------------------------------------------------------- #
# Audit trail — append-only + Tier-M (no secret field) (SC-002)
# --------------------------------------------------------------------------- #
def test_audit_ledger_is_append_only(tmp_path):
    """Records accrete; the ledger is never rewritten/truncated by the module."""
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
    # The file has exactly three JSON lines (append-only, one per record).
    assert len([ln for ln in ledger.read_text().splitlines() if ln.strip()]) == 3


def test_gate_approval_record_carries_no_secret_field(tmp_path):
    """A gate_approval record is Tier-M by construction — no secret/prompt/completion/source."""
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


# --------------------------------------------------------------------------- #
# SIEM export — flag OFF inert (SC-005)
# --------------------------------------------------------------------------- #
def test_export_inert_when_flag_off(tmp_path):
    features = _flag_on(tmp_path, on=False)
    res = siem.export_audit(features_path=features)
    assert res.ran is False
    assert res.target is None
    assert res.read == 0 and res.exported == 0


def test_rbac_enforcement_inert_when_flag_off(tmp_path):
    """With the flag OFF, enforce_gate_closed is inert (returns closed=True, dispatch unchanged)."""
    features = _flag_on(tmp_path, on=False)
    ledger = tmp_path / ".rbac-audit.jsonl"  # empty — would be "not closed" if enforced
    closed, reason = rbac.enforce_gate_closed(
        "DAS-1586", "gate5_deployment", audit_path=ledger, features_path=features
    )
    assert closed is True
    assert "inert" in reason.lower()


# --------------------------------------------------------------------------- #
# SIEM export — read-only OTel/JSON, one-way, redacted (SC-002)
# --------------------------------------------------------------------------- #
def test_export_is_readonly_otel_json_and_never_writes_back(tmp_path):
    """The export reads the ledger and emits OTLP/JSON; it NEVER writes back to the ledger,
    the board event store, or a ticket file."""
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "file:///var/lib/daslab/audit")  # in-tenant sink
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
    # One-way: the source ledger is byte-identical after export (no write-back).
    assert ledger.read_bytes() == before
    # The exporter created no board event store / ticket write anywhere in tmp.
    assert not (tmp_path / ".events.jsonl").exists()

    # The payload is OTLP/JSON log shape.
    assert res.posted is True
    target, payload = captured[0]
    assert "resourceLogs" in payload
    body = json.dumps(payload)
    assert "gate_approval" in body

    # The module exposes NO write-back API (read + export only).
    assert not hasattr(siem, "write_back")
    assert not hasattr(siem, "append")


def test_redaction_probe_over_exported_record(tmp_path):
    """A synthetic audit record carrying planted secrets/PII in a Tier-B field: each is
    replaced by its [REDACTED:...] token and no raw secret substring survives the export."""
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "file:///var/lib/daslab/audit")
    ledger = tmp_path / ".rbac-audit.jsonl"

    api_key = "sk-ant-" + "api03-" + "A" * 40  # fragmented so this test file holds no key
    bearer = "Bearer " + "z" * 40
    dsn = "postgres://user:" + "pw" * 8 + "@db.internal/app"
    email = "alice.founder" + "@example.com"
    # A Tier-B (non-Tier-M) field carrying planted secrets — must be scrubbed on export.
    record = {
        "event_type": "gate_approval",
        "ticket_id": "DAS-1586",
        "principal_id": "founder",
        "principal_kind": "founder",
        "category": "gate5_deployment",
        "gate": "GATE-5",
        "ts": TS,
        "note": f"leak {api_key} {bearer} {dsn} {email}",  # Tier-B free text
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
    # No raw secret/PII substring survives.
    for raw in (api_key, bearer.split(" ", 1)[1], "user:" + "pw" * 8, email):
        assert raw not in body, f"raw secret leaked into export: {raw[:12]}..."
    assert "[REDACTED:" in body
    # Tier-M ids survive intact (no over-redaction).
    assert "DAS-1586" in body and "gate5_deployment" in body


def test_hosted_siem_sink_blocks_the_export(tmp_path):
    """A hosted audit sink fails the in-tenant boundary and BLOCKS the export (audit is not
    an accepted external role — only the model call is)."""
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "https://siem.public-vendor.example.com")  # hosted
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-1586", category="gate5_deployment",
        gate="GATE-5", created_at=TS, audit_path=ledger,
    )
    with pytest.raises(siem.BoundaryError) as exc:
        siem.export_audit(audit_path=ledger, config_path=config, features_path=features, post=True)
    assert "EXTERNAL" in str(exc.value) or "not intact" in str(exc.value)


def test_model_call_is_the_sole_accepted_external_exception(tmp_path):
    """With the audit sink in-tenant, the export proceeds even though the model endpoint is
    an external Anthropic url — the model call is the one accepted exception."""
    features = _flag_on(tmp_path, on=True)
    config = _tenant_config(tmp_path, "http://127.0.0.1:9200")  # in-tenant SIEM (e.g. Elastic)
    ledger = tmp_path / ".rbac-audit.jsonl"
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-1586", category="gate5_deployment",
        gate="GATE-5", created_at=TS, audit_path=ledger,
    )
    res = siem.export_audit(audit_path=ledger, config_path=config, features_path=features)
    assert res.ran is True
    assert res.target == "http://127.0.0.1:9200/v1/logs"
