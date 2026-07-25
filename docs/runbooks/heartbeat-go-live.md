# Runbook — HEARTBEAT go-live (flip `heartbeat_enabled: true`)

> **Audience: the Founder.** This is the safe, evidence-gated procedure for taking
> the WS4 HEARTBEAT autonomous-tempo substrate from **shadow** to **live**. It
> closes ORGANISM remediation **R-4** and unblocks §5 contract rows T1/T3/T4 (and
> therefore the `VERSION 2.0.0` release).
>
> Flipping `heartbeat_enabled` is a **Founder-only act** (QONUN-5 never-auto-approve,
> ADR-0027 SI-7). No agent may do it. This runbook makes the decision **evidence-gated**,
> not vibes.

## What "live" changes

`config/features.yaml` `heartbeat_enabled` gates only whether
`scripts/loop_controller.py --tick` **dispatches** a wave. With it `false` (today),
`--tick` runs in *shadow-observe* mode: it evaluates what it *would* do and logs it,
but dispatches nothing. With it `true`, an OS scheduler entry (launchd/cron) invoking
`--tick` dispatches real waves on the declared triggers — always inside the ADR-0027
safety rails (SI-1..SI-7): one wave at a time, quiet hours, per-day budget cap,
break-glass kill-switch, and **gates/interrupt-cards always wait for the Founder**.

## Two clocks — and one release criterion — do not conflate

Three different "≥N" numbers appear in this runbook. They gate three different
things (ADR-0027 SI-7: "two distinct clocks, do not conflate"). Read this table
before reading any step below.

| # | The bar | Invariant / checker | What it gates | What it does NOT gate |
|---|---|---|---|---|
| 1 | **≥ 3 clean days** (`T1 ≥ 0.60 ∧ T2 ≤ 0.15 ∧ T7 holds`) | ADR-0027 **SI-7**; `scripts/check_heartbeat_readiness.py` (`MIN_CLEAN_DAYS_HEARTBEAT = 3`) | **The heartbeat going live** — the Founder flipping `heartbeat_enabled: true` (step 4) | `config/loop.yaml`; the `VERSION` bump |
| 2 | **≥ 7 clean days** *plus* a human-approved GATE-6 `capability_promotion` record (`max_quality_drop 0`) | ADR-0027 **SI-2**; `scripts/loop_controller.py` (`MIN_CLEAN_DAYS = 7`, `evaluate_promotion`) | **The self-optimizing LADDER** — a human editing `config/loop.yaml` `mode` one rung (`shadow → measured → …`) | `heartbeat_enabled`. The heartbeat can be live while `loop.yaml` stays `shadow` **forever** |
| 3 | **≥ 7 rolling waves** at `T1 ≥ 0.60 / T2 ≤ 0.15` with T7 holding | ORGANISM §5 contract rows (step 7 below) | **A release** — bumping `VERSION` to `2.0.0` + CHANGELOG | Neither clock above. It is **not** a clock at all — it counts *waves*, not days, and authorizes no autonomy |

Rows 2 and 3 both contain the numeral 7 and mean entirely different things. Row 1
is the only one this runbook's flip depends on.

## Precondition (the real blocker)

**Waves must be *counted* to produce shadow evidence.** The anti-gaming regime
(`check_metric_gaming` / `check_wave_reconciliation`) counts a completion only with a
merged PR + green CI + T7 pass. A **local-only** wave (no PR/CI) is honestly *not
counted* and does **not** advance the T1/T2 shadow window. So before this runbook can
even begin accumulating evidence, resolve the **push/CI strategy** (a Founder
decision) so `/daslab-cycle` waves land as counted, CI-backed units.

**MUSTAQIL monthly credit ceiling (SPEC-010 FR-004 / discovery Q9).** The Claude
subscription's **monthly credit** is the *outer* dispatch ceiling — it sits
alongside, never instead of, the SI-5 per-run/per-day caps in `config/budgets.yaml`.
Confirm the ceiling data before starting the window:

```
python3 scripts/ws_b_admission.py     # prints the mustaqil caps + monthly_credit_ceiling
```

Expected: `on_exhaustion: sanctioned_pause` and `metered_overflow: False`. Credit
exhaustion is a **sanctioned pause** — an expected idle, like waiting at a gate —
never a failure and never a reason to keep dispatching. `metered_overflow` stays
OFF; turning it on is a separate Founder-only budget decision made in
`config/budgets.yaml`. The file also carries an open
`[NEEDS VERIFICATION at WS-B go-live]` marker on the live plan's Agent-SDK terms:
confirm the active plan and its credit before the flip. Design for wiring this
ceiling into the `--tick` path: `docs/design/ws-f-tempo-verification.md` §3.

## Steps

1. **Accumulate a ≥3-day clean shadow window.** With the scheduler enabled in
   **shadow** (`heartbeat_enabled: false`), run counted `/daslab-cycle` waves over
   ≥3 calendar days. After each day, append that day's KPI row:
   ```
   python3 scripts/metrics_history_feeder.py --date <YYYY-MM-DD>
   # or scan the whole store, one row per day:
   python3 scripts/metrics_history_feeder.py --all
   ```
   A **clean day** = T1 busy_fraction ≥ 0.60, T2 idle_wave_rate ≤ 0.15, and T7 holds.

2. **Check readiness (evidence-gated).**
   ```
   python3 scripts/check_heartbeat_readiness.py
   ```
   It reads `board/.metrics-history.jsonl` and reports the clean-day streak vs the
   3-day bar. It **never** fabricates readiness — an empty/short/unclean window is
   `NOT READY`. Proceed only on **`VERDICT: READY`** (exit 0).

3. **Confirm the Founder-verified gates** with the comprehensive go/no-go report:
   ```
   python3 scripts/heartbeat_go_no_go.py
   ```
   This reads-only evidence report consolidates all gates and produces either VERDICT: GO (exit 0) or VERDICT: NO-GO (exit 1). Gates report PASS, FAIL, or UNKNOWN states; UNKNOWN never counts as a pass.

   Individual checks (if preferred):
   ```
   python3 scripts/kill_switch_drill.py --smoke      # kill-switch drill passes
   python3 scripts/check_never_auto_approve.py --board board --config config/risk_taxonomy.yaml
   python3 scripts/ws_b_admission.py                 # monthly credit ceiling intact + active plan confirmed
   ```
   and confirm **zero** open gate/interrupt-card violations in the event log.

4. **THE FLIP (Founder-only).** Edit `config/features.yaml`:
   ```
   heartbeat_enabled: false   →   heartbeat_enabled: true
   ```
   This is governance — commit it yourself; no agent may make this edit (QONUN-5).
   Leave `config/loop.yaml` `mode: shadow` / `auto_apply: false` untouched — the
   self-optimizing LADDER is a **separate** gate (ADR-0027 SI-2; `check_loop_mode.py`
   forbids `limited_live`/`full`).

5. **Watch the first live cycles.** `scripts/cockpit_html.py --serve` (live console) +
   the Action Console for any interrupt-card. `scripts/check_heartbeat_readiness.py`
   will now report `heartbeat_enabled: true (LIVE)`.

6. **Rollback (any time).** The break-glass kill-switch stops dispatch immediately:
   ```
   python3 scripts/break_glass.py            # engage; --tick becomes a no-op (SI-3)
   ```
   or set `heartbeat_enabled: false` again.

7. **Release — the *release criterion*, row 3 of the two-clocks table; NOT a clock.**
   Once ≥7 **rolling waves** show T1 ≥ 0.60 / T2 ≤ 0.15 with T7 holding and the §5
   contract rows are green on committed evidence, bump `VERSION` to `2.0.0` +
   CHANGELOG (the deferred half of DAS-1537 / R-6). This counts *waves*, not days;
   it gates a version bump only, and authorizes no autonomy — it is neither the
   ≥3-day heartbeat clock (row 1) nor the ≥7-clean-day LADDER clock (row 2).

## Related

- ADR-0027 (scheduler safety, SI-1..SI-7) · `board/schedule.yaml` · `config/features.yaml`
- `scripts/check_heartbeat_readiness.py` (this runbook's gate) · `scripts/loop_controller.py --tick`
- `scripts/metrics_history_feeder.py` (feeds the clean-day window)
- [`docs/design/ws-f-tempo-verification.md`](../design/ws-f-tempo-verification.md) —
  the SI-1…SI-7 evidence map + per-invariant verification protocol (DAS-1617);
  §3 designs the monthly-credit-ceiling wiring, §4 records this addendum
- `config/budgets.yaml` `mustaqil.monthly_credit_ceiling` (the outer ceiling)
