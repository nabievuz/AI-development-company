# Golden task — frontend-eng-2 — render-null-crash

**Role:** `frontend-eng-2`
**Kind:** deterministic

## Prompt

`fixtures/UserList.jsx` renders fine in Storybook (where `users` is always
passed as an array) but crashes in production with
`TypeError: Cannot read properties of undefined (reading 'map')` whenever the
parent renders `<UserList />` before its data has loaded (i.e. `users` is
`undefined`). Identify the exact line of the unguarded `.map(` call, and name
an appropriate fix strategy.

## Input

- `fixtures/UserList.jsx` — the component source.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "bug_line": <int>,     // 1-indexed line of the unguarded `.map(` call
  "fix_kind": "<str>"    // one of: optional_chaining | default_prop_value | early_return_guard
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `bug_line` points at the line with the unguarded `.map(` call
  (found by scanning the actual fixture source, not a hardcoded line number).
- `0.5` — `fix_kind` is one of the accepted null-safety fix strategies.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
