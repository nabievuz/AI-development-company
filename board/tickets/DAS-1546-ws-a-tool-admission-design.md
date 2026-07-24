---
id: DAS-1546
title: WS-A Design — tool-admission model (overlay allow-list, PreToolUse audit, redaction, egress)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-002, FR-003, FR-005, FR-006]
labels: [security]
zone: docs/design
depends_on: [DAS-1545]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-A).** Design the governed admission
model the Development tickets implement. No code beyond schemas/specs.

- **Least-privilege allow-list (TB-2):** how a role's `<dept>/agents/<role>/AGENTS.md`
  overlay declares an allowed external tool, and how that compiles (ADR-0018/0029) so a
  non-declared tool is unreachable. No blanket grants.
- **PreToolUse audit/deny (TB-3):** the `.claude/settings.json` `PreToolUse` hook shape
  (honored identically by the Claude Code CLI and the Agent SDK) that can audit or DENY
  each external-tool call; how tool transcripts map to ADR-0012 event classification +
  redaction; the invariant that a tool never writes routing fields (C3) or bypasses a
  gate (C4).
- **Egress policy (TB-4/Q5):** deny-all except an explicit domain allow-list; where the
  allow-list lives; how browser egress is treated as untrusted input (FR-006).

Security Lead consulted (accountable stage owner = CTO; responsible = backend-em).

## Acceptance criteria
- [ ] Design doc under `docs/` covering the allow-list schema, the PreToolUse audit/deny contract, the ADR-0012 redaction mapping, and the deny-all + domain allow-list egress policy — each traced to its FR and TB invariant.
- [ ] Negative-path behaviour specified for SC-001/SC-002 (global grant refused, audit-skip denied, non-allow-listed egress blocked) so DAS-1549 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Design). TB-2/TB-3/TB-4 admission model.

### 2026-07-24 — Backend EM
**AADL Stage 2 — Design (GATE-2) authored → in_review.** Design doc:
`docs/design/ws-a-tool-admission.md` (new zone `docs/design/`). Grounded in the
now-Accepted ADR-0033 (TB-1…TB-5, incl. the CTO's ratification tightening that
splits untrusted INGRESS from EGRESS-destination control) + SPEC-002
(FR-001…FR-006), and the on-branch spikes it hardens (not modifies):
`tools/mcp_bridges/audit_external_tool.py`, `langchain_tool_bridge.py`,
`mcp.snippet.json`, `tests/test_ws_a_tool_bridge.py`.

Admission model (four fail-closed gates, each traced to FR + TB):
- **§1 Allow-list (TB-2/FR-002):** SSOT = a new optional `## External tools` fenced
  YAML block in `<dept>/agents/<role>/AGENTS.md` (`server`/`tools`/`egress_profile`/
  `reason`; absent section = zero external tools, no blanket grants). `gen_subagents.py`
  is EXTENDED (not forked — ADR-0029 extend-vs-new) to compile it into the generated
  `board/.tool-allowlist.json` in the exact shape `audit_external_tool.decide()` reads;
  guild-template `## Toolkit allowlist` mirrors it (ADR-0029 G-2/G-5); `check_agents_sync`
  guards drift. Structural unreachability: the hook trusts only the compiled map, so a
  non-declared tool has no key ⇒ deny — analogue of ADR-0026's route-graph rule.
- **§2 PreToolUse audit/deny (TB-3/FR-003):** `.claude/settings.json` `PreToolUse`
  hook, matcher `mcp__.*` → `audit_external_tool.py`, honored identically by CLI +
  Agent SDK (ADR-0034). Deny-all fail-closed default; unconditional append-only audit
  (`board/.tool-audit.jsonl`). Audit-skip is not a reachable state (hook wiring asserted
  as a governance invariant). Transcript → ADR-0012 M/B/F event: Tier-M metadata +
  Tier-B `output_summary`/`args_digest` through the fail-closed §2 scrubber
  (API keys/Bearer/JWT/DSN/private-key/PII); raw payload is Tier-F (never stored). C3
  (no routing-field writes) + C4 (no gate bypass — a tool has no dispatch surface)
  preserved.
- **§3 Egress (TB-4/FR-005+006/Q5):** the ratified INGRESS vs EGRESS split — (a) ingress
  = fetched content is untrusted DATA that can't change goal/approvals/permissions
  (injection guard, Tier-F raw bodies); (b) egress = deny-all + explicit domain
  allow-list in a *tracked* `config/egress-allowlist.yaml` (named profiles referenced by
  the overlay grant), enforced at the sidecar before any network syscall; no prod creds
  by default (ADR-0012 §3). Named the reference `web_fetch` egress gap for DAS-1547/1548.

**Negative-path spec handed to DAS-1549 (§4):**
- SC-001a — no-overlay tool refused (empty compiled map ⇒ `decide` deny for every role;
  granted-to-A denies B; no global role).
- SC-001b — audit-skip denied (`.claude/settings.json` PreToolUse binding asserted;
  malformed/absent allow-list fail-closed to deny; every decision audited once).
- SC-002a — non-allow-listed egress blocked (deny-by-default profile; wildcard sub-domain
  match but not look-alike suffix; no network call on a miss).
- SC-002b — redaction probe (planted `sk-ant`/Bearer/JWT/DSN/PEM/PII → `[REDACTED:…]`;
  fail-closed `[REDACTED:unclassified]`; redact-then-truncate; no over-redaction of
  Tier-M digests).
- SC-003 noted (flag-OFF byte-identical) as out of this doc's FR scope.

Constraints honored: LOCAL-ONLY (no branch/commit/push/PR); touched only
`docs/design/ws-a-tool-admission.md` + this ticket. Validators re-run, both exit 0:
`board_lint` OK; `check_links` OK (see report).

Routing: not self-approving — `status: in_review`, `assignee: cto` (per ROUTING,
backend-em → CTO; Security Lead consulted on redaction + egress). GATE-2 review is
next wave. Downstream: DAS-1547/1548 implement the compile extension, sidecar egress
check, settings wiring, and ADR-0012 tool-event scrubber (with tests), all behind
`ws_a_tool_bridge` OFF.

### 2026-07-24 — Security Lead (BLOCKING SECURITY AUDIT — GATE-2)

**Mandatory pre-gate security review of `docs/design/ws-a-tool-admission.md`** (AADL
Stage-2, security-touching). Judged as an adversary against ADR-0033 TB-1…TB-5,
ADR-0012 (M/B/F + redaction), SPEC-002 FR-001…006 / SC-001…004, and the on-branch
spikes the design hardens (`audit_external_tool.py`, `langchain_tool_bridge.py`).

**OVERALL VERDICT: PASS-WITH-CONDITIONS.** The admission model is structurally
sound — four independent fail-closed gates correctly composed; structural
unreachability of a non-declared tool holds (`decide()` returns deny on `roles is
None`, `load_allowlist()` returns `{}` ⇒ deny-all on any read error); C3/C4
preserved (a tool has no board-mutation and no dispatch surface); the ADR-0012
M/B/F mapping and redact-then-truncate ordering are correct; the INGRESS-untrusted
/ EGRESS-deny-all split is correct. No single structural hole makes the design
unsafe to gate. BUT two security-critical implementation gaps and several hardening
gaps are under-specified and MUST be closed by DAS-1547/1548 and tested by DAS-1549
before this reaches production behind the flag. Conditions are binding requirements,
recorded below for the CTO to attach at GATE-2 closure.

**Per-axis verdicts:**

- **Axis 1 — Least-privilege allow-list (TB-2): PASS-WITH-CONDITIONS.** Structural
  unreachability holds and fail-closed default is correct. Two findings:
  - *F1 (MED) — drift guard vs gitignored posture is self-contradictory.* §1.3
    declares `board/.tool-allowlist.json` gitignored "runtime state, same posture as
    `board/.tool-audit.jsonl`" AND claims `check_agents_sync` generate-and-diff
    "fails CI if the JSON is stale/hand-edited … a hand-edited allow-list JSON is a
    diff, hence a red build." Those are mutually exclusive: generate-and-diff catches
    drift for `.claude/agents/*.md` and `ROUTING.md` **because those are tracked**;
    a gitignored file has no committed baseline, so CI regenerates it fresh and the
    "hand-edit = red build" claim is false. The allow-list is a security **input** to
    the request-path decision, not an output log — it must be diffable/reviewable.
  - *F2 (MED) — wildcard-role bypass branch survives in `decide()`.* The design's
    §1.3 invariant is "no wildcard role — the map is the union of declarations only,"
    but the reference `decide()` (audit_external_tool.py:62) still treats
    `roles == "*"` as **any-role allow**. Note the two distinct `"*"` meanings: an
    overlay `tools: ["*"]` = "all tools of this server" (compiles to a server KEY →
    explicit role LIST), which is legitimate; but a `"*"` **value in the roles list**
    grants every role. The CI drift guard is **not in the request path** — a compile
    bug or a runtime-tampered/hand-dropped `"*"` value grants every role at call time.

- **Axis 2 — PreToolUse audit + ADR-0012 redaction (TB-3): PASS-WITH-CONDITIONS.**
  Audit-is-unconditional, deny-all default, redact-then-truncate, C3/C4, and the
  secret-class coverage (API key/Bearer/JWT/DSN/PEM/PII) are all correct and match
  ADR-0012 §2. Findings:
  - *F3 (MED-HIGH) — the "audit-skip is unreachable" invariant does not cover
    hook-EXECUTION failure.* §2.2 proves the hook can't be bypassed **in-band** and
    that removing the binding is a detectable regression — good. It does NOT pin what
    the harness does when the hook **command itself fails** (python3 missing, script
    moved, crash, non-zero exit, unparseable stdout). The script signals deny via
    stdout JSON with `exit 0`; a spawn/exec failure is a different path, and if the
    Claude Code CLI / Agent SDK treats a failed PreToolUse command as non-blocking
    (fail-OPEN), the tool runs ungoverned. "Audit-skip unreachable" is only as strong
    as the harness's fail-mode on hook-exec failure. This must be pinned to
    fail-CLOSED (deny) and proven, or wrapped to guarantee it.
  - *F4 (LOW) — "unclassifiable ⇒ [REDACTED:unclassified]" slightly overstates
    coverage.* Per ADR-0012 §2 the fail-closed drop fires on scrubber **error**, not
    for every string that matches no pattern; a novel/obfuscated secret shape that
    matches no regex **survives** (ADR-0012's own accepted limitation). Acceptable
    because the PRIMARY control is structural (raw payload is Tier-F, never stored;
    no-secrets-by-default) — but the doc wording should not imply regex completeness.

- **Axis 3 — Egress (TB-4 / Q5 / FR-005+006): PASS-WITH-CONDITIONS.** Deny-all +
  explicit domain allow-list, enforced at the sidecar before the syscall, is the
  right structure; ingress-as-untrusted-data and no-prod-creds-by-default are
  correct. The design honestly names the reference `web_fetch` egress gap as a
  DAS-1547/1548 development item. Findings (the adversarial core of this audit):
  - *F5 (HIGH) — redirect-following egress bypass.* `langchain_tool_bridge.web_fetch`
    uses `urllib.request.urlopen` (langchain_tool_bridge.py:37), which **follows 3xx
    redirects by default with no re-check**. An allow-listed initial host can 302 to
    an arbitrary host and urllib fetches it — defeating the deny-all list. §3.2 checks
    "the request host" once and is silent on redirects.
  - *F6 (HIGH) — SSRF to internal/link-local ranges.* The egress check matches the
    URL host **string** against a domain profile; it does not resolve the host or
    block internal targets. Combined with F5 (or a raw-IP/rebind URL), this reaches
    cloud metadata (169.254.169.254), loopback, and RFC-1918 services. The example
    `qa-browser` profile explicitly allow-lists bare `localhost` — an SSRF foothold
    if that profile is granted at all broadly.
  - *F7 (MED) — label-boundary match must be explicit.* SC-002a already names the
    look-alike test (`*.wikipedia.org` must NOT match `evilwikipedia.org`); make the
    implementation rule explicit — match on a label/dot boundary
    (`host == base or host.endswith("." + base)`), never a bare `endswith(base)`.

- **Axis 4 — Blast radius / TB-4 (browser/computer-use): PASS-WITH-CONDITIONS.** The
  browser is correctly fenced behind §1+§2, egress deny-all, no-secrets-default, and
  flag-OFF. Finding:
  - *F8 (MED) — least privilege stops at the domain, not the ACTION surface.* The
    browser / computer-use tool can navigate, click, **submit credentialed forms,
    upload files, read/write clipboard, drive local apps** — a far wider surface than
    `web_fetch`. The egress list governs network destinations but not these write
    actions (a form-submit to an allow-listed host can still exfiltrate). DAS-1548
    must scope the default browser grant to read/verify actions (navigate + read +
    screenshot) and require a separate explicit reviewed grant for any
    write/submit/upload/clipboard/local-control action.

**BINDING CONDITIONS (attached as GATE-2 requirements; the Development tickets
DAS-1547/1548 and the Testing ticket DAS-1549 MUST satisfy these):**

*DAS-1547 (sidecar / compile extension / settings wiring / scrubber):*
- **C1 (F1):** Make `board/.tool-allowlist.json` a **TRACKED, reviewed** artifact
  (it is a security input, not a runtime log), so generate-and-diff has a committed
  baseline and a hand-edit is a real red build — OR replace §1.3's CI-diff drift
  claim with a mechanism that actually works on a gitignored file. Resolve the
  tracked-vs-gitignored contradiction before wiring; do not ship the false claim.
- **C2 (F2):** The compiler MUST NEVER emit `"*"` as a roles-list value; AND harden
  `decide()` so a `"*"` **roles value** is not treated as any-role (remove/guard the
  `roles == "*"` branch, or add a schema/load check that rejects any `"*"` value in
  the compiled map). Keep the legitimate server-wide `tools:["*"]` overlay grant
  compiling to an explicit role list.
- **C3 (F3):** Pin the harness fail-mode — a PreToolUse hook that **fails to execute**
  (spawn error / non-zero / crash / unparseable output) MUST fail **CLOSED** (tool
  denied) on both the CLI and the Agent SDK. Verify actual semantics; if either fails
  open, add a wrapper that guarantees closed. Hand DAS-1549 the test.
- **C4 (F5):** Egress enforcement MUST disable redirect-following OR re-check **every**
  redirect hop against the invoking profile before following it.
- **C5 (F6):** The egress check MUST resolve the target and **block** loopback,
  link-local (169.254.0.0/16, incl. cloud-metadata 169.254.169.254), and RFC-1918
  ranges unless a profile narrowly and explicitly scopes them; do not trust the URL
  host string alone. Re-justify or drop the bare-`localhost` example grant.
- **C6 (F7):** Domain matching MUST anchor on a label boundary (exact base or
  `.`-prefixed suffix), never a bare substring/suffix match.
- **C7 (F4):** Deliver the ADR-0012 §2 extended pattern set (Bearer/JWT, DSN,
  GitHub-token family, high-entropy fallback, PII) **with tests**, redact-then-truncate
  ordered, high-entropy `{32,}` tuned to not over-redact Tier-M digests; preserve the
  structural primary control (raw payload Tier-F, no-secrets-by-default). Do not let
  the doc imply regex completeness the scrubber does not have.

*DAS-1548 (browser sidecar):*
- **C8 (F8):** Enumerate the browser/computer-use action surface; default grant =
  navigate + read + screenshot only. Write/submit/upload/clipboard/local-app-control
  actions are OUT of the default grant and each require a separate explicit reviewed
  grant. Inherit C4/C5/C6 egress rules at the browser layer.

*DAS-1549 (negative tests) MUST add, beyond the doc's §4 SC-001/SC-002:*
- **T1 (C3):** hook-exec failure (crash / non-zero / malformed stdout) ⇒ tool DENIED.
- **T2 (C4):** allow-listed host 302→non-allow-listed host ⇒ denied, redirect target
  never fetched.
- **T3 (C5):** URL host / redirect resolving to 169.254.169.254 / 127.0.0.1 /
  10.0.0.0-8 ⇒ denied unless explicitly scoped.
- **T4 (C2):** a `"*"` roles value in the compiled map does NOT grant any-role.
- **T5 (C1):** the drift guard fails CI on a tampered/stale compiled allow-list
  (meaningful only once the file is tracked per C1).

**Routing:** PASS-WITH-CONDITIONS ⇒ `status: in_review` unchanged, `assignee: cto`
(already set) so the CTO closes GATE-2 with this audit and the C1…C8/T1…T5 conditions
on record. Not a FAIL — the design's STRUCTURE is sound; C1…C8 are implementation
requirements, not design holes. Constraints honored: LOCAL-ONLY (no branch/commit/
push/PR); edited only this ticket file — all required changes recorded as findings for
the authors, no design/ADR/config/tool/script modified. `board_lint` re-run, exit 0.

### 2026-07-24 — CTO (GATE-2 CLOSURE — RATIFIED)

**AADL Stage-2 / GATE-2 for WS-A REACH: CLOSED.** As the accountable stage owner
(RACI 3.1) I ratify `docs/design/ws-a-tool-admission.md` and **accept the Security
Lead's blocking audit (PASS-WITH-CONDITIONS) in full**, on record.

**Decision on the three security-critical findings (F3 / F5 / F6): all legitimately
deferrable to Development + Testing under binding conditions — none is a design-level
hole.** Rationale, judged independently against ADR-0033 TB-1…TB-5, not rubber-stamped:

- The design is a **four-gate, independently fail-closed admission chain** (§0):
  overlay allow-list (TB-2) → PreToolUse audit/deny (TB-3) → egress deny-all (TB-4) →
  ADR-0012 M/B/F redaction. Every gate exists and is architecturally correct;
  structural unreachability of a non-declared tool holds (`decide()` denies on
  `roles is None`; `load_allowlist()` → `{}` ⇒ deny-all on any read error); C3/C4 hold
  (a tool has no board-mutation and no dispatch surface). **F3/F5/F6 each harden an
  existing gate — none requires a different architecture** — so each is an
  implementation refinement provable by a negative test, not a structural rewrite.
- **F5 (HIGH — redirect-following egress bypass) — DEFERRABLE.** §3.2 already fixes the
  enforcement point (sidecar, before any network syscall: resolve host → match invoking
  profile → refuse on miss) and *honestly names* the reference `web_fetch` egress gap as
  a DAS-1547/1548 development item. Whether the host-check runs once or re-runs on every
  3xx hop is HOW that existing gate enforces, not a new gate. Bound by **C4**, proven by
  **T2**.
- **F6 (HIGH — SSRF to internal / link-local / RFC-1918) — DEFERRABLE.** Same gate.
  "Resolve the host and match the profile" is the design principle; making the resolve
  step *block* loopback, link-local (169.254.0.0/16, incl. cloud-metadata
  169.254.169.254), and RFC-1918 is a refinement of that step, not a structural change.
  Bound by **C5**, proven by **T3**. The bare `localhost` in the §3.2 *example*
  `qa-browser` profile is illustrative, not a live grant — §6 makes clear grants are
  per-role `security_sensitive` + `permission_change` decisions taken later, **none
  pre-granted here** — and C5 requires it re-justified or dropped before any sidecar
  wiring. With no grant issued and the flag OFF, it is inert, not an open hole.
- **F3 (MED-HIGH — hook-exec-failure fail-mode) — DEFERRABLE.** The design's posture is
  unambiguously fail-closed ("losing a legitimate call is preferable to admitting an
  ungoverned one"); §2.2 proves in-band bypass impossible and binding-removal a
  detectable CI regression. The residual gap — what the harness does when the hook
  *command itself* fails to execute (spawn error / crash / non-zero / unparseable
  stdout) — is an **empirical property of the Claude Code CLI / Agent SDK that must be
  verified and wrapped if it fails open.** That cannot be pinned abstractly in the design
  doc; it is correctly a Development+Testing task. Bound by **C3**, proven by **T1**.

**Binding conditions accepted and propagated.** I bind **C1–C8** (implementation,
DAS-1547/1548) and **T1–T5** (tests, DAS-1549) as **MUST-satisfy** GATE-3 / GATE-4
conditions and have written them into each downstream ticket's
`## Security conditions (GATE-2)` section. **GATE-3 (DAS-1547/1548) must not be signed
unless C1–C8 are satisfied; GATE-4 (DAS-1549) must not be signed unless T1–T5 pass.**

**Nothing ships live at gate closure.** The entire WS-A tool surface is behind the
`ws_a_tool_bridge` flag (OFF by default, TB-5 / FR-004): flag OFF ⇒ the sidecar does not
exist and dispatch is byte-identical to pre-merge. No governed tool — least of all the
browser / egress surface that carries F5/F6 — reaches a live network call until Testing
(DAS-1549) proves C1–C8 under T1–T5. **GATE-2 closes the DESIGN; it grants no runtime
reach.**

**Law check:** within CTO charter (AADL GATE-2 accountable; engineering technical
authority — `engineering/CLAUDE.md`). LOCAL-ONLY honored — edited only DAS-1546 + the
three downstream tickets; no design/ADR/config/tool/script modified; no branch / commit /
push / PR. Doc-governance gate (no PR/CI) — validators re-run at closure (board_lint /
check_dependency_graph / check_spec_consistency, all exit 0).

**Status:** DAS-1546 → `done`. Conditions carried downstream to DAS-1547/1548/1549.
