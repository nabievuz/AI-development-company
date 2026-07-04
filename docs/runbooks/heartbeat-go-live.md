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

## Precondition (the real blocker)

**Waves must be *counted* to produce shadow evidence.** The anti-gaming regime
(`check_metric_gaming` / `check_wave_reconciliation`) counts a completion only with a
merged PR + green CI + T7 pass. A **local-only** wave (no PR/CI) is honestly *not
counted* and does **not** advance the T1/T2 shadow window. So before this runbook can
even begin accumulating evidence, resolve the **push/CI strategy** (a Founder
decision) so `/daslab-cycle` waves land as counted, CI-backed units.

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

3. **Confirm the Founder-verified gates** (this tool cannot check them for you):
   ```
   python3 scripts/kill_switch_drill.py --smoke      # kill-switch drill passes
   python3 scripts/check_never_auto_approve.py --board board --config config/risk_taxonomy.yaml
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

7. **Release.** Once ≥7 rolling waves show T1 ≥ 0.60 / T2 ≤ 0.15 with T7 holding and
   the §5 contract rows are green on committed evidence, bump `VERSION` to `2.0.0` +
   CHANGELOG (the deferred half of DAS-1537 / R-6).

## Related

- ADR-0027 (scheduler safety, SI-1..SI-7) · `board/schedule.yaml` · `config/features.yaml`
- `scripts/check_heartbeat_readiness.py` (this runbook's gate) · `scripts/loop_controller.py --tick`
- `scripts/metrics_history_feeder.py` (feeds the clean-day window)
