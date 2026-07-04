# ORGANISM v2.0 — Post-Coding Verification Audit

> Date: 2026-07-03 (evening) · HEAD: `13bf01f` · Auditor: independent session (fresh clone view)
> Method: live runs of diagnostics/validators/tests + 1 adversarial verification subagent
> (negative tests, false-green hunting). Env note: audit sandbox is Python 3.10; repo targets
> 3.11 — tomllib/datetime.UTC/StrEnum shims applied; **all scores below are from the corrected
> environment** (initial 75/100 was a sandbox artifact of fail-closed gates working correctly).

---

## 1 — Headline scores

| Dimension | Ball |
|---|---|
| `diagnostics.py` engine gate | **100/100** (Docs 20, Architecture 20, Code-quality 15, Consistency 15, Portability 15, Security 10, Git-hygiene 5) |
| Test suite | **1662 passed, 1 skipped** (8.4s) — was ~52 tests at v1.0.0 |
| §5 contract (12 rows) | **4 ✅ green · 5 🟡 partial · 3 ❌ unmeasured** ≈ 6.5/12 |
| Capability matrix (self-row) | **88/120** (was 59; target 115) |
| Composite (atom-audit method) | **≈ 8.7/10** (was ≈ 8.5) |
| Release readiness (VERSION 2.0.0) | **NOT YET** — 5 ATTEST tickets open, loop still `shadow` |

## 2 — What was verified REAL (evidence)

- **Clean-room held:** `check_import_ban.py` OK — zero donor libraries in manifests/imports
  (verified twice + grep). Diagnostics Security 10/10.
- **CI has real teeth:** blocking steps for board_lint, comm-flows closed-graph (ADR-0026),
  span-coverage gate, cost/progress-ledger gates, golden-eval `--enforce`, GATE-6
  attestation, kill-drill smoke, kill-switch drill, anti-gaming, pytest — **zero
  `continue-on-error`/`|| true` escapes** in any workflow. Scheduled drills:
  recovery (50 iter), kill-switch (30 iter).
- **Comm-flows enforcement is real:** negative test (undeclared `qa-eng→founder` edge in a
  /tmp copy) → exit 1 with 3 precise ADR-0026 errors. Repo graph: OK.
- **GATEWAY compiles for real:** broken pack (missing manifest key) → rejected with
  actionable FR-002 error; intact sample pack → **28 story tickets compiled, exit 0**;
  second pack proves generality. `board_lint` R12 stage-gate is fail-closed (FIX-B).
- **Golden-eval harness is real and offline-deterministic:** 6 roles × 3 tasks × k=3
  recorded submissions; accuracies 0.83–0.92, all ≥ 0.80 bar; `--enforce` exit 0;
  `--check-gaming` exit 0. Coverage honestly documented as "representative slice, not
  full coverage" (6/32; 26 pending).
- **Durability primitives are real:** `kill_drill.py --smoke` — real SIGKILL mid-wave-2,
  resume with zero lost / zero duplicated tickets, chain clean, fork divergent with
  original intact, "T5 recovery 1.000 over 2 drills".
- **Ops surface built:** `cockpit_html.py` 13 panels + Action Console (+`--serve`),
  `board/interrupts/`, `board/schedule.yaml`, `config/budgets.yaml`,
  `scripts/cost/cost_ledger.py`, `task_ledger.py`, 32 guild templates (all with
  `## Learned`), ADRs 0023–0030 for every ORGANISM decision.
- **Wave hygiene:** 25 waves logged, 55 dispatches, idle rate **0.000**; 57 tickets done,
  62 lint-clean; working tree clean at HEAD.

## 3 — Findings (bugs & gaps found by adversarial pass)

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| F-1 | **HIGH (bug)** | Founder-approval regex is false-green: `\bAPPROVED\b` matches the file's own `# APPROVED-GOAL-QUEUE` header ("-" is a word boundary) — a queue with the explicit `APPROVED:`/`TASDIQLANDI:` line REMOVED still compiled 28 tickets (stopped only later by an unrelated stage-5 check). QONUN-3's signal is not load-bearing. | `scripts/check_approved_goal_queue.py:44` |
| F-2 | **MED (bug)** | Evidence anomaly in **5/5** committed files: `kpi_summary.busy_fraction=1.0` while `model_mix` sums to 0 — yet completions carry `model: "opus"`; all runs single-ticket, created 13:31–14:14 same day. Either model_mix aggregation is broken or evidence was curated/backfilled. | `metrics/evidence/*.json` |
| F-3 | **MED (open work)** | Kill-drill workload is SYNTHETIC — real SIGKILL/resume mechanics, but a hand-rolled dispatcher; the production `wave_runner` does not exist yet. Openly ticketed. | DAS-1499/1501/1502 (todo) |
| F-4 | **MED (unmeasured)** | Org-level T1/T3/T4/T5/T6 validators: "unmeasured — gate inert (loop off)". Loop mode is `shadow`, `auto_apply false`; org event store empty. Live-tempo contract rows cannot be claimed yet. Bare `check_recovery.py` is a vacuous pass on an empty board (CI comment admits it; kill-drill smoke is the real CI tooth). | validator outputs; `config/loop.yaml` |
| F-5 | LOW | `check_import_ban` runs only inside diagnostics (no dedicated CI step); `agent_eval --check-gaming` and `validate_commflows` not direct CI steps (covered indirectly via pytest). | `.github/workflows/ci.yml` |
| F-6 | LOW | Eval coverage 6/32 roles; guardrails piloted on 2 roles; ruff lint gate scope excludes eval fixtures (intentional bait code) but `verify.py` files carry minor SIM102/B905 lint. | `evals/`, `governance/guardrails/` |

## 4 — §5 contract: Expected VS Actual

| # | Kutilgan (§5 contract) | Haqiqiy natija (dalil bilan) | Holat |
|---|------------------------|------------------------------|-------|
| 1 | T1 busy ≥ 0.60 (anti-gaming bilan) | Unmeasured — loop `shadow`, org event store bo'sh; wave-log usulida elapsed-busy 1.8% (uyqu soatlari bilan) | ❌ |
| 2 | T2 idle ≤ 0.15 | **0.000** / 25 wave (`check_idle_waves` OK) | ✅ |
| 3 | T3 concurrency ≥ 6 | Unmeasured — gate inert (loop off) | ❌ |
| 4 | T4 haiku ulushi ≥ 0.25 | Loglangan mix: opus 37 · sonnet 18 · **haiku 0**; validator: unmeasured | ❌ |
| 5 | T5 ≥ 0.99 + kill-drill (0 lost/0 dup) | Kill-drill smoke: **1.000**, zero lost/dup, fork intact — LEKIN synthetic runner (DAS-1501 ochiq); CI'da scheduled 50-iter drill | 🟡 |
| 6 | T6 trend + T7 hold | T7 rubric intact, barcha counted completions t7_pass=true; T6 unmeasured | 🟡 |
| 7 | 100% dispatch → span + cost reconcile | Span sxemasi (ADR-0024) + CI gate mavjud; org store bo'sh, cost "n/a (inert)"; F-2 anomaliya | 🟡 |
| 8 | 32 rol × ≥3 golden, ≥80% | **6/32 rol** × 3 task, hammasi 0.83–0.92 PASS, `--enforce` yashil; 26 rol pending (halol hujjatlangan) | 🟡 |
| 9 | Undeclared route unrepresentable + validator | Closed-graph derived flows + negativ test exit 1 (ADR-0026) + blocking CI step | ✅ |
| 10 | E2E: pack → 6 gate → 0 qo'lda ticket | 28 ticket kompilyatsiya (tekshirildi), 2-pack generality, GATE-5 fail-closed; to'liq delivery "local-only" — repoda run-log yo'q; F-1 approval-bug | 🟡 |
| 11 | Cockpit jonli + interrupt <60s + kill-switch | 13 panel + Action Console + `--serve`; kill-switch drill CI'da (30-iter scheduled); interrupt kartalari mavjud | ✅ |
| 12 | diagnostics 100/100, 0 QONUN buzilish, 0 donor import/kod | **100/100** · board_lint 0 violation · import-ban OK (F-1 validator-teshigi 3-bandda alohida) | ✅ |

**Kontrakt bali: 4 ✅ + 5 🟡 + 3 ❌ ≈ 6.5/12.** Uchala ❌ ham bitta ildizga boradi:
**loop hali live emas** (HEARTBEAT shadow) — bu dizayn bo'yicha Founder flip'ini kutyapti.

## 5 — Capability self-row update (0–10)

| R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 | Σ |
|----|----|----|----|----|----|----|----|----|-----|-----|-----|---|
| v1.0 baseline: 4 | 4 | 4 | 5 | 2 | 4 | 4 | 7 | 2 | 8 | 10 | 5 | **59** |
| **v2.0-rc hozir: 7** | **7** | **8** | **6** | **5** | **6** | **8** | **9** | **6** | **8** | **10** | **8** | **88** |
| v2.0 target: 10 | 10 | 10 | 9 | 9 | 10 | 9 | 10 | 9 | 9 | 10 | 10 | **115** |

59 → **88** (+29). Qolgan 27 ballning ~19 tasi bitta kalitga bog'liq: live loop + real
o'lchov (R1,R5,R6 to'lishi), qolgani evals-scale (R9) va guardrails (R4).

## 6 — Verdict & remediation queue

**Verdict:** natija kutilganga **katta qismda mos** — barcha 7 workstream artefaktlari
mavjud, CI'da haqiqiy tishlar bor, clean-room saqlangan, va eng muhimi: o'lchanmagan
narsani validator halol "unmeasured" deydi (Ruflo-uslub soxta-yashil YO'Q). Lekin §5
kontrakti bo'yicha v2.0 hali YOPILMAYDI: ATTEST bosqichi ochiq va live o'lchov yo'q.

Remediation (tartib bilan):
1. **R-1 (HIGH):** F-1 approval-regex — headerga mos kelmaydigan qat'iy pattern (masalan
   `^APPROVED:|^TASDIQLANDI:` satr boshida) + negativ test. QONUN-3 signalini load-bearing qilish.
2. **R-2:** F-2 — evidence emitter'da model_mix aggregatsiyasini to'g'rilash + evidence
   schema testiga cross-check qo'shish (busy>0 ⇒ model_mix ≥ completions soni).
3. **R-3:** ATTEST'ni yakunlash — DAS-1499 `wave_runner`, DAS-1501 kill-drill retrofit,
   DAS-1502 `/daslab-cycle` wiring, DAS-1500 attestation CI sample (5 ticket, hammasi todo).
4. **R-4:** HEARTBEAT: ≥3 kun shadow ma'lumot yig'ish → Founder flip → T1/T3/T4/T5/T6
   real evidence bilan yashil qilish (kontrakt 1,3,4-qatorlar shunda ochiladi).
5. **R-5:** Evals 6→32 rol (mexanizm tayyor — faqat kontent), guardrails 2→rollout.
6. **R-6 (LOW):** check_import_ban / check-gaming / validate_commflows'ni dedicated CI
   step qilish; keyin VERSION 2.0.0 + CHANGELOG.

*Bu audit hech qanday repo faylini o'zgartirmagan (faqat /tmp scratch).*
