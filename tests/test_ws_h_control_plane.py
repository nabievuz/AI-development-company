"""WS-H control-plane tests (ADR-0039 / DAS-1600).

Covers the hardened control plane: RBAC bound to the WS-E SSOT (``scripts/rbac.decide``
over ``config/rbac.yaml`` — the spike's ``viewer<operator<founder`` tier retired),
fail-closed 503/401/403, audited allow+deny, the governed goal-proposal write, and the
flag-OFF inert / degrade-to-static surface.

The endpoint tests need FastAPI (``importorskip`` — they skip where the optional
control-plane deps are absent and run in CI). The founder-only-by-construction assertion
loads the SSOT directly, so it runs everywhere.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A representative set of the org's agent roles — every one is denied gate.approve /
# run.trigger by construction (DAS-1603 asserts the full 32-role sweep).
AGENT_ROLES = [
    "backend-em", "backend-eng-1", "backend-eng-2", "cto", "ceo",
    "security-lead", "senior-pm", "qa-lead", "frontend-em", "sre-lead",
]

# A secret shape fragmented with ``+`` so no secret-literal is committed (diagnostics
# no-committed-secrets scanner); the scrubber must still redact the reassembled value.
_PLANTED_SECRET = "token=sk-ant-" + "api03-" + ("Z" * 44) + " contact=jane@example.com"


def _load_rbac():
    spec = importlib.util.spec_from_file_location("rbac_probe", ROOT / "scripts" / "rbac.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_app():
    pytest.importorskip("fastapi")
    spec = importlib.util.spec_from_file_location(
        "cp_app", ROOT / "tools" / "control_plane" / "app.py"
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
    """A synthetic tenant root + a vault token map keyed by SSOT PRINCIPAL (not a tier),
    with the WS-H flag ON. The SSOT grant matrix stays the real ``config/rbac.yaml``."""
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
    monkeypatch.setenv("DASLAB_WS_H_FLAG", "1")
    return tmp_path


def _audit_lines(root: Path) -> list[dict]:
    path = root / "audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# Founder-only by construction — runs without FastAPI (pure SSOT).
# ---------------------------------------------------------------------------
def test_founder_only_gate_approve_and_run_trigger_by_construction():
    rbac = _load_rbac()
    grants = rbac.load_grants()
    assert rbac.decide("founder", "gate.approve", config=grants)[0] == "allow"
    assert rbac.decide("founder", "run.trigger", config=grants)[0] == "allow"
    # No agent role, the read-only team, or the orchestrator can hold either — SSOT-enforced.
    for role in AGENT_ROLES:
        assert rbac.decide(f"agent:{role}", "gate.approve", config=grants)[0] == "deny"
        assert rbac.decide(f"agent:{role}", "run.trigger", config=grants)[0] == "deny"
    assert rbac.decide("audit-team", "gate.approve", config=grants)[0] == "deny"
    assert rbac.decide("orchestrator", "run.trigger", config=grants)[0] == "deny"
    assert rbac.decide("bogus-principal", "audit.read", config=grants)[0] == "deny"


# ---------------------------------------------------------------------------
# Flag OFF ⇒ inert surface + degrade-to-static (CP-5 / FR-006).
# ---------------------------------------------------------------------------
def test_flag_off_is_inert_and_degrades_to_static(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_WS_H_FLAG", "0")
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    client = _client(_load_app())
    # /api/* do not exist (inert), not even a 503/401 — the control surface is absent.
    assert client.get("/api/board").status_code == 404
    assert client.post("/api/goals", json={"title": "x y z"}).status_code == 404
    # Health probe answers and reports the flag OFF; GET / degrades to the static cockpit.
    assert client.get("/healthz").json()["flag"] is False
    page = client.get("/")
    assert page.status_code == 200 and "read-only cockpit" in page.text
    # Inert ⇒ nothing written, nothing audited.
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "board" / "goal-inbox").exists()


# ---------------------------------------------------------------------------
# Fail-closed RBAC (CP-2 / FR-002 / SC-001).
# ---------------------------------------------------------------------------
def test_unconfigured_token_map_is_503_and_shell_is_data_free(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_WS_H_FLAG", "1")
    monkeypatch.delenv("DASLAB_CP_RBAC", raising=False)
    client = _client(_load_app())
    assert client.get("/api/board").status_code == 503
    health = client.get("/healthz").json()
    assert health["ok"] is True and health["rbac_configured"] is False
    assert "DAS-1" not in client.get("/").text  # data-free shell answers


def test_structurally_invalid_rbac_config_is_503(env, monkeypatch):
    bad = env / "bad-rbac.yaml"
    bad.write_text("grants:\n  agent:\n    gate.approve: allow\n", encoding="utf-8")
    monkeypatch.setenv("DASLAB_CP_RBAC_CONFIG", str(bad))
    client = _client(_load_app())
    # A tampered security surface (founder-only perm granted to agent) is a LOUD 503,
    # never a silent partial load — even for a valid Founder token.
    assert client.get("/api/board", headers=_h("tf")).status_code == 503
    assert client.get("/healthz").status_code == 200


def test_bad_or_missing_token_is_401_and_audited(env):
    client = _client(_load_app())
    assert client.get("/api/board").status_code == 401                 # no header
    assert client.get("/api/board", headers=_h("nope")).status_code == 401  # unknown token
    assert client.get("/api/board", headers=_h("tx")).status_code == 401    # unresolvable principal
    denies = [r for r in _audit_lines(env) if r["action"] == "auth" and r["decision"] == "deny"]
    assert denies, "a bad-token 401 must append an audited deny"


# ---------------------------------------------------------------------------
# Governed reads + the goal-proposal write; least privilege (CP-2/CP-3 / FR-002/FR-003).
# ---------------------------------------------------------------------------
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
    # The near-term read-only team can read the trail/board...
    assert client.get("/api/board", headers=_h("ta")).status_code == 200
    # ...but the governed goal-proposal write is Founder-authorized (no operator tier).
    denied = client.post("/api/goals", headers=_h("ta"), json={"title": "team goal"})
    assert denied.status_code == 403
    deny = [r for r in _audit_lines(env) if r["action"] == "goal.submit" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "audit-team"
    assert not (env / "board" / "goal-inbox").exists()  # denied write touched nothing


def test_agent_principal_denied_unscoped_read_403_audited(env):
    client = _client(_load_app())
    resp = client.get("/api/board", headers=_h("tb"))
    assert resp.status_code == 403  # agent holds audit.read only for its OWN run (scoped)
    deny = [r for r in _audit_lines(env) if r["action"] == "board.read" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "agent"


def test_cockpit_endpoint_degrades_honestly(env):
    client = _client(_load_app())
    resp = client.get("/api/cockpit", headers=_h("tf"))
    assert resp.status_code == 200
    assert resp.json()["source"] in {"scripts/cockpit.py", "unavailable"}
    assert resp.json()["text"]


# ---------------------------------------------------------------------------
# Audit is Tier-M + ADR-0012 redacted at write (single scrubber reused).
# ---------------------------------------------------------------------------
def test_audit_detail_is_redacted_and_record_is_tier_m(env):
    mod = _load_app()
    mod.audit("goal.submit", "founder", "founder", "allow", "granted", _PLANTED_SECRET)
    rec = _audit_lines(env)[-1]
    # Tier-M shape: controlled-vocab metadata + ids only; no token/secret/payload field.
    assert set(rec) == {"ts", "action", "principal_id", "principal_kind", "decision", "reason", "detail"}
    assert "sk-ant-api03" not in rec["detail"] and "jane@example.com" not in rec["detail"]
    assert "[REDACTED:api_key]" in rec["detail"] and "[REDACTED:pii]" in rec["detail"]


def test_html_shell_carries_no_board_data(env):
    client = _client(_load_app())
    page = client.get("/")
    assert page.status_code == 200
    assert "DAS-1" not in page.text  # shell only; data needs a token (CP-2)


# ===========================================================================
# DAS-1601 — the two governed writes: approve-gate (CP-3c/FR-004) + trigger-run
# (CP-3b/FR-003), both board-canonical (CP-4/FR-005), Founder-only, never-bypass-gate.
# ===========================================================================
_GATE5 = "gate5_deployment"  # a QONUN-5 never-auto-approve category


def _rbac_ledger(root: Path) -> Path:
    """The tenant WS-E gate_approval ledger the approve endpoint appends to (§3.2)."""
    return root / "board" / ".rbac-audit.jsonl"


# ---------------------------------------------------------------------------
# Founder-only approval is EVENT-backed — pure SSOT, runs without FastAPI.
# ---------------------------------------------------------------------------
def test_das1601_non_founder_cannot_emit_gate_approval(tmp_path):
    """A non-Founder / agent principal can never produce a gate_approval — the write is
    refused before anything is appended (FR-004 / SC-002)."""
    rbac = _load_rbac()
    ledger = tmp_path / "rbac.jsonl"
    for principal in ["audit-team", "orchestrator", *(f"agent:{r}" for r in AGENT_ROLES)]:
        with pytest.raises(rbac.ApprovalRefused):
            rbac.append_gate_approval(
                principal=principal, ticket_id="DAS-9", category=_GATE5, gate="GATE-5",
                created_at="2026-07-24T00:00:00Z", audit_path=ledger,
            )
    assert not ledger.exists()  # nothing written by any refused attempt
    assert rbac.iter_gate_approvals(audit_path=ledger) == []


def test_das1601_forged_frontmatter_claim_leaves_gate_open_founder_event_closes(tmp_path):
    """``approval: human:founder`` frontmatter with NO backing event closes NO gate; a real
    Founder-identity gate_approval event does (FR-004 crux / SC-002)."""
    rbac = _load_rbac()
    ledger = tmp_path / "rbac.jsonl"
    closed, _ = rbac.is_gate_closed(
        "DAS-9", _GATE5, approval_claim="human:founder", audit_path=ledger
    )
    assert closed is False  # forged claim, no event => gate stays OPEN
    rbac.append_gate_approval(
        principal="founder", ticket_id="DAS-9", category=_GATE5, gate="GATE-5",
        created_at="2026-07-24T00:00:00Z", audit_path=ledger,
    )
    closed2, _ = rbac.is_gate_closed("DAS-9", _GATE5, audit_path=ledger)
    assert closed2 is True  # a Founder-identity event closes it


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


# ---------------------------------------------------------------------------
# Approve-gate endpoint (needs FastAPI — importorskip; green in CI).
# ---------------------------------------------------------------------------
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
    # No gate_approval event was written by any refused attempt.
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
    # A deny records the decision but appends NO gate_approval event — gate stays OPEN.
    assert rbac.iter_gate_approvals(audit_path=_rbac_ledger(env)) == []
    closed, _ = rbac.is_gate_closed("DAS-9", _GATE5, audit_path=_rbac_ledger(env))
    assert closed is False
    assert [r for r in _audit_lines(env) if r["action"] == "gate.deny"]


# ---------------------------------------------------------------------------
# Trigger-run endpoint — board-canonical INTENT, never a direct dispatch.
# ---------------------------------------------------------------------------
def test_das1601_non_founder_trigger_run_403_audited_no_intent(env):
    client = _client(_load_app())
    resp = client.post("/api/runs", headers=_h("ta"), json={"target": "wave-next"})
    assert resp.status_code == 403
    deny = [
        r for r in _audit_lines(env)
        if r["action"] == "run.trigger" and r["decision"] == "deny"
    ]
    assert deny and deny[-1]["principal_kind"] == "audit-team"
    assert not (env / "board" / "run-inbox").exists()  # denied write touched nothing


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
    # Board-canonical INTENT only: no run was dispatched — no board/runs/ output dir,
    # no wave-ledger append; the intent awaits the ADR-0034 runner / HEARTBEAT (C4).
    assert not (env / "board" / "runs").exists()
    assert not (env / "board" / "wave-ledger.jsonl").exists()
    submits = [
        r for r in _audit_lines(env)
        if r["action"] == "run.trigger" and r["decision"] == "allow"
    ]
    assert submits and submits[-1]["principal_id"] == "founder"


def test_das1601_gate5_open_stays_machine_blocked_after_trigger(env, monkeypatch):
    """A GATE-5-open deployment stays machine-blocked regardless of any button: the trigger
    writes an INTENT (no gate_approval event), and the engine gate enforcement blocks the
    deploy independently of the UI (FR-004 / SC-002 / C4)."""
    client = _client(_load_app())
    rbac = _load_rbac()
    # Founder triggers a run — a button press.
    assert client.post("/api/runs", headers=_h("tf"), json={"target": "deploy"}).status_code == 201
    # The GATE-5 gate has NO backing Founder gate_approval event → it stays CLOSED-shut.
    ledger = _rbac_ledger(env)
    closed, _ = rbac.is_gate_closed("DAS-DEPLOY", _GATE5, audit_path=ledger)
    assert closed is False  # the trigger did not (and cannot) close the gate
    # Engine gate enforcement (flag ON) independently blocks — the button has no path around it.
    monkeypatch.setenv("DASLAB_WS_E_FLAG", "1")
    enforced, _ = rbac.enforce_gate_closed("DAS-DEPLOY", _GATE5, audit_path=ledger)
    assert enforced is False  # machine-blocked at the engine layer, regardless of the UI


# ---------------------------------------------------------------------------
# Flag OFF ⇒ the new write endpoints are inert too (404, not 401/403/503).
# ---------------------------------------------------------------------------
def test_das1601_flag_off_new_endpoints_are_inert(tmp_path, monkeypatch):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_WS_H_FLAG", "0")
    monkeypatch.setenv("DASLAB_CP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    client = _client(_load_app())
    assert client.post("/api/runs", json={"target": "x"}).status_code == 404
    assert client.post("/api/gates/DAS-9/approve", json={"category": _GATE5}).status_code == 404
    assert client.post("/api/gates/DAS-9/deny", json={"category": _GATE5}).status_code == 404
    # Inert ⇒ nothing written anywhere.
    assert not (tmp_path / "board" / "run-inbox").exists()
    assert not (tmp_path / "board" / ".rbac-audit.jsonl").exists()


# ===========================================================================
# DAS-1603 — GATE-4 formal negative suite. Folds in the DAS-1600/1601 tests
# above (SC-001/SC-002 already covered by them) and closes the CTO's GATE-3
# residuals R1-R4 (see the ticket's "## Security conditions (GATE-3)").
# ===========================================================================


# ---------------------------------------------------------------------------
# SC-001 (fail-closed RBAC) — sweep EVERY data/action endpoint, not just
# /api/board, so an unconfigured RBAC 503s uniformly and nothing leaks.
# ---------------------------------------------------------------------------
def test_sc001_every_data_and_action_endpoint_fail_closed_503_when_unconfigured(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DASLAB_ROOT", str(tmp_path))
    monkeypatch.setenv("DASLAB_WS_H_FLAG", "1")
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
    # Fail-CLOSED, not DOWN: /healthz and the data-free shell still answer.
    assert client.get("/healthz").status_code == 200
    shell = client.get("/")
    assert shell.status_code == 200 and "DAS-" not in shell.text
    # Nothing was written by any 503'd request (unconfigured ⇒ no audit either —
    # there is no principal to attribute a deny to yet).
    assert not (tmp_path / "audit.jsonl").exists()


# ---------------------------------------------------------------------------
# R4 — the trigger-run intent never lands in board/runs/ or wave-ledger.jsonl,
# for BOTH the allowed (Founder) and the refused (non-Founder) path. The
# Founder path is already asserted end-to-end in
# ``test_das1601_founder_trigger_run_queues_intent_never_dispatches`` (L373+
# above); this test pins the refused path too, so a future change that makes
# a denied trigger-run partially write cannot slip through unnoticed.
# ---------------------------------------------------------------------------
def test_r4_denied_trigger_run_never_touches_runs_dir_or_wave_ledger(env):
    client = _client(_load_app())
    resp = client.post("/api/runs", headers=_h("ta"), json={"target": "wave-next"})
    assert resp.status_code == 403
    assert not (env / "board" / "runs").exists()
    assert not (env / "board" / "wave-ledger.jsonl").exists()
    assert not (env / "board" / "run-inbox").exists()


# ---------------------------------------------------------------------------
# R1 (GATE-3 residual, LOW) — constant-time bearer-token compare.
# ---------------------------------------------------------------------------
def test_r1_bearer_token_lookup_uses_constant_time_compare():
    # GATE-3 residual R1 (DAS-1603) — CLOSED by backend-em: `_identify` now resolves the
    # bearer token via `_match_token`, iterating the vault map and comparing each candidate
    # with `hmac.compare_digest` (no dict `.get()` hash lookup, no first-entry short-circuit).
    source = (ROOT / "tools" / "control_plane" / "app.py").read_text(encoding="utf-8")
    assert "hmac" in source
    assert "compare_digest" in source


# ---------------------------------------------------------------------------
# R2 (GATE-3 residual, INFO) — canonical-principal assertion: `_kind_of`'s
# case/whitespace normalization can never be reached by attacker input,
# because the principal is resolved ONLY from the vault token map — a
# request can present a bearer token, never a raw principal string.
# ---------------------------------------------------------------------------
def test_r2_principal_resolution_ignores_request_supplied_overrides(env):
    """A non-Founder token cannot escalate by injecting a `principal`/`kind`
    field into the request body, query string, or a custom header — identity
    resolution never looks past the vault-token lookup (FR-002 / SC-001)."""
    client = _client(_load_app())
    resp = client.post(
        "/api/goals",
        headers={**_h("ta"), "X-Principal": "founder", "X-Kind": "founder"},
        params={"principal": "founder", "kind": "founder"},
        json={"title": "escalate attempt", "principal": "founder", "kind": "founder"},
    )
    assert resp.status_code == 403  # still resolved as audit-team, not founder
    deny = [r for r in _audit_lines(env) if r["action"] == "goal.submit" and r["decision"] == "deny"]
    assert deny and deny[-1]["principal_kind"] == "audit-team"


def test_r2_vault_principals_are_already_canonical(env):
    """The vault SHOULD store principals in `_kind_of`'s canonical form
    (lowercase, no incidental whitespace) — normalization is defence-in-depth
    against a sloppily-hand-edited vault file, not the load-bearing mechanism
    that grants a kind, and a vault entry is never attacker-influenced (it is
    a tenant-owned file outside the repo, ADR-0038 TN-5)."""
    rbac = _load_rbac()
    tokens = json.loads((env / "vault-tokens.json").read_text(encoding="utf-8"))["tokens"]
    for entry in tokens.values():
        principal = entry["principal"]
        if principal == "bogus-principal":
            continue  # the fixture's deliberately-unresolvable negative case
        assert principal == principal.strip().lower(), f"non-canonical vault principal {principal!r}"
        assert rbac._kind_of(principal) is not None


# ---------------------------------------------------------------------------
# R3 (GATE-3 residual, INFO) — CI must actually run the FastAPI endpoint
# tests (+ the vendored-bundle offline-boot test), not silently `importorskip`
# them everywhere. As authored, `.github/workflows/ci.yml` does NOT install
# `tools/control_plane/requirements-control.txt` anywhere before `pytest -q`
# runs, so the whole endpoint suite is skipped in CI today too — this is a
# REAL, currently-open gap (not resolved CI-theatre-of-doubt; it IS CI
# theatre). Fixing the workflow is out of this ticket's scope (tests/-only);
# routed to backend-em/sre-lead. xfail(strict=True) keeps this loud instead
# of a silently-green suite.
# ---------------------------------------------------------------------------
def test_r3_ci_installs_control_plane_deps_so_endpoint_tests_actually_run():
    # GATE-3 residual R3 (DAS-1603) — CLOSED by backend-em: the `validate` job now installs
    # tools/control_plane/requirements-control.txt (+ httpx) before `pytest -q`, so the
    # FastAPI TestClient endpoint tests EXECUTE in CI on the 3.11 job instead of silently
    # `importorskip`-skipping. No longer CI-theatre.
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "requirements-control.txt" in ci


# ---------------------------------------------------------------------------
# SC-005 — offline install (see tests/test_ws_h_offline_install_degrade.py
# for the no-network / vendored-bundle coverage) + ruff-clean.
# ---------------------------------------------------------------------------
def test_sc005_control_plane_app_and_install_are_ruff_clean():
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not on PATH in this environment")
    targets = [str(ROOT / "tools" / "control_plane" / "app.py"), str(ROOT / "tools" / "control_plane" / "install")]
    result = subprocess.run([ruff, "check", *targets], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sc005_ruff_module_invocation_also_clean_when_available():
    """Belt-and-suspenders: also try `python -m ruff` (the CI-style
    invocation) when the module is importable in this interpreter; skip
    otherwise (this repo's CI job uses the `ruff` console script — see
    ci.yml — so the `shutil.which` test above is the load-bearing one)."""
    if importlib.util.find_spec("ruff") is None:
        pytest.skip("ruff module not importable in this interpreter")
    targets = [str(ROOT / "tools" / "control_plane" / "app.py"), str(ROOT / "tools" / "control_plane" / "install")]
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", *targets], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
