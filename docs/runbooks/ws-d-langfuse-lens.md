# Runbook — WS-D: self-host Langfuse observability lens (ADR-0036 / ADR-0038 TN-1)

**Goal (MUSTAQIL WS-D):** give roles a redacted trace/eval view of the DGO-X
event store via **self-host Langfuse**, in-tenant only — reach goes up,
governance does not go down.

## What ships

| File | Role |
| --- | --- |
| `tools/observability/otlp_exporter.py` | Read-side exporter: DGO-X event store → OTLP span → in-tenant Langfuse. Reads only; no write path (FR-003). |
| `tools/observability/requirements-observability.txt` | Optional deps (`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`); kept OUT of core `requirements.txt` |
| `config/tenant_boundary.yaml` | TN-1 SSOT — declares `langfuse_observability` at `http://127.0.0.1:3000` |
| `config/features.yaml` | `ws_d_langfuse_lens: false` — the flag this runbook is about, OFF |
| `scripts/check_in_tenant.py` | Boundary guard — fails a run if any code/IP endpoint (including `langfuse_observability`) resolves external |
| `tests/test_ws_d_otlp_exporter.py`, `tests/test_ws_d_tool_admission.py`, `tests/test_ws_d_redaction_testing.py` | Exporter, tool-admission, and redaction test suites (DAS-1573/1574/1575) |

## Deployment (AADL Stage 5 / GATE-5, DAS-1576)

**No production deploy happens here, and this ticket does not stand up
Langfuse or flip the flag.** WS-D ships with `ws_d_langfuse_lens: false`
(`config/features.yaml`) — the exporter and tool-admission reuse land in the
tree, inert, behind the flag. "Deployment" for WS-D means *shippable +
operable while OFF*, never *live*. Everything below is the **documented
procedure** for a later, explicit act — none of it is executed by this
ticket.

### 1. Stand up self-host Langfuse in-tenant (the flip procedure — documented, not executed)

Langfuse is deployed **on the tenant VM** (ADR-0038 TN-1, Q2), never as a
hosted SaaS project:

1. Provision Langfuse (self-host Docker Compose / Helm per the Langfuse
   self-host docs) on the tenant Linux VM, bound to the loopback/private
   interface the exporter reaches — `127.0.0.1:3000` per
   `config/tenant_boundary.yaml`'s `langfuse_observability` entry.
2. Do **not** expose the instance on a public hostname or point it at
   Langfuse Cloud / LangSmith. `config/tenant_boundary.yaml` is the TN-1 SSOT:
   its `langfuse_observability` endpoint carries `carries_code_ip: true` and is
   **not** in `accepted_external_roles` (only the `model` role — the Claude
   call itself — is accepted external, per Q9). A hosted URL here is a
   **config error** that `scripts/check_in_tenant.py` **blocks** — the guard
   fails the run (exit 1) the moment `langfuse_observability` resolves to a
   public hostname or public IP. This is enforced by the same code the
   exporter's own SC-004 test proves (`test_hosted_endpoint_fails_closed`,
   `test_export_blocks_before_post_on_hosted_target`).
3. Confirm the endpoint resolves in-tenant: loopback, an RFC-1918/ULA private
   address, a `.local`/`.internal`/bare-hostname name, or a unix socket/file
   path all pass; a dotted public hostname or public IP does not
   (`scripts/check_in_tenant.py::is_in_tenant`).
4. Update `config/tenant_boundary.yaml`'s `langfuse_observability.url` only if
   the actual deploy host/port differs from the bootstrap `127.0.0.1:3000`
   default — keep it in-tenant per step 2.

### 2. Enable the exporter (a later, explicit Founder/governance act)

1. Install the opt-in deps on the in-tenant host that will run the lens
   (never in the core `requirements.txt` — the flag-OFF exporter carries no
   runtime weight by design):
   ```bash
   pip install -r tools/observability/requirements-observability.txt
   ```
   The core exporter (`tools/observability/otlp_exporter.py`) imports none of
   these — it builds OTLP/HTTP JSON with the stdlib and ships it via
   `urllib`; the optional deps only matter if the official OTLP proto
   SDK/exporter is preferred over the stdlib JSON transport.
2. Confirm the target passes the boundary guard **before** flipping anything:
   ```bash
   python3 scripts/check_in_tenant.py
   ```
   Exit 0 = boundary intact (Langfuse endpoint in-tenant, model call the sole
   accepted external exception). A non-zero exit means fix the endpoint
   (step 1) before proceeding — never flip the flag against a failing guard.
3. Flip `ws_d_langfuse_lens` **ON** in `config/features.yaml`. This is a
   `security_sensitive` + `governance_or_policy` change (QONUN-5) — it must
   never carry `approval: auto*`; it is a **Founder/governance act**, not
   something a role subagent does unilaterally. Scope it to one shell/session
   first if a narrow shadow test is wanted (`DASLAB_WS_D_FLAG=on`, read before
   the file, same override pattern as WS-A's `DASLAB_WS_A_FLAG`), then widen
   to the tracked config once proven.

### 3. Admit the eval/guardrail tools (if needed)

The promptfoo/AgentShield/Presidio sidecars are already wired in `.mcp.json`
(`promptfoo`, `agentshield`, `presidio` entries) and governed by the same
ADR-0033 edge as WS-A:

- **Least privilege (TB-2):** each sidecar reaches only the roles whose
  `<dept>/agents/<role>/AGENTS.md` overlay explicitly allow-lists it — no
  blanket grant. `tests/test_ws_d_tool_admission.py`'s
  `test_compiled_allowlist_has_no_wildcard_roles` proves no server-wide
  "any-role" entry is ever compiled.
- **Every call audited (TB-3):** the same `PreToolUse` hook pattern as WS-A —
  a call that skips the audit is denied
  (`test_audit_skip_denied_malformed_event`); every decision (allow or deny)
  is logged (`test_every_decision_is_audited_allow_and_deny`).
- **They need deps installed to actually run.** The three sidecars are
  Python entry points under `tools/mcp_bridges/`; like the WS-A
  `langchain-tools` bridge, running one for real requires its own package
  installed (promptfoo/AgentShield/Presidio backends) — absent that, the
  `.mcp.json` entry exists but the process fails to import rather than
  silently doing something. Install only on hosts that need to actually
  invoke the tool, matching the `requirements-observability.txt` /
  `requirements-tools.txt` optional-extra pattern.
- A role NOT allow-listed for a tool is refused regardless of flag state
  (`test_non_allowlisted_eval_tool_refused_by_same_decide`,
  `test_tool_present_in_mcp_json_but_no_overlay_denies_every_role`) — identical
  guarantee to the base ADR-0033 edge, no WS-D-specific bypass.

### 4. Redaction guarantee (deploy-relevant)

Every exported span passes the ADR-0012 scrubber **before** any network call
— redact-then-truncate ordering, fail-closed (a scrubber raise drops the
span rather than exporting it unscrubbed):
`test_redaction_on_export_scrubs_planted_secrets`,
`test_scrubber_raise_drops_the_span` / `_span_dropped_in_export`,
`test_tier_b_redact_then_truncate_ordering`
(`tests/test_ws_d_otlp_exporter.py`). This holds **even against the in-tenant
Langfuse instance** — no raw secret leaves the tenant boundary, not even to a
destination that is itself in-tenant. The one documented exception (Tier-M
identifiers such as `gen_ai.agent.name` / `gen_ai.request.model`) is a
narrow, by-design, defense-in-depth boundary covered by DAS-1575's residual
tests (`test_residual1_secret_in_tier_m_key_passes_exporter_unscrubbed_by_design`)
— production callers only ever populate those fields from a typed
`DispatchRecord`'s controlled-vocabulary `role_key`/`model`, never free text.

### How to read the audit log

Same mechanism as WS-A (ADR-0033 edge, shared by the promptfoo/AgentShield/
Presidio sidecars): append-only JSON lines at `$DASLAB_TOOL_AUDIT_LOG`
(default `board/.tool-audit.jsonl`). Filter to WS-D's three eval tools:
```bash
grep -E '"tool": "(promptfoo|agentshield|presidio)"' board/.tool-audit.jsonl | tail -n 20
grep '"decision": "deny"' board/.tool-audit.jsonl | tail -n 20
```

### Rollback

Two independent, additive levers — either alone fully removes the lens and
the three tools; apply both together for defense in depth:

1. **Flip `ws_d_langfuse_lens` OFF** in `config/features.yaml` (already the
   default at merge) — the exporter's `export_spans` becomes fully inert: no
   event-store read, no target resolve, no POST
   (`test_flag_off_is_inert_no_read_no_post`). This is the fastest,
   software-only kill switch and needs no `.mcp.json` edit.
2. **Remove the sidecar entries** — delete the `promptfoo`, `agentshield`,
   and `presidio` objects from the `mcpServers` map in `.mcp.json` (leave
   `ArcRift`/`obsidian`/other entries untouched). With the entries gone the
   tools do not exist from Claude Code's point of view — nothing to call,
   allow-list, or deny. This is the primary, structural rollback for the
   eval/guardrail tools, mirroring WS-A's `langchain-tools`/`browser`
   removal.

Either lever is sufficient; there is no ordering dependency between them.

### Deploy evidence — flag OFF ⇒ byte-identical dispatch

At merge, `ws_d_langfuse_lens: false` in `config/features.yaml` (confirmed —
no override in the environment). No `/daslab-cycle` dispatch code path reads
`ws_d_langfuse_lens`; the flag is consumed only inside
`tools/observability/otlp_exporter.py` and the WS-D tool-admission `decide`
path, neither of which any dispatch import touches, so a wave's dispatch
trace is unchanged whether these files exist or not. Evidence this is a true
no-op:
```bash
python3 -m pytest tests/test_ws_d_otlp_exporter.py -k "flag_off or inert" -q
```
covers the exporter's flag-off inert paths (no read, no target resolve, no
POST) plus the DAS-1575 wave-level byte-identity proof
(`test_sc001_events_file_byte_identical_flag_off_vs_exporter_never_invoked`).

### Publishing beyond the tenant — explicitly out of scope (FR-006)

Publishing the Langfuse endpoint beyond the tenant, or pointing the exporter
at a hosted Langfuse Cloud / LangSmith project, is a **later, explicit
Founder act** — not covered by this runbook's default procedure and not
performed by this ticket. Any such change still must pass
`scripts/check_in_tenant.py`, which will fail it unless the endpoint's role
is added to `accepted_external_roles` — itself a change nothing short of a
Founder ADR should make (`config/tenant_boundary.yaml` header comment).

## Verify quickly

```bash
python3 scripts/board_lint.py
python3 scripts/diagnostics.py
python3 scripts/check_in_tenant.py
python3 -m pytest tests/test_ws_d_otlp_exporter.py -k "flag_off or inert" -q
```
