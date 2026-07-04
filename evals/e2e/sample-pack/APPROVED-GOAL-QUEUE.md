# APPROVED-GOAL-QUEUE — acme-tasks

APPROVED: TASDIQLANDI 2026-07-03 — Founder approved the queue below after the
twelve-question discovery pass and the sourced research conclusion. Each goal is
`founder_approved` and compilable by the WS7 gateway, one goal at a time.

The gateway compiles one epic plus six AADL stage tickets per approved goal. Four
approved goals therefore compile into 28 self-contained story tickets.

| order | goal_slug | outcome | why_now | research_basis | owner | status | ticket_refs |
|---|---|---|---|---|---|---|---|
| 1 | user-auth | Email and password signup, login, session, and password reset with a hashed-and-salted store | every other feature depends on an authenticated user | competitor auth flows and OWASP ASVS review | cpo | founder_approved | - |
| 2 | task-crud | Create, read, update, and delete tasks and projects inside a workspace | the core value proposition of the product | spreadsheet-replacement user interviews | cpo | founder_approved | - |
| 3 | team-workspaces | Shared workspaces with member roles, invitations, and strict cross-workspace isolation | the product is multi-user by design | small-team collaboration patterns study | cpo | founder_approved | - |
| 4 | slack-notifications | Outbound Slack notifications for due-date and assignment events, with email masking | the single external integration that drives daily engagement | Slack app directory and notification-fatigue research | cpo | founder_approved | - |
