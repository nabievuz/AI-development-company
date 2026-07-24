#!/usr/bin/env python3
"""DasLab WS-H — self-hosted web control plane (ADR-0039), RBAC bound to the WS-E SSOT.

A FastAPI app a tenant runs on its own Ubuntu/macOS server to operate DasLab from a
browser. It is a **controller layer** wrapped around the read-only cockpit — it is NOT a
new cockpit and NOT a new dispatch path. Every read/write is authorized against the WS-E
RBAC SSOT and audited. It honours the ADR-0039 invariants (design docs/design/
ws-h-control-plane.md):

* CP-1 — reuses the REAL cockpit via its own CLI (``scripts/cockpit.py``, subprocess, its
  argparse owns the defaults) and embeds its text output; unavailable -> honest NODATA
  line. This app adds a controller layer; it re-implements no cockpit panel.
* CP-2 — no anonymous data access. Authorization is bound to the **WS-E RBAC SSOT**
  (``config/rbac.yaml`` + ``scripts/rbac.decide()``), NOT to any ad-hoc tier: the spike's
  ``viewer < operator < founder`` ``ROLE_RANK`` is **retired** (DAS-1600). A bearer token
  maps (in the tenant vault, ``$DASLAB_CP_RBAC``) to an SSOT **principal** string
  (``founder`` / ``audit-team`` / ``orchestrator`` / ``agent:<role>``); ``decide()``
  default-DENIES. **Fail-closed:** RBAC unconfigured/unloadable -> 503 (only ``/healthz``
  and the data-free HTML shell answer); bad/missing token -> 401 (audited deny); a
  ``decide()`` deny -> 403 (audited deny). ``gate.approve`` / ``run.trigger`` are
  Founder-only *by construction* — the SSOT refuses to load a config that grants them to a
  non-founder kind, so no token, role string, or request body promotes a non-Founder into
  them (the approve-gate / trigger-run *endpoints* land in DAS-1601 on this foundation).
* CP-3 — ONE governed write ships here (CP-3a): **submit a goal proposal** (Founder-
  authorized in the near-term matrix, Q6 — the small team is read-only). It writes a file
  into ``board/goal-inbox/`` for ``/daslab-plan`` triage — it creates NO ticket, approves
  NO gate, dispatches NOTHING. Every request/decision (allow AND deny) is appended to the
  append-only audit trail, its free-text ``detail`` scrubbed through the single ADR-0012
  scrubber (``tools/mcp_bridges/redaction.py``) — the record is Tier-M by construction.
* CP-4 — all state lives in repo files (board/goal-inbox, audit JSONL); no parallel store.
* CP-5/CP-6 — optional, ``ws_h_control_plane``-OFF-by-default process (config/features.
  yaml). With the flag OFF the control surface is **inert** (the ``/api/*`` endpoints do
  not exist) and ``GET /`` degrades to the ADR-0028 static read cockpit; the server
  dispatches NOTHING on its own; loopback bind by default (a network bind is a deliberate
  tenant act per ADR-0038 TN-5).

Vault token map (``$DASLAB_CP_RBAC``) — a per-token **principal**, never a rank tier::

    {"tokens": {"<token>": {"user": "akmal", "principal": "founder"}}}

Env: DASLAB_ROOT (tenant data root, default cwd), DASLAB_CP_RBAC (vault token map,
required), DASLAB_CP_RBAC_CONFIG (optional override of the SSOT grant matrix path;
defaults to the engine ``config/rbac.yaml``), DASLAB_CP_AUDIT_LOG (default
<root>/board/.control-plane-audit.jsonl), DASLAB_WS_H_FLAG (optional flag override).
Run: ``python3 -m uvicorn app:app --host 127.0.0.1 --port 8899`` (loopback by default).
"""
from __future__ import annotations

import hmac
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="DasLab Control Plane (WS-H)", docs_url=None, redoc_url=None)

STATUSES = ["backlog", "todo", "in_progress", "blocked", "in_review", "done"]
NODATA = "(no data — cockpit unavailable in this environment; see scripts/cockpit.py)"
FLAG = "ws_h_control_plane"

# The engine checkout that owns this file — resolved from __file__, INDEPENDENT of
# DASLAB_ROOT (the tenant data root). The WS-E RBAC SSOT, the ADR-0012 scrubber, and the
# feature-flag reader live here and are REUSED verbatim (never forked, never re-implemented).
_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent


def _engine_module(mod_name: str, rel: str) -> Any:
    """Path-load an engine module so we reuse the SSOT/scrubber without a sys.path edit
    (which would trip ruff E402) and without duplicating their logic here."""
    spec = importlib.util.spec_from_file_location(mod_name, _ENGINE_ROOT / rel)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load engine module {rel}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


_rbac = _engine_module("cp_rbac", "scripts/rbac.py")
_flags = _engine_module("cp_feature_flags", "scripts/feature_flags.py")
_safe_scrub: Callable[[object], str] = _engine_module(
    "cp_redaction", "tools/mcp_bridges/redaction.py"
).safe_scrub


# ---------------------------------------------------------------------------
# Paths, feature flag & config (self-locating; no hardcoded absolute paths — ADR-0003)
# ---------------------------------------------------------------------------
def repo_root() -> Path:
    """The tenant DATA root (board/goal-inbox/audit live here). Distinct from the engine
    checkout ``_ENGINE_ROOT`` that owns the SSOT + scrubber code."""
    return Path(os.environ.get("DASLAB_ROOT", ".")).resolve()


def flag_on() -> bool:
    """True iff the WS-H control plane is enabled (ADR-0019). Default OFF ⇒ inert surface.
    ``DASLAB_WS_H_FLAG`` overrides the config for tests/tenant probes."""
    override = os.environ.get("DASLAB_WS_H_FLAG")
    if override is not None:
        return override.strip().lower() in {"1", "true", "on", "yes"}
    return bool(_flags.enabled(FLAG))


def audit_path() -> Path:
    configured = os.environ.get("DASLAB_CP_AUDIT_LOG")
    return Path(configured) if configured else repo_root() / "board" / ".control-plane-audit.jsonl"


def _rbac_config_path() -> Path | None:
    """SSOT grant-matrix path. ``None`` ⇒ scripts/rbac's default (engine config/rbac.yaml)."""
    override = os.environ.get("DASLAB_CP_RBAC_CONFIG")
    return Path(override) if override else None


def load_token_map() -> dict | None:
    """The vault token→principal map, or ``None`` when unconfigured/unreadable (fail-closed).

    Kept OUT of the repo (``$DASLAB_CP_RBAC``, tenant vault, ADR-0038 TN-5). Each entry
    carries an SSOT ``principal`` string — NOT the retired ad-hoc ``role`` tier.
    """
    path = os.environ.get("DASLAB_CP_RBAC")
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tokens = data.get("tokens")
    return tokens if isinstance(tokens, dict) else None


def load_grants() -> dict | None:
    """The SSOT permission grant matrix, or ``None`` when unconfigured/unloadable.

    Fail-closed like ``scripts/rbac.load_grants``: an ABSENT config yields ``{}`` (→ None
    here, treated as unconfigured 503) and a STRUCTURALLY invalid config raises
    ``RbacConfigError`` (a tampered security surface is a loud refusal) → None → 503.
    """
    try:
        grants = _rbac.load_grants(_rbac_config_path())
    except _rbac.RbacConfigError:
        return None
    return grants or None


def rbac_configured() -> bool:
    """Both halves present: the vault token map AND a non-empty, loadable grant matrix."""
    return load_token_map() is not None and load_grants() is not None


def audit(
    action: str,
    principal_id: str,
    principal_kind: str,
    decision: str,
    reason: str = "",
    detail: str = "",
) -> None:
    """Append-only audit trail (ADR-0039 CP-3), Tier-M by construction. The free-text
    ``detail`` (a reference: goal path / ticket id) is scrubbed through the SINGLE ADR-0012
    scrubber before it is written; a secret/PII value can never enter the ledger. The
    write must never crash a request (best-effort append)."""
    record = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        "principal_id": principal_id,
        "principal_kind": principal_kind,
        "decision": decision,
        "reason": reason,
        "detail": _safe_scrub(detail) if detail else "",
    }
    try:
        target = audit_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# AuthN/AuthZ (CP-2) — bound to the WS-E RBAC SSOT; fail-closed 503/401/403.
# ---------------------------------------------------------------------------
def _match_token(tokens: dict, token: str) -> dict | None:
    """Constant-time bearer-token resolution (defence-in-depth vs a timing side-channel on
    the auth secret). Instead of a dict-hash ``tokens.get(token)`` lookup, compare the
    presented token against every stored token with ``hmac.compare_digest`` and never
    short-circuit on a first-byte / first-entry mismatch (the loop always visits every
    candidate). An empty/None token resolves to no entry — still fail-closed 401 upstream."""
    if not token:
        return None
    found: dict | None = None
    for candidate, entry in tokens.items():
        if (
            isinstance(candidate, str)
            and hmac.compare_digest(token, candidate)
            and isinstance(entry, dict)
        ):
            found = entry
    return found


def _identify(request: Request) -> dict:
    """Resolve the bearer token to an SSOT principal. 503 if the token map is unconfigured;
    401 (audited deny) if the token is absent/unknown or its principal resolves to no kind."""
    tokens = load_token_map()
    if tokens is None:
        raise HTTPException(503, "control plane not configured: set DASLAB_CP_RBAC (fail-closed)")
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    entry = _match_token(tokens, token)
    principal = entry.get("principal") if isinstance(entry, dict) else None
    kind = _rbac._kind_of(principal) if principal else None
    if not isinstance(entry, dict) or not principal or kind is None:
        audit("auth", str(principal or "-"), "-", "deny", "bad or missing token")
        raise HTTPException(401, "invalid token")
    return {"user": entry.get("user", "unknown"), "principal": str(principal), "kind": kind}


class RequirePermission:
    """FastAPI dependency: flag-gate → fail-closed RBAC → identified principal on allow.

    Bound to a module-level ``Annotated`` alias so no function-call sits in an argument
    default (ruff B008 clean, per the design §6.2 preferred pattern). Fail-closed order:
    flag OFF ⇒ 404 (inert); RBAC unconfigured/unloadable ⇒ 503; bad/missing token ⇒ 401
    (audited); ``decide()`` deny ⇒ 403 (audited). The allow path is audited by the route.
    """

    def __init__(self, permission: str, action: str) -> None:
        self.permission = permission
        self.action = action

    def __call__(self, request: Request) -> dict:
        if not flag_on():
            raise HTTPException(404, "control plane disabled (ws_h_control_plane OFF)")
        grants = load_grants()
        if grants is None:
            raise HTTPException(503, "control plane RBAC not configured/loadable (fail-closed)")
        who = _identify(request)
        decision, reason = _rbac.decide(who["principal"], self.permission, config=grants)
        if decision != "allow":
            audit(self.action, who["principal"], who["kind"], "deny", reason)
            raise HTTPException(
                403, f"principal '{who['principal']}' may not do this ({self.permission})"
            )
        return {**who, "reason": reason}


# The read endpoints check ``audit.read``; the goal-proposal write checks ``board.work``
# (an EXISTING SSOT permission the Founder holds unconditionally while the near-term team
# is denied — Founder-authorized without reintroducing an ``operator`` tier, design §3.5).
# Widening the proposer beyond Founder is a reviewed ``config.edit.security`` grant edit,
# NOT a hardcoded rank baked into the app.
BoardRead = Annotated[dict, Depends(RequirePermission("audit.read", "board.read"))]
CockpitRead = Annotated[dict, Depends(RequirePermission("audit.read", "cockpit.read"))]
AuditRead = Annotated[dict, Depends(RequirePermission("audit.read", "audit.read"))]
GoalWrite = Annotated[dict, Depends(RequirePermission("board.work", "goal.submit"))]
# The two governed writes DAS-1601 adds — both Founder-only *by construction* (the SSOT
# refuses to load an rbac.yaml that grants either to a non-founder kind, scripts/rbac
# §1.3). ``run.trigger`` guards the trigger-run intent; ``gate.approve`` guards BOTH the
# approve and the deny endpoints (deciding a gate — either direction — is a Founder act).
RunTrigger = Annotated[dict, Depends(RequirePermission("run.trigger", "run.trigger"))]
GateApprove = Annotated[dict, Depends(RequirePermission("gate.approve", "gate.approve"))]


# ---------------------------------------------------------------------------
# Board read (CP-4: reads the canonical files; NODATA-honest when absent)
# ---------------------------------------------------------------------------
def _frontmatter(text: str) -> dict:
    """Minimal ``key: value`` frontmatter parser matching board/tickets format."""
    meta: dict[str, str] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            meta[match.group(1)] = match.group(2).strip()
    return meta


def board_summary() -> dict:
    tickets_dir = repo_root() / "board" / "tickets"
    if not tickets_dir.is_dir():
        return {"nodata": True, "counts": {}, "tickets": []}
    counts = dict.fromkeys(STATUSES, 0)
    rows = []
    for path in sorted(tickets_dir.glob("*.md")):
        try:
            meta = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        status = meta.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
        rows.append({k: meta.get(k, "") for k in ("id", "title", "status", "assignee", "updated")})
    rows.sort(key=lambda r: r.get("updated", ""), reverse=True)
    return {"nodata": False, "counts": counts, "total": len(rows), "tickets": rows[:20]}


def cockpit_text() -> dict:
    """CP-1: run the REAL cockpit CLI (it owns its defaults); degrade to NODATA."""
    script = repo_root() / "scripts" / "cockpit.py"
    if script.is_file():
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, timeout=15, cwd=repo_root(),
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {"source": "scripts/cockpit.py", "text": proc.stdout}
        except (OSError, subprocess.SubprocessError):
            pass
    return {"source": "unavailable", "text": NODATA}


# ---------------------------------------------------------------------------
# The ONE governed write (CP-3a): submit a goal PROPOSAL to board/goal-inbox/
# ---------------------------------------------------------------------------
class GoalIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(default="", max_length=10_000)


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "goal"


def write_goal(goal: GoalIn, user: str) -> Path:
    inbox = repo_root() / "board" / "goal-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = inbox / f"{stamp}-{_slug(goal.title)}.md"
    counter = 1
    while path.exists():
        counter += 1
        path = inbox / f"{stamp}-{_slug(goal.title)}-{counter}.md"
    front = "\n".join(
        [
            "---",
            f"title: {goal.title}",
            f"author: {user}",
            "status: proposed",
            "source: control-plane",
            f"created: {stamp}",
            "---",
        ]
    )
    note = (
        "> Goal PROPOSAL submitted via the WS-H control plane (ADR-0039 CP-3a).\n"
        "> Not a ticket and not approved: it awaits Founder discovery + explicit\n"
        "> approval through /daslab-plan (Founder-Approved Goal Queue law).\n"
    )
    path.write_text(front + "\n\n" + note + "\n" + goal.body + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Governed write (CP-3b): trigger a run — queue an INTENT to board/run-inbox/.
# The control plane DISPATCHES NOTHING itself (CP-5). It writes a canonical run-intent
# to the board queue (C2); the ADR-0034 WS-B headless runner / HEARTBEAT is what later
# picks it up, and that path routes through the board/dispatch chokepoint and honours
# EVERY AADL gate (C4). A GATE-5-open deployment therefore stays machine-blocked no matter
# how many times this endpoint is called — the intent is not a dispatch.
# ---------------------------------------------------------------------------
class RunIn(BaseModel):
    target: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=10_000)


def write_run_intent(run: RunIn, user: str) -> Path:
    inbox = repo_root() / "board" / "run-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = inbox / f"{stamp}-{_slug(run.target)}.md"
    counter = 1
    while path.exists():
        counter += 1
        path = inbox / f"{stamp}-{_slug(run.target)}-{counter}.md"
    front = "\n".join(
        [
            "---",
            f"target: {run.target}",
            f"author: {user}",
            "status: requested",
            "source: control-plane",
            f"created: {stamp}",
            "---",
        ]
    )
    note = (
        "> Run INTENT queued via the WS-H control plane (ADR-0039 CP-3b).\n"
        "> NOT a dispatch: the control plane dispatches NOTHING itself (CP-5). This\n"
        "> intent awaits the ADR-0034 WS-B headless runner / HEARTBEAT, which routes\n"
        "> through the board/dispatch chokepoint and honours every AADL gate (C4) —\n"
        "> a GATE-5-open deployment stays machine-blocked regardless of this request.\n"
    )
    path.write_text(front + "\n\n" + note + "\n" + run.note + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Governed write (CP-3c): approve / deny an AADL gate or interrupt-card.
# Approval is a Founder-identity EVENT, not a button-press claim (FR-004 crux). The route
# calls ``scripts/rbac.append_gate_approval()`` — the ONE canonical producer of a
# ``gate_approval`` record — which (i) re-checks ``decide(principal,"gate.approve")==allow``
# and refuses otherwise (nothing written), and (ii) STAMPS ``principal_kind`` from the
# authenticated session principal, never from request content. So the dashboard can never
# manufacture a ``principal_kind: founder`` event, and ``is_gate_closed()`` closes a gate
# ONLY on a matching Founder-identity event — a forged ``approval: human:founder``
# frontmatter with no backing event closes NO gate. A DENY records the Founder's decision
# but writes NO ``gate_approval`` event, so the gate stays OPEN.
# ---------------------------------------------------------------------------
class GateDecisionIn(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    gate: str = Field(default="", max_length=64)
    note: str = Field(default="", max_length=10_000)


# ---------------------------------------------------------------------------
# Routes — /healthz + / answer always (data-free); /api/* are RBAC-gated & flag-inert.
# ---------------------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "flag": flag_on(), "rbac_configured": rbac_configured()}


@app.get("/api/board")
def api_board(who: BoardRead) -> dict:
    audit("board.read", who["principal"], who["kind"], "allow", who["reason"])
    return board_summary()


@app.get("/api/cockpit")
def api_cockpit(who: CockpitRead) -> dict:
    audit("cockpit.read", who["principal"], who["kind"], "allow", who["reason"])
    return cockpit_text()


@app.get("/api/audit")
def api_audit(who: AuditRead) -> dict:
    audit("audit.read", who["principal"], who["kind"], "allow", who["reason"])
    try:
        lines = audit_path().read_text(encoding="utf-8").splitlines()[-50:]
    except OSError:
        lines = []
    return {"entries": [json.loads(line) for line in lines if line.strip()]}


@app.post("/api/goals", status_code=201)
def api_goals(goal: GoalIn, who: GoalWrite) -> dict:
    path = write_goal(goal, who["user"])
    rel = str(path.relative_to(repo_root()))
    audit("goal.submit", who["principal"], who["kind"], "allow", who["reason"], rel)
    return {"written": rel, "status": "proposed", "next": "Founder discovery via /daslab-plan"}


@app.post("/api/runs", status_code=201)
def api_runs(run: RunIn, who: RunTrigger) -> dict:
    """CP-3b trigger-run (Founder-only ``run.trigger``). Queues a canonical run-intent to
    ``board/run-inbox/`` — it dispatches NOTHING itself (CP-5) and never bypasses an AADL
    gate (C4). Audited + redacted."""
    path = write_run_intent(run, who["user"])
    rel = str(path.relative_to(repo_root()))
    audit("run.trigger", who["principal"], who["kind"], "allow", who["reason"], rel)
    return {
        "queued": rel,
        "status": "requested",
        "dispatched": False,
        "next": "ADR-0034 WS-B headless runner / HEARTBEAT — routes through every AADL gate",
    }


@app.post("/api/gates/{ticket_id}/approve", status_code=201)
def api_gate_approve(ticket_id: str, decision: GateDecisionIn, who: GateApprove) -> dict:
    """CP-3c approve-gate (Founder-only, structural). Records ONE attributed
    ``gate_approval`` event via the canonical ``scripts/rbac.append_gate_approval()`` — the
    ``principal_kind`` is stamped from the session, never from request content. A
    non-Founder is already refused (403 + audited deny) by the ``gate.approve`` dependency
    before this runs; the ledger-layer refusal below is defence-in-depth."""
    created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        record = _rbac.append_gate_approval(
            principal=who["principal"],
            ticket_id=ticket_id,
            category=decision.category,
            gate=decision.gate,
            created_at=created_at,
            audit_path=repo_root() / "board" / ".rbac-audit.jsonl",
            config_path=_rbac_config_path(),
        )
    except _rbac.ApprovalRefused as exc:
        audit("gate.approve", who["principal"], who["kind"], "deny", str(exc)[:200], ticket_id)
        raise HTTPException(403, "gate approval refused by the SSOT (Founder-only)") from exc
    audit("gate.approve", who["principal"], who["kind"], "allow", who["reason"], ticket_id)
    return {
        "gate_approval": True,
        "ticket_id": record["ticket_id"],
        "principal_kind": record["principal_kind"],
        "category": record["category"],
        "gate": record["gate"],
    }


@app.post("/api/gates/{ticket_id}/deny", status_code=201)
def api_gate_deny(ticket_id: str, decision: GateDecisionIn, who: GateApprove) -> dict:
    """CP-3c deny-gate (Founder-only). Records the Founder's decision in the control-plane
    audit trail but writes **NO** ``gate_approval`` event — so ``is_gate_closed()`` stays
    False and the gate remains OPEN. A deny never closes a never-auto-approve gate; only a
    Founder approve does."""
    audit("gate.deny", who["principal"], who["kind"], "allow", who["reason"], ticket_id)
    return {
        "gate_approval": False,
        "ticket_id": ticket_id,
        "category": decision.category,
        "gate_closed": False,
        "note": "deny recorded; no gate_approval event written — gate stays open",
    }


_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>DasLab Control Plane (WS-H)</title><style>
body{font-family:ui-monospace,Menlo,monospace;margin:2rem;background:#0b1020;color:#dbe2ff}
h1{font-size:1.1rem} .card{background:#141b34;border:1px solid #2a3560;border-radius:8px;
padding:1rem;margin:1rem 0;max-width:72rem} input,textarea{width:100%;background:#0b1020;
color:#dbe2ff;border:1px solid #2a3560;border-radius:4px;padding:.4rem;margin:.2rem 0}
button{background:#3452c8;color:#fff;border:0;border-radius:4px;padding:.5rem 1rem;cursor:pointer}
pre{white-space:pre-wrap;font-size:.78rem} small{color:#8ea0d8} .err{color:#ff9d9d}
</style></head><body>
<h1>DasLab Control Plane <small>(WS-H — ADR-0039; governed, audited, RBAC bound to the WS-E SSOT)</small></h1>
<div class="card"><b>Token</b> <input id="tok" type="password"
 placeholder="Bearer token (principal: founder / audit-team / …)">
<button onclick="refresh()">Load</button> <span id="msg" class="err"></span></div>
<div class="card"><b>Board</b><pre id="board">(not loaded)</pre></div>
<div class="card"><b>Cockpit (real scripts/cockpit.py)</b><pre id="cockpit">(not loaded)</pre></div>
<div class="card"><b>Submit goal proposal</b> <small>Founder-authorized; files into
board/goal-inbox/ — awaits Founder approval via /daslab-plan; approves nothing, dispatches nothing</small>
<input id="gt" placeholder="Goal title"><textarea id="gb" rows="3"
 placeholder="Goal detail (optional)"></textarea>
<button onclick="submitGoal()">Submit proposal</button> <span id="gmsg"></span></div>
<div class="card"><b>Trigger run</b> <small>Founder-only (run.trigger); queues a run INTENT
into board/run-inbox/ — dispatches NOTHING itself, never bypasses an AADL gate</small>
<input id="rt" placeholder="Run target (wave / goal ref)"><textarea id="rn" rows="2"
 placeholder="Note (optional)"></textarea>
<button onclick="triggerRun()">Queue run intent</button> <span id="rmsg"></span></div>
<div class="card"><b>Approve / deny gate</b> <small>Founder-only (gate.approve); an approval
is an attributed Founder-identity EVENT — the dashboard never signs a gate; a GATE-5-open
deployment stays machine-blocked regardless</small>
<input id="kt" placeholder="Ticket id">
<input id="kc" placeholder="Category (e.g. gate5_deployment)">
<input id="kg" placeholder="Gate (e.g. GATE-5)">
<button onclick="gate('approve')">Approve</button>
<button onclick="gate('deny')">Deny</button> <span id="kmsg"></span></div>
<script>
const H=()=>({"Authorization":"Bearer "+document.getElementById("tok").value,
              "Content-Type":"application/json"});
async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(r.status+" "+
 (await r.text()).slice(0,200));return r.json()}
async function refresh(){const m=document.getElementById("msg");m.textContent="";try{
 const b=await j("/api/board",{headers:H()});
 document.getElementById("board").textContent=b.nodata?"(no board/tickets here)":
  "total "+b.total+"  |  "+JSON.stringify(b.counts)+"\\n\\n"+
  b.tickets.map(t=>`${t.id}  [${t.status}]  ${t.title}  — ${t.assignee}`).join("\\n");
 const c=await j("/api/cockpit",{headers:H()});
 document.getElementById("cockpit").textContent="source: "+c.source+"\\n\\n"+c.text;
}catch(e){m.textContent=e.message}}
async function submitGoal(){const m=document.getElementById("gmsg");m.textContent="";try{
 const r=await j("/api/goals",{method:"POST",headers:H(),body:JSON.stringify(
  {title:document.getElementById("gt").value,body:document.getElementById("gb").value})});
 m.textContent="written: "+r.written+" (status: proposed)";}catch(e){m.textContent=e.message}}
async function triggerRun(){const m=document.getElementById("rmsg");m.textContent="";try{
 const r=await j("/api/runs",{method:"POST",headers:H(),body:JSON.stringify(
  {target:document.getElementById("rt").value,note:document.getElementById("rn").value})});
 m.textContent="queued: "+r.queued+" (dispatched: "+r.dispatched+")";}catch(e){m.textContent=e.message}}
async function gate(act){const m=document.getElementById("kmsg");m.textContent="";try{
 const id=encodeURIComponent(document.getElementById("kt").value);
 const r=await j("/api/gates/"+id+"/"+act,{method:"POST",headers:H(),body:JSON.stringify(
  {category:document.getElementById("kc").value,gate:document.getElementById("kg").value})});
 m.textContent=act+": gate_approval="+r.gate_approval+(r.principal_kind?" ("+r.principal_kind+")":"");
}catch(e){m.textContent=e.message}}
</script></body></html>"""


_STATIC_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>DasLab (read-only cockpit)</title><style>
body{font-family:ui-monospace,Menlo,monospace;margin:2rem;background:#0b1020;color:#dbe2ff}
small{color:#8ea0d8}</style></head><body>
<h1>DasLab — read-only cockpit</h1>
<p>The WS-H control plane is <b>disabled</b> (<code>ws_h_control_plane</code> OFF). The
operator surface is the ADR-0028 static read cockpit — run
<code>python3 scripts/cockpit.py</code> or open the static snapshot. The control plane is
an <b>optional</b>, Founder-enabled process; it dispatches nothing on its own.</p>
<small>No data is served here without the control plane enabled and a token (CP-2).</small>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Data-free shell. With the flag OFF the whole control surface is inert and this
    degrades to the ADR-0028 static read cockpit (CP-5). Either way it carries NO data —
    all board/cockpit/audit content requires a token via ``/api/*`` (CP-2)."""
    return _PAGE if flag_on() else _STATIC_PAGE


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("DASLAB_CP_BIND", "127.0.0.1"), port=8899)
