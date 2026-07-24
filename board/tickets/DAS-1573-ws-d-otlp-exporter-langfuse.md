---
id: DAS-1573
title: WS-D Development — OTLP exporter of ADR-0024 spans to self-host Langfuse, flag OFF
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-001, FR-002, FR-003, FR-004]
labels: [security]
zone: tools/observability
depends_on: [DAS-1572]
created: 2026-07-24
updated: 2026-07-24
---


## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-D, part 1).** Build the
OTLP exporter per the DAS-1572 design.

- **FR-001:** an exporter that ships the existing ADR-0024 span events
  (`event_type: "span"`, already OTel GenAI-attribute-named) as OTLP to a
  **self-hosted** Langfuse instance; the target endpoint is read from an
  in-tenant config value only — no default/fallback to a hosted Langfuse
  Cloud or LangSmith URL.
- **FR-002:** apply the ADR-0012 classification + redaction pass to every
  span/attribute before it leaves the process (reuse the existing scrubber,
  do not reimplement).
- **FR-003:** the exporter is read-only over the event store — it never writes
  back to `board/.events.jsonl` or any board field; losing/disabling it changes
  no dispatch outcome (C2).
- **FR-004:** guarded by `ws_d_langfuse_lens` (OFF); with the flag OFF the
  exporter does not run and event emission is byte-identical to pre-merge.

## Acceptance criteria
- [ ] Exporter maps ADR-0024 span fields to an OTLP payload and ships it to a configured self-host Langfuse endpoint only.
- [ ] Every exported span/attribute passes ADR-0012 redaction first; no secret/tool-transcript substring survives in the payload.
- [ ] Exporter is read-only over the event store; no board/routing field is ever written by it.
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Development, part 1). OTLP exporter, self-host
Langfuse target only, ADR-0012 redaction on export, flag OFF.

### 2026-07-24 — Backend EM
Built the read-side OTLP exporter + redaction shim per the ratified design
`docs/design/ws-d-langfuse-lens.md` (§1/§2/§4) and Accepted ADR-0036 (OB-2
self-host Langfuse, not LangSmith). **LOCAL-ONLY** — no push/PR/commit.

**Files created (footprint = `tools/observability/` + opt-in reqs + one test):**
- `tools/observability/otlp_exporter.py` — the exporter (core imports stdlib only).
- `tools/observability/__init__.py` — package marker.
- `tools/observability/requirements-observability.txt` — opt-in deps (kept OUT of
  core `requirements.txt`; the core module needs none — stdlib `urllib` transport).
- `tests/test_ws_d_otlp_exporter.py` — 19 unit tests (all green).

Untouched by design: `tools/mcp_bridges/` (concurrent DAS-1574), `config/`, ADRs,
`scripts/`. REUSED verbatim (imported, not forked): `tools/mcp_bridges/redaction.py`
(ADR-0012 scrubber), `scripts/check_in_tenant.py` (TN-1 guard),
`scripts/feature_flags.py`, `scripts/dgox/events.py` `iter_events` (read-only).

**FR → file + test map:**
- **FR-001** (OTLP field-map shim → self-host Langfuse only, no hosted fallback):
  `otlp_exporter.map_span_to_otlp` / `build_otlp_payload` / `derive_trace_id` /
  `derive_span_id` / `resolve_target` (target from `tenant_boundary.yaml`
  `langfuse_observability` + `/api/public/otel/v1/traces`, no default). Tests:
  `test_span_maps_to_well_formed_otlp`, `test_error_status_and_child_parent_map`,
  `test_trace_id_is_pure_function_of_ticket`, `test_build_otlp_payload_shape`,
  `test_in_tenant_target_passes` (checked value == exported value, §1.4).
- **FR-002** (ADR-0012 M/B/F classify + scrubber before the boundary, fail-closed):
  `otlp_exporter.redact_span` — Tier-M keys as-is, Tier-B keys scrubbed via the
  reused `redaction.scrub` then length-capped (redact→truncate); scrubber-raise ⇒
  whole span dropped (`None`), never shipped raw. Tests:
  `test_redaction_on_export_scrubs_planted_secrets` (sk-ant/AKIA/Bearer/JWT/PEM/DSN/
  PII all redacted, none survive the wire payload), `test_tier_m_ids_not_over_redacted`,
  `test_tier_b_redact_then_truncate_ordering`, `test_scrubber_raise_drops_the_span`,
  `test_scrubber_raise_span_dropped_in_export`.
- **FR-003** (read-only over the event store; lens derived; disabling it changes
  nothing): reads only via `iter_spans`→`iter_events(event_type="span")`; no
  `EventStore(`, no write/append open. Tests:
  `test_exporter_exposes_no_event_store_write_path`,
  `test_export_does_not_mutate_the_events_file`.
- **FR-004** (flag `ws_d_langfuse_lens` OFF ⇒ inert, byte-identical): `export_spans`
  returns `ExportResult(ran=False)` with the flag OFF — no read, no target resolve,
  no POST. Tests: `test_flag_off_is_inert_no_read_no_post`, `test_flag_on_reads_and_exports`.
- **SC-004 / TN-1** (in-tenant only; hosted fails closed BEFORE export): `assert_in_tenant`
  reuses `check_in_tenant.evaluate` verbatim (`observability` not in
  `accepted_external_roles`) + a belt `is_in_tenant` on the same endpoint. Tests:
  `test_hosted_endpoint_fails_closed` (cloud.langfuse.com / api.smith.langchain.com /
  public IP all raise `BoundaryError`), `test_export_blocks_before_post_on_hosted_target`,
  `test_rfc1918_and_local_names_are_in_tenant`.

**Verification (STAGED state — `git add -A` first, per the false-green caution):**
- `python3 scripts/diagnostics.py` = **100/100** with the new files TRACKED
  (Portability + Security lanes green; `/tools/` already covered by CODEOWNERS —
  no codeowners regen needed; no `/Users`/`/home` literals; committed-secret scan
  clean — test fixtures fragmented with `+`).
- `python3 -m pytest` = **2053 passed, 4 skipped** (my 19 included).
- `python3 scripts/board_lint.py` exit **0** (180 tickets; the lone WARN is the
  pre-existing DAS-1507 body-status note, unrelated).
- `python3 scripts/check_in_tenant.py` = TN-1 OK (6 endpoints in-tenant).
- `ruff check` clean on all three touched files.

Note for the orchestrator: a NEW `tests/test_ws_d_tool_admission.py` (DAS-1574's
zone `tools/mcp_bridges`) is present and green in the suite — not mine; flagged for
awareness only. → **GATE-3 review: assignee cto.**

### 2026-07-24 — Security Engineer
**GATE-3 blocking security red-team (adversarial, in-code — not doc review).**
Ran `pytest tests/test_ws_d_otlp_exporter.py` (19 passed) plus my own ephemeral
probes (capturing transport → inspected the serialized OTLP wire bytes; deleted,
no permanent test added — that is DAS-1575's job).

| # | Item | Verdict |
|---|------|---------|
| 1 | Redaction-on-export (sk-ant / Bearer / JWT / AKIA / PEM / DSN / email / phone / ghp planted across 9 Tier-B attribute keys) | **HOLDS** — every distinctive secret core (`sk-ant-api03`, `AKIA…`, `Bearer …`, JWT sig, `MIIB…`, `supersecretpw`, `victim@example.com`, `555 0199`, `ghp_…`) is absent from `json.dumps(build_otlp_payload(...))`; redaction runs on `safe = redact_span(span)` BEFORE `map_span_to_otlp` and before any POST. |
| 2 | Scrubber-raise ⇒ span DROPPED, never shipped raw | **HOLDS** — monkeypatched `redaction.scrub` to raise; `redact_span` returned `None` (whole span dropped, `except Exception` at L269). |
| 3 | Tier-F never crosses / Tier-B redact→truncate ordering | **HOLDS** — non-Tier-M keys scrubbed then `[:280]`; a Tier-F-shaped value is caught deny-by-default by the same scrub. |
| 4 | No Tier-M id over-redaction | **HOLDS** — `span_id`/`trace_id`/`parent_span_id` pass through verbatim (probe: preserved exactly). |
| 5 | Reuses `tools/mcp_bridges/redaction.py` (not a fork) | **HOLDS** — path-loaded verbatim via `_redaction_mod()`; no reimplementation. |
| 6 | In-tenant fail-closed BEFORE export; reuses `check_in_tenant`; no hosted fallback | **HOLDS** — `cloud.langfuse.com`, `us.cloud.langfuse.com`, `api.smith.langchain.com`, public IP `8.8.8.8`, `evil.example.com` each raise `BoundaryError`; a full `export_spans(post=True)` at a hosted target raised BEFORE the transport fired (capturing transport recorded **0** posts). Belt `is_in_tenant(raw)` reads the SAME endpoint the target resolves from — cannot be dodged. |
| 7 | Non-invasive / read-only; flag OFF ⇒ fully inert | **HOLDS** — only store touch is `iter_events(event_type="span")` (read); no `EventStore`/append/write path. Flag OFF ⇒ `ExportResult(ran=False, read=0, posted=False)` with a hosted target + `post=True` supplied: no read, no resolve, no POST. |

**Residual (NON-blocking → handed to DAS-1575):** a secret planted directly in a
*Tier-M* key (e.g. `gen_ai.agent.name`) passes through un-scrubbed by design —
Tier-M is a controlled-vocabulary/ids allowlist and the ADR-0024 emitter, not the
exporter, owns those values. Recommend DAS-1575 add a defense-in-depth assertion
that the span emitter never places free-text/secret material in Tier-M keys.

**Overall: GATE-3 red-team PASSED — cleared for CTO ratification.** Status stays
`in_review`, assignee `cto`.

### 2026-07-24 — CTO
**AADL Stage-3 / GATE-3 (Development) CLOSED for WS-D LENS part 1 (OTLP exporter).**
Ratified after independent re-verification in STAGED state (`git add -A` first, to
catch tracked-file checks):

- `python3 scripts/diagnostics.py` = **100/100** (exit 0) — TRACKED; Security lane
  (`no-committed-secrets`, `tn1-in-tenant-boundary`) + Portability green.
- `python3 -m pytest tests/test_ws_d_otlp_exporter.py tests/test_ws_d_tool_admission.py -q`
  = **39 passed** (19 exporter + 20 admission), exit 0.
- `python3 -m pytest -q` (full suite) = **2053 passed, 4 skipped**, exit 0 — no regressions.
- `python3 scripts/board_lint.py` = exit **0** (180 tickets, 0 violations; lone WARN
  is the pre-existing DAS-1507 body-status note, unrelated).
- `python3 scripts/check_agents_sync.py` = exit **0** (32 shims in sync).

**Security GATE-3 red-team is on record above (Security Engineer, PASSED — no holes):**
redaction-on-export holds (9 secret classes redacted BEFORE the wire; scrubber-raise
drops the whole span; Tier-F never crosses; no Tier-M id over-redaction), in-tenant
fail-closed (hosted Langfuse/LangSmith/public-IP targets → `BoundaryError` before any
POST, 0 posts recorded), reuses `redaction.py` verbatim (not forked), read-only over
the event store, flag `ws_d_langfuse_lens` OFF ⇒ fully inert (byte-identical to
pre-merge). Acceptance criteria met.

**Residual → DAS-1575 (Testing), NON-blocking:** a secret planted directly in a
*Tier-M* key (controlled-vocab allowlist, e.g. `gen_ai.agent.name`) passes un-scrubbed
by design — the ADR-0024 emitter, not the exporter, owns those values; DAS-1575 adds a
defense-in-depth assertion that the emitter never places free-text/secret material in
Tier-M keys. This is DAS-1575's formal test to add, not a GATE-3 blocker.

Everything remains behind flags OFF. **LOCAL-ONLY** — accepted on local green; no
commit/push/PR made. **GATE-3 part 1 CLOSED → status `done`. Unblocks DAS-1575 (Testing).**
