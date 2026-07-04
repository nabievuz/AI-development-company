# ADR 0012 — DGO-X event store: content-classification + redaction policy (the P2/P3 tool-event security contract)

- **Status:** Accepted (**Security Lead decision/signed** — security discipline is Security-Lead-owned org-wide, engineering charter §Authority; **CTO reviewed + ratified — 2026-06-22** per `board/ROUTING.md`, security-lead → CTO).
- **Date:** 2026-06-22
- **Scope:** Platform / security — the **content** that may enter the DGO-X append-only event store (`board/.events.jsonl`), across Phase 1 (metadata only) and the Phase 2/3 events that first carry agent/tool free-content. **Policy + design only**; the redaction code lands in the P2/P3 implementation tickets.
- **Deciders:** **Security Lead (accountable/signed)**; CTO (reviewer — security RACI); Backend EM (consulted — authors the event-store contract this constrains, ADR 0011).
- **Relates:** the DGO-X adoption ADR [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) (binding constraints C1–C6); the Phase-1 data contracts ADR [0011](0011-dgox-phase-1-data-contracts.md) (the `routing_decision` / `agent_invocation` event shapes, the `secrets_policy` / `context_contract` fields, and the gitignore rule this pins); the non-blocking memory loop [0008](0008-nonblocking-arcrift-memory-loop.md) (the gitignored-outbox pattern the event store reuses).
- **Supersedes:** nothing — first event-store security policy of the DGO-X set; it *constrains* ADR 0011's contract, it does not change it.

> This ADR is a **binding security prerequisite**: it gates the implementation of any
> tool-transcript / agent-body event in DGO-X Phase 2 (P2) and Phase 3 (P3). It is **not** a
> Phase-1 dev item — Phase 1 events are metadata-only and carry no free content (see §1), so
> Phase 1 has no exposure to redact. Every P2/P3 ticket that adds an event field able to hold
> free-form agent input/output, or a tool transcript, **MUST cite this ADR and satisfy §1–§4**
> before it merges. A PR that writes raw tool output or an un-scrubbed transcript into
> `board/.events.jsonl` is rejected on principle.

## Context

ADR 0011 makes every state transition an **append-only event** in `board/.events.jsonl`. In
**Phase 1** the only emitted shape with operator-supplied strings is `routing_decision` (ADR
0011 Shape A): its fields are **supervisor-authored metadata** (`assignee`, `model`, `reason`,
`confidence`, `policy_checks`, `fallback`) — there is no path for raw tool output or a captured
transcript to reach the store. So Phase 1 is, by construction, **metadata-only and exposure-free**.

The exposure begins later. ADR 0011 Shape B (`agent_invocation`) carries a `context_contract`
(the agent's task context — the prompt surface) and is recorded from P2 onward; ADR 0010
component #6 (the sandboxed worker runner, P3) explicitly captures **"tool transcripts as
events."** A `context_contract` can incidentally embed a printed secret or prompt-injected repo
content; a tool transcript can contain command output that prints an API key, a `Bearer` token,
a connection string, a private key, customer PII, or attacker-controlled text crafted to be read
back as an instruction. The following controls were identified:

| Report §10 risk | Required control (verbatim intent) |
|---|---|
| Prompt injection from repo/docs/web | Context contract strips irrelevant content; **tool outputs are classified**; high-risk actions require gate review. |
| Secret exposure | **No secrets mounted by default**; short-lived scoped tokens only after gate approval; **secret scanning in CI**. |
| Data exfiltration | **Egress policy in sandbox**; restricted workflows deny external-runtime agents. |
| Non-reproducible decision | Every route, gate, approval, model call, tool call, and CI result is evented. |

The event store therefore needs an explicit, enforceable answer to **what content is allowed in,
and what must be scrubbed before it lands** — pinned **before** the first transcript-bearing
event is built, not after. ADR 0011's Consequences section flagged exactly this and deferred it
to a Security-Lead-consulted policy; this ADR **is** that policy.

**Reuse, do not reinvent (binding).** The engine already ships the enforcement primitives this
policy stands on; they are wired into CI today and this ADR's rules are written to **call them**,
not to duplicate them:

- **`scripts/check_secrets.py`** (CI `ci.yml` step "Secrets never in prompts/runtime (R-6)") —
  scans **`board/.events.jsonl`** (the event store) and `experiments/` for secret patterns in any
  event value, "especially the `agent_invocation` `context_contract` (the agent's prompt)." It is
  **inert (exit 0)** when no event store exists and fails the build (exit 1) on a hit. Current
  pattern set: `sk-ant-*` (Anthropic keys), `AKIA…` (AWS access key id), `ghp_…` (GitHub PAT),
  `-----BEGIN … PRIVATE KEY-----` (PEM). This is the CI **detection backstop** for AC-2/AC-3.
- **`scripts/check_injection_guard.py`** (CI step "Prompt-injection guard (R-6)") — validates
  `agent_invocation` events: the `context_contract` must **not** expose raw/full org state
  (`raw_full_state` / `full_org_state` / `all_state` / `raw_org_state`), `external_content_policy`
  must resolve to **data** (not command), and `allowed_tools` must be a **bounded** allowlist (no
  wildcard/family). This is the CI enforcement of the §10 prompt-injection control.
- **`scripts/check_permissions.py`** (CI step "Least-privilege per agent (R-6)") — least-privilege
  per agent; `is_unbounded_tool` is the shared wildcard test the injection guard reuses.
- **`.gitignore`** already lists `board/.events.jsonl` (beside `board/.arcrift-outbox.jsonl` and
  `board/.wave-log`, ADR 0008 / 0011) — the store is **runtime state, never tracked, never
  pushed**.

## Decision

### 1. Content classification — what may carry free content vs. what stays metadata-only

Every event field is classified into exactly one of three tiers. The tier decides whether the
field may hold free-form, agent- or tool-originated content, and what must happen to it first.

| Tier | Definition | May hold free/agent/tool content? | Examples (ADR 0011 shapes) | Rule |
|---|---|---|---|---|
| **M — Metadata (allowed, default)** | Controlled-vocabulary or structured values authored by the supervisor / gate engine / adapters from a **closed set** (ids, enums, role keys, model names, ISO timestamps, booleans, numeric scores, declared path strings, hash digests). | **No** — not a free-content channel. | `event_type`, `ticket_id`, `run_id`, `from_status`/`to_status`, `assignee`, `reviewer`, `role_key`, `model`, `confidence`, `policy_checks`, `fallback`, `created_at`, `workspace_id`, `severity`, `security_class`, `trace_ids`, `files_changed` (paths). | **Allowed as-is.** These are the only fields Phase 1 emits, which is why Phase 1 is exposure-free. |
| **B — Bounded free text (allowed, scrubbed)** | Short human-/agent-readable rationale or minimal task context authored **inside the control plane** — not raw external output, but free enough to incidentally contain a secret or injected fragment. | **Yes, but** must pass §2 scrubbing + the injection-guard contract, and is **length-bounded**. | `reason` (routing rationale), `context_contract` (minimal task context — ADR 0011 §8.3 / `check_injection_guard.py`), `routing_reason`. | **Allowed only after §2 scrub**; `context_contract` must additionally satisfy `check_injection_guard.py` (no raw/full org state; external content = data; bounded tools). |
| **F — Forbidden raw payload** | Raw, unclassified tool/command output; full file contents pulled from the repo/web; complete model prompts/completions; anything mounting or echoing a credential. | **Never — must not enter the store as raw content.** | a raw `stdout`/`stderr` blob; a full diff/file body; an entire web page; a verbatim transcript; an env dump; a secret value of any kind. | **Forbidden.** A tool transcript (P3) enters **only** as a §2-scrubbed, length-capped, structured **summary** — never the raw payload. Raw output stays in the gitignored worktree/run workspace, referenced by `run_id`/`trace_ids`, not copied into the event. |

**Field-shape rules that make this concrete for the P2/P3 implementer:**

1. **`routing_decision` (Shape A) stays Tier-M + one Tier-B field.** All fields are metadata except
   `reason`, which is Tier-B (scrubbed, ≤ 280 chars). No tool output ever appears in this shape.
2. **`agent_invocation` (Shape B) carries no raw output.** `context_contract` is the only Tier-B
   field and is bound by `check_injection_guard.py`; `allowed_tools`, `secrets_policy`,
   `exit_contract`, `role_key`, `model`, `workspace_id` are Tier-M. The contract is **minimal task
   context, never raw full org state** (ADR 0011 §8.3).
3. **Any future `tool_call` / `tool_result` event (P3) is metadata + a scrubbed summary.** The
   allowed fields are: `event_type`, `ticket_id`, `run_id`, `tool_name` (Tier-M, enum/registry),
   `args_digest` (a hash or a §2-scrubbed, key-redacted shape — **never** raw args), `status`/
   `exit_code` (Tier-M), `output_summary` (**Tier-B**: a §2-scrubbed, length-capped summary, not
   the raw blob), and `trace_ids`/`created_at` (Tier-M). The **raw** transcript is **Tier-F** and
   does not enter the store. P3 references it by `run_id` into the gitignored run workspace.
4. **When in doubt, a field is Tier-F** (deny by default). Promoting a field from F→B requires an
   explicit update to this ADR with Security-Lead sign-off — it is never a silent implementation choice.

### 2. Redaction / scrubbing rule for any captured transcript or Tier-B field

Before **any** Tier-B field (`reason`, `context_contract`, `output_summary`, `args_digest` shape)
is appended to the store, it is passed through a redaction step that removes the following classes.
The step **reuses** the engine's existing secret detector and **extends** its pattern set for the
transcript surface (the extension is implemented by the P3 ticket; this ADR fixes the required
coverage so the implementer has an exact target):

| Class | Patterns (minimum coverage) | Already covered by `check_secrets.py`? | Action |
|---|---|---|---|
| **API keys / tokens** | `sk-ant-*` (Anthropic), `AKIA…` (AWS), `ghp_/gho_/ghu_/ghs_/ghr_…` (GitHub), generic `[A-Za-z0-9_\-]{32,}` high-entropy token shapes | partly (`sk-ant`, `AKIA`, `ghp_`) | **Replace value with `[REDACTED:api_key]`.** Extend `check_secrets.py`'s `SECRET_PAT` (or the P3 scrubber that wraps it) to add the GitHub token family + high-entropy fallback. |
| **Bearer / JWT** | `Authorization: Bearer …`, three-segment `eyJ…\.…\.…` JWTs | **no — gap** | `[REDACTED:bearer]` / `[REDACTED:jwt]`. **New pattern for P3.** |
| **Connection strings** | `postgres://…`, `mysql://…`, `mongodb(+srv)://…`, `redis://…`, `amqp://…`, any `scheme://user:pass@host` | **no — gap** | `[REDACTED:dsn]` (host may be kept; **credentials must be stripped**). **New pattern for P3.** |
| **Private keys** | `-----BEGIN … PRIVATE KEY-----` … `-----END …-----` blocks | yes (BEGIN marker) | `[REDACTED:private_key]` (drop the whole block). |
| **PII** | emails, phone numbers, national-ID / card-number shapes, customer names where structurally detectable | **no — gap** | `[REDACTED:pii]`. **New pattern for P3** (mirror the engine's existing PII-redaction intent referenced in the runtime backlog; do not write raw PII to the audit log). |
| **Prompt-injected repo/web content** | content fetched from the repo/docs/web that is being read **back** into the control plane | n/a (structural, not regex) | Treated as **DATA, not command** via `check_injection_guard.py` (`external_content_policy = data`, bounded `allowed_tools`, no raw/full org state). Tier-F raw bodies never enter the store; only the §1.3 scrubbed summary does. |

**Mechanics (binding on the P3 implementer):**

- **Redact, then truncate, then append.** Scrub for the classes above first, then enforce the
  Tier-B length cap (so a partially-matched secret cannot survive truncation), then write.
- **Fail closed.** If the scrubber errors or cannot classify a value, the field is **dropped**
  (replaced with `[REDACTED:unclassified]`), never written raw. Losing a rationale string is
  always preferable to leaking a secret into an append-only, un-editable log.
- **Append-only ⇒ scrub-before-write is the only chance.** The store is never edited in place
  (ADR 0011); a leaked secret cannot be "removed later" without a compensating-event rewrite. The
  redaction therefore happens **at emit time, before the line is appended** — there is no
  post-hoc cleanup path.
- **CI is the backstop, not the primary control.** `check_secrets.py` runs in CI against the
  (gitignored, normally absent in CI) store and against `experiments/`; it is the **detection net**
  that fails the build if an un-scrubbed secret pattern is ever found in a committed/exported event
  sample. The **primary** control is emit-time scrubbing; CI catches regressions.

### 3. Storage, egress, and secrets posture (confirmation + pin)

- **The event store stays gitignored.** `board/.events.jsonl` is already in `.gitignore` (beside
  `board/.arcrift-outbox.jsonl`, ADR 0008). This ADR **pins** that as a security invariant: the
  store is **runtime state, never tracked, never committed, never pushed**. A change that would
  track it (or copy its contents into a tracked file) is a security regression and is rejected.
- **No external egress.** The security posture requires that the event store remain **local-only**.
  Nothing ships `board/.events.jsonl` (or any derived transcript) to an external endpoint. The
  ArcRift memory loop (ADR 0008) is the **only** sanctioned durable sink, it is **local** (local
  SQLite + local Ollama embeddings + the local claude-bridge), and it receives **stored facts,
  not raw event payloads**. A future SQLite/Postgres backing of the store (ADR 0011) must remain
  local and inherit this no-egress rule and these scrubbing rules unchanged.
- **`secrets_policy` = no-secrets-by-default.** ADR 0011's `agent_invocation.secrets_policy`
  field defaults to **no secrets mounted**; short-lived, narrowly-scoped credentials are provided
  **only** after an explicit gate approval (secret-exposure control), and even then the
  **value never enters an event** — only the fact-of-grant + scope + ttl as Tier-M metadata. The
  default state of every dispatched run is "no secrets," so the common case has nothing to leak.

### 4. How the P2/P3 tool-event tickets consume this policy (the binding hand-off)

Any DGO-X ticket that introduces an event field able to hold free content, or a tool transcript,
**must**:

1. **Cite this ADR (0012)** in its description and acceptance criteria.
2. **Classify every new field** into Tier M/B/F per §1, and keep raw payloads (Tier-F) **out** of
   the store — referencing them by `run_id`/`trace_ids` into the gitignored run workspace instead.
3. **Route every Tier-B field through the §2 scrubber** at emit time (fail-closed), and **extend
   `check_secrets.py`'s pattern set** (or a P3 scrubber wrapping it) to add the named gaps
   (Bearer/JWT, connection strings, PII, GitHub token family, high-entropy fallback) **with tests**.
4. **Keep `agent_invocation` within `check_injection_guard.py`** (minimal `context_contract`,
   `external_content_policy = data`, bounded `allowed_tools`).
5. **Preserve §3**: store stays gitignored, no external egress, `secrets_policy` no-secrets-default.

A P2/P3 PR that adds a transcript-bearing event without (2)+(3) is **incomplete** and is rejected
by the reviewer (the author's manager per ROUTING) on this ADR.

## Consequences

**Positive:** the event store gains a **deny-by-default content contract** (Tier-F is the default;
only metadata and scrubbed bounded text are allowed) and a **fail-closed scrubbing rule**, pinned
**before** the first transcript-bearing event exists — so DGO-X cannot grow an append-only,
un-editable audit log that silently accumulates secrets, PII, or injected instructions. The policy
**reuses** the engine's already-CI-wired primitives (`check_secrets.py`, `check_injection_guard.py`,
`check_permissions.py`, the `.gitignore` entry) rather than inventing parallel machinery, so the
enforcement surface is one place, not three. The P2/P3 implementers get an **exact** target
(Tier table + the named pattern gaps), which removes ambiguity from the most security-sensitive
part of the migration.

**Negative / accepted:** the redaction set is **best-effort, not perfect** — a novel secret shape
or an obfuscated credential can evade a regex (the universal limit of pattern-based scrubbing),
which is precisely why the **primary** mitigation is structural (Tier-F raw payloads never enter
the store; `secrets_policy` is no-secrets-by-default, so the common case carries nothing to leak)
and the regex scrubber is the **second** line, with CI as a **third**. Scrubbing also **loses
information** from the audit log (a truncated/redacted rationale is less useful for debugging) —
accepted, because a leak into an un-editable log is strictly worse than a lossy log, and the raw
material remains in the gitignored, local-only run workspace keyed by `run_id` for as long as it
is retained there. Extending the pattern set (Bearer/JWT, DSNs, PII) is **deferred to the P3
ticket**, not delivered by this policy ADR — until that ticket lands, **no transcript-bearing event
may be implemented** (which is the whole point of gating it here).

**Law check:** **Charter / RACI** — security discipline is Security-Lead-owned org-wide
(engineering charter §Authority); this ADR is **Security-Lead-signed** and **CTO-reviewed** per
`board/ROUTING.md` (security-lead → CTO); Security Lead does not self-review (the reviewer is the
CTO). **Board audit** — the event store *strengthens* the audit trail; this policy keeps it
honest (no secrets/PII pollute it) and keeps the board canonical (ADR 0010 C2; nothing here writes
ticket frontmatter). **DGO-X constraints** — consistent with C2 (board canonical), C3 (workers
never write routing fields — unchanged), and the security controls defined in this ADR (prompt injection, secret
exposure, data exfiltration). **Project placement** — this is a platform security doc under
`docs/adr/`, no project/product content (ADR 0010 C6 / CLAUDE.md LAW 1). **No-hollow-gate (LAW 2)**
— the policy is backed by **real, CI-wired** validators (`check_secrets.py`, `check_injection_guard.py`),
and it honestly marks the Bearer/JWT/DSN/PII coverage as a **gap to be closed by the P3 ticket**
rather than claiming coverage the code does not yet have.

## Enforcement / acceptance

- **This ADR is the citation** any future "what may enter the DGO-X event store / how is a tool
  transcript redacted / is the store egress-free?" question resolves to.
- **It gates P2/P3 tool-event work**: a ticket that adds a free-content or transcript-bearing
  event is not `done` until it satisfies §4 (cite this ADR; classify fields; fail-closed scrub
  reusing/extending `check_secrets.py` **with tests**; stay within `check_injection_guard.py`;
  preserve gitignore + no-egress + no-secrets-default).
- **CI already enforces the floor today** (`check_secrets.py` over the store + `experiments/`;
  `check_injection_guard.py` over `agent_invocation` events; both inert until events exist). When
  the P3 scrubber extends the pattern set, those validators (or their successor) carry the new
  patterns, so the gate tightens automatically as transcript events land.
- **Signed:** Security Lead — DasLab engineering, 2026-06-22. **Reviewed + ratified: CTO — 2026-06-22 (per ROUTING, security-lead → CTO).** The CTO review confirmed: the M/B/F tiers are coherent and deny-by-default (§1.4) routes raw payloads to Tier-F (never stored, kept in the gitignored run workspace by `run_id`); the reuse claims are true against source (`check_secrets.py` `SECRET_PAT` = `sk-ant`/`AKIA`/`ghp_`/PEM only, and the Bearer/JWT, DSN, PII, GitHub-token-family, high-entropy gaps are named — not silently assumed covered — and handed to the P3 scrubber **with tests**); `check_secrets.py` + `check_injection_guard.py` are CI-wired today (`ci.yml`); and §3's gitignored + no-egress + no-secrets-default posture matches ADR 0011 and the actual `.gitignore` (`board/.events.jsonl`). **Remaining gate the CTO records for the P2/P3 implementers:** no transcript-bearing / free-content event may be implemented until the P3 scrubber ticket extends the pattern set (Bearer/JWT, DSN, PII, GitHub family, high-entropy fallback) **with tests** per §2/§4 — and the high-entropy `{32,}` fallback must be tuned in P3 to avoid over-redacting legitimate Tier-M hash digests/long ids (fail-closed over-redaction is lossy, acceptable, but should be minimised).
