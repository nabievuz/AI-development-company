# Golden task — senior-pm — requirements-decomposition

**Role:** `senior-pm`
**Competency:** requirements decomposition (turning one bundled, informal
stakeholder ask into discrete, independently-implementable requirements)
**Kind:** deterministic

## Prompt

`fixtures/stakeholder-thread.md` is a forwarded thread bundling several
distinct asks from Sales, Finance, Auditors, Legal, and Ops into one informal
message. Decompose it into the atomic requirements hidden inside it — the
set of independently-shippable pieces of work a backend/frontend engineer
could each turn into one ticket.

## Input

- `fixtures/stakeholder-thread.md` — the forwarded thread, unscoped.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "requirements": ["<one-sentence requirement>", "<one-sentence requirement>", ...] }
```

Each string should describe ONE atomic requirement in your own words (not a
verbatim copy of the thread) — precise enough that an engineer could act on
it without re-reading the thread.

## Scoring (deterministic, fractional credit)

The thread bundles a fixed number of atomic requirements. `verify.py` checks
each submitted string against a set of required keyword groups (not shown
here — that key lives only in `verify.py`); a submitted requirement "covers"
an atomic requirement when it contains ALL of that requirement's keywords
(case-insensitive substring match). Each atomic requirement can be covered at
most once (matching it twice does not double-count).

```
credit = clamp01( (covered - padding_penalty) / total_atomic_requirements )
```

where `padding_penalty` only kicks in once the submission lists far more
items than there are atomic requirements (discourages "dump every possible
sentence and hope one matches" instead of genuine decomposition). An empty
or missing `requirements` list scores `0.0`.
