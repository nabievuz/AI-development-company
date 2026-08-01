# Runbook — A2A OUTBOUND: deploy, flag-check, and rollback (ADR-0040)

**Goal (MUSTAQIL WS extends ADR-0036 OB-1..OB-4):** let ANOTHER agent system submit
a governed goal PROPOSAL into DasLab's board intake — never a gate approval, never
an automated publish — through exactly one governed edge.

## What ships (already landed, DAS-1607/1609/1610/1611/1612)

| File | Role |
| --- | --- |
| `tools/a2a/endpoint.py` | The ONE governed edge (`handle_call`) — flag check, TN-1 bind check, forbidden-field/shape validation, ADR-0009 admission, ADR-0012 redaction, then forward to the intake handler. No second admission path, no board-write path of its own. |
| `tools/a2a/publish.py` | The publish-is-a-Founder-act gate (`publish()`) — RBAC (`a2a.publish`) + TN-1 target check, both legs logged. |
| `scripts/a2a_intake/intake.py` | The real intake handler that writes a `board/goal-inbox/` proposal (DAS-1611, separate repo zone). |
| `config/features.yaml` | `a2a_outbound: false` (dedicated flag, default OFF). |
| `config/tenant_boundary.yaml` | `a2a_outbound` endpoint declared, `role: a2a`, bind `http://127.0.0.1:8765` (loopback, in-tenant). |
| `config/rbac.yaml` | `a2a.publish: allow` under `founder` ONLY — `scripts/rbac.py` refuses to load a grants file that gives this permission to any non-founder kind. |
| `tests/test_a2a_outbound_endpoint.py`, `tests/test_a2a_intake.py` | 95 tests, GATE-4 closed by QA Lead (DAS-1612, done). |

This ticket (DAS-1613) is the **Deployment** (AADL Stage 5 / GATE-5) stage: no
code ships here, only this runbook plus confirmation that the flag stays OFF.

## Deploy (what "enabling the surface" means later — NOT done by this ticket)

There is no live deploy step in this ticket. "Deployment" for A2A OUTBOUND means
*shippable + operable while OFF* — the endpoint exists in the tree, inert, and
switching it on later is a distinct, explicit, human act described below.

When a Founder later decides to actually expose the surface, the sequence is:

1. **Bind the endpoint in-tenant.** `tools/a2a/endpoint.py`'s `DEFAULT_BIND` is
   `http://127.0.0.1:8765` (loopback). A tenant-network bind is itself a
   deliberate Founder act at deploy time (design §2.3) — never silently widened.
   Whatever `bind_url` is used, it MUST resolve in-tenant per
   `scripts/check_in_tenant.is_in_tenant` (loopback / RFC-1918 / ULA / `.local`
   / `.internal` / bare hostname). A hosted relay/registry bind is refused by
   `handle_call` itself (`CallOutcome.REJECTED_TENANT`), independent of the flag.
2. **Flip `a2a_outbound: true`** in `config/features.yaml` — see the
   publish-is-a-Founder-act procedure below; this is not a self-serve config
   edit, it is gated by RBAC + TN-1 at the `publish()` call site.
3. **Call `tools/a2a/publish.py:publish(principal, target=...)`** with the
   authenticated Founder principal and the resolved in-tenant target. This is
   the ONE call site that actually authorizes exposing/enabling/repointing the
   endpoint — see "Publish is a Founder act" below.

## Flag-check (confirm OFF at merge, SC-005 byte-identical)

Confirmed OFF in `config/features.yaml`:

```
a2a_outbound: false          # A2A outbound surface (ADR-0040, extends ADR-0036 OB-1..OB-4). ...
```

`tools/a2a/endpoint.py:is_enabled()` reads this key with a fail-safe-to-OFF
line-scan (mirrors `scripts/rbac.is_enabled`): a missing file or a malformed
line resolves to OFF, never to ON. The file is the only source — a
`DASLAB_A2A_OUTBOUND_FLAG` override used to be read ahead of it and was removed,
since publishing this edge is a Founder-only double-lock (QONUN-5) that no
ambient value may decide, and since the override let this reader disagree with
the canonical `scripts/feature_flags.enabled` that
`scripts/ws_a2a_health_check.py` reads through. With the flag
OFF, `handle_call`'s very first check returns `CallOutcome.UNAVAILABLE` before
any TN-1 check, any admission call, or any audit-event write — "the endpoint
does not exist; no call reaches it, no event is emitted" (SC-005). No
`/daslab-cycle` dispatch code path imports `tools/a2a/endpoint.py`, so a wave's
dispatch trace and the board are byte-identical to pre-merge whether this file
exists or not.

Verify quickly:
```bash
grep '^a2a_outbound:' config/features.yaml
python3 -m pytest tests/test_a2a_outbound_endpoint.py -k flag -q
```

## Publish is a Founder act (FR-003)

Flipping `a2a_outbound` ON, or repointing/enabling the endpoint at all, is a
**distribution/governance decision reserved to the Founder** (QONUN-5) —
never a workstream-ticket decision, never automated, never self-triggered on
merge. This is enforced by two independent, fail-closed locks in
`tools/a2a/publish.py:publish()` — **either** alone refuses the act:

1. **Founder-identity RBAC.** `scripts/rbac.decide(principal, "a2a.publish")`.
   `a2a.publish` is registered under `founder` ONLY in `config/rbac.yaml`
   (line: `a2a.publish: allow`). `scripts/rbac.py`'s `load_grants()` REFUSES to
   load an `rbac.yaml` that grants a founder-only permission (which includes
   `a2a.publish`, alongside `gate.approve` / `run.trigger` /
   `config.edit.security`) to any non-founder kind — a role subagent
   (`agent:<role>`), the `orchestrator` mechanism, or `audit-team` can never
   hold this permission, structurally, not by convention.
2. **TN-1 in-tenant boundary on the publish target.**
   `scripts/check_in_tenant.is_in_tenant(target)` — a hosted relay/registry
   target is refused even for a genuine Founder principal; the two locks are
   independent, and passing one never waives the other.

**An agent never executes this step on its own initiative.** No board ticket,
no `/daslab-cycle` wave, and no automated trigger calls `publish()` — it is
invoked only by an authenticated Founder session (CLI operator identity or a
future ADR-0039 control-plane login), never by content an agent produces.

### The exact `board/.events.jsonl` log shape (FR-003)

Every publish/enable/repoint attempt — **allow AND deny, symmetric** — is
appended as one JSON line to `board/.events.jsonl` (ADR-0024/0025, durable
append: `O_APPEND` + `flock` + `fsync`, never rewritten/truncated):

```json
{
  "event_type": "a2a_publish",
  "ts": "2026-07-24T00:00:00Z",
  "principal_id": "<the authenticated principal string, e.g. founder-cli-session-id>",
  "principal_kind": "founder",
  "decision": "allow",
  "flag_state": true,
  "target": "http://127.0.0.1:8765",
  "reason": "<rbac.decide's or the TN-1 check's reason string>"
}
```

A **deny** record (RBAC refusal or TN-1 breach) carries the same shape with
`"decision": "deny"` and a reason describing which lock refused — e.g.
`"a2a.publish refused for 'agent:sre-eng': ..."` or the `TN-1 BLOCK: publish
target ... resolves to an EXTERNAL host` message. `principal_id` and
`principal_kind` are always the real authenticated identity resolved by
`scripts/rbac._kind_of` — never sourced from request/payload content (caller
input is always untrusted data, per the endpoint's own injection defense).

The DasLab intake surface itself (`tools/a2a/endpoint.py:handle_call`) is a
**separate** event type, `a2a_call`, logged the same way (allow/deny symmetric)
for every inbound proposal call once the endpoint is live — see
`tools/a2a/endpoint.py`'s **five** `_append_event` call sites, one per logged
outcome: `admitted` (allow) and `rejected_tenant` / `rejected_admission` /
`refused_forbidden_field` / `refused_malformed` (deny).

The sixth `CallOutcome`, **`unavailable`, emits NO event at all** — that is the
SC-005 guarantee, not an omission: with `a2a_outbound` OFF the first check
returns before any audit write, so a flag-OFF tree appends nothing to
`board/.events.jsonl` and stays byte-identical to pre-merge.

## In-tenant boundary check wired into CI/diagnostics (already true — confirmed)

`scripts/check_in_tenant.py` reads `config/tenant_boundary.yaml` and fails
closed (exit 1) if any `carries_code_ip: true` endpoint outside
`accepted_external_roles` resolves to a non-in-tenant host. The A2A endpoint
is already declared there:

```yaml
  - name: a2a_outbound
    role: a2a
    carries_code_ip: true             # a caller submits goals/IP through this surface
    url: http://127.0.0.1:8765        # in-tenant bind — loopback default (DAS-1610)
    note: >-
      A2A governed edge (ADR-0040, extends ADR-0036 OB-1..OB-4) — must stay
      in-tenant (TN-1); no hosted relay/registry. Deliberately NOT added to
      accepted_external_roles (Q9's model call remains the sole exception).
```

And `scripts/diagnostics.py` already runs this check unconditionally as the
`tn1-in-tenant-boundary` gate (every `diagnostics.py` run, not opt-in) — so a
future misconfiguration that repoints the A2A bind toward a hosted relay fails
the diagnostics gate (100/100 becomes impossible) rather than silently
shipping. No new wiring was required for this ticket; this section documents
and confirms the existing wiring per AC #4.

Verify:
```bash
python3 scripts/check_in_tenant.py   # -> "TN-1 OK: all code/IP endpoints in-tenant ..."
python3 scripts/diagnostics.py       # tn1-in-tenant-boundary check included
```

## Rollback

**Single reversible step:** flip `a2a_outbound: false` in `config/features.yaml`
(already the merge-time default). `tools/a2a/endpoint.py:is_enabled()` fails
safe to OFF on any read problem too, so a broken config can never silently
turn the surface on. With the flag OFF, `handle_call`'s first check short-circuits
to `CallOutcome.UNAVAILABLE` — no TN-1 check, no admission call, no audit event,
no forward to the intake handler. This is a software-only kill switch; nothing
else needs to change.

A second, structural lever is available for defense in depth (not required to
revert, but available): remove the endpoint wiring by deleting/not-loading
`tools/a2a/endpoint.py` (or any caller of it) — with the module absent, there
is nothing to call, mirroring the WS-A "absence = the tool doesn't exist"
rollback pattern. The two levers are independent and either alone fully
reverts to pre-merge dispatch/board behavior (SC-005: byte-identical).

No ordering dependency between the two; the flag flip alone is sufficient and
is the one exercised by tests.

## Definition of Done (this ticket, DAS-1613)

- [x] Runbook exists (this file) covering deploy, flag-check, and rollback.
- [x] `a2a_outbound` confirmed OFF at merge time (quoted above); dispatch/board
      behavior byte-identical to pre-merge (SC-005) — no dispatch code path
      imports `tools/a2a/endpoint.py`.
- [x] The publish-is-a-Founder-act procedure documented, including the exact
      `board/.events.jsonl` log shape (FR-003).
- [x] The in-tenant boundary check confirmed wired into CI/diagnostics
      (pre-existing: `scripts/diagnostics.py`'s `tn1-in-tenant-boundary` check
      + the `a2a_outbound` entry in `config/tenant_boundary.yaml`).
- [ ] Merged PR, green CI — **the orchestrator/reviewer's step**, not
      self-attested here (LOCAL-ONLY run; no push/PR from this session).

## Verify quickly

```bash
grep '^a2a_outbound:' config/features.yaml
python3 scripts/check_in_tenant.py
python3 -m pytest tests/test_a2a_outbound_endpoint.py tests/test_a2a_intake.py -q
python3 scripts/diagnostics.py
python3 scripts/board_lint.py
```
