# PR #4127 — `feat(payments): add POST /wallet/transfer endpoint`

**Author:** backend-eng-1
**Base:** `main`  **Branch:** `feat/wallet-transfer`

## Summary
Adds a new endpoint that moves funds between two internal wallet accounts.
This is a money-moving endpoint that clients (including a retrying mobile
client) will call over an unreliable network.

## CI status
- Unit tests: **green** (42/42 passed)
- Lint: **green**
- Integration tests: **green**

## Review comments

**@security-eng** (2 hours ago, thread status: **unresolved**, marked
`blocking`):
> This endpoint has no idempotency key and no dedup mechanism. A client
> retry on timeout will double-transfer funds between wallets. This needs
> to be fixed before merge — CI is green because there's no test for the
> retry case yet.

**@backend-eng-2** (1 hour ago, thread status: resolved):
> Nit: rename `amt` to `amount` for readability. Author pushed a fix,
> thread resolved.

**Author's latest comment** (30 minutes ago):
> Addressed the naming nit. Still need to look at the idempotency
> question — filing as a fast-follow ticket so we can ship this sprint.

## Current state
The security thread is still open and still tagged `blocking`. No commit
since the author's last comment addresses it. CI is green only because no
retry/duplicate-request test exists yet.
