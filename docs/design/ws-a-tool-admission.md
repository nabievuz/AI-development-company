# WS-A tool-admission design — overlay allow-list, PreToolUse audit/deny, ADR-0012 redaction, deny-all egress

- **Status:** Design (AADL Stage 2 — GATE-2) — awaiting review (CTO accountable; Security Lead consulted)
- **Date:** 2026-07-24
- **Ticket:** DAS-1546 (WS-A Design); epic DAS-1544 (MUSTAQIL WS-A REACH)
- **Author:** Backend EM (responsible); CTO (accountable stage owner); Security Lead (consulted — tool admission + ADR-0012 redaction + egress)
- **Binds to:** ADR-0033 (TB-1…TB-5, Accepted 2026-07-24), `docs/specs/002-mustaqil-ws-a-reach/SPEC.md` (FR-001…FR-006, SC-001…SC-004, reviewed), ADR-0012 (event classification + redaction), ADR-0018/0029 (overlay + guild compile path), Founder discovery answer Q5 (deny-all + explicit domain allow-list egress)
- **Downstream:** DAS-1547 (FastMCP sidecar under `tools/`), DAS-1548 (browser sidecar), DAS-1549 (negative tests — this doc hands it §4), DAS-1550 (deploy), DAS-1551 (maintenance)

> **Scope of this doc.** WHAT the governed admission model is and HOW its pieces
> compile and interlock — schemas, hook contract, redaction mapping, egress
> policy, and the negative-path spec the Testing ticket implements. It ships **no
> runtime code**: the sidecar, the generator extension, the settings wiring, and
> the egress-allow-list file are built by DAS-1547/1548 against this design. The
> on-branch spikes (`tools/mcp_bridges/audit_external_tool.py`,
> `tools/mcp_bridges/langchain_tool_bridge.py`, `tools/mcp_bridges/mcp.snippet.json`,
> `tests/test_ws_a_tool_bridge.py`) are the reference the design hardens — cited,
> not modified here (this ticket touches only `docs/design/` + the ticket file).

## 0. The admission chain (one picture)

An external tool call is admitted only if it survives **four** independent gates,
each fail-closed. Any one failing denies the call:

```
role overlay (SSOT)                       config/egress-allowlist.yaml (SSOT)
  ── ## External tools block                 ── deny-all + domain list
        │  gen_subagents.py compile                │
        ▼  (generate-and-diff, ADR-0029 G-4)       │
  .claude/agents/<role>.md  +  board/.tool-allowlist.json (generated)
        │                                          │
        ▼                                          ▼
[1] TB-2 allow-list ──▶ [2] TB-3 PreToolUse audit/deny ──▶ [3] TB-4 egress ──▶ tool runs
   (is this role         (settings.json hook:              (sidecar checks       │
    granted this          decide + append-only audit)       host vs allow-list)  ▼
    tool at all?)              │                                          [4] ADR-0012 redaction
                              deny-all default                            (transcript → scrubbed event)
```

- **[1] TB-2 (FR-002)** — §1. Least privilege: the role must declare the tool in
  its overlay; the compiled allow-list is the only thing the hook trusts.
- **[2] TB-3 (FR-003)** — §2. Every external call passes a `PreToolUse` hook that
  audits and may deny; deny-all is the default when a call is unrecognised.
- **[3] TB-4 egress (FR-005/FR-006/Q5)** — §3. Deny-all outbound except an explicit
  domain allow-list; fetched content is untrusted data (ingress) that can never
  change goal/approvals/permissions.
- **[4] ADR-0012** — §2.3. The transcript becomes a classified, scrubbed event;
  the raw payload never lands in an append-only log.

`external tool` throughout means an MCP tool — a tool whose name begins with
`mcp__` (e.g. `mcp__playwright__browser_navigate`, `mcp__langchain-tools__web_fetch`).
Claude Code built-ins (`Read`/`Bash`/`WebFetch`/…) are governed by the existing
permission + `check_permissions.py` layer and are out of scope here — the hook
passes them through unchanged (`decide()` returns `allow, "not an external tool"`).

---

## 1. Least-privilege allow-list (TB-2 / FR-002)

**Requirement (FR-002 / TB-2):** a role reaches an external tool only when its
`<dept>/agents/<role>/AGENTS.md` overlay allow-lists it. No blanket grants; a
non-declared tool is **structurally unreachable**.

### 1.1 Source of truth — the overlay `## External tools` block

The overlay is the single hand-authored SSOT for a role's external-tool grants.
A role that needs an external tool gains a new **optional** section, a fenced YAML
block that machine-parses:

```markdown
## External tools
<!-- TB-2 least-privilege grants (ADR-0033). Absent section = no external tools.
     Compiled by scripts/gen_subagents.py into board/.tool-allowlist.json.
     Adding/editing this block is a security_sensitive + permission_change ticket
     (never approval: auto*, QONUN-5). -->
```yaml
external_tools:
  - server: mcp__playwright         # server-level grant: all tools of this server
    tools: ["*"]                    #   or an explicit list e.g. ["browser_navigate","browser_click"]
    egress_profile: qa-browser      # names a domain set in config/egress-allowlist.yaml (§3)
    reason: visual regression + screenshot verification
  - server: mcp__langchain-tools    # tool-level grant is also allowed:
    tools: ["web_fetch"]            #   only web_fetch of this server, not the whole server
    egress_profile: research-read
    reason: sourced market/competitor research
```
```

Field rules:

| Field | Required | Meaning |
|---|---|---|
| `server` | yes | MCP server key exactly as it appears in `.mcp.json` and in the tool name prefix (`mcp__<server>`). |
| `tools` | yes | Explicit tool short-names, or `["*"]` for a server-wide grant. `["*"]` is a **reviewed** widening, not a shortcut — the reviewer (CTO, Security Lead consulted) must justify it; it is never the default. |
| `egress_profile` | yes for any network-capable tool | Names a domain set in `config/egress-allowlist.yaml` (§3). A tool with no profile gets the empty (deny-all) profile. |
| `reason` | yes | One line of craft justification, mirrored into the audit trail and the ADR-0029 guild template. |

**No section ⇒ no external tools.** The absence of `## External tools` is the
common case and means the role reaches **zero** MCP tools — the deny-all posture
is the default, not an opt-out.

### 1.2 Guild-template mirror (ADR-0029 G-2)

The same grant is reflected in the role's `governance/agent-templates/<role>.md`
`## Toolkit allowlist` section as a *positive craft statement* (ADR-0029 G-2) —
"the tools this role reaches for". Per G-5 the template **references, never
re-decides**: the overlay block is the SSOT; the template restates it for craft
locality and is kept honest by `check_agents_sync.py`. The template's existing
disclaimer stands — it "does NOT widen any security boundary; the sandbox/
permission layer remains the boundary." The security boundary is §1.3's compiled
allow-list + §2's hook, not the prose bullet.

### 1.3 Compilation — overlay → generated allow-list (ADR-0018/0029 path)

`scripts/gen_subagents.py` already walks every `<dept>/agents/<role>/AGENTS.md`
overlay and regenerates `.claude/agents/<role>.md` + `board/ROUTING.md`
idempotently (delete-and-fully-regenerate, generate-and-diff clean). WS-A
**extends** that same pass — it does not fork a new pipeline (ADR-0029
extend-vs-new posture):

1. For each overlay, parse the `## External tools` YAML block (absent ⇒ no grants).
2. Emit a single generated artifact **`board/.tool-allowlist.json`** — the compiled
   grant map, in exactly the shape `audit_external_tool.py` already reads:

```json
{
  "mcp__playwright": ["qa-lead", "design-lead"],
  "mcp__langchain-tools__web_fetch": ["product-analyst"]
}
```

   - A **server-level** grant (`tools: ["*"]`) emits the server key
     `mcp__<server>` → sorted list of role keys that granted it.
   - A **tool-level** grant emits the full tool key
     `mcp__<server>__<tool>` → sorted list of role keys.
   - A role appears under a key **only** if its overlay declared it. The map is
     the *union of declarations* — there is no default entry, no wildcard role.
3. `$DASLAB_TOOL_ALLOWLIST` (the env var the hook reads) points at this generated
   file. The file is generated runtime state, listed in `.gitignore` alongside
   the other `board/.` artifacts — same posture as `board/.tool-audit.jsonl` and
   `board/.events.jsonl`.

**Structural unreachability (the FR-002 invariant).** The hook trusts *only* the
compiled allow-list. A tool that no overlay declared has **no key** in
`board/.tool-allowlist.json`; `decide()` hits `roles is None` and returns
`deny`. There is no code path from "present in `.mcp.json`" to "callable" that
skips the overlay declaration — a non-declared tool is unreachable by
construction, not by convention. This is the exact analogue of ADR-0026's
route-graph rule ("a route the role is not granted has no place in its
definition — structurally unrepresentable"), applied to tools.

**Drift guard.** `check_agents_sync.py` is extended (or a sibling check under the
same generate-and-diff pattern) to fail CI if `board/.tool-allowlist.json` is
stale relative to the overlays, or if the guild-template `## Toolkit allowlist`
disagrees with the overlay grant — the same way it already guards `model:` and
ROUTING drift (ADR-0029 G-4). A hand-edited allow-list JSON is a diff, hence a
red build.

**Trace:** overlay declaration → `gen_subagents.py` compile → generated
`board/.tool-allowlist.json` → `audit_external_tool.decide()` — closes **FR-002 /
TB-2**.

---

## 2. PreToolUse audit / deny + ADR-0012 redaction (TB-3 / FR-003)

**Requirement (FR-003 / TB-3):** every external-tool call passes a `PreToolUse`
audit hook that may **deny** it; every tool transcript is classified + redacted
under ADR-0012; a tool never writes routing fields (C3) or bypasses an AADL gate
(C4).

### 2.1 The `.claude/settings.json` hook contract

The hook is filesystem-configured in `.claude/settings.json`, honored
**identically by the Claude Code CLI and the Agent SDK** (ADR-0034 — the headless
runner reads the same settings surface). The wiring DAS-1547 lands:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          { "type": "command",
            "command": "python3 tools/mcp_bridges/audit_external_tool.py" }
        ]
      }
    ]
  }
}
```

- **Matcher `mcp__.*`** scopes the hook to external (MCP) tools; built-ins never
  reach it, and the hook itself second-checks the `mcp__` prefix so a broadened
  matcher cannot accidentally deny a built-in (`decide()` passes non-external
  tools through).
- **Event in (stdin):** the PreToolUse JSON — at minimum `tool_name`, the calling
  `agent_type`/`agent` (role key), and `tool_input`.
- **Decision out (stdout):**
  - **deny** → `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
    "permissionDecision": "deny", "permissionDecisionReason": "[WS-A governance] …"}}`
  - **allow** → `{}` (empty object).
- **Fail-closed default.** An unlisted tool, an unparseable event, or a missing
  allow-list all resolve to `deny` (the spike's `load_allowlist()` returns `{}` on
  any read error, and `{}` denies every external tool). Losing a legitimate call
  is always preferable to admitting an ungoverned one.
- **Audit is unconditional.** Every decision — allow *and* deny — appends one
  record to the append-only `$DASLAB_TOOL_AUDIT_LOG` (default
  `board/.tool-audit.jsonl`): `{ts, tool, agent, decision, reason}`. Auditing
  must never block or crash a wave (the append is best-effort/​try-guarded), but a
  successful call always leaves an audit trace.

### 2.2 "Skip the audit" is not a reachable state (the SC-001b invariant)

The audit/deny gate is not optional decoration — a call that is not seen by the
hook must not reach the tool. Two structural facts enforce this:

1. The hook is registered in `.claude/settings.json` for the `mcp__.*` matcher;
   the harness (CLI and SDK alike) invokes it **before** dispatching any matching
   tool. There is no in-band way for an agent to call an `mcp__` tool that bypasses
   its own PreToolUse hook.
2. Removing or neutering the hook is a **detectable governance regression**: a
   check asserts `.claude/settings.json` carries the `PreToolUse` `mcp__.*` →
   `audit_external_tool.py` binding, so deleting it fails CI rather than silently
   opening the door. DAS-1549 asserts both the presence of the binding and that
   `decide()` fail-closes (§4 SC-001b).

### 2.3 Transcript → ADR-0012 event classification + redaction

A tool call produces a transcript (args + output). Under ADR-0012 it becomes a
`tool_call` / `tool_result` event that is **metadata + a scrubbed summary — never
a raw payload**:

| Field | ADR-0012 tier | Content |
|---|---|---|
| `event_type`, `ticket_id`, `run_id`, `tool_name`, `status`/`exit_code`, `trace_ids`, `created_at` | **M — metadata** | Controlled-vocabulary / ids / enums. Allowed as-is. |
| `args_digest` | **M/B** | A hash **or** a §2-scrubbed, key-redacted shape of the arguments — **never** raw args. |
| `output_summary` | **B — bounded free text** | A **§2-scrubbed, length-capped summary** of the tool output. |
| raw stdout/stderr, full fetched page, verbatim transcript | **F — forbidden** | **Never enters the store.** Stays in the gitignored run workspace, referenced by `run_id`/`trace_ids`. |

Before any Tier-B field is written, it passes the ADR-0012 §2 scrubber —
**redact, then truncate, then append**, fail-closed (an unclassifiable value is
dropped to `[REDACTED:unclassified]`, never written raw). Required redaction
coverage (ADR-0012 §2): API keys/tokens (`sk-ant-*`, `AKIA…`, `ghp_/gho_/ghu_/
ghs_/ghr_…`, high-entropy fallback), Bearer/JWT, connection strings (`scheme://
user:pass@host`), private-key blocks, PII. The browser/​web transcript surface is
exactly the "P3 tool-transcript" surface ADR-0012 §2 names — WS-A's tool-event
scrubber is that P3 scrubber, delivered **with tests** per ADR-0012 §4, and must
not over-redact legitimate Tier-M hash digests / long ids (the tuning note ADR-0012
records for the high-entropy `{32,}` fallback). The same scrub applies to the
`output_summary`/`reason` fields written into `board/.tool-audit.jsonl`.

### 2.4 A tool never writes routing fields (C3) or bypasses a gate (C4)

- **C3 (no routing-field writes).** External tools are read/act sidecars; they are
  not granted any board-mutation capability. Routing fields (`assignee`, dispatch
  order, `status`) are mutated only by the orchestrator/reviewer edit path, never
  by a tool. The admission chain never exposes a tool that writes ticket
  frontmatter; a bridge PR that did would be rejected against this invariant.
- **C4 (never past an open gate).** An external tool is substrate (ADR-0033 Law
  check C1/C2); it advances no AADL status and signs no gate. The dispatcher's
  gate order (`depends_on` / open-gate skips) is unchanged by the presence of a
  sidecar (TB-5 — flag OFF is byte-identical; flag ON adds tool reach, not
  dispatch power). A tool call cannot dispatch a ticket past an open gate because
  it has no dispatch surface at all.

**Trace:** `.claude/settings.json` PreToolUse hook → `decide()` deny + append-only
audit → ADR-0012 M/B/F classification + fail-closed scrub; C3/C4 preserved —
closes **FR-003 / TB-3**.

---

## 3. Egress policy — deny-all except an explicit domain allow-list (TB-4 / FR-005 + FR-006 / Q5)

**Requirement (FR-005 + FR-006 / TB-4 / Q5):** a browser/computer-use tool is
admitted only behind §1 + §2, with **egress deny-all except an explicit domain
allow-list**, and fetched content treated as **untrusted input**. The ratified
ADR-0033 TB-4 draws two *distinct* controls — this section keeps them separate:

### 3.1 (a) INGRESS — fetched content is untrusted DATA (FR-006)

Content a tool pulls in (a web page, an API response, a file) is **data, never
command**. It can never change the agent's goal, approvals, or permissions
(prompt-injection defense — the documented Jules-style exfiltration class). Design
controls:

- The sidecar returns fetched content as an **inert tool result** — a title +
  bounded text excerpt (the reference `web_fetch` already caps at
  `_MAX_CHARS`) — surfaced to the agent as *observed data*, not as instructions to
  execute.
- ADR-0012's `check_injection_guard.py` contract holds for the agent invocation
  that consumes tool output: `external_content_policy = data`, bounded
  `allowed_tools`, no raw/full org state. A fetched page cannot re-open an AADL
  gate, re-route a ticket, or widen the tool grant — those live in the board /
  overlay SSOTs, which a tool result has no path to write (C3, §2.4).
- Raw fetched bodies are Tier-F (§2.3): they never enter the event store; only the
  scrubbed `output_summary` does.

### 3.2 (b) EGRESS — deny-all + explicit domain allow-list (FR-005 / Q5)

Outbound network access is **deny-all**; a request reaches only a host on an
explicit allow-list (Founder answer Q5). Design:

- **Where the allow-list lives:** a tracked config file **`config/egress-allowlist.yaml`**
  (created by DAS-1547/1548 — named here, not created by this ticket), pointed to by
  `$DASLAB_EGRESS_ALLOWLIST`. It is *tracked* (unlike the generated allow-list JSON),
  because the set of approved destinations is a reviewed governance surface, not
  runtime state. Editing it is a `security_sensitive` + `governance_or_policy`
  change (never `approval: auto*`, QONUN-5).
- **Shape** — named profiles referenced by an overlay grant's `egress_profile`
  (§1.1):

```yaml
# config/egress-allowlist.yaml — deny-all is implicit; only listed hosts are reachable.
profiles:
  qa-browser:            # visual verification of our own surfaces
    - staging.qaqn.uz
    - localhost
  research-read:         # sourced research
    - "*.wikipedia.org"
    - api.crossref.org
# Anything not listed under the invoked profile is DENIED.
```

- **Enforcement point:** at the **sidecar** (the FastMCP bridge / browser server),
  before any network syscall. The sidecar resolves the request host, matches it
  against the invoking role's profile, and **refuses** (returns an
  `error: egress denied — <host> not in <profile>` tool result) on any miss. This
  is the layer the reference `web_fetch` currently **lacks** — its stdlib
  `urllib.request.urlopen` fetches any host — so egress filtering is a named
  **development gap** DAS-1547/1548 must close and DAS-1549 must test (§4 SC-002a).
- **No production credentials by default** (TB-4): the sidecar runs with no mounted
  secrets unless a call is explicitly scoped one via a gate approval (ADR-0012 §3
  `secrets_policy = no-secrets-by-default`); the credential value never enters an
  event (fact-of-grant + scope + ttl only, Tier-M).

**Trace:** ingress = untrusted data (FR-006, §3.1) + egress = deny-all + domain
allow-list at the sidecar (FR-005 / Q5, §3.2) — closes **TB-4**.

---

## 4. Negative-path spec for DAS-1549 (Testing / GATE-4)

The behaviours the Testing ticket (DAS-1549, `zone: tests`, `implements:
[SC-001, SC-002]`) must assert. Each is written so it can be implemented directly
against the spike surface (`hook.decide`, `bridge.web_fetch`, the egress check,
the ADR-0012 scrubber) and folded into `tests/test_ws_a_tool_bridge.py`.

### SC-001 — global grant refused + audit-skip denied (TB-2 / TB-3)

- **SC-001a — no-overlay tool is refused (structural unreachability).**
  A tool present in `.mcp.json` but declared by **no** overlay compiles to **no
  key** in `board/.tool-allowlist.json`. Assert:
  - `hook.decide("mcp__playwright__browser_navigate", "<any-role>", {})[0] == "deny"`
    (empty compiled allow-list ⇒ deny for every role).
  - With a compiled allow-list that grants the tool to role **A only**, a call by
    role **B** denies: `decide(tool, "B", {"mcp__playwright": ["A"]})[0] == "deny"`
    while `decide(tool, "A", {…})[0] == "allow"`. There is **no** "global" role and
    no default entry — a tool nobody declared is reachable by nobody.
  - A "blanket grant" attempt (a role expecting a tool it did not declare) yields
    `deny` — the compiled map is the union of *declarations* only.
- **SC-001b — a call that skips the PreToolUse audit is denied.**
  - Assert `.claude/settings.json` carries the `PreToolUse` binding with matcher
    `mcp__.*` → `audit_external_tool.py`; a config lacking it fails the test
    (removing the hook is a detectable regression, §2.2).
  - Assert fail-closed decode: `decide()` on a malformed/empty event, and
    `load_allowlist()` with an unreadable/absent `$DASLAB_TOOL_ALLOWLIST`, both
    resolve to `deny` for any `mcp__` tool.
  - Assert every decision (allow and deny) appends exactly one record to
    `$DASLAB_TOOL_AUDIT_LOG` — i.e. no admitted call is unaudited.

### SC-002 — non-allow-listed egress blocked + redaction probe passes (TB-4 / ADR-0012)

- **SC-002a — egress to a non-allow-listed domain is blocked.**
  - With `config/egress-allowlist.yaml` profile `research-read` = `["api.crossref.org"]`,
    a fetch to a host **outside** the profile (e.g. `https://evil.example/…`)
    returns an egress-denied error result and performs **no** network call;
    a fetch to `https://api.crossref.org/…` is permitted by the egress check.
  - Assert the check is **deny-by-default**: an empty/absent profile denies every
    host. (This exercises the egress layer DAS-1547/1548 add to the sidecar — the
    reference `web_fetch` must gain host-matching before this passes.)
  - Assert wildcard host rules (`*.wikipedia.org`) match sub-domains but not a
    look-alike suffix (`evilwikipedia.org` denied).
- **SC-002b — tool-event redaction probe passes.**
  - Feed a synthetic tool transcript containing planted secrets — an
    `sk-ant-…` key, an `Authorization: Bearer …` / a three-segment `eyJ….….…`
    JWT, a `postgres://user:pass@host/db` DSN, a `-----BEGIN … PRIVATE KEY-----`
    block, and a PII email — through the ADR-0012 §2 scrubber before it becomes an
    `output_summary` / audit record. Assert each is replaced by the corresponding
    `[REDACTED:…]` token and that **no** raw secret substring appears in the
    resulting `board/.tool-audit.jsonl` line or the `tool_result` event.
  - Assert **fail-closed**: an unclassifiable value is dropped to
    `[REDACTED:unclassified]`, never written raw; and redact-then-truncate ordering
    holds (a secret split by truncation cannot survive).
  - Assert **no over-redaction** of a legitimate Tier-M hash digest / long id (the
    ADR-0012 high-entropy `{32,}` tuning note).

### SC-003 guard (out of this doc's FR scope, noted for DAS-1549 completeness)

With the `ws_a_tool_bridge` flag **OFF** (default), a wave's dispatch behaviour is
byte-identical to pre-merge (TB-5 / FR-004) — the tool simply does not exist.
DAS-1549 already lists this; it is not a §1–§3 admission behaviour, so it is noted,
not specified here.

**Hand-off:** SC-001 → §1 (TB-2) + §2.2 (TB-3 audit-skip); SC-002 → §3.2 (TB-4
egress) + §2.3 (ADR-0012 redaction). All assertions are expressible against the
existing spike functions plus the egress + scrubber surfaces DAS-1547/1548 add.

---

## 5. Traceability matrix

| SPEC FR | ADR-0033 | This design | DAS-1549 SC |
|---|---|---|---|
| FR-002 — overlay allow-list, no blanket grants | TB-2 | §1 (overlay block + compile + structural unreachability) | SC-001a |
| FR-003 — PreToolUse audit/deny + ADR-0012 redaction; no C3/C4 breach | TB-3 | §2 (hook contract, audit-skip invariant, M/B/F redaction, C3/C4) | SC-001b, SC-002b |
| FR-005 — browser behind allow-list + audit; deny-all egress; no unscoped prod creds | TB-4 (egress) | §3.2 (`config/egress-allowlist.yaml`, sidecar enforcement, no-secrets-default) | SC-002a |
| FR-006 — fetched content is untrusted input | TB-4 (ingress) | §3.1 (data-not-command, injection guard, Tier-F raw bodies) | SC-002b (redaction) / covered structurally |

## 6. Open items handed downstream (not decided here)

- **DAS-1547/1548** create `config/egress-allowlist.yaml`, add the sidecar egress
  host-check (the reference `web_fetch` gap, §3.2), extend `gen_subagents.py` to
  emit `board/.tool-allowlist.json` from the overlay `## External tools` block
  (§1.3), wire `.claude/settings.json` (§2.1), and deliver the ADR-0012 tool-event
  scrubber **with tests** (§2.3). All behind `ws_a_tool_bridge` OFF (TB-5).
- **Security Lead (consulted)** reviews §2.3 redaction coverage + §3 egress posture
  against ADR-0012; **CTO (accountable)** ratifies GATE-2 closure.
- Which roles actually receive which grants (the concrete overlay edits) is a
  per-role `security_sensitive` + `permission_change` decision made when a role
  demonstrably needs the tool — not pre-granted here (least privilege).
