# WS-E TENANT hardening design — RBAC (Founder-gate), SIEM audit export, secrets/egress, and the in-tenant runtime BOM (LiteLLM gateway, deferred vLLM/SGLang eject-path, Presidio+promptfoo)

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead + COO consulted)
- **Date:** 2026-07-24
- **Ticket:** DAS-1581 (WS-E Design); epic DAS-1579 (MUSTAQIL WS-E TENANT)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — RBAC, secrets, audit export), COO (consulted — GATE-6 maintenance surface)
- **Binds to:** ADR-0038 (TN-1…TN-5 + the **binding** scope boundary, **Accepted** 2026-07-24), `docs/specs/006-mustaqil-ws-e-tenant/SPEC.md` (FR-001…FR-008, SC-001…SC-005, reviewed), ADR-0009 (LAW-8 admission layer / a true transport proxy only under the ADR-0034 SDK runner), ADR-0012 (M/B/F content-classification + redaction), ADR-0033 (the governed MCP edge — TB-1…TB-5; guardrails/evals reuse it), ADR-0034 (the headless SDK runner — the seam that owns the transport), ADR-0024/0025 (span-event schema + event store canonical), ADR-0031/0032 (wave attestation), the landed `scripts/check_in_tenant.py` + `config/tenant_boundary.yaml` (DAS-1543), WS-A `config/egress-allowlist.yaml` posture (`docs/design/ws-a-tool-admission.md`), the in-tenant runtime BOM (`docs/research/2026-07-23-daslab-production-stack-and-toolkits-mining.md` §2), Founder discovery answers Q6 (Founder-only approval + team read-only audit), Q9 (Claude subscription default; open-weight in-tenant serving a DEFERRED eject-path), Q10 (internal self-host ONLY — no SaaS / SOC 2 / SSO / multi-tenant)
- **Downstream:** DAS-1582 (RBAC model + audit event store + SIEM export under `tools/`/`config/`), DAS-1583 (LiteLLM in-tenant gateway + the deferred vLLM/SGLang eject-path adapter), DAS-1584 (Presidio+classifier+policy guardrail chain + promptfoo golden-set evals), DAS-1585 (negative tests — this doc hands it §6), DAS-1586 (deploy runbook — flag OFF; the VM stand-up is a Founder act), DAS-1587 (maintenance / health-eval)

> **Scope of this doc.** WHAT the tenant-hardening model is and HOW its pieces
> interlock — the RBAC principal/role/permission model + Founder-gate binding, the
> SIEM audit-export contract, the secrets/egress policy, and the in-tenant runtime
> BOM wiring (gateway, deferred eject-path, guardrail chain, evals) — each traced to
> its FR and its TN invariant, plus the negative-path spec the Testing ticket
> implements. It ships **no runtime code**: the RBAC config, the export shim, the
> gateway wiring, the adapter, the guardrail chain, and the eval config are built by
> DAS-1582/1583/1584 against this design. The landed `scripts/check_in_tenant.py` +
> `config/tenant_boundary.yaml` (DAS-1543), the WS-A tool-admission edge
> (`docs/design/ws-a-tool-admission.md`), and the WS-D lens
> (`docs/design/ws-d-langfuse-lens.md`) are the reference this design **reuses** —
> cited, not modified here (this ticket touches only `docs/design/` + the ticket
> file). Everything is behind `ws_e_tenant_hardening` (config/features.yaml line 24,
> from DAS-1543) DEFAULT **OFF**.

## 0. The hardening model (one picture)

WS-E is not a new dispatch path — it is a set of **admission and boundary controls**
layered onto the existing engine, each fail-closed and each flag-gated. With
`ws_e_tenant_hardening` OFF the whole surface does not exist and dispatch behaves
exactly as today (SC-005). With it ON, four controls interlock:

```
  RBAC (TN-3, §1)                          IN-TENANT BOUNDARY (TN-1, §4)
  ── config/rbac.yaml (SSOT)                ── config/tenant_boundary.yaml (SSOT, DAS-1543)
     principals → permissions                  every code/IP endpoint in-tenant;
     Founder-identity = only gate.approve       model call = sole accepted exception
        │                                            │  check_in_tenant.py (fail-closed)
        ▼                                            ▼
  [1] gate.approve ── an ATTRIBUTED Founder-identity EVENT, never a chat string / agent output
        │                                            │
        ▼                                            ▼
  AADL gate closes                          [4a] LiteLLM gateway (FR-004) ── admission (ADR-0009/0034)
        │                                     [4b] vLLM/SGLang eject-path (FR-005) ── DEFERRED, own flag OFF
        ▼                                     [4c] Presidio+classifier+policy (FR-006) ── ADR-0012 + ADR-0033 edge
  [2] AUDIT EVENT (append-only, ADR-0024/0025)      [4d] promptfoo golden-set (FR-007) ── evals/ CI
        │  redact (ADR-0012), one-way
        ▼
  [3] SIEM EXPORT (TN-4, §2) ── read-only OTel/JSON, redacted, never a write path back
        │
        └── SECRETS in tenant vault (TN-5, §3); egress deny-all + WS-A allow-list; browser = untrusted egress
```

- **[1] RBAC / Founder-gate (TN-3 / FR-001)** — §1. Only a Founder-identity
  principal holds `gate.approve` for a never-auto-approve category (QONUN-5); an
  agent identity can never hold it; a small team holds **read-only** audit access.
  Approval is an *attributed RBAC event*, not a chat string an agent can emit.
- **[2]/[3] Audit + SIEM export (TN-4 / FR-002)** — §2. Every routing / tool / gate
  / approval / run event lands append-only in the canonical event store (ADR-0024/
  0025) + attestation (ADR-0031/0032), and exports **read-only** to the tenant SIEM
  as redacted OTel/JSON — no code/IP, never a write path back into the board.
- **Secrets / egress (TN-5 / FR-003)** — §3. Secrets in the tenant vault (never repo
  / spans); egress deny-all except the reused WS-A allow-list; browser/computer-use
  is untrusted egress.
- **[4] In-tenant runtime BOM (TN-1 / FR-004…007)** — §4. The LiteLLM gateway
  realizes the ADR-0009 admission layer; the vLLM/SGLang eject-path is a **deferred**
  flag-OFF adapter; the Presidio guardrail chain binds to ADR-0012 and enters through
  the ADR-0033 edge; promptfoo golden-set evals wire into `evals/` CI. Every code/IP
  endpoint stays in-tenant — the Claude model call is the one accepted exception.
- **Non-goals (FR-008 / Q10)** — §5. SaaS / SOC 2 / SSO-SAML-SCIM / multi-tenant /
  billing are **binding** out-of-scope; a PR that adds them is rejected.

---

## 1. RBAC — the Founder-gate model (TN-3 / FR-001 / Q6)

**Requirement (FR-001 / TN-3):** the 32-role org + the Founder gate map onto real
access control. Every never-auto-approve category (QONUN-5) maps to a **human-only,
Founder-identity** role; an agent identity can **never** hold gate-approval
authority; a small team **may** hold read-only audit access (read the trail;
approve/trigger/mutate nothing). Approval is a **Founder-identity RBAC event**, never
a chat string or an agent's own output.

### 1.1 Where the model lives — `config/rbac.yaml` (SSOT)

RBAC is a **tracked config file**, `config/rbac.yaml`, in the same posture as
`config/tenant_boundary.yaml` (§4) and `config/egress-allowlist.yaml` (§3): the set
of principals and their permissions is a **reviewed governance surface**, not runtime
state. Editing it is a `security_sensitive` + `governance_or_policy` +
`permission_change` change (never `approval: auto*`, QONUN-5). It is **not** invented
per-ticket; a single-VM tenant edits it once at stand-up (DAS-1586 runbook) and rarely
after. The near-term self-host tenant is one Founder + a small read-only team (Q6/Q8),
so the file is small.

### 1.2 The principal / permission model

Three **principal kinds**, and the permissions each may hold:

| Permission | `founder` (human) | `audit-team` (human) | `agent` (role subagent) | `orchestrator` (mechanism) |
|---|---|---|---|---|
| **`gate.approve`** — close a never-auto-approve AADL gate (QONUN-5 categories) | ✓ | ✗ | ✗ (structural, §1.3) | ✗ |
| **`run.trigger`** — start `/daslab-run` (ADR-0034 headless runner) | ✓ | ✗ | ✗ | mechanism only (executes a Founder-triggered run) |
| **`board.mutate.routing`** — write `assignee` / dispatch order / gate status | ✓ | ✗ | ✗ | ✓ (the single dispatch chokepoint, ADR-0009) |
| **`board.work`** — edit the agent's own ticket body + work-state (`todo`→`in_progress`→`in_review`) | ✓ | ✗ | own ticket only | ✗ |
| **`audit.read`** — read the event store / attestation / SIEM export | ✓ | ✓ | own run only | ✓ |
| **`config.edit.security`** — edit `rbac.yaml` / `tenant_boundary.yaml` / `egress-allowlist.yaml` / `features.yaml` | ✓ | ✗ | ✗ | ✗ |

Read the table by its two load-bearing rows: **`gate.approve` and `config.edit.security`
are Founder-identity only** — nobody else, and no agent, ever. `audit-team` is a
pure **reader** (least privilege): it can inspect every event but holds no write, no
approve, no trigger. An `agent` works its own ticket (the existing board lifecycle)
and reads its own run's audit, but never approves a gate, never triggers a run, never
touches routing, and never edits a security config. The `orchestrator` is a
**mechanism**, not a person: it executes a Founder-triggered run and owns routing
fields as the dispatch chokepoint (ADR-0009), but it cannot *originate* a
`gate.approve` or a `run.trigger` — those require a Founder-identity event upstream of
it.

### 1.3 Why an agent identity can NEVER approve (the QONUN-5 invariant)

Two structural facts, not a policy hope:

1. **The permission is absent from the `agent` kind.** In `config/rbac.yaml` no
   principal of kind `agent` — no matter which of the 32 roles — is assignable
   `gate.approve` or `run.trigger`. The RBAC evaluator (`decide(principal, permission)`,
   DAS-1582) returns `deny` for `(agent, gate.approve)` by construction; there is no
   role string, no ticket field, and no chat message that promotes an agent principal
   into that permission. This is the exact analogue of ADR-0026's route-graph rule and
   WS-A's tool-allowlist rule ("a capability the principal is not granted has no place
   in its definition — structurally unrepresentable"), applied to gate approval.
2. **QONUN-5 is enforced independently at the ticket layer.** The existing
   `scripts/check_never_auto_approve.py` already fails any never-auto-approve-category
   ticket that carries `approval: auto*`. WS-E's RBAC is the *second* lock on the same
   door: the category still requires `approval: human:founder`, **and** §1.4 requires
   that string be backed by a real Founder-identity event. Losing one lock cannot open
   the gate.

### 1.4 Approval is an attributed EVENT, not a chat string (the FR-001 crux)

The central trap FR-001 closes: an agent can *write the string* `approval:
human:founder` into a ticket, or *say* "the Founder approves" in its output. **Neither
is an approval.** Approval binds to a Founder-identity RBAC **event**, and the frontmatter
string alone is not trusted — the same discipline as the Model-Allocation law
("the frontmatter alone is not trusted; `model` is always passed explicitly").

- **What an approval IS.** A record appended to the canonical event store (ADR-0024/
  0025) of `event_type: gate_approval`, carrying `{principal_id, principal_kind:
  founder, category, ticket_id, gate, ts, attestation_ref}`. The `principal_id` is
  **stamped by the runtime** — the CLI operator identity or the ADR-0039 control-plane
  login session — **not** by any content an agent produces. The agent has no code path
  to write the Founder `principal_id`; the identity is established by the human's
  authenticated session outside the model's output channel.
- **The frontmatter string is a CLAIM, not the fact.** `approval: human:founder` on a
  ticket is a *claim of* approval. The RBAC layer (DAS-1582) treats a
  never-auto-approve gate as closed only when the claim is **backed by a matching
  `gate_approval` event** whose `principal_kind == founder` and whose `ticket_id` +
  `category` match. A claim with **no** backing Founder-identity event is a **forged
  approval** and is rejected (§6, SC-001) — the gate stays open.
- **Why this cannot be forged by an agent.** The event store is append-only and
  attributed; an agent principal writing a `gate_approval` event would have to stamp
  `principal_kind: founder` — which the RBAC evaluator refuses to any non-Founder
  principal (§1.3). The only producer of a valid Founder-identity approval event is a
  Founder-authenticated session. This mirrors ADR-0009: an approval is an **admission
  event** the runtime attributes, not a byte in a payload the agent controls.

**Trace:** `config/rbac.yaml` principal/permission model → Founder-only `gate.approve`
/ `config.edit.security`, agent structurally excluded, team read-only → approval =
attributed Founder-identity event, frontmatter string is an unverified claim — closes
**FR-001 / TN-3**.

---

## 2. Audit trail + SIEM export (TN-4 / FR-002)

**Requirement (FR-002 / TN-4):** the event store + attestation (ADR-0024/0025/0031/
0032) MUST be exportable **read-only** to the tenant's SIEM as OTel/JSON, redacted per
ADR-0012. The export carries no source code or IP and is **never a write path back
into the board**.

### 2.1 The audit record — append-only, attributed, redacted at write

Every governance-relevant action already emits an event; WS-E fixes the **audit
completeness** requirement that the RBAC events (§1) join the same canonical stream:

| Event class | Examples | Where |
|---|---|---|
| routing | dispatch, `assignee`/status change | `board/.events.jsonl` (ADR-0025 canonical) |
| tool | `tool_call` / `tool_result` (WS-A `board/.tool-audit.jsonl`) | append-only, ADR-0012-scrubbed |
| gate / approval | `gate_approval` (§1.4), gate open/close | canonical event store + attestation |
| run | wave start/end, attestation (ADR-0031/0032) | committed wave attestation |

- **Append-only.** Records are appended, never mutated or deleted; the wave
  attestation (ADR-0031/0032) hash-chains them so a tamper is detectable. This is the
  existing substrate — WS-E adds the `gate_approval` event class, not a new store.
- **Redacted at write (ADR-0012).** Every Tier-B field passes the ADR-0012 §2 scrubber
  before it is appended — **redact → truncate → append**, fail-closed. A `gate_approval`
  event is **by construction Tier-M**: principal id, category, ticket id, gate name,
  timestamp, attestation ref — controlled-vocabulary metadata, **no secret payload**.
  There is no raw-secret field in an audit record because a secret value never enters
  one (Tier-F stays in the gitignored run workspace, referenced by `run_id`).

### 2.2 The SIEM export contract — read-only OTel/JSON, one-way

The export is a **read-side adapter** in the same posture as the WS-D Langfuse lens
(`docs/design/ws-d-langfuse-lens.md` §1.3/§3) — it *reads* the canonical stream and
*writes outward* to the tenant SIEM; it never writes back:

- **Shape.** OTel/JSON — the same OTel GenAI-named span/event shape ADR-0024 already
  persists, so the export is a **field-map shim over already-correctly-named data**,
  not a schema change (WS-D §1.1). A SIEM ingesting OTLP/JSON (Splunk, Elastic, an
  OTel collector) consumes it directly.
- **Read-only + one-way (the TN-4 invariant).** Data flows exactly one direction:
  canonical event store → redaction pass → SIEM. The exporter has **no write path**
  into `board/.events.jsonl`, a ticket file, an attestation, or the SIEM-as-source: a
  SIEM outage or divergence changes **no** board/dispatch outcome (the event store
  stays system-of-record, ADR-0025 / C2). "The tenant's security team audits every
  event **without DasLab holding the data**" — the tenant runs the SIEM; DasLab only
  emits.
- **Redaction at the boundary (ADR-0012, belt-and-suspenders).** Even though audit
  records are redacted at write (§2.1), the exporter re-applies the ADR-0012 §2
  scrubber before the boundary — reusing the **same** scrubber the WS-A tool path and
  WS-D lens use (no third redactor). An unclassifiable value drops to
  `[REDACTED:unclassified]`, never exported raw; the Tier-M ids (attestation hash,
  hex trace id) survive intact (the ADR-0012 high-entropy `{32,}` tuning note). No
  source code and no IP is in the exported shape — audit records are metadata + counts.

### 2.3 Optional SIEM export shape (illustrative, not a live target)

The concrete export the tenant points at its SIEM (target resolved from
`config/tenant_boundary.yaml`, §4 — the SIEM endpoint is added there as an in-tenant
`role: audit` sink; a hosted SIEM URL fails `check_in_tenant.py` unless the tenant
explicitly runs it off-box as a Founder act, §4.2):

```json
{ "event_type": "gate_approval", "principal_kind": "founder",
  "principal_id": "founder", "category": "gate5_deployment",
  "ticket_id": "DAS-1586", "gate": "GATE-5", "ts": "2026-07-24T…Z",
  "attestation_ref": "<hash>", "trace_id": "<hex>" }
```

No `secret`, `token`, `prompt`, `completion`, `source`, or `diff` field appears — by
construction, not by filtering.

**Trace:** append-only attributed audit (ADR-0024/0025) + `gate_approval` class →
ADR-0012 redaction at write and again at the boundary → one-way read-only OTel/JSON
SIEM export, no write-back — closes **FR-002 / TN-4**.

---

## 3. Secrets + egress (TN-5 / FR-003)

**Requirement (FR-003 / TN-5):** secrets live in the tenant's vault, never in the repo
or in spans (gitleaks + ADR-0012); egress is constrained by an allow-list at the tenant
boundary; the browser/computer-use tool (ADR-0033 TB-4) is untrusted egress.

- **Secrets in the tenant vault.** Secret *values* live in the tenant's vault
  (env/secret-manager on the VM), never committed and never written into a span or an
  audit record. An event carries **fact-of-use** only — `{secret_ref, scope, ttl}`,
  Tier-M — never the value (ADR-0012 §3 `no-secrets-by-default`). gitleaks + the
  ADR-0012 §2 scrubber (which covers `sk-ant-*`, `AKIA…`, `ghp_/gho_/…`, Bearer/JWT,
  `scheme://user:pass@host` DSNs, private-key blocks, PII) are the two guards; WS-E
  adds no third secret store.
- **Egress — reuse the WS-A allow-list, do not fork.** Outbound access is **deny-all
  except an explicit domain allow-list**, and WS-E **reuses `config/egress-allowlist.yaml`
  verbatim** (the WS-A posture, `docs/design/ws-a-tool-admission.md` §3.2) — it does
  **not** create a parallel egress mechanism. A tenant-boundary firewall/allow-list is
  the outer ring; the WS-A sidecar host-check is the inner ring. Editing the allow-list
  is `security_sensitive` + `governance_or_policy` (never `approval: auto*`).
- **The browser/computer-use tool is untrusted egress (ADR-0033 TB-4).** It is admitted
  only behind the WS-A four-gate chain, gets the empty (deny-all) egress profile unless a
  specific host is reviewed onto its profile, and its fetched content is **untrusted data,
  never command** (ingress — cannot re-open a gate, re-route a ticket, or widen a grant;
  WS-A §3.1). No production credentials by default.

**Trace:** vault-resident secrets + fact-of-use-only events (ADR-0012 §3) + reused WS-A
deny-all egress allow-list + browser-as-untrusted-egress (ADR-0033 TB-4) — closes
**FR-003 / TN-5**.

---

## 4. The in-tenant runtime BOM (TN-1 / FR-004, 005, 006, 007)

**Requirement (TN-1):** every endpoint that carries code or IP MUST resolve in-tenant;
a hosted endpoint carrying code/IP is a **config error that BLOCKS the run**. **The one
accepted proprietary exception is the Claude model call** (Q9) — the sole `role: model`
entry in `config/tenant_boundary.yaml`'s `accepted_external_roles`. This is already
enforced, fail-closed, by the landed `scripts/check_in_tenant.py` (DAS-1543); WS-E's BOM
elements each declare their endpoint into that same SSOT and **reuse that one guard** —
no BOM element adds a parallel boundary check.

### 4.1 LiteLLM in-tenant gateway (FR-004) — realizing the ADR-0009 admission layer

**Requirement (FR-004):** model access MUST route through an in-tenant model gateway
(LiteLLM) that realizes the ADR-0009 admission layer (TN-1): every model call resolves
to an in-tenant endpoint, the default is the Claude subscription via account auth (Q9,
NOT a metered API key), and the auth path stays swappable. Any hosted/external endpoint
carrying code/IP is a config error that BLOCKS the run.

- **Where the gateway is a real chokepoint (the ADR-0009 honesty reconciliation).**
  ADR-0009 records that under the *Claude Code harness* runtime, DasLab does **not** own
  the LLM transport — LAW-8 is an in-orchestrator **admission** layer, not a transport
  proxy. ADR-0009 §2 names the seam where a **true** transport proxy becomes achievable:
  a **future SDK-based runner** (ADR-0034, WS-B RUNNER — `/daslab-run` on the Agent SDK,
  the Q9 subscription path). The **LiteLLM gateway is exactly that transport chokepoint,
  realized on the ADR-0034 runner**: on the self-host tenant the headless SDK runner owns
  the transport, so every model call physically traverses the in-tenant LiteLLM gateway.
  The design is therefore honest to ADR-0009: WS-E does not claim a transport proxy on the
  harness — it places the gateway on the runner that *does* own the transport.
- **In-tenant + the accepted model exception.** The LiteLLM gateway itself runs
  in-tenant (localhost/VM). It routes to the model endpoint, whose default is the Claude
  subscription over **account auth** (Q9) — the single `role: model` entry that
  `accepted_external_roles` permits to resolve to Anthropic. Every *other* endpoint the
  gateway or the runner touches (sandbox, observability, audit, memory, embeddings) stays
  in-tenant; a code/IP endpoint pointed off-box fails `check_in_tenant.py` and blocks.
- **Swappable auth path (FR-004).** Because agents call the gateway, not a provider SDK,
  the auth/model target is a **gateway config change**, not an agent rewrite:
  Claude-subscription (default) ↔ Bedrock/Vertex in-tenant-cloud ↔ the §4.2 open-weight
  vLLM/SGLang eject-path — swapped without touching a single role. This is the ADR-0009
  "the Manager governs admission and concurrency" law realized as a routing surface.

### 4.2 vLLM / SGLang open-weight eject-path (FR-005) — DEFERRED, behind its own flag OFF

**Requirement (FR-005):** an open-weight in-tenant inference eject-path (vLLM / SGLang
behind the gateway) MUST be built only as a **DEFERRED** adapter behind its **own**
feature flag DEFAULT OFF — it is **NOT** the near-term build (Q9). The near-term default
stays the Claude subscription; the adapter + its unit tests are buildable with **no live
serving stack present**, and the flag stays OFF until a Founder decision opens the
eject-path.

- **A sub-flag inside the workstream.** The eject-path is gated by its **own** build-time
  sub-flag (e.g. `ws_e_openweight_ejectpath`) nested under `ws_e_tenant_hardening`,
  DEFAULT OFF. It is a Development artifact (DAS-1583), not created at Planning — the
  parent `ws_e_tenant_hardening` OFF already makes it inert; the sub-flag is the explicit
  Founder switch to *open* the eject-path independently.
- **Buildable with no serving stack.** The adapter is a **gateway route** (a LiteLLM
  backend pointing at a would-be in-tenant vLLM/SGLang endpoint, e.g.
  `http://127.0.0.1:8000`). DAS-1583 delivers it + unit tests that assert the route
  *shape and the flag gating* against a **mock** endpoint — no live GPU/serving stack is
  required to build or test it. The tests prove: (a) with the sub-flag OFF the route is
  inert (never selected); (b) the route target, when declared, is an **in-tenant** host
  (so it *strengthens* TN-1 — an open-weight model served in-tenant means **even the
  model call** no longer leaves the tenant); (c) no agent changes to switch to it.
- **Not the near-term path.** The default stays the Claude subscription (§4.1). The
  eject-path is DasLab's answer to "what if a tenant's policy forbids *any* external model
  call, including Claude?" — a wiring decision, not a rewrite (mining brief §2.1) — held
  behind the OFF flag until a Founder opens it.

### 4.3 Presidio + classifier + policy guardrails (FR-006)

**Requirement (FR-006):** guardrails MUST be a layered chain — Presidio (PII detection)
+ a classifier + policy — wired into the ADR-0012 redaction / guardrail path and admitted
through the ADR-0033 governed MCP edge (least-privilege, PreToolUse audit), never a bulk
import.

- **A layered chain into the ADR-0012 path.** The chain is
  **Presidio (PII detection/anonymization) → a classifier (M/B/F tier) → policy (redact/
  block/allow)**, wired into the **existing ADR-0012 redaction / guardrail path** — it
  **complements, never replaces**, the ADR-0012 §2 scrubber. Presidio widens PII coverage
  (names, locations, national ids) that a regex scrubber misses; the classifier assigns
  the ADR-0012 tier; policy decides. A payload with planted PII/secret is detected and
  **redacted before storage/export** (§2).
- **Admitted through the ADR-0033 edge (reuse WS-D §5, do not fork).** Presidio enters
  DasLab **only** through the governed MCP edge — an out-of-process sidecar under `tools/`,
  a least-privilege overlay `## External tools` grant compiled into
  `board/.tool-allowlist.json`, the `mcp__.*` PreToolUse audit/deny hook, deny-all egress.
  **Presidio's own I/O is Tier-B/F and is itself scrubbed** the same way (its findings name
  the PII it found — those must not leak). No bulk `pip install`, no second admission path,
  no blanket grant. The concrete per-role grant is a `security_sensitive` +
  `permission_change` edit DAS-1584 makes, reviewed on its own — not pre-granted here.

### 4.4 promptfoo + hand-labeled golden set (FR-007)

**Requirement (FR-007):** evals MUST use a hand-labeled golden set (promptfoo) checked
**BEFORE** any LLM-judge, with an anti-gaming probe, wired into the existing `evals/` CI
path — golden-set-before-dashboard discipline (ADR-0017/0020). No golden-set pass ⇒ not
green.

- **Golden-set-before-judge.** promptfoo runs a **hand-labeled golden set** as the
  first gate in the `evals/` CI path; only if the golden set passes does any LLM-judge /
  dashboard scoring run. A false-green cannot pass because the deterministic golden set is
  the gate, not the judge (ADR-0020 no-false-green).
- **Anti-gaming probe.** The golden set includes an **anti-gaming probe** — a case
  crafted so a model that *pattern-matches the eval* rather than *doing the work* fails —
  so "teaching to the test" is caught. No golden-set pass (including the probe) ⇒ the eval
  gate is **red**.
- **Reuse the existing evals path + the ADR-0033 edge.** promptfoo wires into the
  existing `evals/` harness (diagnostics 100/100 discipline), and — as a tool — is admitted
  through the **same** ADR-0033 edge as Presidio (WS-D §5.2 lists it): tool-level grant,
  deny-all egress, local fixtures only. DAS-1584 makes the per-role grant + the golden-set
  fixtures.

**Trace:** LiteLLM gateway on the ADR-0034 runner realizes the ADR-0009 admission layer
under TN-1 (§4.1) + deferred vLLM/SGLang eject-path behind its own OFF flag, buildable
without a serving stack (§4.2) + Presidio chain into ADR-0012 via the ADR-0033 edge
(§4.3) + promptfoo golden-set-before-judge in `evals/` CI (§4.4) — every element
in-tenant, model call the sole exception — closes **FR-004 / FR-005 / FR-006 / FR-007 /
TN-1**.

---

## 5. Non-goals — internal self-host ONLY (FR-008 / Q10 / ADR-0038 boundary)

**Requirement (FR-008 / Q10):** the workstream scope is **internal self-host ONLY**. The
following are **binding** out-of-scope, and a change that introduces any of them is
**rejected** under this workstream (ADR-0038 scope boundary):

- **SaaS packaging / multi-tenant isolation / billing** — DasLab is *runnable inside* an
  enterprise, not *sellable as* a multi-tenant SaaS. No tenant-isolation layer, no metering/
  billing surface.
- **SOC 2 certification tooling** — out of scope; a separate, later, Founder-funded
  program with its own ADR.
- **SSO / SAML / SCIM** — the RBAC model (§1) is a small self-host principal file, **not**
  an identity-federation surface. No SSO/SAML/SCIM.

**The review rule (binding).** A WS-E PR that adds SOC 2 tooling, SSO/SAML/SCIM,
multi-tenant isolation, or billing is **out of scope and rejected** — that work needs its
own funded program and ADR (ADR-0038 §"Scope boundary (binding)"). This design introduces
**none** of them: §1's RBAC is a config file of local principals, not federation; §2's
export is one-way audit egress, not a billing/metering meter; there is no tenant-isolation
or SaaS surface anywhere in §1–§4. Any future "are we building a SaaS / do we need SOC 2 /
SSO?" question resolves at ADR-0038 — **no**.

**Trace:** binding non-goals restated + the reject-on-sight review rule, and the design
verified to introduce none of them — closes **FR-008 / Q10**.

---

## 6. Negative-path spec for DAS-1585 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1585, `zone: tests`, `implements: [SC-001, SC-002,
SC-003, SC-004]`) must assert. Each is written so it can be implemented directly against
the DAS-1582 RBAC evaluator (`decide(principal, permission)`) + audit/export surface, the
DAS-1583 gateway route + deferred-flag, the DAS-1584 guardrail chain + promptfoo config,
the reused ADR-0033 hook (`audit_external_tool.decide`), the ADR-0012 scrubber, and the
landed `check_in_tenant.py` + `tenant_boundary.yaml`, folded into
`tests/test_ws_e_tenant_hardening.py`.

### SC-001 — RBAC deny: non-Founder / agent approval refused (TN-3 / FR-001)

- **Agent identity cannot approve.** Assert `decide("agent:<any-of-32-roles>",
  "gate.approve")[0] == "deny"` for **every** role — there is no role string that promotes
  an agent principal into `gate.approve`. Repeat for `run.trigger` and
  `config.edit.security`.
- **Non-Founder human refused.** Assert `decide("audit-team", "gate.approve") == deny`,
  and that an `audit-team` principal holds `audit.read` **but** `gate.approve` /
  `run.trigger` / `board.mutate.routing` / `config.edit.security` all **deny** (read-only:
  it can inspect the trail, mutate nothing).
- **Only Founder approves.** Assert `decide("founder", "gate.approve") == allow` and that
  `founder` is the **only** principal with `gate.approve` and `config.edit.security`.
- **Forged approval string rejected (the FR-001 crux).** Given a never-auto-approve-category
  ticket carrying `approval: human:founder` **with no matching `gate_approval` event** whose
  `principal_kind == founder`, assert the gate evaluates **NOT closed** (forged claim
  rejected). Given the same ticket **with** a matching Founder-identity `gate_approval`
  event, assert the gate closes. Assert an `agent` principal **cannot emit** a `gate_approval`
  event stamped `principal_kind: founder` (the write is refused — §1.4).

### SC-002 — audit completeness + redaction; export read-only (TN-4 / FR-002)

- **Read-only OTel/JSON, no write-back.** Assert the SIEM export is OTel/JSON and that the
  exporter has **no** write path into `board/.events.jsonl`, a ticket file, or an
  attestation — attempting a write-back is not a reachable operation (one-way dataflow,
  §2.2). A SIEM absence/outage changes no board/dispatch outcome.
- **Redaction probe over an exported event.** Feed a synthetic audit/span event carrying
  planted secrets — an `sk-ant-…` key, an `Authorization: Bearer …` / three-segment
  `eyJ….….…` JWT, a `postgres://user:pass@host/db` DSN, a `-----BEGIN … PRIVATE KEY-----`
  block, and a PII email/name — through the ADR-0012 §2 scrubber (and the Presidio chain,
  §4.3) before export. Assert each is replaced by its `[REDACTED:…]` token and that **no**
  raw secret/PII/source substring appears in the exported payload. Assert **fail-closed**:
  an unclassifiable value drops to `[REDACTED:unclassified]`; redact→truncate ordering holds
  (a secret split by the cap cannot survive); **no over-redaction** of Tier-M ids
  (attestation hash / hex trace id survive).
- **Audit completeness.** Assert a `gate_approval` action appends **exactly one**
  append-only `gate_approval` record `{principal_id, principal_kind, category, ticket_id,
  gate, ts}` — no approval is unaudited — and that the record carries **no** secret/prompt/
  completion/source field (Tier-M by construction).

### SC-003 — in-tenant-boundary block: hosted endpoint refused (TN-1 / FR-004/005)

- **Hosted code/IP endpoint blocks.** Rewrite a code/IP endpoint in
  `config/tenant_boundary.yaml` (e.g. the gateway's non-model backend, or the §2.3 SIEM
  `role: audit` sink) to a **hosted** host (`https://…public…`) and assert
  `check_in_tenant.py` returns exit 1 with a `resolves to an EXTERNAL host` violation — the
  run is BLOCKED. Assert the **model** call (`role: model` → Anthropic) is the **only**
  accepted external exception (in `accepted_external_roles`) and does **not** trip the guard.
- **Gateway otherwise routes in-tenant.** With all code/IP endpoints in-tenant,
  `check_in_tenant.py` returns exit 0 and the gateway resolves the in-tenant/model target
  (§4.1).
- **Eject-path inert behind its deferred flag OFF.** Assert that with
  `ws_e_openweight_ejectpath` OFF (default) the vLLM/SGLang route is **never selected**
  (inert); and that its declared route target, when present, is an **in-tenant** host (§4.2)
  — the adapter is buildable/testable with **no live serving stack** (mock endpoint).

### SC-004 — guardrail trip + eval-gate skip (FR-006 / FR-007)

- **Guardrail trip.** Feed a payload with planted PII **and** a secret through the
  Presidio+classifier+policy chain (§4.3); assert both are **detected and redacted** before
  storage/export, and that Presidio's **own I/O** is itself scrubbed (its findings do not
  leak). Assert the chain is admitted through the ADR-0033 edge — a Presidio call by a role
  that did **not** declare it in its overlay is **denied** by the same `decide()` that denies
  any undeclared tool (structural unreachability, WS-A §1.3), with no WS-E exemption.
- **Eval-gate skip ⇒ not green.** Assert the promptfoo **golden set runs BEFORE** any
  LLM-judge, and that **no golden-set pass ⇒ the eval gate is RED** (a run that skips /
  fails the golden set cannot report green). Assert the **anti-gaming probe** fails a model
  that pattern-matches the eval rather than doing the work (ADR-0020 no-false-green).

### SC-005 guard (flag OFF byte-identical — noted for DAS-1585 completeness)

With `ws_e_tenant_hardening` **OFF** (default), a wave's dispatch behaviour is
byte-identical to pre-merge — the hardening surface does not exist (SC-005). Assert
`config/features.yaml` carries `ws_e_tenant_hardening: false`, and that flag-OFF produces a
byte-identical `board/.events.jsonl` + dispatch outcome vs. the surface absent. This is not
a §1–§4 admission behaviour, so it is noted here (like WS-A §4 / WS-D §6), and DAS-1585
already lists it under SC-005.

**Hand-off:** SC-001 → §1; SC-002 → §2; SC-003 → §4.1/§4.2 + §4 (`check_in_tenant.py`);
SC-004 → §4.3/§4.4 + the reused ADR-0033 edge. All assertions are expressible against the
DAS-1582/1583/1584 surfaces, the reused ADR-0033 hook (`decide`), the ADR-0012 scrubber,
and the landed `check_in_tenant.py` + `tenant_boundary.yaml`.

---

## 7. Traceability matrix

| SPEC FR / SC | ADR-0038 TN | This design | DAS-1585 SC | Builds in |
|---|---|---|---|---|
| FR-001 — RBAC Founder-only gate approval; agent never; team read-only; approval = attributed event | TN-3 | §1 (`config/rbac.yaml`, permission matrix, structural agent-exclusion, event-not-string) | SC-001 | DAS-1582 |
| FR-002 — event store + attestation → read-only redacted OTel/JSON SIEM export; no write-back | TN-4 | §2 (append-only attributed audit + `gate_approval` class, one-way export, ADR-0012 redaction) | SC-002 | DAS-1582 |
| FR-003 — secrets in vault; deny-all egress allow-list; browser untrusted | TN-5 | §3 (vault + fact-of-use events, reused WS-A `egress-allowlist.yaml`, ADR-0033 TB-4) | (SC-002 redaction) | DAS-1582 |
| FR-004 — in-tenant LiteLLM gateway realizing the ADR-0009 admission layer; model = accepted exception; swappable auth | TN-1 | §4.1 (gateway on the ADR-0034 runner = the transport chokepoint; `check_in_tenant.py`) | SC-003 | DAS-1583 |
| FR-005 — deferred vLLM/SGLang eject-path behind its own flag OFF; buildable without a serving stack | TN-1 | §4.2 (`ws_e_openweight_ejectpath` sub-flag, mock-endpoint route, in-tenant strengthens TN-1) | SC-003 | DAS-1583 |
| FR-006 — Presidio+classifier+policy chain into ADR-0012, via the ADR-0033 edge; no bulk import | TN-5 | §4.3 (layered chain, complements the §2 scrubber, governed-tool admission) | SC-004 | DAS-1584 |
| FR-007 — promptfoo golden-set-before-judge + anti-gaming probe in `evals/` CI | — | §4.4 (golden-set gate, anti-gaming, reuse evals + ADR-0033 edge) | SC-004 | DAS-1584 |
| FR-008 — internal self-host ONLY; no SaaS/SOC2/SSO/multi-tenant/billing; reject-on-sight | scope boundary | §5 (binding non-goals + review rule; design introduces none) | — | (review rule) |
| SC-005 — flag OFF byte-identical | all (flag) | §0 + §6 SC-005 (`ws_e_tenant_hardening` OFF) | SC-005 | all |

## 8. Open items handed downstream (not decided here)

- **DAS-1582** builds `config/rbac.yaml` (§1) + the RBAC evaluator `decide(principal,
  permission)` + the `gate_approval` event class and the Founder-identity binding (§1.4) +
  the read-only OTel/JSON SIEM export shim (§2) reusing the ADR-0012 scrubber, behind
  `ws_e_tenant_hardening` OFF. It declares the SIEM sink as an in-tenant `role: audit`
  endpoint in `config/tenant_boundary.yaml`.
- **DAS-1583** builds the in-tenant LiteLLM gateway route realizing the ADR-0009 admission
  layer on the ADR-0034 runner (§4.1) + the **deferred** vLLM/SGLang eject-path adapter
  behind `ws_e_openweight_ejectpath` OFF (§4.2), buildable + unit-tested with **no live
  serving stack** (mock endpoint).
- **DAS-1584** builds the Presidio+classifier+policy guardrail chain into the ADR-0012 path
  (§4.3) + the promptfoo golden-set (with anti-gaming probe) into `evals/` CI (§4.4), and
  makes the per-role `## External tools` overlay grants for Presidio/promptfoo — each a
  `security_sensitive` + `permission_change` edit reviewed on its own, compiled by
  `gen_subagents.py` through the ADR-0033 edge.
- **DAS-1585** implements §6 as `tests/test_ws_e_tenant_hardening.py`.
- **DAS-1586** is a **deploy runbook** (flag OFF): it documents the tenant-VM stand-up
  (RBAC principals seeded in `config/rbac.yaml`, vault, SIEM sink, gateway) — but the actual
  VM stand-up is a **Founder act** (a real in-tenant deploy needs a VM). Per the prior
  workstreams' pattern, the runbook + the flag-OFF ship **closes GATE-5 on local-green**; the
  flag flip on a live VM is a separate Founder decision (Q2), not this workstream's.
- **Security Lead (consulted)** reviews §1 RBAC + §2 redaction coverage + §3 secrets/egress
  posture against ADR-0012/QONUN-5; **COO (consulted)** reviews the §8 GATE-6 maintenance
  surface (DAS-1587); **CTO (accountable)** ratifies GATE-2 closure.
- The concrete RBAC principal list, the SIEM product, and whether the open-weight eject-path
  is ever opened are **tenant/Founder** decisions made at stand-up (DAS-1586) / by Founder
  switch — not pre-decided here (least privilege, Q6/Q9).
