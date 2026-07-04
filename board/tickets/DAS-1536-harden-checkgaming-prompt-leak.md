---
id: DAS-1536
title: Harden check-gaming with a prompt-leak detector + guild-wide eval cleanup
status: done
assignee: qa-lead
author: cto
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
zone: agent-eval-antigaming
created: 2026-07-04
updated: 2026-07-04
---

## Description

Follow-up from the R-5 GATE-4 review (DAS-1508 epic): the adversarial qa-lead
review caught a SYSTEMIC anti-gaming flaw that `agent_eval.py --check-gaming`
did NOT detect — a task's agent-visible `task.md` "Required submission" example
printed the EXACT graded answer instead of a placeholder, so a live agent
copying its own prompt scored ~0.85–1.0 with zero competence. The existing
gaming probe only tested EMPTY/degenerate submissions and was blind to this.

**Two deliverables:**

1. **Detector (`scripts/agent_eval.py`).** New `prompt_leak_findings()` +
   `_json_candidates()`: for every deterministic task, parse each JSON block in
   `task.md` and score it through the task's OWN `verify.py`; flag a leak when any
   example scores ≥ `MAX_PROMPT_LEAK_CREDIT` (0.5). Non-answer placeholders
   (`<int>`, `<tag>`) are not valid JSON, so they are ignored. Folded into
   `gaming_findings()` so `--check-gaming` now catches it. +5 unit tests.

2. **Guild-wide cleanup.** The detector found the leak was NOT limited to the 5
   the human review flagged — it originated in 4 of the 6 ORIGINAL reference
   evals (backend-eng-1, product-analyst, security-eng, sre-eng) and had been
   copied into 3 wave-2 evals the review had passed (backend-eng-2,
   legal-analyst, sre-lead): 17 tasks across 7 roles. All fixed — task.md
   examples replaced with non-answer placeholders; `verify.py`/`fixtures`/
   `submissions` untouched, so enforce accuracy is unchanged.

## Acceptance criteria
- [x] `agent_eval.py --check-gaming` catches task.md answer-key leaks (was blind).
- [x] All 17 leaking tasks (7 roles) fixed → `--check-gaming` exit 0 across all 32 roles.
- [x] `--all --enforce` still 32/32 PASS (accuracy unchanged by the placeholder swap).
- [x] +5 detector unit tests; `diagnostics.py` 100/100; full suite green.

## Log
### 2026-07-04 — CTO
Created + closed same session. Detector added to scripts/agent_eval.py
(prompt_leak_findings/_json_candidates, threshold 0.5, folded into gaming_findings).
Guild cleanup: 7 qa-eng subagents fixed 17 leaking task.md examples across
backend-eng-1/2, legal-analyst, product-analyst, security-eng, sre-eng, sre-lead
(each self-verified LEAK-CHECK CLEAN + enforce unchanged). check-gaming now exit 0
across 32 roles; --all --enforce 32/32; +5 tests; full suite 1747 passed;
diagnostics 100/100. Local-only (no push). Noted follow-up: 2 sre-lead tasks show
0.4 coincidental example/answer overlap (below the 0.5 clear-leak threshold) —
candidate for a stricter zero-overlap pass if the guild wants it.

### 2026-07-04 — CTO (follow-up: strict zero-overlap — CLOSED)
Tightened the detector to strict zero-overlap: MAX_PROMPT_LEAK_CREDIT 0.5 → 0.0
(flag ANY task.md example scoring > 0 through its own verifier, not just >= 0.5). A
full-tree sweep found 5 partial overlaps the 0.5 bar missed — sre-lead/{incident-
severity-triage, rollback-go-nogo} (0.4) and support-lead/{canned-response-match
(0.4), sla-breach-check (0.333), ticket-triage-routing (0.2)} — all format examples
reusing real fixture ids/values. Fixed: task.md examples → unquoted `<...>`
placeholders (score 0.0). +1 partial-leak regression test. Whole tree now
zero-overlap; --check-gaming exit 0; --all --enforce 32/32 unchanged (task.md-only
edits); full suite 1748 passed; diagnostics 100/100. Follow-up fully closed.
