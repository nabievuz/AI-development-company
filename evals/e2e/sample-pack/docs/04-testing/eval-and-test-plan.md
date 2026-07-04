# Stage 4 — Testing: test and eval plan

## Automated tests
- Unit tests for auth, workspace isolation, and the task state machine.
- Integration tests that exercise create/read/update/delete across two workspaces
  and assert no cross-workspace read is ever possible.
- A contract test for the Slack `notify` path using a stub webhook, asserting
  email masking and the three-retry policy.

## Non-functional checks
- Latency: a load test asserts task-create p95 stays at or under 400ms.
- Delivery: a soak test asserts Slack notification success at or above 99%.

## Red-team pass
- Attempt cross-workspace reads via forged workspace ids.
- Attempt to leak an unmasked email through the Slack payload.

## GATE-4 exit
The test and latency suites run in CI with thresholds, integration tests are
green, the two red-team findings classes are closed, and the QA lead signs off.
