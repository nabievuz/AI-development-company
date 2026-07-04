# Stage 6 — Maintenance: KPI monitor and feedback loop

## KPI monitoring
- Median first-response time tracked against the ten-minute target.
- Triage routing accuracy tracked against the 90% threshold.
- Auto-sent reply count monitored to stay at exactly zero.

## Cost vs value
- Model and infrastructure spend tracked against the USD 800 plus USD 200 caps.

## Feedback loop
- Human corrections to routing and drafts are captured and fed back into the eval
  set, so accuracy improves over time and regressions are caught in CI.

## GATE-6 exit
KPIs are reported against the Stage-1 baselines, the cost-to-value balance is
positive, and human corrections are entering the eval set.
