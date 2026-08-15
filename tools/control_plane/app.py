#!/usr/bin/env python3

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
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

app = FastAPI(
    title="DasLab Control Plane (WS-H)", docs_url=None, redoc_url=None, openapi_url=None
)

STATUSES = ["backlog", "todo", "in_progress", "blocked", "in_review", "done"]
NODATA = "(no data — cockpit unavailable in this environment; see scripts/cockpit.py)"
FLAG = "ws_h_control_plane"

DEFAULT_MAX_REQUEST_BYTES = 64 * 1024
MAX_REQUEST_BYTES_ENV = "DASLAB_CP_MAX_REQUEST_BYTES"
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent


def _engine_module(mod_name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(mod_name, _ENGINE_ROOT / rel)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load engine module {rel}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _dashboard_package() -> Any:
    entry = str(Path(__file__).resolve().parent)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module("dashboard_api")


_rbac = _engine_module("cp_rbac", "scripts/rbac.py")
_flags = _engine_module("cp_feature_flags", "scripts/feature_flags.py")
_safe_scrub: Callable[[object], str] = _engine_module(
    "cp_redaction", "tools/mcp_bridges/redaction.py"
).safe_scrub


def repo_root() -> Path:
    return Path(os.environ.get("DASLAB_ROOT", ".")).resolve()


FEATURES_PATH: Path | None = None


def flag_on() -> bool:
    return bool(_flags.enabled(FLAG, FEATURES_PATH))


def audit_path() -> Path:
    configured = os.environ.get("DASLAB_CP_AUDIT_LOG")
    return Path(configured) if configured else repo_root() / "board" / ".control-plane-audit.jsonl"


def _rbac_config_path() -> Path | None:
    override = os.environ.get("DASLAB_CP_RBAC_CONFIG")
    return Path(override) if override else None


def load_token_map() -> dict | None:
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
    try:
        grants = _rbac.load_grants(_rbac_config_path())
    except _rbac.RbacConfigError:
        return None
    return grants or None


def rbac_configured() -> bool:
    return load_token_map() is not None and load_grants() is not None


def audit(
    action: str,
    principal_id: str,
    principal_kind: str,
    decision: str,
    reason: str = "",
    detail: str = "",
) -> None:
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


class AuthFailure(Enum):
    MISSING_HEADER = "no authorization header"
    MALFORMED_HEADER = "malformed authorization header (expected 'Bearer <token>')"
    EMPTY_TOKEN = "empty bearer token"
    UNKNOWN_TOKEN = "unknown bearer token"
    UNUSABLE_PRINCIPAL = "token maps to an unusable principal"


class Identity:

    __slots__ = ("kind", "principal", "role", "user")

    def __init__(self, user: str, principal: str, kind: str, role: str = "") -> None:
        self.user = user
        self.principal = principal
        self.kind = kind
        self.role = role

    def as_dict(self) -> dict:
        return {
            "user": self.user,
            "principal": self.principal,
            "kind": self.kind,
            "role": self.role,
        }


def _token_bytes(value: str) -> bytes:
    return value.encode("utf-8", errors="surrogateescape")


def _match_token(tokens: dict, token: str) -> dict | None:
    if not token:
        return None
    probe = _token_bytes(token)
    found: dict | None = None
    for candidate, entry in tokens.items():
        if not isinstance(candidate, str) or not isinstance(entry, dict):
            continue
        if hmac.compare_digest(probe, _token_bytes(candidate)):
            found = entry
    return found


def _bearer_token(header: str) -> tuple[str, AuthFailure | None]:
    if not header:
        return "", AuthFailure.MISSING_HEADER
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "bearer":
        return "", AuthFailure.MALFORMED_HEADER
    token = rest.strip()
    if not token:
        return "", AuthFailure.EMPTY_TOKEN
    return token, None


def _resolve_identity(tokens: dict, token: str) -> tuple[Identity | None, AuthFailure | None]:
    entry = _match_token(tokens, token)
    if not isinstance(entry, dict):
        return None, AuthFailure.UNKNOWN_TOKEN
    principal = entry.get("principal")
    if not isinstance(principal, str) or not principal:
        return None, AuthFailure.UNUSABLE_PRINCIPAL
    kind = _rbac._kind_of(principal)
    if kind is None:
        return None, AuthFailure.UNUSABLE_PRINCIPAL
    user = entry.get("user")
    role = entry.get("role")
    return (
        Identity(
            str(user) if user else "unknown",
            principal,
            str(kind),
            str(role) if isinstance(role, str) else "",
        ),
        None,
    )


def _identify(request: Request) -> dict:
    tokens = load_token_map()
    if tokens is None:
        raise HTTPException(503, "control plane not configured: set DASLAB_CP_RBAC (fail-closed)")
    token, failure = _bearer_token(request.headers.get("authorization", ""))
    identity: Identity | None = None
    if failure is None:
        identity, failure = _resolve_identity(tokens, token)
    if identity is None:
        audit("auth", "-", "-", "deny", (failure or AuthFailure.UNKNOWN_TOKEN).value)
        raise HTTPException(401, "invalid token")
    audit("auth", identity.principal, identity.kind, "allow", "token accepted")
    return identity.as_dict()


def max_request_bytes() -> int:
    raw = os.environ.get(MAX_REQUEST_BYTES_ENV, "").strip()
    if not raw:
        return DEFAULT_MAX_REQUEST_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_REQUEST_BYTES
    return value if value > 0 else DEFAULT_MAX_REQUEST_BYTES


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers") or []:
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _replay_body(body: bytes) -> Receive:
    sent = False

    async def receive() -> dict:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


class RequestSizeLimit:

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        limit = max_request_bytes()
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await self._reject(scope, receive, send, limit)
            return
        if declared is None and scope.get("method") in _BODY_METHODS:
            body = b""
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    break
                body += message.get("body", b"")
                if len(body) > limit:
                    await self._reject(scope, receive, send, limit)
                    return
                if not message.get("more_body", False):
                    break
            await self.app(scope, _replay_body(body), send)
            return
        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        audit(
            "request.reject",
            "-",
            "-",
            "deny",
            f"request body exceeds {limit} bytes",
            str(scope.get("path", "")),
        )
        response = JSONResponse(
            {"detail": f"request body too large (limit {limit} bytes)"}, status_code=413
        )
        await response(scope, receive, send)


app.add_middleware(RequestSizeLimit)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    audit(
        "request.error",
        "-",
        "-",
        "error",
        type(exc).__name__,
        f"{request.method} {request.url.path}: {exc}",
    )
    return JSONResponse({"detail": "internal error"}, status_code=500)


class RequirePermission:

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


BoardRead = Annotated[dict, Depends(RequirePermission("audit.read", "board.read"))]
CockpitRead = Annotated[dict, Depends(RequirePermission("audit.read", "cockpit.read"))]
AuditRead = Annotated[dict, Depends(RequirePermission("audit.read", "audit.read"))]
GoalWrite = Annotated[dict, Depends(RequirePermission("board.work", "goal.submit"))]


RunTrigger = Annotated[dict, Depends(RequirePermission("run.trigger", "run.trigger"))]
GateApprove = Annotated[dict, Depends(RequirePermission("gate.approve", "gate.approve"))]


def _frontmatter(text: str) -> dict:
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


class GateDecisionIn(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    gate: str = Field(default="", max_length=64)
    note: str = Field(default="", max_length=10_000)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "flag": flag_on(),
        "rbac_configured": rbac_configured(),
        "dashboard": dict(DASHBOARD_STATUS),
    }


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


DASHBOARD_STATUS: dict[str, Any] = {"router": False, "spa": False, "error": ""}


def _install_dashboard() -> None:
    try:
        package = _dashboard_package()
        deps = package.ControlPlaneDeps(
            identify=_identify,
            audit=audit,
            flag_on=flag_on,
            load_grants=load_grants,
        )
        app.include_router(package.build_router(deps))
        DASHBOARD_STATUS["router"] = True
        DASHBOARD_STATUS["spa"] = bool(package.mount_spa(app))
    except Exception as exc:
        DASHBOARD_STATUS["error"] = f"{type(exc).__name__}: {exc}"


_install_dashboard()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE if flag_on() else _STATIC_PAGE


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("DASLAB_CP_BIND", "127.0.0.1"), port=8899)
