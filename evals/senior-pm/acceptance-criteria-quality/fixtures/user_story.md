# User story — password reset via email link

**As a** user who forgot their password,
**I want** to request a reset link by email and set a new password,
**so that** I can regain access to my account without contacting support.

## Context from support tickets (last quarter)

- A recurring complaint: users click a reset link from an old email (days
  later) and it silently fails with no useful message.
- Two incidents where an automated script hammered the "forgot password"
  endpoint hundreds of times in a minute for the same account — no limit
  currently stops that.
- Several users pasted their email with a trailing space or missing `@`
  and got a generic 500 instead of a clear validation message.
- One security report: a reset link was used successfully, then used AGAIN
  a few minutes later by someone with access to the same inbox — the token
  should not be reusable after the password has already been changed once.

## Your task

Write the acceptance criteria for this story. Cover the happy path AND the
edge cases implied by the support-ticket context above. Use whatever format
you think best communicates a testable condition (Given/When/Then is
encouraged but not mandatory).
