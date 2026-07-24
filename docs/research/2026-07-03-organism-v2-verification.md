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

---

# §7 — RE-AUDIT (2026-07-04, HEAD `a9370e7`, VERSION 2.0.0)

Repo re-verified after the remediation + release wave (295 commits; repo was actively
moving during the audit). Environment: same py3.11 shims. **No repo files modified.**

## 7.1 Delta scores

| Dimension | Oldingi audit | Hozir |
|---|---|---|
| diagnostics.py | 100/100 | **100/100** |
| pytest | 1662 passed | **1757 passed, 1 skipped** |
| board_lint | 62 tickets, 0 violations | **98 tickets, 0 violations** |
| Eval coverage | 6/32 rol | **32/32 rol × 3 task (96), hammasi ≥0.80; `--enforce` exit 0** |
| Kontrakt (12 qator) | 4✅/5🟡/3❌ | **6✅ / 3🟡 / 3⏳** (⏳ = evidence-gated go-live ortida) |
| Capability self-row | 88/120 | **95/120** |
| Kompozit | ≈8.7/10 | **≈9.0/10** |

## 7.2 Previous findings — closure status (live re-tested)

| Finding | Status | Dalil |
|---|---|---|
| F-1 approval-regex false-green (HIGH) | **FIXED** | Docstring documents the header-chrome trap; live negative test: stripped queue → "1 violation(s)", **exit 1** (pipefail-verified); positive control exit 0 |
| F-2 evidence model_mix anomaly | **FIXED** | 7 evidence files, 0 anomalies (busy>0 ∧ model_mix=0 pattern eliminated) |
| F-3 kill-drill synthetic runner | **FIXED** | `scripts/wave_runner.py` exists; kill_drill references it 15×; `--smoke`: T5 1.000, 0 corrupted; ATTEST DAS-1497..1502 all done |
| F-4 T1/T3/T4 unmeasured | **OPEN by declared design** | Loop still `shadow`; NEW `check_heartbeat_readiness.py` verdict: "NOT READY — 0/3 consecutive clean shadow days" + Founder runbook (`docs/runbooks/heartbeat-go-live.md`); CHANGELOG 2.0.0 carries an explicit "Honest scope" note ("no KPI number fabricated; unmeasured reported as unmeasured") |
| F-5 missing dedicated CI steps | **FIXED** | Commit `85a1bd6` (R-6): dedicated steps for import-ban / check-gaming / commflows |
| F-6 eval coverage + guardrails | **HALF-FIXED** | Evals scaled 6→32 roles (96 tasks) + anti-answer-key-leak gaming gates (DAS-1536); guardrails still 2 pilot roles (backend-eng-1, security-lead) |

## 7.3 Kontrakt VS (yakuniy holat)

✅ (6): T2 idle 0.000 · T5 kill-drill real-runner 1.000 · 32/32 evals ≥0.80 · comm-flows
teeth · cockpit+drills · diagnostics 100/100 + clean-room.
🟡 (3): T6/T7 (T6 unmeasured) · spans/cost (live data flip'dan keyin) · E2E (28 ticket
kompilyatsiya tasdiqlangan, lekin to'liq 6-gate delivery run-summary hali repoda yo'q).
⏳ (3, evidence-gated): T1 busy, T3 concurrency, T4 model-mix — QONUN-5 go-live
protsedurasi: ≥3 kun toza shadow → `check_heartbeat_readiness.py` READY → Founder flip.

## 7.4 Qolgan ish (10/10 uchun)

1. Shadow rejimda ≥3 kun counted-wave ma'lumot yig'ish (`metrics_history_feeder.py` bilan
   kunlik qatorlar) → readiness READY → Founder `heartbeat_enabled: true`.
2. Flip'dan keyin T1/T3/T4/T6 + span/cost qatorlarini real evidence bilan yashillash.
3. E2E full-delivery run-summary'ni repoga commit qilish (row 10 → ✅).
4. Guardrails 2→32 rollout (mexanizm tayyor).

**Yakuniy baho: v2.0.0 "ORGANISM" halol substrat-reliz — barcha qurilish va'dalari
bajarilgan va tekshirilgan; qolgan 3 qator ataylab Founder qarori ortida turibdi.**

---

# §8 — FINAL RESULT AUDIT (2026-07-04, HEAD `643de7e`, FINALE P0–P1)

Uchinchi mustaqil tekshiruv, FINALE dasturi ishga tushgandan keyin. Gate battery
(pipefail exit-kodlar bilan): diagnostics **100/100** · pytest **1876 passed** ·
board_lint / import-ban / commflows / idle / T7 / `--enforce` / `--check-gaming`
**hammasi exit 0**.

## 8.1 FINALE progress (dalil bilan)

- **P0 DONE:** 9 ta D-karta materialize qilingan (`board/interrupts/FINALE-D0..D8.json`
  + schema; commit `4765cf9` "Founder real-time sign-off").
- **P1 asosan DONE:** guardrails **32/32 rol** (R4 build) · R3 wave-level pre-dispatch
  INPUT scope screen (`c133fda`) + R13 marker hardening · R6 `run_end.token_total`
  reconciliation (`6f29334`) · R10 composite recall ranking `memory_lib.py`da (19 ta
  half-life/importance nuqtasi) + `schedule.yaml`da consolidation job (hozircha
  documented-only) · R2 ledger'lar production yo'lida (`wave_runner.py` 12 ta
  task/progress-ledger chaqiruvi) · 16 ta adversarial-review topilmasi fix (`b2d4bee`)
  · kosmetika: W11 status-in-body lint + CONTRIBUTING py3.11 eslatmasi.
- **R12 FULL ✅:** E2E driver + **ikkala pack uchun committed run-summary**:
  28 ticket (100% kompilyator chiqargan, zero hand-written), GATE-1..6 to'liq
  yurilgan, 0 buzilish, va **negativ-prob** bilan checker'ning vacuous emasligi
  isbotlangan. `board/runs/e2e-*/run-summary.md`.
- **R6 birinchi REAL zanjir ✅:** `finale-live-das1540` — tech-writer, haiku, DAS-1540,
  real token'lar (input 156,882 · cached 516,816 · output 6,141, 21 call) →
  span → `run_end.token_total` → cost_ledger, birinchi non-zero cost. Committed
  run-summary + evidence.
- **Kutish rejimida (vaqt-gated):** `heartbeat_enabled: false`, loop `shadow`,
  readiness: **NOT READY — 0/3 toza shadow kun** (P2 burn-in endi boshlangan).

## 8.2 Mustaqil capability-row (hozirgi FINAL)

| R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | R11 | R12 | **Σ** |
|----|----|----|----|----|----|----|----|----|-----|-----|-----|-------|
| 9 | 8 | 9 | 8 | 6 | 8 | 8 | 9 | 9 | 9 | 10 | **10** | **103/120** |

95 → **103** (+8 FINALE P1'dan). Qolgan **+12 ning 11 tasi sof vaqt-gated**
(3 kun shadow → flip → ≥2 kun live-proof): R5+3, R2+2, R6+2, R4+1, R7+1, R8+1,
R3+1(live enforce). Bitta build-item qoldi: **R1 fork-drill CI'da** (+1) — FINALE
backlog'ida, scheduler bajaradi.

## 8.3 §5 kontrakt — FINAL VS

**7 ✅:** T2 idle 0.000 · T5 real-runner drill 1.000 · 32/32 evals ≥0.80 ·
comm-flows teeth · **E2E ×2 committed (row 10 endi to'liq yashil)** · cockpit+drills ·
100/100+clean-room. **1 🟡:** spans/cost — zanjir bir marta real isbotlangan,
uzluksiz live coverage flip'dan keyin. **4 ⏳:** T1/T3/T4/T6 — 0/3 shadow kun,
avtopilot yig'moqda.

## 8.4 Verdict

**Kompozit ≈ 9.3/10.** Qurilish 100% tugagan va uchinchi tomon tekshiruvidan o'tdi;
"documented ≫ enforced" tezisi butunlay yopildi (negativ-problar hatto E2E ichida).
Σ=115 endi kod yozishga emas, faqat kalendarga bog'liq: FINALE avtopiloti
(D-1 shartli flip + P5 closer) taxminan **5–6 kunda** (yoki FINALE_FAST bilan ~2
kunda) yakuniy attestatsiya va `v2.1.0 "ORGANISM LIVE"` tag'ini o'zi chiqaradi.
Qo'lda qiladigan yagona ish: hech narsa.
