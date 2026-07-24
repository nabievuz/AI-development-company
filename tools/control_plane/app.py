#!/usr/bin/env python3
"""DasLab WS-H — self-hosted web control plane PoC (ADR-0039).

A FastAPI app a tenant runs on its own Ubuntu/macOS server to operate DasLab
from a browser. PoC scope, honoring the ADR-0039 invariants:

* CP-1 — reuses the REAL cockpit via its own CLI (``scripts/cockpit.py``,
  subprocess, its argparse owns the defaults) and embeds its text output; if the
  cockpit is unavailable the panel degrades to an honest NODATA line. This app
  adds a controller layer; it re-implements no cockpit panel.
* CP-2 — no anonymous data access: every data/action endpoint requires a
  ``Authorization: Bearer <token>`` mapped to a role in the RBAC file
  (``$DASLAB_CP_RBAC``). **Fail-closed:** RBAC unconfigured -> 503 for
  everything but ``/healthz`` and the empty HTML shell.
* CP-3 — ONE governed write ships in this PoC: **submit a goal proposal**
  (operator+). It writes a file into ``board/goal-inbox/`` for `/daslab-plan`
  triage — it creates NO ticket, approves NO gate, dispatches NOTHING.
  Gate approval (Founder-only) and run-trigger are follow-up tickets.
* CP-4 — all state lives in repo files (board/goal-inbox, audit JSONL); the app
  holds no parallel store.
* CP-5 — the server dispatches nothing on its own; it only serves requests.

RBAC file format::

    {"tokens": {"<token>": {"user": "akmal", "role": "founder"}}}

Roles (ranked): viewer < operator < founder.
Env: DASLAB_ROOT (repo root, default cwd), DASLAB_CP_RBAC (required),
DASLAB_CP_AUDIT_LOG (default <root>/board/.control-plane-audit.jsonl).
Run: ``python3 -m uvicorn app:app --host 127.0.0.1 --port 8899`` (loopback by
default; a network bind is a deliberate tenant act per ADR-0038 TN-5).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="DasLab Control Plane (WS-H PoC)", docs_url=None, redoc_url=None)

ROLE_RANK = {"viewer": 0, "operator": 1, "founder": 2}
STATUSES = ["backlog", "todo", "in_progress", "blocked", "in_review", "done"]
NODATA = "(no data — cockpit unavailable in this environment; see scripts/cockpit.py)"


# ---------------------------------------------------------------------------
# Paths & config (self-locating; no hardcoded absolute paths — ADR-0003)
# ---------------------------------------------------------------------------
def repo_root() -> Path:
    return Path(os.environ.get("DASLAB_ROOT", ".")).resolve()


def audit_path() -> Path:
    configured = os.environ.get("DASLAB_CP_AUDIT_LOG")
    return Path(configured) if configured else repo_root() / "board" / ".control-plane-audit.jsonl"


def load_rbac() -> dict | None:
    """Return the token map, or None when RBAC is not configured/readable (fail-closed)."""
    path = os.environ.get("DASLAB_CP_RBAC")
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tokens = data.get("tokens")
    return tokens if isinstance(tokens, dict) else None


def audit(action: str, user: str, role: str, decision: str, detail: str = "") -> None:
    """Append-only audit trail (ADR-0039 CP-3); must never crash a request."""
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        "user": user,
        "role": role,
        "decision": decision,
        "detail": detail,
    }
    try:
        target = audit_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# AuthN/AuthZ (CP-2: no anonymous data access; fail-closed without RBAC)
# ---------------------------------------------------------------------------
def identify(request: Request) -> dict:
    tokens = load_rbac()
    if tokens is None:
        raise HTTPException(503, "control plane not configured: set DASLAB_CP_RBAC (fail-closed)")
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    entry = tokens.get(token)
    if not entry or entry.get("role") not in ROLE_RANK:
        audit("auth", "unknown", "-", "deny", "bad or missing token")
        raise HTTPException(401, "invalid token")
    return {"user": entry.get("user", "unknown"), "role": entry["role"]}


def require(min_role: str):
    def dependency(request: Request) -> dict:
        who = identify(request)
        if ROLE_RANK[who["role"]] < ROLE_RANK[min_role]:
            audit("authz", who["user"], who["role"], "deny", f"needs >= {min_role}")
            raise HTTPException(403, f"role '{who['role']}' may not do this (needs {min_role}+)")
        return who

    return dependency


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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
# Routes
# ---------------------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "rbac_configured": load_rbac() is not None}


@app.get("/api/board")
def api_board(who: dict = Depends(require("viewer"))) -> dict:
    audit("board.read", who["user"], who["role"], "allow")
    return board_summary()


@app.get("/api/cockpit")
def api_cockpit(who: dict = Depends(require("viewer"))) -> dict:
    audit("cockpit.read", who["user"], who["role"], "allow")
    return cockpit_text()


@app.get("/api/audit")
def api_audit(who: dict = Depends(require("operator"))) -> dict:
    audit("audit.read", who["user"], who["role"], "allow")
    try:
        lines = audit_path().read_text(encoding="utf-8").splitlines()[-50:]
    except OSError:
        lines = []
    return {"entries": [json.loads(line) for line in lines if line.strip()]}


@app.post("/api/goals", status_code=201)
def api_goals(goal: GoalIn, who: dict = Depends(require("operator"))) -> dict:
    path = write_goal(goal, who["user"])
    rel = str(path.relative_to(repo_root()))
    audit("goal.submit", who["user"], who["role"], "allow", rel)
    return {"written": rel, "status": "proposed", "next": "Founder discovery via /daslab-plan"}


_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>DasLab Control Plane (WS-H PoC)</title><style>
body{font-family:ui-monospace,Menlo,monospace;margin:2rem;background:#0b1020;color:#dbe2ff}
h1{font-size:1.1rem} .card{background:#141b34;border:1px solid #2a3560;border-radius:8px;
padding:1rem;margin:1rem 0;max-width:72rem} input,textarea{width:100%;background:#0b1020;
color:#dbe2ff;border:1px solid #2a3560;border-radius:4px;padding:.4rem;margin:.2rem 0}
button{background:#3452c8;color:#fff;border:0;border-radius:4px;padding:.5rem 1rem;cursor:pointer}
pre{white-space:pre-wrap;font-size:.78rem} small{color:#8ea0d8} .err{color:#ff9d9d}
</style></head><body>
<h1>DasLab Control Plane <small>(WS-H PoC — ADR-0039; governed, audited, RBAC)</small></h1>
<div class="card"><b>Token</b> <input id="tok" type="password"
 placeholder="Bearer token (viewer / operator / founder)">
<button onclick="refresh()">Load</button> <span id="msg" class="err"></span></div>
<div class="card"><b>Board</b><pre id="board">(not loaded)</pre></div>
<div class="card"><b>Cockpit (real scripts/cockpit.py)</b><pre id="cockpit">(not loaded)</pre></div>
<div class="card"><b>Submit goal proposal</b> <small>operator+; files into board/goal-inbox/ —
awaits Founder approval via /daslab-plan; approves nothing, dispatches nothing</small>
<input id="gt" placeholder="Goal title"><textarea id="gb" rows="3"
 placeholder="Goal detail (optional)"></textarea>
<button onclick="submitGoal()">Submit proposal</button> <span id="gmsg"></span></div>
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
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Empty HTML shell — carries NO data; all data/actions require a token (CP-2)."""
    return _PAGE


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("DASLAB_CP_BIND", "127.0.0.1"), port=8899)
