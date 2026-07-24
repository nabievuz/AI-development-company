# SPEC 006 — MUSTAQIL WS-E TENANT (enterprise-internal self-host hardening + in-tenant runtime BOM)

- **Goal:** mustaqil-ws-e-tenant
- **Owner:** backend-em
- **Status:** draft

> WHAT/WHY only. The HOW (LiteLLM gateway wiring, Presidio/classifier plumbing,
> promptfoo config, vLLM/SGLang serving, RBAC data model, SIEM export format,
> `.claude/settings.json` mechanics) lives in ADR-0038 and the AADL Stage-2 design
> ticket, not here. Binds to ADR-0038 (TN-1…TN-5 + the binding scope boundary), the
> in-tenant runtime BOM in the production-stack mining
> (`docs/research/2026-07-23-daslab-production-stack-and-toolkits-mining.md` §2),
> Master Prompt v3.0 Part 2 (TN-1 in-tenant precondition, MODEL STANCE Q9), and
> Founder discovery answers Q6 (Founder-only approval + team read-only audit),
> Q9 (Claude subscription default; open-weight in-tenant serving a DEFERRED
> eject-path), and Q10 (internal self-host ONLY — no SaaS / SOC 2 / SSO / multi-tenant).

## User Scenarios

- **P1 —** Given the never-auto-approve gate categories (QONUN-5), when any AADL gate needs approval, then only a Founder-identity RBAC principal can approve it — an agent identity (or any non-Founder actor) can never hold gate-approval authority, and the attempt is refused (TN-3, Q6).
- **P1 —** Given a small team granted read-only audit access, when they read the trail, then they can inspect every routing / tool / gate / approval / run event, but cannot approve a gate, trigger a run, or mutate the board (least privilege, TN-3).
- **P1 —** Given the TN-1 in-tenant precondition, when a wave is about to dispatch and any model / sandbox / observability / tool endpoint resolves to a hosted external endpoint that carries code or IP, then the run is BLOCKED as a config error — nothing leaves the tenant boundary.
- **P1 —** Given the `ws_e_tenant_hardening` feature flag is OFF (default), when a wave runs, then dispatch behaves exactly as today — the hardening surface simply does not exist.
- **P2 —** Given the model gateway, when an agent makes a model call, then it resolves to an in-tenant endpoint via the admission layer (default = the Claude subscription over account auth, Q9); the open-weight vLLM/SGLang serving path is a DEFERRED eject-path behind its own flag and is not the near-term build.
- **P2 —** Given a tool transcript or an event exported to the tenant SIEM, when it is written or exported, then it is classified and redacted under ADR-0012, read-only, as OTel/JSON — the tenant's security team audits without DasLab holding the data (TN-4).
- **P2 —** Given a payload that contains PII or a secret, when it passes the guardrail chain, then the layered Presidio + classifier + policy detects and redacts it before storage/export (TN-5, BOM guardrails).
- **P2 —** Given the evals CI path, when the golden-set eval runs, then a hand-labeled golden set (promptfoo) is checked before any LLM-judge, with an anti-gaming probe, so a false-green cannot pass (BOM evals, ADR-0020).
- **P2 —** Given a PR that adds SOC 2 tooling, SSO/SAML/SCIM, multi-tenant isolation, or billing, when it is reviewed under this workstream, then it is rejected as out of scope (ADR-0038 binding scope boundary, Q10).

## Functional Requirements

- **FR-001** — RBAC MUST map the org + Founder gate onto real access control (TN-3): every never-auto-approve category (QONUN-5) maps to a human-only, Founder-identity role; an agent identity can NEVER hold gate-approval authority; approval is a Founder-identity RBAC event, never a chat string or an agent's own output. A small team MAY hold read-only audit access — read the trail, approve/trigger/mutate nothing.
- **FR-002** — The event store + attestation (ADR-0024/0025/0031/0032) MUST be exportable read-only to the tenant's SIEM as OTel/JSON, redacted per ADR-0012 (TN-4). The export carries no source code or IP and is never a write path back into the board.
- **FR-003** — Secrets MUST live in the tenant's vault, never in the repo or in spans (gitleaks + ADR-0012), and egress MUST be constrained by an allow-list at the tenant boundary (TN-5); the browser/computer-use tool (ADR-0033 TB-4) is treated as untrusted egress.
- **FR-004** — Model access MUST route through an in-tenant model gateway (LiteLLM) that realizes the ADR-0009 admission layer (TN-1): every model call resolves to an in-tenant endpoint, the default is the Claude subscription via account auth (Q9, NOT a metered API key), and the auth path stays swappable. Any hosted/external endpoint that carries code/IP is a config error that BLOCKS the run.
- **FR-005** — An open-weight in-tenant inference eject-path (vLLM / SGLang behind the gateway) MUST be built only as a DEFERRED adapter behind its own feature flag DEFAULT OFF — it is NOT the near-term build (Q9). The near-term default stays the Claude subscription; the adapter + its unit tests are buildable with no live serving stack present, and the flag stays OFF until a Founder decision opens the eject-path.
- **FR-006** — Guardrails MUST be a layered chain — Presidio (PII detection) + a classifier + policy — wired into the ADR-0012 redaction / guardrail path and admitted through the ADR-0033 governed MCP edge (least-privilege, PreToolUse audit), never as a bulk import (TN-5, BOM guardrails).
- **FR-007** — Evals MUST use a hand-labeled golden set (promptfoo) checked BEFORE any LLM-judge, with an anti-gaming probe, wired into the existing `evals/` CI path — golden-set-before-dashboard discipline (BOM evals, ADR-0017/0020). No golden-set pass ⇒ not green.
- **FR-008** — The whole WS-E hardening surface MUST be feature-flagged in `config/features.yaml` DEFAULT **OFF** (`ws_e_tenant_hardening`, from the DAS-1543 scaffold); merging MUST change no dispatch behaviour (rollback = flag stays OFF / remove the config). The workstream scope is internal self-host ONLY: a change adding SOC 2 / SSO / SAML / SCIM / multi-tenant / billing is out of scope and rejected (ADR-0038 boundary, Q10).

## Success Criteria

- **SC-001** — A negative test proves an agent identity (and any non-Founder actor) cannot approve any AADL gate, and a read-only-audit principal cannot approve / trigger / mutate — only a Founder-identity principal can approve (RBAC, TN-3).
- **SC-002** — A test proves an audit export is read-only OTel/JSON and a redaction probe over an exported event passes (no secret / PII / source survives); the export cannot write back to the board (TN-4/TN-5).
- **SC-003** — A negative test proves a model call resolving to a hosted/external endpoint that carries code/IP evaluates to a BLOCKED config error, and the gateway otherwise routes to the in-tenant endpoint (TN-1); the open-weight eject-path stays inert behind its deferred flag OFF.
- **SC-004** — A guardrail probe proves planted PII / secrets are detected + redacted by the Presidio+classifier+policy chain, and the promptfoo golden set passes WITH the anti-gaming probe (BOM guardrails + evals).
- **SC-005** — With `ws_e_tenant_hardening` OFF, a wave's dispatch behaviour is byte-identical to pre-merge; `diagnostics.py` 100/100, `board_lint`/`check_spec_consistency`/`check_dependency_graph`/validators green, no `project:` field on any WS-E ticket (board_lint R9), committed attestation for the wave.
