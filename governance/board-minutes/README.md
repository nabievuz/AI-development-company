# Board Minutes — Cadence and Index

**Owner:** Chairman of the Board
**Status:** v1 — adopted 2026-05-18
**Authority:** RACI 1.5 (Chairman A), Charter §5 (strategic cadence).

This directory is the canonical record of board activity. If a decision is not written here (or in a linked issue / PR), it did not happen — per Charter Value 2.

## Cadence

| Cadence | Day / Time | Duration | Required | Notes |
|---|---|---|---|---|
| **Weekly board sync** | Mondays, 10:00 UTC | 30 min | Chairman, Board Member, CEO | Operating review. Uses `templates/weekly-agenda.md`. |
| **Monthly strategic review** | First Monday of each month, 10:00 UTC | 60 min | Chairman, Board Member, CEO, all CXOs | Replaces that week's sync. Uses [`templates/monthly-agenda.md`](templates/monthly-agenda.md). Next: 2026-06-01. |
| **Ad-hoc** | As needed | — | Quorum: Chairman + Board Member | Triggered by `request_board_approval` SLA breach, SEV-1, or charter amendment. |

Schedule is binding on the Chairman, Board Member, and CEO. CXOs attend the monthly review by default and the weekly sync only when their dept is on the agenda.

## File layout

```
board-minutes/
  README.md                          # this file — cadence + index
  templates/
    weekly-agenda.md                 # standing weekly agenda template
  YYYY/
    YYYY-MM-DD-weekly.md             # weekly sync minutes (one per Monday)
    YYYY-MM-DD-monthly.md            # monthly strategic review minutes
    YYYY-MM-DD-adhoc-<slug>.md       # ad-hoc minutes
```

One file per meeting. Filename uses the meeting date in ISO format. Filenames are immutable once merged; corrections go in a follow-up entry that links back.

## Authoring rules

1. **Chairman drafts minutes within 24h of the meeting.** Board Member reviews; CEO is informed.
2. **Every decision in minutes must link to:**
   - the authority that grants it (charter section or RACI row), and
   - the issue or PR that captures the follow-up work.
3. **Action items are tracked as DAS issues**, not as TODOs in this file. Minutes link to the issues; issues link back to the minutes file path.
4. **Dissent is recorded.** If the Board Member disagrees with a Chairman call (or vice versa), the dissent goes in the minutes with reasoning. Per RACI §Conflict resolution.
5. **Cancellations.** If a meeting is cancelled, still create the dated file with `Status: cancelled` and the reason. Empty weeks are not allowed.

## Index

| Date | Type | File | Status |
|---|---|---|---|
| _(none yet)_ | — | — | — |

Update this index when a new meeting file lands.
