# Three incoming items for the Backend EM's queue

Per the Backend EM's charter (`engineering/agents/backend-em/AGENTS.md`):
decisions inside team scope get **delegated** to an engineer
(`backend-eng-1` or `backend-eng-2`); decisions that exceed the EM's
charter authority or carry cross-department impact get **escalated** to the
CTO.

## Scenario 1

A ticket asks for a new read-only field on the *internal* admin dashboard
API, sourced from an existing table. Small diff, no schema migration, no
external consumers, normal sprint work.

## Scenario 2

A ticket proposes deleting production database backups older than 30 days
to cut storage cost. Legal has an open data-retention policy requiring
7-year retention on financial records, and no one has confirmed whether any
of the backups being deleted fall under that policy. There is no rollback
plan if a required backup is deleted.

## Scenario 3

A ticket asks for a refactor of the internal in-process caching layer used
by one backend service, purely for performance, with existing test coverage
and no API or schema change. Entirely inside the backend team's own service
boundary.
