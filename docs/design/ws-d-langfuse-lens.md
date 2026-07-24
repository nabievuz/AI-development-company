# WS-D LENS design — OTLP exporter to self-host Langfuse, redaction-on-export, and governed-tool admission for the eval/guardrail shortlist

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted)
- **Date:** 2026-07-24
- **Ticket:** DAS-1572 (WS-D Design); epic DAS-1570 (MUSTAQIL WS-D LENS)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — redaction on export, egress boundary, governed-tool admission)
- **Binds to:** ADR-0036 (OB-1…OB-4, **Accepted** 2026-07-24 — self-host Langfuse via OTLP, **NOT** LangSmith/Langfuse-cloud), `docs/specs/005-mustaqil-ws-d-lens/SPEC.md` (FR-001…FR-006, SC-001…SC-005, reviewed), ADR-0024 (the `gen_ai.*`-named span-event schema this exporter maps), ADR-0012 (M/B/F content-classification + redaction), ADR-0033 (the governed MCP edge — TB-1…TB-5; the eval/guardrail tools reuse it), ADR-0038 TN-1 (in-tenant only), ADR-0019 (feature flags), ADR-0025 (event store canonical / C2), the master prompt row D (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`)
- **Downstream:** DAS-1573 (OTLP exporter + redaction shim under `tools/`), DAS-1574 (tool-admission overlay wiring for promptfoo/AgentShield/Presidio), DAS-1575 (negative tests — this doc hands it §6), DAS-1576 (deploy / flag flip), DAS-1577 (maintenance)

> **Scope of this doc.** WHAT the observability lens + governed-tool-admission
> model is and HOW its pieces interlock — the ADR-0024 → OTLP field mapping, the
> redaction-on-export pass, the self-host-only target check, and the reuse of the
> ADR-0033 edge for the eval/guardrail shortlist, plus the negative-path spec the
> Testing ticket implements. It ships **no runtime code**: the exporter shim, the
> overlay grants, and the config wiring are built by DAS-1573/1574 against this
> design. The on-branch spikes under `tools/` (the WS-A tool bridge) and the
> already-landed `scripts/check_in_tenant.py` + `config/tenant_boundary.yaml` are
> the reference this design reuses — cited, not modified here (this ticket touches
> only `docs/design/` + the ticket file).

## 0. The export path (one picture)

The WS-D exporter is a **non-invasive read-side adapter**. Dispatch already emits
ADR-0024 span records into the canonical event store; the exporter reads those
records, redacts them, and ships an OTLP copy to a self-host Langfuse. Nothing on
the write/dispatch path changes — with the flag OFF the adapter does not run at
all, and with it ON the adapter only *reads*.

```
DISPATCH (unchanged)                         EVENT STORE (canonical, ADR-0025 / C2)
  build_span(...) ─ ADR-0024 ──▶ EventStore.append ──▶ board/.events.jsonl
                                                            │  (system-of-record — never
                                                            │   the exporter's output)
                                                            ▼  read-only, flag-gated
                                          [1] ADR-0012 M/B/F classify + scrub  (FR-002)
                                                            │  fail-closed, in-process
                                                            ▼
                                          [2] gen_ai.* → OTLP field-map shim    (FR-001)
                                                            │
                                                            ▼
                                          [3] in-tenant target check (TN-1)     (SC-004)
                                                            │  hosted URL ⇒ blocked
                                                            ▼
                                          OTLPSpanExporter ──▶ self-host Langfuse
                                                                /api/public/otel
                                                                (127.0.0.1:3000, in-tenant)
```

- **[1] redaction (FR-002 / OB-3)** — §2. Every span/attribute passes the ADR-0012
  classifier + scrubber **before** it leaves the process; fail-closed.
- **[2] field-map shim (FR-001 / OB-2)** — §1. The persisted names *are* the OTel
  GenAI attribute names (ADR-0024), so this is a mapping shim, not a schema change.
- **[3] in-tenant check (SC-004 / TN-1)** — §4. The target must resolve in-tenant;
  a hosted Langfuse/LangSmith URL is a config error that blocks.
- The **event store stays canonical** (§3, C2): the exporter is a derived view; a
  Langfuse outage or divergence changes no board/dispatch outcome.

Separately, the **eval/guardrail tools** the lens draws on (promptfoo, AgentShield,
Presidio) enter DasLab only through the existing ADR-0033 governed MCP edge (§5) —
never a second admission path.

---

## 1. OTLP exporter — the `gen_ai.*` → Langfuse field-map shim (OB-2 / FR-001)

**Requirement (FR-001 / OB-2):** DasLab MUST export the ADR-0024 OTel-shaped spans
via an OTLP exporter to a **self-hosted** Langfuse instance (in-tenant, TN-1); it
MUST NOT default to, or silently fall back to, any hosted/external observability
endpoint (LangSmith or Langfuse-cloud).

### 1.1 Why this is a shim, not a migration

ADR-0024 already persists the OpenTelemetry GenAI **semantic-convention attribute
names** (`gen_ai.agent.name`, `gen_ai.usage.input_tokens`, …) as the span's JSON
field names — the whole point of that ADR ("Why the vendor-neutral names now").
Langfuse ingests OTLP on its own `/api/public/otel` trace endpoint. So the exporter
is a **field-mapping shim over already-correctly-named data**: read the span record,
map its fields onto an OTLP `Span` proto, POST via `OTLPSpanExporter`. No field is
renamed on disk; the ADR-0024 §2 mapping table is the single authoritative
change-point, and this exporter is its first consumer.

### 1.2 The field-map (ADR-0024 span record → OTLP)

The shim mirrors the ADR-0024 §2 table; only the transforms below are non-identity:

| ADR-0024 span field | OTLP target | Transform |
|---|---|---|
| `trace_id` (= ticket id, human-readable) | OTLP `trace_id` (16-byte hex) | **derive** — a pure function (hash) of the ticket id at export time; ADR-0024 already reserves this. |
| `span_id` | OTLP `span_id` (8-byte) | derive/encode the opaque id to the OTLP width. |
| `parent_span_id` (`null` ⇒ root) | OTLP `parent_span_id` | identity; empty ⇒ root. |
| `kind` (`invoke_agent`/`chat`/`execute_tool`/`wave`/`run`) | attribute `gen_ai.operation.name` | identity (the ADR-0024 operation-name axis). |
| `gen_ai.agent.name`, `gen_ai.request.model` | span attributes, same keys | **identity** — verbatim OTel attribute names. |
| `gen_ai.usage.input_tokens` / `output_tokens` / `cached_input_tokens` | span attributes, same keys | identity. |
| `start` / `end` (ISO-8601 `Z`) | OTLP start/end (unix-nanos) | convert ISO-8601 → unix-nanos. |
| `status` (`ok`/`error`) | OTLP span status (`OK`/`ERROR`) | enum map. |
| `duration_ms`, `cached` (`daslab.*`) | `daslab.span.duration_ms`, `daslab.usage.cached` | identity, kept in the `daslab.*` namespace. |
| `run_id` | trace resource / link attribute | identity, promoted to a resource attribute at export. |

DasLab-specific fields with no GenAI attribute stay namespaced `daslab.*` (ADR-0024)
— the shim never squats an un-owned `gen_ai.*` name. **If OTel renames an
attribute, only ADR-0024 §2 and this shim's map change** — nothing on disk.

### 1.3 Non-invasive: read-side only, no dispatch change

The exporter reads the already-emitted span stream (`board/.events.jsonl`,
`event_type: "span"`) — it is **not** wired into `EventStore.append` and never
mutates a span. Emitting a span is unchanged (ADR-0024 §5 — additive, observational,
shadow-mode); the exporter is a **second, downstream reader** of that stream, in the
same posture as any replay/scorer. There is **no new write path** and no change to
`build_span`/`validate_span`. This is the structural guarantee behind SC-001 (§6.1):
flag OFF ⇒ the reader never runs ⇒ dispatch/event behaviour is byte-identical.

### 1.4 Self-host endpoint shape + no hosted fallback

- The OTLP target is read from `config/tenant_boundary.yaml`'s
  `langfuse_observability` endpoint (already declared: `http://127.0.0.1:3000`,
  `role: observability`, `carries_code_ip: true`) — **not** from an ad-hoc env
  default. There is no built-in hosted default and no fallback branch: an absent /
  unreachable target means the lens is simply down (a view outage, OB-2), never a
  silent redirect to a cloud endpoint.
- The endpoint value flows through the §4 in-tenant check before the first export;
  a hosted URL fails that check and blocks (SC-004). "Point it at Langfuse-cloud or
  LangSmith" is therefore not a reachable configuration.

**Trace:** ADR-0024 span stream → §1.2 field-map shim → `OTLPSpanExporter` → in-tenant
Langfuse `/api/public/otel`, no hosted fallback — closes **FR-001 / OB-2**.

---

## 2. Redaction-on-export — ADR-0012 M/B/F, fail-closed, before the boundary (OB-3 / FR-002)

**Requirement (FR-002 / OB-3):** the exporter MUST apply ADR-0012
content-classification + redaction to **every** span/attribute before it leaves the
process; no secret or unredacted tool transcript may cross the export boundary.

### 2.1 Every exported attribute is classified first

A span attribute is exported only after it is classified M/B/F (ADR-0012 §1) and,
if Tier-B, passed through the §2 scrubber. The classification of the ADR-0024 span
fields:

| Span attribute | ADR-0012 tier | Export rule |
|---|---|---|
| `trace_id`, `span_id`, `parent_span_id`, `kind`, `gen_ai.agent.name`, `gen_ai.request.model`, `status`, `run_id`, `start`, `end`, `duration_ms`, `cached`, the `gen_ai.usage.*` counts | **M — metadata** | Controlled-vocabulary / ids / enums / numerics / ISO timestamps. Exported as-is. |
| any free-text attribute an emitter attached to a span (e.g. an error message, a summary) | **B — bounded free text** | **§2-scrubbed + length-capped** before export — redact, then truncate, then emit; fail-closed. |
| raw stdout/stderr, a full fetched page, a verbatim tool transcript, a prompt/completion body, any secret value | **F — forbidden** | **Never exported.** By ADR-0024/0012 these never enter the span in the first place; the export shim additionally drops any Tier-F-shaped value to `[REDACTED:unclassified]` rather than shipping it. |

The dominant case is Tier-M: an ADR-0024 span is *by construction* metadata + token
counts, which is exactly why the lens is safe to ship. The redaction pass is the
**belt-and-suspenders boundary guard** for any Tier-B attribute and a fail-closed
backstop against a Tier-F value that a future emitter might attach.

### 2.2 Fail-closed ordering, reuse the ADR-0012 scrubber

- The exporter reuses the **same** ADR-0012 §2 scrubber the WS-A tool-event path
  uses (the P3 transcript scrubber) — it does not fork a second redactor. Coverage
  is ADR-0012 §2: API keys/tokens (`sk-ant-*`, `AKIA…`, `ghp_/gho_/ghu_/ghs_/ghr_…`,
  high-entropy fallback), Bearer/JWT, connection strings (`scheme://user:pass@host`),
  private-key blocks, PII.
- **Order is redact → truncate → emit** (ADR-0012 §2), so a secret split by the
  length cap cannot survive. An unclassifiable value is dropped to
  `[REDACTED:unclassified]`, never emitted raw (deny-by-default, ADR-0012 §1.4).
- The pass runs **in-process, before the OTLP POST** — no raw attribute is ever
  handed to the transport. If the scrubber raises, the span is dropped from the
  export (a missing view row), never shipped unredacted — losing a view row is
  always preferable to leaking one.
- Must not **over-redact** legitimate Tier-M values — the ADR-0024 opaque `span_id`
  / derived hex `trace_id` are high-entropy ids that must survive (the ADR-0012
  high-entropy `{32,}` tuning note applies).

**Trace:** span attribute → ADR-0012 M/B/F classify → Tier-B §2 scrub (fail-closed,
redact-then-truncate) → OTLP export; Tier-F never crosses — closes **FR-002 / OB-3**.

---

## 3. The event store stays the system-of-record; the lens is derived (OB-2 / FR-003 / C2)

**Requirement (FR-003 / OB-2 / C2):** `board/.events.jsonl` + the committed wave
attestations (ADR-0025/0031/0032) remain the canonical audit record; the self-host
Langfuse lens is a derived view only — disabling or losing it MUST change no
board/dispatch outcome.

- **The exporter can never become a second source of truth.** It only *reads* the
  canonical stream and *writes* to Langfuse; it never writes back to
  `board/.events.jsonl`, a ticket file, or an attestation (§1.3 — no new write
  path). Data flows one way, canonical → lens.
- **"What actually happened" is answered by the event store**, never by Langfuse.
  If Langfuse is down, unreachable, or diverges from the stream, the stream wins and
  Langfuse is re-derived from it — identical to the ADR-0024 §4 / ADR-0011 §1
  canonical/derived rule for `graph_state`. A divergence is a lens bug, not a truth
  question.
- **No dispatch reads the lens.** Nothing in `/daslab-cycle` triage, gate order, or
  attestation consults Langfuse; the lens is a human viewing/eval surface. This is
  what makes SC-001 hold (flag OFF or lens absent ⇒ no behaviour change).

**Trace:** one-way canonical→lens dataflow + no dispatch dependency on the lens —
closes **FR-003 / OB-2 / C2**.

---

## 4. In-tenant target check — hosted endpoint fails closed (SC-004 / TN-1 / FR-001)

**Requirement (SC-004 / TN-1):** a check MUST prove the exporter target resolves to
an in-tenant/self-host endpoint only; a config pointing at a hosted Langfuse/LangSmith
URL fails closed (ADR-0038 TN-1).

### 4.1 Reuse the landed `check_in_tenant.py` — no second boundary check

The TN-1 guard already exists (`scripts/check_in_tenant.py`, DAS-1543) and already
declares the exporter's endpoint: `config/tenant_boundary.yaml` carries a
`langfuse_observability` endpoint (`role: observability`, `carries_code_ip: true`,
`url: http://127.0.0.1:3000`). WS-D **reuses that guard verbatim** — it adds no
parallel boundary check:

- `is_in_tenant()` treats loopback / RFC-1918 / ULA / `.local`/`.internal`/bare
  hostname / unix-socket-or-file as in-tenant, and any public hostname or public IP
  as EXTERNAL.
- `observability` is **not** in `accepted_external_roles` (only `model` is — the
  Q9 Claude exception), so a `langfuse_observability.url` pointing at a hosted host
  (`cloud.langfuse.com`, `api.smith.langchain.com`, any public IP) makes
  `check_in_tenant.py` return exit 1 and **blocks the run** — before any export.
- The exporter additionally resolves its OTLP target *from this same endpoint entry*
  (§1.4), so the checked value and the exported-to value are the **same value** —
  the check cannot be bypassed by the exporter reading a different config.

### 4.2 Publishing off-box is a Founder act (FR-006 / OB-4)

Widening the endpoint beyond the tenant, or pointing the exporter at a hosted
project, is an explicit **Founder** decision (OB-4, QONUN-5) — editing
`tenant_boundary.yaml`'s `accepted_external_roles` or the endpoint URL is a
`security_sensitive` + `governance_or_policy` change (never `approval: auto*`) and
is logged to `board/.events.jsonl`. No workstream ticket may self-trigger it.

**Trace:** exporter target = the `tenant_boundary.yaml` `langfuse_observability`
endpoint → `check_in_tenant.py` (observability not accepted-external) → hosted URL
fails closed; off-box widening is a Founder act — closes **SC-004 / TN-1 / FR-006**.

---

## 5. Governed-tool admission for the eval/guardrail shortlist (OB-3 / FR-005)

**Requirement (FR-005 / OB-3):** promptfoo, AgentShield, and Presidio MUST enter
DasLab **only** through the existing ADR-0033 governed MCP edge — out-of-process
sidecar, least-privilege overlay allow-list, `PreToolUse` audit/deny, ADR-0012
redaction — never as a bulk import, never a second admission path, never a blanket
grant.

### 5.1 Reuse the ADR-0033 / WS-A edge verbatim — no WS-D-specific mechanism

Each of the three tools is admitted **identically to any other external MCP tool**,
through the four-gate chain the WS-A design (`docs/design/ws-a-tool-admission.md`)
specifies and DAS-1547 builds — WS-D adds nothing to that chain:

```
overlay ## External tools ─ gen_subagents.py compile ─▶ board/.tool-allowlist.json
   [1] TB-2 allow-list ─▶ [2] TB-3 PreToolUse audit/deny ─▶ [3] TB-4 egress ─▶ [4] ADR-0012 redaction
```

- **TB-1 — out-of-process sidecar.** Each tool is exposed by a small MCP sidecar
  under `tools/` (FastMCP, the `ArcRift` shape), wired in `.mcp.json`. The engine
  stays server-free; the sidecar's absence means the tool simply does not exist.
- **TB-2 — least-privilege allow-list.** A role reaches one of these tools only if
  its `<dept>/agents/<role>/AGENTS.md` overlay `## External tools` block declares it;
  `gen_subagents.py` compiles the declarations into `board/.tool-allowlist.json`, the
  only thing the hook trusts. A non-declared tool has no key and is structurally
  unreachable (WS-A §1.3).
- **TB-3 — PreToolUse audit/deny.** Every call passes the `mcp__.*` PreToolUse hook
  (`audit_external_tool.py`); deny-all is the fail-closed default, and every decision
  (allow *and* deny) appends one record to `board/.tool-audit.jsonl`.
- **ADR-0012 redaction.** Each tool's transcript is classified + scrubbed exactly
  like any tool event (WS-A §2.3) — Presidio especially, whose whole job is PII, must
  have its own I/O scrubbed the same way (its findings are Tier-B/​F).
- **Egress (TB-4).** These three tools are **in-process eval/guardrail** utilities,
  not browsers; each gets the empty (deny-all) egress profile unless a specific need
  is reviewed. No production credentials by default.

### 5.2 Illustrative starting allow-list (least privilege — NOT a live grant)

Which role plausibly needs which tool, as a *starting point for review* — each is a
per-role `security_sensitive` + `permission_change` edit made **only when the role
demonstrably needs the tool**, never pre-granted here:

| Tool | Purpose | Plausible role overlay | Least-privilege note |
|---|---|---|---|
| **promptfoo** | prompt/eval regression harness | `qa-eng` (also QA Lead) | tool-level grant; deny-all egress; local fixtures only. |
| **AgentShield** | agent-guardrail / red-team checks | `security-lead` | tool-level grant; deny-all egress; consulted role for the WS-D boundary. |
| **Presidio** | PII detection/anonymization | the redaction/PII layer (`security-lead`, or a dedicated redaction role) | its own I/O is Tier-B/F and scrubbed; complements — never replaces — the ADR-0012 §2 scrubber. |

The table is **illustrative**, not applied: this ticket writes no overlay `##
External tools` block and mints no grant. DAS-1574 makes the concrete per-role edits
against this design, each reviewed on its own.

### 5.3 No second admission path (the FR-005 invariant)

There is exactly **one** way any of the three tools becomes callable: an overlay
declaration compiled into `board/.tool-allowlist.json`, gated by the PreToolUse hook.
WS-D introduces no side channel, no bulk `pip install` toolkit import, no global
grant. A promptfoo/AgentShield/Presidio call by a role that did **not** declare it is
denied by the *same* `decide()` that denies any undeclared tool — this is what SC-003
(§6.3) tests, with **no WS-D-specific bypass** to exempt.

**Trace:** promptfoo/AgentShield/Presidio → ADR-0033 sidecar → TB-2 overlay allow-list
→ TB-3 PreToolUse audit/deny → ADR-0012 redaction; one admission path only — closes
**FR-005 / OB-3**.

---

## 6. Negative-path spec for DAS-1575 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1575, `zone: tests`, `implements: [SC-001,
SC-002, SC-003, SC-004]`) must assert. Each is written so it can be implemented
directly against the WS-D exporter surface (DAS-1573), the reused ADR-0033 hook
surface (`audit_external_tool.decide`), the ADR-0012 scrubber, and the landed
`check_in_tenant.py`, and folded into `tests/test_ws_d_langfuse_lens.py`.

### SC-001 — flag OFF is byte-identical (FR-004)

- Assert `config/features.yaml` `DEFAULTS` carries `ws_d_langfuse_lens: false`.
- With the flag OFF, run a wave (or a dispatch/event fixture) and assert the
  produced `board/.events.jsonl` and dispatch outcome are **byte-identical** to a
  run with the exporter code absent — the read-side adapter never runs (§1.3), so
  there is no span mutation, no new event, no OTLP call.
- Assert flipping the flag ON begins export **without** altering any board/dispatch
  outcome (the exporter only reads; §3).

### SC-002 — redaction-on-export probe (FR-002 / ADR-0012)

- Feed a synthetic span carrying a free-text attribute with planted secrets — an
  `sk-ant-…` key, an `Authorization: Bearer …` / three-segment `eyJ….….…` JWT, a
  `postgres://user:pass@host/db` DSN, a `-----BEGIN … PRIVATE KEY-----` block, and a
  PII email — through the ADR-0012 §2 scrubber **before** the OTLP field-map. Assert
  each is replaced by its `[REDACTED:…]` token and that **no** raw secret substring
  appears in the OTLP payload handed to `OTLPSpanExporter`.
- Assert **fail-closed**: an unclassifiable value is dropped to
  `[REDACTED:unclassified]`, never exported raw; redact-then-truncate ordering holds
  (a secret split by the length cap cannot survive); if the scrubber raises, the span
  is **dropped from export**, never shipped.
- Assert **no over-redaction** of the Tier-M ids — the ADR-0024 opaque `span_id` and
  derived hex `trace_id` survive the pass intact (the ADR-0012 high-entropy `{32,}`
  tuning note).

### SC-003 — tool-admission negative test (FR-005 / ADR-0033)

- **Non-allow-listed tool refused.** With a compiled `board/.tool-allowlist.json`
  that grants promptfoo to role **A only**, assert
  `decide("mcp__promptfoo__…", "B", allowlist)[0] == "deny"` while `… "A" …[0] ==
  "allow"`; and that a tool present in `.mcp.json` but declared by **no** overlay
  compiles to **no key** and denies for **every** role (structural unreachability).
  Repeat for AgentShield and Presidio — all three are governed by the *same*
  `decide()`, with no WS-D exemption.
- **Audit-skip denied.** Assert `.claude/settings.json` carries the `PreToolUse`
  `mcp__.*` → `audit_external_tool.py` binding (removing it is a detectable
  regression), and that a malformed/empty event or an unreadable allow-list
  fail-closes to `deny`. Assert every decision (allow and deny) appends exactly one
  record to `board/.tool-audit.jsonl` — no admitted call to any of the three is
  unaudited.

### SC-004 — in-tenant-only target; hosted endpoint blocked (TN-1 / FR-001)

- **In-tenant passes.** With `config/tenant_boundary.yaml`'s `langfuse_observability`
  endpoint at `http://127.0.0.1:3000` (or a `.local`/RFC-1918 tenant host),
  `check_in_tenant.py` returns exit 0 and the exporter resolves that target.
- **Hosted fails closed.** Rewrite the `langfuse_observability.url` to a hosted host
  (`https://cloud.langfuse.com/…` or `https://api.smith.langchain.com/…`) and assert
  `check_in_tenant.py` returns exit 1 with an `observability … resolves to an
  EXTERNAL host` violation — `observability` is not in `accepted_external_roles`
  (only `model` is), so the hosted endpoint blocks the run before any export.
- Assert the exporter's target and the checked endpoint are the **same value** (§1.4)
  — there is no separate exporter config that could dodge the check.

**Hand-off:** SC-001 → §1.3/§3; SC-002 → §2; SC-003 → §5; SC-004 → §4. All
assertions are expressible against the DAS-1573 exporter surface, the reused
ADR-0033 hook (`decide`), the ADR-0012 scrubber, and the landed
`check_in_tenant.py` + `tenant_boundary.yaml`.

---

## 7. Traceability matrix

| SPEC FR / SC | ADR-0036 OB | This design | DAS-1575 SC |
|---|---|---|---|
| FR-001 — export OTLP spans to self-host Langfuse; no hosted fallback | OB-2 | §1 (field-map shim, self-host endpoint, no fallback) + §4 (in-tenant check) | SC-004 |
| FR-002 — ADR-0012 redaction before the export boundary | OB-3 | §2 (M/B/F classify, fail-closed scrub, redact-then-truncate) | SC-002 |
| FR-003 — event store canonical; lens derived; disabling it changes nothing | OB-2 / C2 | §3 (one-way dataflow, no dispatch dependency) | SC-001 |
| FR-004 — feature-flagged default OFF; flag OFF byte-identical | OB-4 | §1.3 (read-side only, `ws_d_langfuse_lens` OFF) | SC-001 |
| FR-005 — eval/guardrail tools via the ADR-0033 edge only | OB-3 | §5 (reuse TB-1…TB-4 + ADR-0012; one admission path) | SC-003 |
| FR-006 — publishing off-box is a Founder act | OB-4 | §4.2 (Founder-gated `tenant_boundary.yaml` edit) | covered structurally |

## 8. Open items handed downstream (not decided here)

- **DAS-1573** builds the OTLP exporter shim under `tools/` (the §1.2 field-map, the
  §2 redaction pass reusing the ADR-0012 scrubber, resolving the target from
  `tenant_boundary.yaml` per §1.4), behind `ws_d_langfuse_lens` OFF. It runs the §4
  in-tenant check before the first export.
- **DAS-1574** makes the concrete per-role overlay `## External tools` grants for
  promptfoo/AgentShield/Presidio (§5.2) — each a per-role `security_sensitive` +
  `permission_change` edit, reviewed on its own, and compiled by `gen_subagents.py`.
  It creates the three MCP sidecars under `tools/` and their `.mcp.json` entries.
- **DAS-1575** implements §6 as `tests/test_ws_d_langfuse_lens.py`.
- **Security Lead (consulted)** reviews §2 redaction coverage (especially Presidio's
  own I/O, §5.1) and §4/§5 boundary posture against ADR-0012; **CTO (accountable)**
  ratifies GATE-2 closure.
- Whether the self-host Langfuse VM is provisioned (Founder answer Q2) and the flag
  is flipped is a deploy decision (DAS-1576), not this design's.
