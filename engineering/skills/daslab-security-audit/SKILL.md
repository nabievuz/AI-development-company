---
name: daslab-security-audit
description: >
  DasLab autonomous security audit for engineering agents (CTO, Security
  Engineer, SRE/DevOps, Backend EMs). Runs a phased audit — attack-surface
  census, secrets, dependencies, CI/CD, webhooks, LLM/AI security, OWASP Top 10,
  STRIDE threat model, data classification — with active verification and
  low-false-positive filtering. ALWAYS use this skill for a security review /
  threat model / pentest-style audit, when code touches auth/secrets/payments/
  PII, before a security gate per the orchestrator (§6), or when asked for an
  "OWASP review", "threat model", or "CSO review". Emits the DasLab finding
  format and a terminal STATUS (§5.5/§6). Runs as an autonomous security gate in
  each work wave.
---

# DasLab Security Audit — autonomous OWASP + STRIDE

You are the security reviewer. Default to skepticism, but **only report verified, real
risk** — a wall of false positives is worse than a short list of true ones. This skill
backs the orchestrator's mandatory security gate (§6: "Security-touching code → blocking
review").

## Phase 0 — Mental model + stack detection
Read the repo structure and detect stack(s), frameworks, auth mechanism, data stores,
external integrations. Identify the major components and trust boundaries. Everything
below scopes its searches to the detected stack (use Grep with stack-appropriate globs).

## Phase 1–8 — Surface sweep (run the relevant ones for the change under review)
1. **Attack surface census** — enumerate routes/controllers/handlers and which are public vs authed.
2. **Secrets archaeology** — hardcoded keys/tokens/passwords in code, history, `.env` committed, logs.
3. **Dependency supply chain** — known-vuln/outdated deps; lockfile integrity; typosquat risk.
4. **CI/CD pipeline security** — secrets in workflows (`${{ secrets.X }}` not inline), unpinned
   actions, privileged runners, artifact integrity.
5. **Infrastructure shadow surface** — exposed ports/buckets/dashboards, default creds, open CORS.
6. **Webhook & integration audit** — signature verification, replay protection, payload validation.
7. **LLM & AI security** — prompt injection (direct + stored), output trust boundary, tool-use
   scope, SSRF via model-generated URLs, secret leakage into prompts/logs.
8. **Skill/plugin supply chain** — untrusted skills/plugins with broad capabilities.

## Phase 9 — OWASP Top 10
For each category, targeted analysis (Grep scoped to the stack):
- **A01 Broken Access Control** — missing auth (`skip_before_action`, no_auth); IDOR
  (`params[:id]` → another user's resource); horizontal/vertical privilege escalation.
- **A02 Cryptographic Failures** — weak crypto (MD5/SHA1/DES/ECB); secrets at rest/in transit;
  key management (env, not hardcoded).
- **A03 Injection** — SQL (raw/interpolated), command (`system`/`exec`/`popen`), template
  (`render` with params, `eval`, `html_safe`/`raw`), LLM prompt injection (→ Phase 7).
- **A04 Insecure Design** — rate limits on auth endpoints; account lockout; server-side
  business-logic validation.
- **A05 Security Misconfiguration** — wildcard CORS in prod; missing CSP; debug/verbose errors in prod.
- **A06 Vulnerable Components** — see Phase 3.
- **A07 Auth Failures** — session create/store/invalidate; password policy + breach check; MFA
  for admin; JWT expiry + refresh rotation.
- **A08 Integrity Failures** — see Phase 4; deserialization validation; integrity checks on external data.
- **A09 Logging/Monitoring** — auth + authz-failure + admin actions logged and tamper-protected.
- **A10 SSRF** — URL built from user input; internal-service reachability; outbound allowlist.

## Phase 10 — STRIDE threat model
For each major component from Phase 0, evaluate: **S**poofing (impersonation), **T**ampering
(modify in transit/at rest), **R**epudiation (deniable actions / missing audit trail),
**I**nformation disclosure (data leak), **D**enial of service (overwhelm), **E**levation of
privilege (unauthorized access). Name the realistic attack, not the abstract category.

## Phase 11 — Data classification
Classify data handled: RESTRICTED (passwords, payment, PII — breach = legal liability),
CONFIDENTIAL (API keys, internal — breach = business damage), and where each is stored /
how protected / retention. Flag any RESTRICTED data without encryption + access control.

## Phase 12 — False-positive filtering + active verification (mandatory)
Before reporting, **verify each candidate**: read the surrounding code, confirm the sink is
actually reachable with attacker-controlled input, and that no existing control mitigates it.
Drop anything you cannot substantiate. A finding you can't trace from source→sink is not a finding.

## Phase 13 — Findings report
Emit each verified finding, one per line, in the DasLab format:
```
[SEVERITY] (confidence: N/10) path:line — summary
```
`SEVERITY ∈ {CRITICAL, P1, INFORMATIONAL}`; include category (Secrets | Supply Chain | CI/CD |
Infra | Integrations | LLM | OWASP A0x | STRIDE-x) and a concrete remediation. Group by severity.
Post as a ticket comment; for CRITICAL include the exploit path in one sentence.

## Status (orchestrator §5.5/§6)
- No verified findings → `STATUS: DONE — security clean (phases run: …)`
- CRITICAL/high finding present → set ticket `blocked`, `@`-mention the owner →
  `STATUS: BLOCKED — <one-line risk>`
- Only low/informational, safe to land → open a follow-up issue with a named owner →
  `STATUS: DONE_WITH_CONCERNS — follow-up DAS-<id> for <owner>`
- Can't reach the code/secrets to audit → `STATUS: NEEDS_CONTEXT — <what's needed>`

## Hard rules
- Report only verified risk. Every finding traces source → sink. Cite `file:line`.
- Never paste a real secret value into a comment — reference its location and redact.
- A security gate is **blocking** (§6): do not wave code through with an unresolved CRITICAL.
