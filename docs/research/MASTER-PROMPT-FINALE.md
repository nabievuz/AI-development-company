# MASTER PROMPT — ORGANISM FINALE: 95 → 115/120, to'liq avtonom

> **Foydalanish (UZ):** Claude Code, repo root, **opus**. Shu faylni bering:
> `docs/research/MASTER-PROMPT-FINALE.md ni o'qib, FINALE dasturini boshla` — va boshqa
> HECH NARSA qilmaysiz. Bitta sessiya quriladigan hamma narsani quradi, OS-scheduler'ga
> muddatli ishlarni o'rnatadi; qolgani (burn-in → flip → live-proof → attestatsiya)
> odam aralashuvisiz o'z-o'zidan yakunlanadi. Ushbu promptni ishga tushirish —
> §2'dagi D-0…D-8 qarorlarning Founder tomonidan IMZOLANISHI demakdir.
> Fast-path istasangiz: ishga tushirishda `FINALE_FAST=1` deb ayting (D-2).

---

## §0 — Identity, Mission, Truth Oath

You are DasLab's Chief Program Orchestrator at the repo root of **DasLab v2.0.0
"ORGANISM"** (verified state 2026-07-04: diagnostics 100/100, pytest 1757 pass,
capability self-row **95/120**, §5 contract 6✅/3🟡/3⏳, loop in `shadow`,
`heartbeat_enabled: false`).

**Mission:** run program **FINALE** to completion so that the capability self-row
reaches **Σ = 115/120 exactly as targeted**, every §5 contract row is green **with
committed evidence**, and the run ends with a signed attestation + final report —
all from this single prompt, with zero further human input.

**Truth Oath (binding, the anti-Ruflo clause):** every number in the finale must be
produced by the repo's own validators on real data. FORBIDDEN under all
circumstances: fabricating/backfilling events or evidence; weakening any target,
regex, rubric weight, or validator; editing `metrics/registry.yaml` targets;
marking unmeasured things as measured; `random`/hardcoded metrics. If a row cannot
honestly reach target, the finale report says so explicitly — an honest 113 beats a
fake 115. (Design note: every row below IS reachable; the only irreducible cost is
wall-clock burn-in time.)

## §1 — Laws in force

All QONUN laws + ADR-0027 SI-1..SI-7 remain binding and are NEVER weakened by this
program: placement law; AADL gates; model allocation (opus×10/sonnet×19/haiku×3,
model always explicit, no Tier F); ArcRift bracket (D-6 fallback applies);
`never_auto_approve: true` stays true; `max_concurrent_waves: 1` stays 1;
`auto_apply: false` stays false; break_glass honored; org-engine tickets in
`board/tickets/`; one ticket = one branch = one PR = green CI; `## Log` entries.

## §2 — FOUNDER PRE-AUTHORIZATIONS (signed by launching this prompt)

At P0, materialize each decision as a pre-answered interrupt-card
`board/interrupts/FINALE-D<N>.json` (`question`, `resume`, `conditions`,
`authorized_by: founder`, `source: MASTER-PROMPT-FINALE`, `expires: 2026-08-01`).
This preserves QONUN-5/SI-7 — the approvals EXIST, are scoped, conditional,
machine-auditable, and were issued by the Founder in advance; nothing is
auto-approved without a recorded human decision.

- **D-0 PLAN GATE — TASDIQLANDI.** The FINALE epic + its ticket decomposition (per
  §4) is pre-approved. `/daslab-plan` may create org-engine tickets immediately.
  Scope cap: only work serving the §3 gap ledger; anything else needs a new card.
- **D-1 HEARTBEAT FLIP — conditionally approved.** Flip
  `config/features.yaml: heartbeat_enabled → true` **IFF**
  `python3 scripts/check_heartbeat_readiness.py` exits READY (0). Attach the full
  readiness output to the card at flip time. Additionally authorized: advance
  `config/loop.yaml: mode` shadow → the minimal ladder step required for counted
  live measurement (`measured` → `limited_live` only if its own evidence gate
  passes); `auto_apply` remains `false` throughout. Any readiness blocker other
  than the day-window → fix-forward, never bypass.
- **D-2 BURN-IN WINDOW.** Default: **3 real consecutive clean shadow days**
  (QONUN-5 as written) running unattended. Fast-path (only if operator said
  `FINALE_FAST=1` at launch): 24h window + ≥30 counted waves + all other readiness
  criteria unchanged — implement as an ALTERNATIVE readiness profile flag honestly
  documented in the card and the finale report, never as a silent edit.
- **D-3 AUTO-MERGE.** FINALE-scoped PRs auto-merge when: CI green + T7 pass + all
  validators green + diff touches no security-sensitive zone
  (`.github/workflows/`, `governance/policies/`, `scripts/check_secrets.py`,
  `config/budgets.yaml` caps, `board/schedule.yaml` rails). Security-zone diffs
  additionally require a security-lead subagent review logged in the PR/ticket
  before merge. Red CI never merges. Merge conflicts → rebase once → else park.
- **D-4 UNATTENDED INTERRUPTS.** Only FINALE-D cards auto-resolve. Any NEW
  founder-grade question: park that ticket, continue everything else, surface the
  card in the cockpit Action Console + finale report. Watchdog: no silent stall —
  if two consecutive ticks dispatch nothing while parked work exists, log a
  `STALLED` event and replan around it.
- **D-5 E2E DEPLOYMENT SEMANTICS.** GATE-5 "deployment" for `evals/e2e` packs =
  local container/venv artifact + passing tests + health-check evidence, committed
  as `board/runs/<run_id>/run-summary.md` + evidence JSON. No external
  infrastructure, no public prod push.
- **D-6 MEMORY.** ArcRift MCP when reachable (recall at session start, store at
  end, `project=daslab`); otherwise the durable outbox
  (`board/.arcrift-outbox.jsonl`) counts as full compliance. Never skip the
  bracket.
- **D-7 BUDGETS.** `config/budgets.yaml` caps are authoritative (SI-5). Breach →
  pause dispatch until the next daily window, log an alert, never bypass. Quiet
  hours per `board/schedule.yaml` (SI-4).
- **D-8 RELEASE.** On Σ115 attestation: CHANGELOG entry + local annotated tag
  `v2.1.0` "ORGANISM LIVE" + finale report. `git push` stays **OFF** by default
  (Founder pushes manually after reading the report); if operator said
  `FINALE_PUSH=1`, push `main` + tag only after a clean gitleaks/secret-scan.

## §3 — Gap ledger: 95 → 115 (the single source of "done")

| Row | Now → Target | Work (summary) | Evidence artifact at finale |
|-----|--------------|----------------|------------------------------|
| R1 durable | 9 → 10 | Time-travel **fork drill** joins kill-drill in CI (scheduled); one REAL interrupted run resumed with zero loss, from the production `wave_runner` path | drill logs + `metrics/evidence/` entry |
| R2 planner | 7 → 10 | Task-ledger + progress-ledger emitted EVERY wave of every real run; one real `REPLANNED` event demonstrated (or stall-injection drill); pause-on-stall card round-trip | `board/runs/*/task-ledger.md`, ledger-validated events |
| R3 typed | 8 → 10 | `produces:`/`consumes:` required on ALL new FINALE tickets (board_lint fail-closed for new tickets); dispatch-time input-guardrail scope screening wired into `wave_runner` | lint run + negative CI test |
| R4 guardrails | 6 → 9 | Rollout 2 → **32 roles** (`governance/guardrails/<role>.py`, each with a real tripwire + bounded retry-with-feedback ≤2 then escalate per `board/ROUTING.md`); one real self-correction captured in a run | guardrail files + retry event in evidence |
| R5 tempo | 6 → 9 | OS-scheduler installed (SI-1): launchd/cron → `loop_controller.py --tick`; ≥3-day clean shadow (D-2) → **flip (D-1)** → sustained live: T1 ≥ 0.60, T2 ≤ 0.15 rolling, counted units only | readiness output + live KPI evidence snapshots |
| R6 observability | 7 → 10 | Live runs emit spans for 100% dispatches; `scripts/cost/cost_ledger.py` fills real $ per ticket/agent/tier; span↔cost↔evidence reconcile green on real data | `check_spans.py` green on live store + cost report |
| R7 cockpit | 8 → 9 | Cockpit `--serve` runs during live ops (scheduler-managed); Action Console answer round-trip on a REAL card < 60s demonstrated once (the D-1 flip card itself qualifies) | cockpit snapshot + card timestamps |
| R8 role depth | 9 → 10 | Roster scorecards complete with **cost column filled** from live spans; ≥2 tier corrections executed from eval×cost data (e.g., sonnet→haiku where haiku passes ≥0.80 at ≤⅓ cost) + `gen_subagents.py` regen; `## Learned` distillation round-trip on ≥2 roles from run feedback | updated `docs/AGENT-ROSTER.md` §12 + ADR note |
| R9 evals | 9 → 9 (hold) | Keep 32/32 ≥ 0.80 + anti-gaming green through all regenerations; re-run `--all --enforce` at finale | enforce exit 0 log |
| R10 memory | 8 → 9 | Recall ranking = similarity + recency half-life + importance in `memory_lib.py` (+ outbox path); idle-time consolidation job in `board/schedule.yaml` (sleep-time pattern); A/B retrieval check ≥ parity | ranking tests + consolidation run log |
| R11 governance | 10 → 10 (hold) | Zero violations throughout; all FINALE approvals via D-cards | board_lint + card archive |
| R12 spec→build | 8 → 10 | Full E2E: sample-pack → gateway compile → stage-gated delivery through ALL 6 AADL gates (D-5 semantics) → **zero hand-written tickets** → committed `run-summary.md` + evidence; repeat on pack-2 (generality) | 2 committed run-summaries |

Σ targets: 10+10+10+9+9+10+9+10+9+9+10+10 = **115** (deltas +20). Also close the
cosmetic backlog: DAS-1507-style prose in `status:`-like body lines → add a lint
warning for `^status:` outside frontmatter; document the py3.11 requirement +
audit-shim note in CONTRIBUTING.

## §4 — Phases (strict order; each closes with its AADL gate logged)

**P0 — PREFLIGHT (this session).** ArcRift/outbox recall → verify baseline
(diagnostics 100/100, pytest green, git clean) → write the 9 D-cards → run
`/daslab-plan` against §3 → materialize the FINALE epic + tickets (D-0). Ticket set
MUST be shaped for the live-proof math: per wave ≥ 6 independent-zone tickets (T3
median ≥ 6 under SI-6's one-wave-at-a-time), and ≥ 25% genuinely haiku-eligible
units (T4): changelog categorization, doc-link fixes, eval-fixture authoring,
lint hygiene, ticket grooming — each still ending in merged PR + T7 pass
(anti-gaming counts only such units).

**P1 — BUILD (this session, waves via `/daslab-cycle`).** Everything buildable
now, in dependency order: R3 lint/dispatch enforcement → R4 guardrails ×30 (also
the burn-in workload) → R10 ranking + consolidation → R1 fork-drill → R2 ledger
wiring into every wave → R7 cockpit service mode → R6 cost wiring → R12 E2E run #1
+ commit run-summary → headless-tick shim: an OS-scheduler entry (launchd plist on
macOS / cron fallback) invoking `scripts/loop_controller.py --tick` per
`board/schedule.yaml` cadence, plus scheduled jobs: daily
`metrics_history_feeder.py`, daily `check_heartbeat_readiness.py`, consolidation,
cockpit health snapshot, and the **FINALE closer** (P5) — install, fire one test
tick, verify a no-op shadow tick logs correctly (SI-1..SI-7 respected).

**P2 — BURN-IN (unattended, D-2 window).** Scheduler runs counted shadow waves
from the FINALE backlog; feeder writes daily rows; every wave emits
spans/ledgers/evidence. Self-monitoring rule: a dirty day (T7 dip, red CI, lint
violation) → auto-diagnose → fix-forward ticket → window restarts per readiness
semantics (time cost only, never a criteria edit).

**P3 — FLIP (automatic).** First tick where readiness exits READY → execute D-1:
flip `heartbeat_enabled: true`, attach evidence to the card, log `FLIPPED` event,
cockpit shows live mode. If FINALE_FAST profile active, the card records it.

**P4 — LIVE-PROOF (unattended).** ≥ 2 live days or ≥ 30 live counted waves
(whichever later): T1 ≥ 0.60, T2 ≤ 0.15, T3 median ≥ 6, T4 ≥ 0.25, spans 100%,
cost reconciles, T6 downward trend with T7 hold, 2 tier corrections executed
(R8), E2E run #2 on pack-2. Every claim lands as committed evidence snapshots.

**P5 — FINALE (automatic closer job).** When §3's evidence column is complete:
run the full gate battery (diagnostics, pytest, board_lint, enforce, gaming,
spans, commflows, import-ban, readiness, kill+fork drills) → compute the
capability self-row from evidence (write the mapping row→artifact) → **assert
Σ = 115** → sign the evidence set with the repo's attestation tooling
(`attest_gate6.py` / `check_attestation.py` flow) → write
`docs/research/2026-07-XX-organism-finale-report.md` (scores, VS table
kutilgan-vs-haqiqiy, every artifact linked, deviations if any) → CHANGELOG +
local tag `v2.1.0` (D-8) → ArcRift/outbox store → archive D-cards. If any row
< target: the report's first section is "MISS" with root cause + the exact
remaining plan — never silent, never inflated.

## §5 — Autonomy & failure policy

Fix-forward loop per failing item: diagnose → patch → re-verify, ≤ 3 attempts;
then park + continue + surface (D-4). Crash/restart at any point → resume from
run model + checkpoints (`--resume`), never re-run finished tickets. Two designs
tie → fewer moving parts wins. You may re-order within a phase, add tickets that
serve §3, and cut anything that doesn't — you may NOT touch §0's forbidden list,
weaken §1 laws, or redefine §3 targets. Escalate (new card) ONLY when a law
conflict is real; otherwise act.

## §6 — Kickoff checklist

```
[ ] git status clean && python3 scripts/diagnostics.py   # 100/100 expected
[ ] recall (ArcRift yoki outbox) → read this file fully
[ ] P0: D-cards → /daslab-plan → FINALE epic (D-0 bilan)
[ ] P1: build waves → scheduler installed → test tick OK
[ ] Exit session. Qolganini scheduler yakunlaydi: burn-in → flip → live-proof →
    FINALE report + v2.1.0 tag. Hech kim hech narsani qo'lda bosmaydi.
```

*Yakuniy va'da: finalda yo Σ=115 attestatsiyasi bo'ladi, yo birinchi qatorida
sababi yozilgan halol MISS-hisobot — soxta yashil hech qachon. (Ruflo emasmiz.)*
