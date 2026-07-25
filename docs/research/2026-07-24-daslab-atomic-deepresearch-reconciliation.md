# DasLab × Atomic Deep-Research — Reconciliation & Harvest Map

- **Type:** Reconciliation brief — folds the uploaded *"DasLab Agent-Platform Deep Research — Atomic Edition (v2)"* into the MUSTAQIL program.
- **Date:** 2026-07-24
- **Status:** Draft for Founder review. Companion to `2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`, `2026-07-23-daslab-mustaqil-master-prompt-v3.md`, and the 2026-07-24 similarity scan.
- **Source under reconciliation:** *Atomic Edition v2* (4-layer / 3-plane teardown of Manus · Perplexity Computer · Devin · Augment · GitHub Copilot · Factory + an OSS build blueprint).

---

## 0 — TL;DR (the one thing to get right)

The Atomic report is a **mechanism library**, not a competing architecture. Its *mechanisms* (how each platform isolates, browses, retrieves, verifies, and governs) are architecture-neutral gold — harvest them into workstreams A–H. Its *stack recommendations* rest on a **stale working assumption** (DasLab = OpenClaw-orchestration + Dokploy + model-agnostic + build-your-own-Firecracker) that partly conflicts with decisions already locked in MUSTAQIL v3.0. Where the report's mechanism and our locked decision agree → **adopt**. Where the mechanism is neutral but the report's stack differs → **adapt** to our stack. Where the report proposes a control-plane/brain choice → **hold the line** (ADR-0010 C1).

Net: this doc turns the report into (a) a per-workstream harvest table, (b) a "steal verbatim" list, (c) a "hold the line" list, (d) security acceptance-criteria for the new surfaces, and (e) the G-PROOF benchmark spec.

---

## 1 — How to use this document

1. When you author each workstream's ADR delta (0033–0040), open the matching row(s) in §2 and copy the **mechanism** — not the report's product choice.
2. Treat §3 as done-decisions (adopt) and §4 as guardrails (do **not** let these drift back in).
3. Feed §5 into the ADR **acceptance criteria** for A/C/E — the new browser + sandbox surfaces must *inherit* the governance we already lead on.
4. Feed §6 into the G-PROOF harness so the proof number is decision-grade, not marketing.

---

## 2 — Master harvest map (mechanism → workstream → ADR → verdict)

Verdict legend: **✅ adopt** (mechanism + our stack already agree) · **🔁 adapt** (mechanism is neutral; bind it to our stack, not the report's) · **⛔ hold line** (report's choice conflicts with a locked decision — do not adopt).

| WS | Atomic layer/plane | Mechanism to harvest | Source | Target ADR | Verdict |
|----|--------------------|----------------------|--------|-----------|---------|
| **A REACH** | B — browser | a11y-tree action model (click `ref_N`, not pixels) + `browser-use` | Manus/Comet/Mariner | 0033 | ✅ adopt (already our pick) |
| **A REACH** | B — browser | CDP deterministic escape hatch: checked-in Playwright for login/MFA/brittle flows | Devin (:29229) | 0033 | ✅ adopt |
| **A REACH** | Governance | BrowseSafe-style injection classifier → domain allowlist → block `file://`/`chrome://` → PreToolUse audit | Comet CVE track record | 0033 | ✅ adopt (mandatory before any unattended browsing) |
| **B RUNNER** | D — front door | Headless `droid exec` pattern: read-only default, tiered `--auto low/med/high`, JSON-RPC control | Factory | 0034 | 🔁 adapt (autonomy tiers ride under QONUN-5/AADL gates) |
| **B RUNNER** | D — front door | Copilot delivery guardrails: branch-scoped push, no self-approve, CI human-gated | Copilot | 0034 | ✅ adopt (we already exceed via QONUN-5; runner must enforce mechanically) |
| **C LOOP** | A — runtime | microVM-class isolated sandbox per task | Manus (E2B)/Perplexity | 0035 | 🔁 adapt → **E2B/OpenHands** (not DIY Firecracker; see §4) |
| **C LOOP** | A — runtime | pause / **branch** / resume lifecycle + snapshot | Perplexity SPACE | 0035 | ✅ adopt |
| **C LOOP** | A — runtime | root-in-sandbox but host-isolated; `rm -rf`/fork-bomb containment test | Manus Zero-Trust | 0035 | ✅ adopt (as acceptance test) |
| **C LOOP** | Governance | **inject-at-use** credentials, destroyed-with-VM; sub-agents get short-lived proxy tokens, never raw keys | Perplexity SPACE | 0035 + 0038 | ✅ adopt (mandatory) |
| **C LOOP** | Orchestration | `todo.md` self-tracking + one-tool-per-step discipline | Manus CodeAct | 0035 | 🔁 adapt (we already have board + wave-ledger; CodeAct is optional) |
| **D LENS** | Governance/eval | `promptfoo` golden-set evals admitted through the 0033 edge | production-stack | 0036 | ✅ adopt (already in v3.0) |
| **D LENS** | Governance | audit logs → SIEM export; per-connector/model allowlists | Perplexity | 0036 + 0039 | ✅ adopt |
| **E TENANT** | Layer C/Gov | **Proof-of-Possession** hash-challenge at the retrieval layer | Augment/Cursor | retrieval ADR / 0038 | 🔁 adapt (only *if/when* indexed retrieval is built — see §4) |
| **E TENANT** | Layer C | self-hosted embeddings; never ship code embeddings to a 3rd-party vector DB (invertible to source) | Augment/Sourcegraph | retrieval ADR | ✅ adopt (as a principle) |
| **E TENANT** | Governance | spend caps + runaway-retry auto-stop; SIEM audit; retention default | Perplexity failure mode | 0027 SI-5 / 0038 | ✅ adopt (SI-5 exists; extend to browser + sandbox surfaces) |
| **G PROOF** | Benchmark | SWE-bench **Pro** (not saturated *Verified*) + a private task suite | Part 3 | 0037 | ✅ adopt |
| **G PROOF** | Benchmark | fix-the-harness, per-layer atomic metrics, pipelined per-item, log every dropped case | Part 3 | 0037 | ✅ adopt |
| **H CONTROL** | Governance | governance dashboard = allowlists + spend caps + audit export + retention policy | Part 5.6 | 0039 | ✅ adopt |
| **F TEMPO** | Verification | assert-before-acting verification as the *trust surface* gating shadow→live | Devin | 0027 | ✅ adopt (feeds HEARTBEAT go-live evidence) |
| **(existing-repo, G4)** | Layer C | code-graph SCIP ("what calls this?") **consumed via MCP**, not rebuilt | Sourcegraph | 0033 edge | 🔁 adapt (consume for existing-repo work; greenfield stays agentic-search-first) |

---

## 3 — Steal these mechanisms verbatim (architecture-neutral gold)

These are independent of whatever brain/stack sits above them, and every one strengthens a plane DasLab already leads on:

- **Devin's assert-before-acting** — the agent writes its *expected* result immediately **before** each action, not after, so the model can't rationalize a failure as a pass. Cheapest large trust win in the whole report; it is the mechanism that makes autonomy sellable and directly feeds the F-TEMPO shadow→live evidence.
- **Perplexity's inject-at-use credential model** — secrets never persist in the sandbox; injected only at moment of use, destroyed with the VM; sub-agents get short-lived proxy tokens. Near-impossible to retrofit — bake it into ADR-0035/0038 now.
- **Augment/Cursor Proof-of-Possession** — serve retrieval context for a file only to a caller who can present its content hash; enforce at the retrieval layer, not just an API gateway. This is the feature enterprise buyers actually audit.
- **Copilot's delivery guardrails** — branch-scoped push, cannot merge, cannot approve own PR, CI human-gated. We already exceed this via QONUN-5 + AADL; the point is to make the *new headless runner* enforce it mechanically, not by convention.
- **BrowseSafe injection classifier** — scan externally-retrieved content *before* the agent acts, in parallel with reasoning, safe-stop on suspicious content. Layer-1 of Layer-B defense-in-depth; non-negotiable given the Comet CVE record.
- **SWE-bench-Pro + fix-the-harness benchmark discipline** — the only way the G-PROOF number is decision-grade.

---

## 4 — Hold the line (report choices that conflict with locked decisions)

Do **not** let these drift back in — each contradicts a decision already made:

- **⛔ OpenClaw Gateway as the orchestrator/brain.** The report's orchestration plane defaults to OpenClaw. Locked: **board + AADL + RACI + LangGraph substrate** is the brain (**ADR-0010 C1** — an external framework is *substrate in its lane, never the top-level brain*). Our orchestration equivalent = `board/ROUTING.md` + wave_runner + LangGraph-as-DGO-X. OpenClaw is not adopted as a control plane; WS-H is the one governed control plane.
- **⛔ Model-agnostic / 19-model routing.** Locked: **Claude-only** by the Model-Allocation Law (opus/sonnet/haiku), subscription auth via the Agent SDK. Model routing across vendors is out of scope by identity choice, not oversight.
- **⛔ Build-your-own Firecracker (emberd/crucible).** Locked: **E2B/OpenHands** managed microVM-class sandbox under DGO-X (ADR-0035). Adopt the *lifecycle + isolation posture + credential model*; do **not** stand up a bare-metal Firecracker fleet unless E2B/OpenHands proves insufficient (Northflank estimates a DIY sandbox at 2–3 senior engineers × 3–6 months).
- **⛔ Vector-DB / Sourcegraph indexed retrieval as the default.** Locked: **agentic-search-first** (grep / Read / 07-CONTEXT-PACK / ArcRift recall); no vector DB by default; the board stays the source of truth (C2). Indexed retrieval (PoP + Sourcegraph MCP) is a **metric-justified escape hatch** for large existing-repo work only, approved by the retrieval-strategy ADR — never the default, never the source of truth.

The pattern: harvest the report's **mechanisms**, refuse its **brain/stack defaults** wherever they touch ADR-0010 C1, the Model-Allocation Law, or the agentic-search-first retrieval stance.

---

## 5 — Security mechanisms → ADR acceptance criteria (the "real employee" plane)

Turn Part 5 of the report into pass/fail criteria on the new surfaces (this is where we already lead — the job is to make sure REACH + LOOP *inherit* it, not weaken it):

- **ADR-0035 (sandbox):** isolation is microVM-class (E2B/OpenHands); a deliberate `rm -rf` / fork-bomb inside the sandbox must not touch the host (containment test in CI); credentials inject-at-use and are destroyed with the VM; sub-agents receive short-lived proxy tokens only.
- **ADR-0033 (browser/tool edge):** every external tool enters through the governed MCP edge (least-privilege allow-list + PreToolUse audit + 0012 redaction); a BrowseSafe-class classifier + domain allowlist gates all browsing; tool output is untrusted data and can never change the goal/approvals (injection defense; already in the master prompt).
- **ADR-0034 (runner):** pushes only to a task branch; cannot merge; cannot self-approve; CI is human/gate-gated — mechanically, not by convention.
- **ADR-0038 (tenant):** in-tenant endpoints only (TN-1); spend caps as a hard dispatch ceiling with runaway-loop auto-stop (SI-5); audit exportable to SIEM; retention policy set.
- **Retrieval ADR (only if indexed retrieval is built):** Proof-of-Possession hash-challenge; self-hosted embeddings; no third-party vector DB.

---

## 6 — Benchmark spec → G-PROOF (ADR-0037)

From Part 3, so the proof is decision-grade:

- **External:** SWE-bench **Pro** (multi-language, hidden tests) as the primary code-fix score; **Terminal-Bench** as the Layer-A/tool-use proxy. Treat the saturated SWE-bench *Verified* as legacy comparison only.
- **Method:** fix the harness and vary one thing at a time (harness alone swings scores several points); label every number with its date and pool (self-reported vs verified); re-run monthly.
- **Per-layer atomic metrics:** A → VM cold-start p50/p95, pause→resume, branch cost, containment test; B → success-rate on graded human-level flows + **injection-resistance %** (target → 0); C → precision@k / recall@k + freshness lag + **leak test** (a restricted file must never surface = PoP correctness); D → time-to-first-green-PR, revisions-to-green, **guardrail escape = automatic fail**.
- **Cross-cutting:** cost per resolved task; **verification catch-rate** (bugs the agent's own test loop caught before human review); audit completeness (every action attributable). Run pipelined per-item; **log every dropped/failed case** (silent truncation reads as "100% covered" when it isn't).

---

## 7 — Concrete next actions

1. Author the ADR deltas with the §2 rows inline as "mechanism source" notes; add §5 as each ADR's acceptance criteria.
2. Add one line to `docs/adr/README.md` noting this reconciliation as the mechanism provenance for 0033–0037.
3. Optionally file the *Atomic Edition v2* itself under `docs/research/` (it is currently an upload, not in-repo) so the provenance links resolve.
4. Keep the §4 "hold the line" list visible in the WS-A/WS-C ADRs so the OpenClaw/model-agnostic/DIY-Firecracker defaults don't creep back in during implementation.

---

## Sources

- **Under reconciliation:** *DasLab Agent-Platform Deep Research — Atomic Edition (v2)*, compiled 2026-07-24 (uploaded).
- **Locked program:** `2026-07-23-daslab-mustaqil-master-prompt-v3.md` (WS A–H, model stance, retrieval + tool-admission discipline) · `2026-07-23-daslab-mustaqil-discovery-answers.md` (Founder Q1–Q12) · `2026-07-22-daslab-vs-autonomous-coding-agents-parity.md` (7-gap analysis) · ADR-0010 (DGO-X / C1), ADR-0027 (scheduler-safety / SI-5), ADRs 0033–0040 (proposed).
- **Platform mechanisms (primary sources are catalogued in the Atomic Edition Appendix A):** Devin computer-use + verification; Perplexity SPACE security; Augment Proof-of-Possession + quantized retrieval; Factory `droid exec`; Copilot coding-agent guardrails; BrowseSafe (`arXiv:2511.20597`).
