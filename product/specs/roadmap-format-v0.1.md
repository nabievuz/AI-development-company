# Roadmap Format

**Owner:** CPO
**Status:** Active format definition
**Established:** 2026-05-18
This document defines the canonical format for `roadmap.md` — the single, living artifact the product team uses to communicate what we are building, when, and why.

## Where it lives

- **Path:** `roadmap.md` at the repo root of `daslab/product`.
- **One file, no fragmentation.** Quarterly themes live in `specs/qN-YYYY-themes.md`; the roadmap links to them. Per-feature specs live in `specs/`; the roadmap links to them. The roadmap itself never duplicates that content.
- **Source of truth.** If `roadmap.md` and a slide deck disagree, `roadmap.md` wins. Decks are derived views.

## Cadence

| Event | Action |
|---|---|
| Weekly (Mondays) | CPO updates "Now" status lines and shifts items between Now / Next / Later as reality changes. |
| Quarterly (2 weeks before quarter start) | Themes for the upcoming quarter are locked in and linked from "Themes" section. |
| On material change | When an item is added, dropped, or substantially rescoped, update the same day and add a one-line note to the changelog. |

## Required sections

The file MUST contain these sections, in this order:

### 1. Header

- One-line product mission statement (mirrors `CLAUDE.md` mission, do not invent a second one).
- Last-updated date (ISO 8601: `YYYY-MM-DD`).
- Link to the current quarter's themes spec.

### 2. Now (this quarter)

The work we are actively executing or expect to start this quarter. Each item:

- **Title** — short, outcome-shaped (e.g. "DasFlow public beta live"), not task-shaped ("Build auth").
- **Theme** — which quarterly theme it serves. If it serves none, justify its inclusion or drop it.
- **Owner** — one named role (CPO / Sr. PM / Tech Writer / Product Analyst). Not a team.
- **Status** — `on track` / `at risk` / `slipped` / `done`. One word.
- **Target date** — ISO date. Best-known estimate, not a wish.
- **Spec link** — link to `specs/...md` if one exists, or "spec pending" with an owner.

### 3. Next (next quarter, indicative)

Same fields as Now, but understood as indicative — not committed. Promotion to Now happens at the quarterly planning event.

### 4. Later (parking lot)

Just title + one-line rationale. No owners, no dates. Items here are explicitly not scheduled. Cleared at least once per quarter so it does not become a graveyard.

### 5. Recently shipped

Last 8 weeks of completed items, with ship date and a one-line outcome. Drop items older than 8 weeks — they belong in commit history, not the roadmap.

### 6. Themes

Bullet list linking to the current and prior quarter theme docs (e.g. `specs/q3-2026-themes.md`). Two quarters of history is enough.

### 7. Changelog

Append-only list, newest first. One line per change:

```
- 2026-05-18 — CPO — Added "DasFlow public beta" to Now under Theme 1.
```

## Style rules

- **Outcome-shaped item titles.** "Public beta live" not "Build sign-up flow."
- **One owner per item.** "CPO + CTO" is not an owner; pick the accountable role.
- **No vague statuses.** "In progress" is not a status; `on track` / `at risk` / `slipped` is.
- **No hidden commitments.** If a date is in the file, we have committed to it externally; if not, mark as "TBD".
- **Cross-link, do not duplicate.** Detailed scope belongs in `specs/`; rationale belongs in the quarterly theme doc. The roadmap is the index, not the encyclopedia.

## Template

```markdown
# DasLab Product Roadmap

**Mission:** Define what we build, for whom, and why.
**Last updated:** 2026-MM-DD
**Current themes:** Q3 2026 themes (planned)

## Now — Q3 2026

| Item | Theme | Owner | Status | Target | Spec |
|---|---|---|---|---|---|
| DasFlow public beta live | 1 | Sr. PM | on track | 2026-09-15 | DAS-7 |
| Pricing A/B experiment | 2 | Sr. PM | on track | 2026-09-30 | spec pending |
| Event schema in production | 3 | Product Analyst | on track | 2026-09-01 | spec pending |

## Next — Q4 2026 (indicative)

| Item | Theme | Owner | Status | Target | Spec |
|---|---|---|---|---|---|
| Slack + GitHub integrations | TBD | Sr. PM | TBD | TBD | TBD |

## Later

- Self-host distribution (parked until hosted retention proves out)
- Enterprise SSO/audit (deferred per MVP brief)
- Design / marketing / ops agent archetypes

## Recently shipped

- 2026-05-18 — Stakeholder map v0.1 ([spec](stakeholder-map-v0.1.md))
- 2026-05-17 — MVP discovery brief v0.1 ([spec](mvp-brief-v0.1.md))

## Themes

- Q3 2026 themes (planned) — current
- (no prior quarter yet)

```

## Out of scope

- Per-team sub-roadmaps (only the org-level roadmap is standardized for now).
- Confidence levels / probability bands on dates (revisit once we have shipped one quarter and know our slip rate).
- Public-facing roadmap (separate decision for CMO + CPO once DasFlow is live).

## Revision policy

This format is owned by CPO. Material changes go through the same review path as any product spec: draft, C-suite review, publish. Minor edits (typos, clarifying examples) can be made directly with a note in this file's own changelog at the bottom.

