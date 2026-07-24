# MUSTAQIL — Founder Discovery Gate: answers (intake record for v3.0)

- **Type:** The Founder Discovery Gate answers required by the Founder-Approved Goal Queue law (≥10 before a goal becomes tickets). Answers to `2026-07-23-daslab-mustaqil-master-prompt-v3.md` Part 3.
- **Date:** 2026-07-23
- **Status:** Answered by the Founder. Next: feed to `/daslab-plan` → `APPROVED-GOAL-QUEUE.md` → explicit `APPROVED:` / `TASDIQLANDI:` → `/daslab-run`.

---

## The 12 answers

| # | Question | Answer | Locks in |
|---|---|---|---|
| 1 | Proof project (G6) | **WS-H dashboard slice** | First 0→100 = extend the control-plane dashboard (e.g. CP-3b trigger-run). Dogfood: building it proves the finisher. |
| 2 | Tenant infra | **One Linux VM** | Single Linux VM; Docker E2B/OpenHands + self-host Langfuse. Simplest in-tenant footprint. |
| 3 | Budget ceiling | **Conservative defaults** | Low caps in `budgets.yaml`; breach → idle + alert. (Now anchored to the subscription's monthly credit — see below.) |
| 4 | Autonomy appetite | **Supervised first** | Approve each gate until the first proof lands; then HEARTBEAT shadow → live. |
| 5 | Browser / egress | **Deny-all + allow-list** | No unattended browsing until WS-A governance is live; explicit domain allow-list only. |
| 6 | RBAC | **Founder-only + team read** | Only the Founder approves gates / triggers runs; a small team gets read-only audit. |
| 7 | "Shipped" for the proof | **Merged + CI + deployed** | Merged to main + green CI + deployed to the tenant VM. Strongest proof. |
| 8 | Effort & timeline | **Solo full-time** ⚠️ *(off-default)* | You, full-time → **~4–6 weeks to first proof** (not the 2–3-month part-time estimate). |
| 9 | Model / inference stance | **"Must work on a Claude subscription"** ⚠️ *(custom)* | Run on a Claude subscription via the ADR-0034 Agent SDK runner (account auth, not a metered API key). Full analysis below. |
| 10 | Scope guardrail | **Confirmed: internal only** | Internal self-host only (ADR-0038 boundary); reject SaaS / SOC 2 / SSO / multi-tenant. |
| 11 | Retrieval policy | **Agentic-search-first** | grep / Read / CONTEXT-PACK / ArcRift; no vector DB unless a metric justifies it. |
| 12 | Interop (A2A) | **Defer until after proof** | Land G first; build A2A / ADR-0040 as the first post-proof reach increment. |

Ten of twelve took the recommended default. Two are deliberate deviations, both consequential.

## Deviation 1 — Solo **full-time** (Q8)

Moves the first end-to-end autonomous proof from ~2–3 months (part-time) to **~4–6 weeks**. The capability core (A–D) compresses accordingly. This is a schedule change only; it does not alter scope, sequencing, or any gate.

## Deviation 2 — "Must work on a **Claude subscription**" (Q9) — analysis

This is an **architectural constraint**, not a preference, so it was verified against current Anthropic terms rather than assumed.

**Feasible, and aligned with DasLab's existing design.** Anthropic's Help Center confirms the **Claude Agent SDK is usable on Pro, Max, Team, and Enterprise plans** via **Claude-account authentication (not an API key)**, and the covered usage explicitly includes **programmatic Agent SDK projects (Python/TypeScript)** and **`claude -p` (non-interactive / headless) Claude Code**. That is exactly the WS-B RUNNER path (ADR-0034: `daslab_sdk`, headless dispatch). So "run on a subscription" is not a workaround — it is the sanctioned, documented mode.

**What it changes for MUSTAQIL:**

- **Budget = the monthly subscription credit.** Agent SDK usage "draws from your monthly credit before any other source" (Pro $20 / Max-5× $100 / Max-20× $200 per month). This *is* the ADR-0027 SI-5 hard ceiling — no separate metered API billing needed, which is the point of the answer. It fits Q3's "conservative defaults" cleanly.
- **Credit exhaustion = a sanctioned pause, not a failure.** Per the terms: when the monthly credit depletes, "additional Agent SDK usage flows to usage credits at standard API rates — but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes." For an autonomous finisher this means: **size waves to fit the monthly credit**, and treat a credit-refresh wait as an expected halt (like a gate), never a false-green or a crash. Keeping overflow (usage credits) **disabled** is the way to guarantee the "subscription-only, no metered $" intent.
- **Auth path:** the runner authenticates via the Claude account/OAuth, distinct from "Claude Platform accounts using an API key." Keep model access behind the ADR-0009 admission layer so the auth method stays swappable.
- **In-tenant boundary (TN-1) reading:** a subscription means the model call goes to Anthropic — the already-accepted "Claude is the one proprietary dependency" exception. The Founder has now explicitly chosen subscription-Claude **over** in-tenant open-weight. Code, IP, sandbox, observability, and audit still stay in-tenant. The open-weight vLLM/SGLang path in the WS-E BOM becomes a **deferred eject-path**, not the near-term build.

**Honest caveat ([NEEDS VERIFICATION] at build time):** the credit-based subscription model was announced for **2026-06-15 and then paused** ("nothing has changed" as of that date). The exact live mechanics may differ or shift. Before WS-B goes live, confirm the current plan's Agent-SDK terms, per-plan credit, and whether headless/autonomous use is in-policy for the specific plan in use.

## What the answers lock in for the program

A single Linux VM running the self-host stack; **subscription-Claude via the Agent SDK runner** as the model path with the monthly credit as the budget ceiling; deny-all egress; Founder-only approval with team read-only audit; the first proof = a WS-H dashboard slice, shipped = merged + CI + deployed to the VM; supervised until that proof, then HEARTBEAT shadow → live; agentic-search-first; A2A deferred; internal self-host only. Full-time → ~4–6 weeks to first proof.

## Next step

1. Hand **v3.0 Part 2** + these answers to `/daslab-plan` (the Discovery Gate is now satisfied).
2. `/daslab-plan` enriches with research and writes `APPROVED-GOAL-QUEUE.md`; nothing dispatches until the Founder signs `APPROVED:` / `TASDIQLANDI:`.
3. `/daslab-run` drains the queue; each workstream authors its ADR (0033–0040 + the retrieval-strategy ADR) and closes its AADL gate before the next starts.

---

**Sources:** [Use the Claude Agent SDK with your Claude plan — Anthropic Help Center](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) (plan support, account auth, headless/`claude -p` coverage, monthly-credit model, credit-exhaustion behavior, 2026-06-15 pause).
