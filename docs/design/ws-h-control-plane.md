# WS-H control-plane design — governed control over the read-only cockpit, Founder-only RBAC bound to the WS-E SSOT, offline-install, NOT-a-daemon

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted — RBAC/audit; CDO consulted — dashboard UX)
- **Date:** 2026-07-24
- **Ticket:** DAS-1599 (WS-H Design); epic DAS-1597 (MUSTAQIL WS-H CONTROL)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — Founder-only RBAC, approval-as-event, audit/redaction), CDO (consulted — approve-gate / trigger-run dashboard UX)
- **Binds to:** ADR-0039 (CP-1…CP-6, **Accepted** 2026-07-24 — CTO ratified, RACI 3.1/3.6 A), `docs/specs/008-mustaqil-ws-h-control/SPEC.md` (FR-001…FR-008 / SC-001…SC-005, reviewed 2026-07-24 at GATE-1), which **extends** ADR-0028 (the read-only, static-first, NOT-a-daemon cockpit — its `render()`/`_render_panel`/`NODATA` seam + the `cockpit_html.py` wrapper), depends on ADR-0034 (WS-B headless SDK runner — trigger a run), ADR-0038 (RBAC + in-tenant TN-1/TN-3/TN-5), ADR-0036 (self-host Langfuse — live status); honors ADR-0027 (NOT-a-daemon + never-auto-approve), ADR-0024/0025 (event store canonical), ADR-0012 (M/B/F content-classification + redaction), ADR-0019 (feature flag). **Reuses verbatim** the WS-E RBAC SSOT — `config/rbac.yaml` + `scripts/rbac.py` (`decide` / `append_gate_approval` / `is_gate_closed`) and the design `docs/design/ws-e-tenant-hardening.md` §1. Founder discovery Q6 (Founder-only approval; read-only audit for a small team).
- **Downstream:** DAS-1600 (harden the spike `tools/control_plane/app.py` — RBAC/audit against the SSOT), DAS-1601 (the two remaining governed writes — approve-gate + trigger-run — bound to the real machinery), DAS-1602 (offline vendored-wheel install + degrade-to-static), DAS-1603 (negative tests — this doc hands it §7), DAS-1604 (deploy runbook — flag OFF), DAS-1605 (maintenance / health-eval).

> **Scope of this doc.** WHAT the governed-control model is and HOW its pieces
> interlock — how the read-only cockpit becomes a governed view+controller, how
> every write is RBAC-authorized against the **WS-E SSOT** (not the spike's ad-hoc
> tier) and audited+redacted, why an approval is a Founder-identity **event** the
> dashboard can never sign, the offline-install + degrade-to-static + NOT-a-daemon
> contract, and the spike-hardening the Development ticket applies — each traced to
> its FR and its CP invariant, plus the negative-path spec the Testing ticket
> (DAS-1603) implements. It ships **no runtime code**: the hardened app, the two new
> governed writes, and the vendored-wheel bundle are built by DAS-1600/1601/1602
> against this design. The on-branch spike `tools/control_plane/app.py` + its runbook
> `docs/runbooks/ws-h-control-plane.md` + `tests/test_ws_h_control_plane.py` are the
> reference this design **hardens** — cited, not modified here (this ticket touches
> only `docs/design/` + the ticket file). The landed WS-E RBAC SSOT (`config/rbac.yaml`
> + `scripts/rbac.py`), the ADR-0028 cockpit render seam (`scripts/cockpit.py` +
> `scripts/cockpit_html.py`), the ADR-0034 runner, and the ADR-0012 scrubber are
> **reused**, never re-implemented. Everything is behind `ws_h_control_plane`
> (`config/features.yaml` line 27) DEFAULT **OFF** — with the flag OFF the whole
> surface does not exist and the ADR-0028 static read cockpit is the shipped default.

## 0. The governed-control model (one picture)

WS-H is not a new cockpit and not a new dispatch path. It is a **controller layer**
wrapped around the *existing* read-only cockpit, where every write is admitted only
if it survives an RBAC check against the WS-E SSOT and lands in the canonical event
store. Four invariants interlock, each fail-closed:

```
  READ SEAM (CP-1, §1)                       RBAC SSOT (CP-2, §2)  ── config/rbac.yaml + scripts/rbac.py
  ── ADR-0028 cockpit.render()/_render_panel     principal kinds: founder / audit-team / agent / orchestrator
     + cockpit_html.py wrapper (the SAME             gate.approve + run.trigger = FOUNDER-ONLY (structural)
     panels; a controller layer, not a fork)         unconfigured RBAC ⇒ 503 (fail-closed, no anon access)
        │                                                │  decide(principal, permission)  — default-DENY
        ▼                                                ▼
  GET  /  → data-free HTML shell (no token)     every /api/* data+action endpoint identified to a principal
  GET  /api/cockpit, /api/board  → read (audit.read)      │
        │                                                ▼
        │                              THREE GOVERNED WRITES (CP-3, §3) — each decide()-authorized + audited
        │                                ── (a) submit goal PROPOSAL → board/goal-inbox/ (awaits Founder /daslab-plan)
        │                                ── (b) trigger run  → run.trigger  → ADR-0034 WS-B headless runner
        │                                ── (c) approve/deny gate → gate.approve → append_gate_approval() [FOUNDER-ONLY]
        │                                          │  each → canonical event store (ADR-0024/0025)
        ▼                                          ▼  redact (ADR-0012), append-only, attributed
  BOARD-CANONICAL (CP-4, §4) ── every read+write routes through board/tickets + goal queue + event store;
     no parallel dashboard state; a divergence resolves to the board (C2).
        │
        ▼
  OPTIONAL / OFFLINE / NOT-A-DAEMON (CP-5,6, §5) ── Founder-enabled process, flag ws_h_control_plane OFF by default;
     degrades to the ADR-0028 static cockpit when absent; dispatches NOTHING itself; loopback-default bind;
     offline-installable from a vendored wheel bundle; in-tenant only, no external SaaS.
```

- **[CP-1] Extends the cockpit (§1).** The control plane reuses the ADR-0028
  `render()`/`_render_panel`/`NODATA` seam + `cockpit_html.py` wrapper and adds a
  controller layer around the *same* panels; it never forks a second view. The
  read cockpit is the degrade-to-static base (CP-5).
- **[CP-2] Founder-only RBAC, fail-closed (§2).** Every data/action endpoint is
  identified to a **principal** and authorized by `scripts/rbac.decide()` against
  `config/rbac.yaml` (the WS-E SSOT). Unconfigured RBAC ⇒ 503 for every data/action
  endpoint; only a health probe + a data-free HTML shell answer. No anonymous or
  default-open access; in-tenant bind only. The spike's ad-hoc `viewer<operator<founder`
  tier is **replaced** by the SSOT kinds `founder`/`audit-team`/`agent`/`orchestrator`.
- **[CP-3] Three governed writes + audit (§3).** Exactly three write classes —
  goal proposal, trigger run, approve/deny gate — each RBAC-authorized, each appended
  to the canonical event store (ADR-0024/0025) and redacted per ADR-0012. Approval
  binds to a **Founder-identity `gate_approval` event**, not a button-press claim; the
  dashboard can never sign a gate; a GATE-5-open deployment stays machine-blocked
  regardless of any button.
- **[CP-4] Board-canonical view+controller (§4).** Every read+write routes through
  the board / goal queue / event store; there is no parallel dashboard state; a
  divergence resolves to the board.
- **[CP-5/CP-6] Optional / offline / NOT-a-daemon / in-tenant (§5).** An optional,
  Founder-enabled, `ws_h_control_plane`-OFF-by-default process that degrades to the
  ADR-0028 static cockpit and dispatches nothing itself; offline-installable from a
  vendored wheel bundle; in-tenant only, no external SaaS.
- **Spike hardening (§6).** DAS-1600 migrates the spike off its ad-hoc tier onto the
  SSOT `decide()` and cleans the ~10 B008 ruff violations. **Negative-path spec (§7)**
  is what DAS-1603 asserts.

---

## 1. Extends the cockpit — one render seam, a controller layer, not a second cockpit (CP-1 / FR-001)

**Requirement (FR-001 / CP-1):** the control plane MUST extend the ADR-0028 cockpit
through its single render seam (`render()`/`_render_panel`/`NODATA` + the
`cockpit_html.py` wrapper), adding a controller layer around the *same* panels; it
MUST NOT fork a second cockpit view. The read-only cockpit remains the
degrade-to-static base.

### 1.1 The read side reuses the ADR-0028 seam verbatim

The cockpit's panel content is owned by `scripts/cockpit.py` (`render()`,
`_render_panel(num, title, lines)`, the `NODATA` sentinel) and its HTML skin by
`scripts/cockpit_html.py` (ADR-0028 D-4). WS-H's read endpoints are a **thin
pass-through** over that seam:

- `GET /api/cockpit` renders the **real** cockpit and embeds its output — exactly the
  ADR-0028 D-4 "one cockpit, two skins" contract. The spike already does this honestly
  by shelling `scripts/cockpit.py` through its own CLI (its argparse owns the defaults)
  and degrading to the `NODATA` line when the cockpit is unavailable; **the hardened
  app SHOULD prefer importing the `cockpit_html.render_html(state)` seam directly**
  (ADR-0028 D-1/D-5: a pure `render_html` callable with no socket bound) so the web
  surface is a *skin*, not a subprocess — but the subprocess fallback stays the honest
  NODATA base. Either way there is exactly one place that decides *what* a panel says
  (`cockpit.py`) and a thin place that decides *how it looks* (the wrapper). No panel
  is re-implemented; the terminal, static-HTML, and control-plane surfaces cannot drift.
- The **controller layer is additive**: WS-H wraps the read seam with (a) authn/authz
  (§2) and (b) the three governed writes (§3). It adds routes *around* the panels; it
  never copies panel logic, the `NODATA` text, or a data source.

### 1.2 Degrade-to-static is inherited, not bolted on

ADR-0028 D-5 makes the static `file://` snapshot the **base case**, not a fallback
path. WS-H inherits that structurally (§5.2): the control plane is the *extension*;
the static read cockpit is the *base*. Non-fabrication is inherited too — an empty
event store yields a valid, honest HTML page (`NODATA`, no fabricated number), the
same guarantee the terminal cockpit gives.

**Trace:** WS-H read endpoints are a thin controller over the ADR-0028
`render()`/`_render_panel`/`NODATA` + `cockpit_html.py` seam (D-4), degrade-to-static
inherited from D-1/D-5 — closes **FR-001 / CP-1**.

---

## 2. Founder-only RBAC, fail-closed — bound to the WS-E SSOT, NOT the spike tier (CP-2 / FR-002 / FR-007 / Q6)

**Requirement (FR-002 / CP-2):** every data and action endpoint MUST identify the
request to a role via authentication + RBAC — no anonymous or default-open access;
unconfigured RBAC MUST **fail closed** (503 for all data/action endpoints, only a
health probe + a data-free HTML shell answer); the surface serves **only within the
tenant** (ADR-0038 TN-1/TN-3). **Requirement (FR-007 / CP-6):** the control plane,
its auth, and its data all run in-tenant with **no external SaaS**; secrets stay in
the tenant vault (TN-5).

### 2.1 The binding decision — reuse `scripts/rbac.decide()`, retire the spike tier

The single most important design constraint carried from ADR-0039's sign-off and the
SPEC-008 GATE-1 review note: **the control plane reuses the WS-E RBAC SSOT
(`config/rbac.yaml` + `scripts/rbac.py`) — it does NOT keep the spike's ad-hoc
`viewer < operator < founder` tier.** The spike (`tools/control_plane/app.py`) shipped
a local `ROLE_RANK = {"viewer": 0, "operator": 1, "founder": 2}` and a `require(min_role)`
rank check. That tier is **retired by DAS-1600** and replaced by the SSOT model, whose
principal kinds are:

| Principal kind | Who | Holds (near-term self-host, Q6) |
|---|---|---|
| `founder` | the human Founder identity | everything: `gate.approve`, `run.trigger`, `board.mutate.routing`, `board.work`, `audit.read`, `config.edit.security` |
| `audit-team` | a small human team | **`audit.read` ONLY** — read the trail; approve/trigger/mutate NOTHING (least privilege) |
| `agent` | a role subagent (`agent:<role>`) | `board.work` (own ticket), `audit.read` (own run) — **never** `gate.approve`/`run.trigger` (structural) |
| `orchestrator` | the dispatch mechanism | `board.mutate.routing`, `audit.read` — cannot *originate* a `gate.approve`/`run.trigger` |

Read it by its two load-bearing rows (`config/rbac.yaml` header): **`gate.approve` and
`config.edit.security` are Founder-identity ONLY** — nobody else, no agent, ever. In
the near-term tenant (one Founder + a small read-only team, Q6) this means the
web surface is, for every non-Founder principal, a **read-only lens**: it can inspect
the board/cockpit/audit but performs no write. This is exactly the Q6 posture — and it
is a *stronger* default than the spike's `operator` tier, which could self-authorize a
goal-proposal write.

### 2.2 Identity — a token/session maps to a principal STRING, not to an ad-hoc role field

The control plane's authn establishes a **principal string** that `decide()` and
`_kind_of()` understand — `founder`, `audit-team`, `orchestrator`, or `agent:<role>`.

- **Where the map lives (FR-007 / TN-5).** The token→principal map lives in the
  **tenant vault**, out of the repo — the spike's `DASLAB_CP_RBAC` file (ADR-0038 TN-5,
  kept in `/secure/…`, never committed). DAS-1600 changes its shape only in the value:
  the per-token entry carries a `principal` resolving to an SSOT kind
  (`{"<token>": {"user": "akmal", "principal": "founder"}}`), **not** the ad-hoc
  `role: operator`. A `principal` that `_kind_of()` does not recognise resolves to **no
  kind** and holds nothing (fail-closed) — an unknown/forged principal is denied
  everything.
- **The Founder identity is established by the session, not by agent content.** The
  `principal_id` the control plane hands to `append_gate_approval()` (§3.3) is stamped
  from the **authenticated login session** — the ADR-0039 control-plane login — exactly
  as WS-E §1.4 specifies ("the CLI operator identity or the ADR-0039 control-plane login
  session — not by any content an agent produces"). The dashboard's HTML/JS never
  supplies the principal kind; the server derives it from the session token.
- **In-tenant bind (FR-007 / CP-6).** The server binds **loopback by default**
  (`127.0.0.1`); a tenant-network bind (`DASLAB_CP_BIND`) is a deliberate tenant act
  (ADR-0038 TN-5) and even then serves **only within the tenant** — no component phones
  a hosted SaaS; live status is read from the in-tenant event store and self-hosted
  Langfuse (ADR-0036); secrets stay in the vault.

### 2.3 Fail-closed — the exact SC-001 contract

The fail-closed rule is the spike's already-correct shape, re-expressed against the SSOT:

- **RBAC unconfigured ⇒ 503.** `scripts/rbac.load_grants()` returns `{}` when
  `config/rbac.yaml` is absent (nothing grantable — every `decide()` denies), and
  raises `RbacConfigError` when the file is present but structurally invalid (a tampered
  security surface is a **loud** refusal, never a silent partial load). The control
  plane maps an unconfigured/unloadable RBAC to **503** on every data/action endpoint;
  **only** `GET /healthz` and the **data-free HTML shell** (`GET /`) answer. There is no
  default-open surface.
- **Missing/invalid token ⇒ 401.** A request with no `Authorization: Bearer <token>`,
  or a token absent from the vault map, or a token whose `principal` does not resolve to
  a kind, is **401** with an **audited deny** (§3.2).
- **Authorized but not permitted ⇒ 403 + audited deny.** A recognised non-Founder
  principal that requests a Founder-only write (`decide(principal, "run.trigger") ==
  deny`) is **403** with an audited deny — the deny path is symmetric to the allow path.
- **The HTML shell leaks no data (SC-001).** `GET /` returns the **empty** shell
  (form + panels labelled "not loaded"); it carries **no** board/cockpit/audit content.
  All data arrives only through a token-bearing `/api/*` call.

**Trace:** every data/action endpoint identified to a principal via
`scripts/rbac.decide()` over `config/rbac.yaml` (the SSOT; spike tier retired) →
unconfigured RBAC 503 / bad token 401 / not-permitted 403+audited-deny / data-free
shell → in-tenant loopback-default bind, vault-resident token map, no external SaaS —
closes **FR-002 / FR-007 / CP-2 / CP-6**.

---

## 3. Three governed writes + audit; Founder-only approval as an EVENT (CP-3 / FR-003 / FR-004 / Q6)

**Requirement (FR-003 / CP-3):** the dashboard MUST expose exactly three governed write
classes — (a) submit a goal proposal to the Founder-approved queue, (b) trigger a run
via the WS-B headless runner (ADR-0034), (c) approve/deny a gate or interrupt-card —
each RBAC-authorized and each appended to the event store (ADR-0024/0025), redacted per
ADR-0012. **Requirement (FR-004 / Q6 / QONUN-5):** gate/interrupt-card approval MUST
bind to a **Founder-role identity**: the dashboard, an agent, or any non-Founder role
MUST NOT be able to sign a gate, and a GATE-5-open deployment MUST stay machine-blocked
regardless of any UI action.

### 3.1 The exact write surface — three classes, each mapped to an SSOT permission

| # | Write class | Endpoint (hardened) | SSOT permission checked | Executes through | Ships in |
|---|---|---|---|---|---|
| (a) | Submit a **goal proposal** | `POST /api/goals` | Founder-authorized in the near-term matrix (Q6 — team is read-only; §3.5) | writes a `status: proposed` file into `board/goal-inbox/`; creates **no** ticket, approves **nothing**, dispatches **nothing** — awaits Founder discovery via `/daslab-plan` (Founder-Approved Goal Queue law) | spike (a) hardened by DAS-1600 |
| (b) | **Trigger a run** | `POST /api/runs` | `run.trigger` (**Founder-only** per SSOT) | the ADR-0034 WS-B headless runner (`/daslab-run`) — the control plane calls the existing runner entrypoint; it re-implements no dispatch | **new**, DAS-1601 |
| (c) | **Approve/deny** a gate or interrupt-card | `POST /api/gates/{id}/approve` (+ `/deny`) | `gate.approve` (**Founder-only**, structural) | `scripts/rbac.append_gate_approval()` → one attributed `gate_approval` event; for an interrupt-card, the Founder answer via the existing card mechanism (`board/interrupts/<id>.json`) | **new**, DAS-1601 |

Each write is (1) authorized by `decide()` **before** it acts, (2) executed only
through the **canonical entrypoint** (goal-inbox file / ADR-0034 runner / the real gate
+ interrupt-card machinery — never a PoC stub), and (3) appended to the event store,
redacted per ADR-0012. A principal not granted the write is refused with an **audited
deny** (§3.2).

### 3.2 The audit record shape + redaction mapping (ADR-0012)

Every control-plane request/decision — allow **and** deny — is appended to an
append-only audit ledger. The spike already writes `board/.control-plane-audit.jsonl`
with `{ts, action, user, role, decision, detail}`; **DAS-1600 aligns it to the SSOT
vocabulary** so it joins the same canonical, attributed stream as the WS-E
`gate_approval` ledger:

| Field | Meaning | Tier (ADR-0012) |
|---|---|---|
| `ts` | UTC timestamp | M |
| `action` | controlled vocabulary — `auth` / `board.read` / `cockpit.read` / `audit.read` / `goal.submit` / `run.trigger` / `gate.approve` / `gate.deny` | M |
| `principal_id` | the authenticated principal string (`founder`, `audit-team`, `agent:<role>`) — stamped from the session, never from request content | M |
| `principal_kind` | resolved kind (`_kind_of`) | M |
| `decision` | `allow` / `deny` | M |
| `reason` | the `decide()` reason string | M |
| `detail` | relative path / ticket id / run id — a **reference**, never a payload | M (references only) |

- **Redaction mapping (ADR-0012, redact→truncate→append, fail-closed).** An audit
  record is **Tier-M by construction** — controlled-vocabulary metadata + ids + a
  reference path, with **no** secret/prompt/completion/source/diff field. Any free-text
  `detail` value is passed through the **same** ADR-0012 §2 scrubber the WS-A tool path,
  the WS-D lens, and `scripts/rbac.append_gate_approval()` use (no third redactor):
  Tier-M ids survive; a Tier-B value is scrubbed; an unclassifiable value drops to
  `[REDACTED:unclassified]`. A token/secret **never** enters an audit record (the token
  lives in the vault, §2.2; the record carries only the resolved principal).
- **The `gate_approval` write (c) reuses the WS-E ledger, not a new store.** The
  approve write does not append to the control-plane ledger's own schema for its
  *governance* fact — it calls `scripts/rbac.append_gate_approval()`, which writes the
  attributed `gate_approval` record `{event_type, ticket_id, principal_id,
  principal_kind, category, gate, ts, attestation_ref?, trace_id?, run_id?}` to the
  dedicated `board/.rbac-audit.jsonl` ledger (WS-E §2.1), redacted at write. The
  control-plane ledger additionally records the **request/decision** fact (who pressed,
  allowed/denied) for operability. One governance fact, one canonical producer.

### 3.3 Approval is a Founder-identity EVENT — the dashboard can never sign a gate (FR-004 crux)

This is the invariant FR-004/Q6 closes, and it is enforced **structurally** by reusing
`scripts/rbac.append_gate_approval()` — not by dashboard discipline:

- **What an approval IS.** Pressing "approve" in the dashboard calls
  `append_gate_approval(principal=<session principal>, ticket_id=…, category=…,
  gate=…, …)`. That function (i) **first** checks `decide(principal, "gate.approve") ==
  allow` and raises `ApprovalRefused` (nothing written) otherwise, and (ii) **stamps**
  `principal_kind` from `_kind_of(principal)` — **not** from any caller/request content.
  So the only way an appended `gate_approval` carries `principal_kind: founder` is if the
  authenticated session principal *is* the Founder.
- **A button-press is a CLAIM, not the fact.** A gate closes only when
  `scripts/rbac.is_gate_closed(ticket_id, category)` finds a matching Founder-identity
  `gate_approval` event. A dashboard button that merely *sets a status* or *writes
  `approval: human:founder` into frontmatter* produces a **forged claim with no backing
  event** — `is_gate_closed` returns `NOT closed` (WS-E §1.4 / SC-001). The dashboard
  cannot manufacture the event because the server refuses to stamp `founder` for a
  non-Founder session, and the event store is append-only + attributed.
- **Why an agent can NEVER sign.** `decide("agent:<any-of-32-roles>", "gate.approve")
  == deny` by construction (the permission is absent from the `agent` kind **and**
  `load_grants()` refuses to load an `rbac.yaml` that granted it to a non-founder kind).
  There is no role string, ticket field, or chat message that promotes an agent
  principal into `gate.approve`. This is the ADR-0026 route-graph / WS-A tool-allowlist
  "structurally unrepresentable" pattern applied to gate approval.
- **GATE-5-open stays machine-blocked regardless of any button (C4).** Two independent
  reasons the dashboard cannot deploy past an open GATE-5: (1) the control plane
  **dispatches nothing itself** (CP-5, §5.3) — a wave advances only from a human
  `run.trigger` write or the HEARTBEAT, never because the server is running or a button
  was pressed; (2) the AADL gate order is enforced by the engine's dispatcher +
  `scripts/rbac.enforce_gate_closed()` / `scripts/check_never_auto_approve.py`
  independently of the UI — an open `gate5_deployment` gate with no backing Founder
  `gate_approval` event blocks the deploy at the engine layer, and the button has no
  path around it. The button can *record* a Founder approval event; it cannot *skip* a
  gate.

### 3.4 The two-flag interplay (control-plane authorization vs. engine enforcement)

WS-H is gated by `ws_h_control_plane` (its own process); the WS-E gate enforcement is
gated by `ws_e_tenant_hardening`. These are distinct locks and the design keeps them
honest:

- The **pure library primitives** `decide()` / `append_gate_approval()` /
  `is_gate_closed()` are **usable directly regardless of the WS-E flag** (per
  `scripts/rbac.py` — "the pure evaluator `decide` is a library primitive usable
  directly"). The control plane calls them to authorize its **own** writes whenever the
  CP process runs — so a WS-H write is SSOT-authorized even if `ws_e_tenant_hardening`
  is OFF.
- The engine's **dispatch-path** enforcement (`enforce_gate_closed`) is inert when
  `ws_e_tenant_hardening` is OFF (dispatch byte-identical to pre-merge). That is the WS-E
  contract and WS-H does not change it. The near-term deploy posture (DAS-1604 runbook)
  makes both flags a Founder stand-up decision.
- Net: the control plane never *weakens* a gate — with WS-E enforcement OFF the gate is
  governed exactly as it is today (the existing `check_never_auto_approve.py` ticket-layer
  lock); with it ON, WS-H's Founder `gate_approval` events are what close a gate. A
  control action can only ever be **as governed as, or more governed than**, the CLI.

### 3.5 The goal-proposal write (a) under the SSOT — no `operator` tier reintroduced

The spike let an `operator` submit a goal proposal. Under the SSOT there is **no
`operator` kind**, and the near-term team is **read-only** (`audit-team` holds only
`audit.read`, Q6). The design therefore authorizes the goal-proposal write to the
**Founder** in the shipped near-term `rbac.yaml`, and does **not** reintroduce a
non-Founder writer tier. A goal proposal is the *softest* write (it creates no ticket
and dispatches nothing — it awaits Founder discovery), so if a specific tenant later
wants a non-read-only proposer, that is a **reviewed `config.edit.security` edit** to
`rbac.yaml` (Founder-only, `security_sensitive` + `permission_change`, never
`approval: auto*`) adding an explicit grant — **not** a hardcoded rank tier baked into
the app. Least privilege by default; widening is an explicit, audited config act.

**Trace:** exactly three governed writes, each `decide()`-authorized + executed through
the canonical entrypoint + audited/redacted (ADR-0012) → approval = attributed
Founder-identity `gate_approval` event via `append_gate_approval()`, button-press is an
unverified claim, agent structurally excluded, GATE-5 machine-blocked by CP-5 +
independent gate enforcement → goal-proposal Founder-authorized without reintroducing an
`operator` tier — closes **FR-003 / FR-004 / CP-3 / Q6**.

---

## 4. Board-canonical view+controller — no parallel dashboard state (CP-4 / FR-005)

**Requirement (FR-005 / CP-4):** all reads and writes MUST go **through** the canonical
board (`board/tickets/`), goal queue, and event store — never a parallel dashboard
state; the control plane is a view+controller that orchestrates existing entrypoints and
re-implements no dispatch; a divergence resolves to the board (C2).

- **Reads** come from the canonical files: tickets from `board/tickets/` (the spike's
  `board_summary()` parses frontmatter directly), the cockpit from the ADR-0028 seam
  (§1), the audit tail from the append-only ledgers. The app holds **no** in-memory or
  on-disk cache that could diverge — every request re-reads the source (the spike
  re-reads RBAC per request; the same discipline applies to board/cockpit/audit reads).
- **Writes** land in the canonical stores: goal proposals in `board/goal-inbox/`, runs
  through the ADR-0034 runner (which itself routes through the board/dispatch
  chokepoint), gate approvals in the canonical event store via `append_gate_approval()`.
  The control plane **orchestrates existing entrypoints**; it does not re-implement
  dispatch, routing, or gate logic.
- **A divergence resolves to the board.** There is no dashboard "state" to reconcile —
  the board / goal queue / event store are the single source of truth (C2), and the
  dashboard is a stateless projection + a set of authorized writes onto them. This is
  the ADR-0039 CP-4 rule and the ADR-0025 "event store is load-bearing" law.

**Trace:** stateless view over the canonical board/goal-queue/event-store + writes
through the existing entrypoints only, no parallel store, divergence resolves to the
board — closes **FR-005 / CP-4 / C2**.

---

## 5. Offline-install, degrade-to-static, NOT-a-daemon, in-tenant (CP-5 / CP-6 / FR-006 / FR-008)

### 5.1 Offline-installable from a vendored wheel bundle (FR-008 / CP-6)

**Requirement (FR-008):** the control plane MUST be **offline-installable** from a
vendored wheel bundle (full dependency closure, platform-matched), so a no-network
in-tenant server can install and boot it without reaching any package index; the
vendored bundle is a machine-specific install cache, **not** tracked source.

- **The bundle.** `tools/control_plane/.vendor/site-packages` holds the full
  dependency closure (`fastapi` + `uvicorn` + `starlette` + `pydantic` + `anyio` +
  `exceptiongroup` + …), platform-matched (e.g. `aarch64` / `cp310`). It is built **once**
  in a network-connected environment (`pip download … --platform … --only-binary=:all:`
  then `pip install --no-index --find-links=wheels --target=site-packages`) and copied to
  the target. **DAS-1602 owns building + verifying this bundle**; the spike already
  proved the pattern (14 wheels, ~3 MB, verified against the real `Requires-Dist`
  metadata — a note the runbook flags because `pip`'s cross-platform resolution once
  silently dropped `exceptiongroup`; DAS-1602 MUST verify the closure by hand, not trust
  the resolver).
- **No-network boot.** With the bundle present the target sets
  `PYTHONPATH="$(pwd)/tools/control_plane/.vendor/site-packages"` and runs uvicorn — no
  `pip install`, no package-index fetch (ADR-0039 CP-6 verified on-device:
  fastapi/uvicorn/starlette/pydantic import clean, `/healthz` 200, arm64/cp310).
- **Not tracked source.** `tools/control_plane/.vendor/` is **gitignored** — a
  machine-specific install cache, not committed source (same posture as other run-cache
  state). DAS-1603 tests the offline boot (SC-003) against the built bundle; the test
  does not require the bundle to be in git.
- **The optional deps stay OUT of core `requirements.txt`.**
  `tools/control_plane/requirements-control.txt` carries `fastapi`/`uvicorn`; the core
  engine does not depend on them (CP-5 — the control plane is an optional process, not
  core runtime). With the flag OFF and the process absent, the engine has no FastAPI
  dependency at all.

### 5.2 Degrade-to-static — the read cockpit is the base case (CP-5 / FR-006)

The degrade-to-static contract is **structural**, inherited from ADR-0028 D-5:

- When the optional control-plane process is **not running**, the operator's surface is
  the ADR-0028 **static read cockpit** — a complete, readable, honestly-timestamped
  `file://` snapshot (or the terminal `python3 scripts/cockpit.py`). The control plane is
  the *extension*; the static cockpit is the *base*. There is no error state and no
  daemon requirement — opening DasLab with the CP process absent "just works" as the
  read-only cockpit.
- This makes the fallback path the **ordinary** path (exercised on every flag-OFF run),
  not an emergency-only branch — the ADR-0028 D-1 argument. SC-004 asserts it.

### 5.3 NOT-a-daemon — optional, Founder-enabled, dispatches nothing (CP-5 / FR-006)

**Requirement (FR-006):** the server MUST be an **optional, Founder-enabled** process,
feature-flagged **OFF** by default (`ws_h_control_plane`), that degrades to the static
cockpit when absent and **dispatches nothing on its own**.

- **Feature-flagged OFF (ADR-0019).** `config/features.yaml` carries
  `ws_h_control_plane: false` (line 27, confirmed present + `false`). With the flag OFF
  the whole surface does not exist; dispatch behaviour is byte-identical to pre-merge
  (SC-004).
- **Optional, Founder-enabled process.** The server runs only if the Founder starts it
  (a foreground `uvicorn` run, or an opt-in `systemd`/`launchd` unit the Founder installs
  — DAS-1604 runbook ships the unit *example*, but the actual stand-up is a Founder act).
  DasLab does **not** install a daemon, a cron, or a launchd entry itself — the same
  ADR-0027/0028 posture (any cadence lives in an external OS entry the Founder owns).
- **Dispatches nothing on its own (the NOT-a-daemon crux).** The web server serves
  requests; it never advances a wave by itself. A wave advances **only** from a human
  write action through §3 (a `run.trigger` the Founder authorizes) or from the HEARTBEAT
  (ADR-0027) — **never** because the server is up. The server has no timer, no
  self-scheduler, no background dispatch loop. This is what reconciles a long-running web
  process with the NOT-a-daemon law: it is a passive request-server that dispatches
  nothing, exactly as ADR-0028's optional live cockpit is a passive request-server that
  writes nothing.
- **Loopback-default bind (CP-6).** Binds `127.0.0.1` by default; a tenant-network bind
  is a deliberate Founder act (§2.2) and even then serves only within the tenant.

**Trace:** vendored-wheel offline install (bundle built + verified by DAS-1602,
gitignored cache, optional deps out of core) + degrade-to-static inherited from ADR-0028
D-5 (read cockpit is the base case) + optional Founder-enabled flag-OFF process that
dispatches nothing itself and binds loopback-default — closes **FR-006 / FR-008 / CP-5 /
CP-6**.

---

## 6. Spike hardening — the DAS-1600 clean-up (SC-005)

The Development ticket DAS-1600 hardens `tools/control_plane/app.py` from PoC to the
design above. Two concrete items this design specifies:

### 6.1 Retire the ad-hoc tier; call the SSOT `decide()`

- Remove `ROLE_RANK = {"viewer": 0, "operator": 1, "founder": 2}` and the
  `require(min_role)` rank dependency. Replace with a permission-check dependency that
  calls `scripts/rbac.decide(principal, permission)` — e.g. a `RequirePermission(perm)`
  dependency that resolves the session `principal` (§2.2) and returns the identified
  principal on `allow`, raising 403 + audited deny on `deny`. The read endpoints check
  `audit.read`; `POST /api/runs` checks `run.trigger`; `POST /api/gates/{id}/approve`
  goes through `append_gate_approval()` (which checks `gate.approve` internally).
- The RBAC file's per-token value changes `role: <viewer|operator|founder>` →
  `principal: <founder|audit-team|agent:<role>|orchestrator>` (§2.2).

### 6.2 Fix the ~10 B008 ruff violations (FastAPI `Depends`/`require` in argument defaults)

The spike triggers `ruff` B008 ("do not perform function call in argument defaults")
on every `who: dict = Depends(require("viewer"))` route signature (~10 occurrences).
The **fix pattern** (SC-005 wants them cleaned, not `# noqa`-suppressed):

- **Preferred — `Annotated` dependency (the modern FastAPI idiom).** Move the `Depends`
  into the type annotation via `typing.Annotated`, so the parameter has **no call in its
  default**:
  ```python
  from typing import Annotated
  from fastapi import Depends
  RunTrigger = Annotated[dict, Depends(RequirePermission("run.trigger"))]
  @app.post("/api/runs")
  def api_runs(who: RunTrigger) -> dict: ...
  ```
  `Annotated[dict, Depends(...)]` places the dependency in the annotation metadata, not
  the default value — ruff B008 does not fire, and FastAPI resolves it identically.
- **Alternative — module-level singleton dependency.** Bind the `Depends(...)` to a
  module-level constant once and reference the *name* as the default
  (`_AUDIT_READ = Depends(RequirePermission("audit.read"))`; `def api_board(who: dict =
  _AUDIT_READ)`). The default is now a name, not a call — B008 does not fire. (The
  `Annotated` form is preferred because it also types the parameter.)

SC-005 also requires: `diagnostics.py` 100/100, `ruff` clean on `tools/control_plane/`,
`board_lint`/`check_spec_consistency`/`check_dependency_graph` green, green CI on every
WS-H PR, no `project:` field on any WS-H ticket (board_lint R9), committed wave
attestation (ADR-0031/0032).

**Trace:** SSOT `decide()` replaces the ad-hoc tier + `Annotated`/module-singleton
dependency pattern clears the B008 violations — closes the hardening half of **SC-005**.

---

## 7. Negative-path spec for DAS-1603 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1603, `zone: tests`, `implements: [SC-001,
SC-002, SC-003]`, red-team consulted) must assert, folding in and extending the spike's
7-test suite `tests/test_ws_h_control_plane.py`. Each is written to be implemented
directly against the hardened `tools/control_plane/app.py` (DAS-1600/1601), the reused
`scripts/rbac.decide()`/`append_gate_approval()`/`is_gate_closed()`, the ADR-0012
scrubber, and the DAS-1602 offline bundle — using FastAPI's `TestClient`.

### SC-001 — fail-closed RBAC (FR-002 / CP-2)

- **Unconfigured RBAC ⇒ 503 on every data/action endpoint.** With `config/rbac.yaml`
  (or `DASLAB_CP_RBAC`) absent/unloadable, assert `GET /api/board`, `GET /api/cockpit`,
  `GET /api/audit`, `POST /api/goals`, `POST /api/runs`, `POST /api/gates/{id}/approve`
  each return **503**, and that **only** `GET /healthz` (200) and `GET /` (the data-free
  HTML shell) answer. Assert a **structurally invalid** `rbac.yaml` (e.g. `gate.approve`
  granted to `agent`) makes `load_grants()` raise `RbacConfigError` → 503 (loud
  fail-closed, not a silent partial load).
- **Missing/invalid token ⇒ 401.** Assert no `Authorization` header, a token absent
  from the vault map, and a token whose `principal` does not resolve to a kind each
  return **401** with an **audited deny** record appended.
- **The HTML shell leaks no board data without a token.** Assert `GET /` returns the
  empty shell and contains **no** ticket id / status count / cockpit panel / audit line —
  the response body carries no board data.

### SC-002 — Founder-only approval; GATE-5 stays blocked (FR-004 / Q6)

- **Non-Founder approval refused + audited.** Assert `decide("audit-team",
  "gate.approve") == deny` and `decide("agent:<any-of-32-roles>", "gate.approve") ==
  deny` for **every** role; that `POST /api/gates/{id}/approve` by a non-Founder session
  returns **403** with an **audited deny**; and that `append_gate_approval(principal=
  "audit-team"|"agent:…", …)` raises `ApprovalRefused` and writes **no** record.
- **Only a Founder-identity closes a gate.** Assert `decide("founder", "gate.approve")
  == allow`; that a Founder-session approve appends **exactly one** attributed
  `gate_approval` record with `principal_kind == founder`; and that `founder` is the
  **only** principal holding `gate.approve` / `run.trigger` / `config.edit.security`.
- **A button cannot forge an approval (the FR-004 crux).** Given a
  never-auto-approve-category ticket carrying `approval: human:founder` frontmatter **but
  no backing `gate_approval` event**, assert `is_gate_closed(ticket_id, category)`
  returns **NOT closed** (forged claim rejected); with a matching Founder-identity
  `gate_approval` event, assert it returns closed. Assert an `agent`/`audit-team`
  principal **cannot emit** a record stamped `principal_kind: founder` (the write is
  refused before anything is written).
- **GATE-5-open stays machine-blocked regardless of any dashboard action.** Assert that
  with an **open** `gate5_deployment` gate and **no** backing Founder `gate_approval`
  event, no dashboard call advances the deployment — the control plane **dispatches
  nothing itself** (no `POST` triggers a wave), and the engine's gate enforcement
  (`enforce_gate_closed` when ON / `check_never_auto_approve.py` at the ticket layer)
  blocks it independently of the UI. A button press records at most a *claim*; it never
  skips the gate.

### SC-003 — offline install + boot + redacted audit (FR-008 / FR-003)

- **Offline boot.** Assert the app imports and boots against the vendored
  `tools/control_plane/.vendor/site-packages` closure with **no network** (no package
  index reachable) and answers `GET /healthz` → 200 (`{"ok": true, ...}`). The test runs
  against the DAS-1602 bundle via `PYTHONPATH`; it does not require the bundle in git.
- **Every governed write appends a redacted audit record (ADR-0012).** Feed a governed
  write whose `detail`/body carries a **planted secret** (an `sk-ant-…` key, an
  `Authorization: Bearer …` / JWT, a `postgres://user:pass@host/db` DSN, a PII
  email/name) through the write path; assert the appended audit record replaces each
  with its `[REDACTED:…]` token, that **no** raw secret/PII substring appears in the
  ledger, and that the record is **Tier-M** (no secret/prompt/completion/source field).
  Assert **fail-closed** ordering (redact→truncate→append) and that Tier-M ids
  (attestation hash / hex trace id) survive un-over-redacted.

### SC-004 guard — flag OFF byte-identical + process-absent degrade-to-static

- **Flag OFF.** Assert `config/features.yaml` carries `ws_h_control_plane: false`, and
  that with the flag OFF a wave's dispatch behaviour is **byte-identical** to pre-merge
  (`board/.events.jsonl` + dispatch outcome unchanged) — the control-plane surface does
  not exist and the engine has no FastAPI dependency.
- **Process absent ⇒ degrade-to-static.** Assert that with the optional process **not
  running**, the operator surface is the ADR-0028 static read cockpit (a valid,
  honestly-timestamped snapshot) with **no error and no daemon** — the control plane is
  opt-in convenience, never a required daemon.

### SC-005 hardening guard (noted for DAS-1603/DAS-1600 completeness)

- Assert `ruff` is **clean** on `tools/control_plane/` (the ~10 B008 spike violations
  cleared, §6.2) and the spike's `viewer/operator/founder` tier is **gone** (no
  `ROLE_RANK` symbol; authorization goes through `scripts/rbac.decide()`).

**Hand-off:** SC-001 → §2; SC-002 → §3; SC-003 → §5.1 + §3.2; SC-004 → §5.2/§5.3; SC-005
→ §6. All assertions are expressible against the hardened `app.py`, the reused
`scripts/rbac.py` primitives (`decide` / `append_gate_approval` / `is_gate_closed` /
`ApprovalRefused`), the ADR-0012 scrubber, and the DAS-1602 offline bundle.

---

## 8. Traceability matrix

| SPEC FR / SC | ADR-0039 CP | This design | DAS-1603 SC | Builds in |
|---|---|---|---|---|
| FR-001 — extend the ADR-0028 cockpit through its one render seam; no second cockpit | CP-1 | §1 (thin controller over `render()`/`_render_panel`/`NODATA` + `cockpit_html.py`; degrade-to-static inherited) | (SC-004 degrade) | DAS-1600 |
| FR-002 — every endpoint identified to a principal via RBAC; unconfigured ⇒ fail-closed 503; in-tenant | CP-2 | §2 (reuse `scripts/rbac.decide()` over `config/rbac.yaml`; spike tier retired; 503/401/403; data-free shell) | SC-001 | DAS-1600 |
| FR-003 — exactly three governed writes, each RBAC-authorized + audited + redacted | CP-3 | §3.1/§3.2 (goal-proposal / trigger-run / approve-gate; audit shape + ADR-0012 mapping) | SC-003 | DAS-1600/1601 |
| FR-004 — approval binds to a Founder-role identity; dashboard/agent cannot sign; GATE-5 stays blocked | CP-3 | §3.3 (`append_gate_approval()` stamps `founder`; button = unverified claim; agent structural deny; GATE-5 machine-blocked) | SC-002 | DAS-1601 |
| FR-005 — all reads+writes through the canonical board/queue/event store; no parallel state | CP-4 | §4 (stateless view+controller; canonical entrypoints only; divergence resolves to board) | (SC-002/003) | DAS-1600/1601 |
| FR-006 — optional Founder-enabled flag-OFF process; degrades to static; dispatches nothing | CP-5 | §5.2/§5.3 (`ws_h_control_plane` OFF; NOT-a-daemon; loopback-default; dispatches nothing) | SC-004 | DAS-1602/1604 |
| FR-007 — control plane + auth + data in-tenant; no external SaaS; secrets in vault | CP-6 | §2.2 (vault-resident token map, loopback-default, self-hosted Langfuse, no SaaS) | SC-001 | DAS-1600/1602 |
| FR-008 — offline-installable from a vendored wheel bundle (platform-matched closure) | CP-6 | §5.1 (`.vendor/site-packages` gitignored cache; no-network boot; verify closure by hand) | SC-003 | DAS-1602 |
| SC-005 — diagnostics 100/100; ruff clean (10 B008 cleaned); validators green; flag OFF | all (flag) | §6 (SSOT `decide()` replaces tier; `Annotated`/module-singleton B008 fix) | SC-005 guard | DAS-1600 |

## 9. Open items handed downstream (not decided here)

- **DAS-1600** hardens `tools/control_plane/app.py`: retire the `viewer/operator/founder`
  tier for `scripts/rbac.decide()` (§2/§6.1), align the audit ledger to the SSOT
  vocabulary + ADR-0012 redaction (§3.2), clean the ~10 B008 violations via `Annotated`
  dependencies (§6.2), and read/authorize the goal-proposal write (a) under the
  near-term Founder-only matrix (§3.5). Behind `ws_h_control_plane` OFF.
- **DAS-1601** builds the two new governed writes: (b) `POST /api/runs` → `run.trigger`
  → the ADR-0034 WS-B headless runner, and (c) `POST /api/gates/{id}/approve`|`/deny` →
  `gate.approve` → `scripts/rbac.append_gate_approval()` bound to the **real** gate +
  interrupt-card machinery (never a PoC stub), each audited/redacted (§3).
- **DAS-1602** builds + verifies the vendored wheel bundle (`.vendor/site-packages`,
  platform-matched closure, verified against real `Requires-Dist`, gitignored) and the
  degrade-to-static / process-absent path (§5).
- **DAS-1603** implements §7 as folded-in extensions to `tests/test_ws_h_control_plane.py`.
- **DAS-1604** is a **deploy runbook** (flag OFF): tenant-VM stand-up (RBAC principals
  in `config/rbac.yaml`, vault token map, optional `systemd`/`launchd` unit example) —
  but the actual VM stand-up + flag flip is a **Founder act** (Q2), not this workstream's.
  Per the prior workstreams' pattern, the runbook + flag-OFF ship **closes GATE-5 on
  local-green**; the flip on a live VM is a separate Founder decision.
- **Security Lead (consulted)** reviews §2/§3 (Founder-only RBAC, approval-as-event,
  audit/redaction coverage) against ADR-0012/QONUN-5/the WS-E SSOT; **CDO (consulted)**
  reviews the approve-gate / trigger-run dashboard UX (§3); **CTO (accountable)** ratifies
  GATE-2 closure.
- The concrete RBAC principal list, the loopback-vs-network bind, and whether the
  goal-proposal write is ever widened beyond Founder are **tenant/Founder** decisions
  made at stand-up (DAS-1604) — not pre-decided here (least privilege, Q6).
