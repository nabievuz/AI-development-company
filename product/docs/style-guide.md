# DasFlow Documentation — Style Guide

**Status:** Draft — updated to reflect approved IA decisions; pending CPO review
**Author:** Technical Writer
**Date:** 2026-05-19

---

## Purpose

This guide governs all external-facing developer documentation on the DasFlow docs site. Every author — human or agent — must follow it before submitting content for review. The CPO is the approver of record.

---

## Voice and Tone

### Principles

| Principle | Means | Avoid |
|-----------|-------|-------|
| **Direct** | Lead with what the reader needs to do or know | Throat-clearing preambles ("In this section we will…") |
| **Concrete** | Show real code, real slugs, real API responses | Vague reassurances ("simply", "just", "easily") |
| **Respectful of time** | Every page completable in < 10 minutes | Padding, over-explanation of basics |
| **Technically honest** | State limits, failure modes, and caveats clearly | Glossing over constraints to appear simpler |
| **Neutral** | Explain; don't sell | Marketing language, exclamation points, superlatives |

### Person and register

- Use **second person** ("you", "your agent") throughout.
- Use **imperative mood** for instructions: "Run the command." not "You should run the command."
- Write **present tense**: "The API returns a JSON object." not "The API will return…"
- Avoid gendered pronouns. Prefer "they" or restructure the sentence.

### Forbidden words and phrases

| Do not use | Use instead |
|------------|-------------|
| simply / just / merely | *(omit or rewrite)* |
| easy / straightforward | *(show, don't claim)* |
| leverage | use |
| utilize | use |
| robust / powerful / seamless | *(be specific about the capability)* |
| please | *(imperative is sufficient)* |
| Note that… / Please note… | > **Note:** *(admonition block)* |

---

## Terminology Glossary

Use these terms exactly as written. Do not invent synonyms.

| Term | Definition | Notes |
|------|------------|-------|
| **Agent** | An AI worker assigned a role within DasFlow | Capitalize; never "bot", "AI", or "worker" |
| **Cycle** | A single execution window in which an agent wakes, works, and exits | Lowercase as a noun; never "run" or "tick" in user-facing copy |
| **Task** | A unit of work tracked in the DasFlow inbox | Capitalize only when referring to the UI element "Task" |
| **Inbox** | The agent's prioritized work queue | Capitalize when referring to the UI; lowercase when generic |
| **Role** | The function an agent is hired to perform (e.g., CTO, Developer) | Capitalize named roles; lowercase "role" as a concept |
| **Skill** | A specialist capability loaded into an agent | Lowercase; operator/advanced-user term — not featured in MVP onboarding copy |
| **Budget** | Spend limit assigned to an agent or team | Lowercase |
| **Company** | A DasFlow organizational workspace | Capitalize only when referring to the DasFlow object |
| **Reporting line** | The management chain above an agent | Lowercase; never "chain of command" in user-facing copy |
| **Comment** | A structured message on a Task | Capitalize when referring to the UI element |
| **Claim** | The act of an agent claiming a task for execution | Lowercase; use as a verb or noun |
| **Routine** | A recurring scheduled task | Lowercase; operator/advanced-user term — not featured in MVP onboarding copy |
| **DasFlow** | The product name | Always one word, capital D, capital F; never "Dasflow", "DAS Flow", or "dasflow" |

---

## Formatting Conventions

### Headings

- Use sentence case: "Create your first agent" not "Create Your First Agent".
- H1 (`#`) — page title only; one per page.
- H2 (`##`) — major sections.
- H3 (`###`) — sub-sections within a major section.
- H4 (`####`) and deeper — avoid; restructure or use a list instead.
- Do not skip heading levels.
- Do not end headings with punctuation.

### Paragraphs and lists

- One idea per paragraph; aim for ≤ 4 sentences.
- Use **bulleted lists** (`-`) for unordered items; use **numbered lists** for sequential steps.
- Lead list items with a verb when possible: "Install the CLI." not "CLI installation."
- Do not nest lists more than one level deep. If you need a second level, consider a sub-section instead.

### Code blocks

- Use fenced code blocks with a language tag:

  ````markdown
  ```bash
  git status
  ```
  ````

- Always use the language tag. Common tags: `bash`, `json`, `yaml`, `typescript`, `python`, `plaintext`.
- Use `plaintext` for output that is not a programming language.
- For inline code, wrap with backticks: `` `agent.id` ``, `` `status: done` ``.
- Annotate shell output separately from the command. Show the command, then add a `plaintext` block for output if it aids comprehension.

### Callouts / admonitions

Use blockquote-style callouts with a bold label. Four types only:

```markdown
> **Note:** Supplementary information that is useful but not required to proceed.

> **Tip:** A recommended shortcut or best practice.

> **Warning:** A gotcha that will cause silent failure or data loss.

> **Important:** A prerequisite or constraint that must be met before proceeding.
```

- Do not create custom callout types.
- Keep callout bodies to ≤ 3 sentences. For longer context, add a sub-section.

### Tables

- Use tables for reference data with 3+ items and 2+ columns.
- Left-align all columns.
- Include a header row.
- Keep cell content concise; link to longer explanations rather than embedding them.

### Links

- Use descriptive link text: "[Create an agent](/getting-started/first-agent)" not "[click here](/…)".
- Internal links use root-relative paths: `/getting-started/first-agent`.
- External links open in a new tab (handled by the site renderer; no special syntax required).
- Do not link to internal pages that do not yet exist. Use a plain reference instead.

---

## Versioning and Changelog Format

### API version references

DasFlow ships a single API version (`v1`) at launch. No parallel version documentation exists until a breaking change ships.

Rules:
- Do **not** add `/v1/` slug prefixes pre-emptively. Let the platform add versioning slugs when a second version actually ships.
- Reference the current version as `v1` only when a page is explicitly version-gated.
- When a feature is version-gated (post-v1), add an inline version badge at the top of the relevant section:

  ```markdown
  **Requires API v2+**
  ```

- Do not retroactively re-version content; add a note at the top if a section applies only to newer versions.

### Changelog entries

All product changelog entries (`changelog/`) follow this format:

```markdown
## YYYY-MM-DD — Release title

**Type:** Feature | Improvement | Fix | Breaking change

One-sentence summary of what changed.

### What changed

- Bullet list of specific changes.

### Why

One or two sentences on motivation.

### Migration (if breaking)

Step-by-step migration instructions.
```

Changelog entry types:

| Type | Use when |
|------|----------|
| **Feature** | A net-new capability that did not exist before |
| **Improvement** | An enhancement to existing functionality |
| **Fix** | A bug correction with no behavior change for correct usage |
| **Breaking change** | Any change that requires users to update code, config, or workflow |

---

## File and Slug Conventions

Consistent with `docs/IA.md`:

- All filenames: `kebab-case`, no spaces.
- Index files: `index.md` inside each folder.
- Asset filenames: `descriptive-name.png` / `descriptive-name.svg`.
- URL slugs mirror folder structure exactly: `getting-started/quick-start` → file `getting-started/quick-start.md`.
- Do not include dates in filenames (versioning is in frontmatter, not filenames).

### Frontmatter

Every page includes this frontmatter block:

```yaml
---
title: "Page title (sentence case)"
description: "One-sentence description for search and meta tags (≤ 160 characters)."
section: getting-started   # top-level section slug
content_type: tutorial     # tutorial | how-to | concept | reference | changelog
last_updated: YYYY-MM-DD
---
```

---

## Content Types

From the IA, five content types. Each has a distinct job and structure:

| Type | Job | Structure |
|------|-----|-----------|
| **Tutorial** | Guide a beginner through a learning experience step-by-step | Intro → Prerequisites → Numbered steps → Result → Next steps |
| **How-to guide** | Help an experienced user accomplish a specific task | Goal → Prerequisites → Steps → Troubleshooting |
| **Conceptual explainer** | Build mental model; explain why things work the way they do | Problem / motivation → Core idea → Details → Related concepts |
| **Reference** | Provide complete, accurate, scannable lookup material | Consistent entry format; no prose narrative |
| **Changelog** | Record what changed and when | Date → Type → Summary → Details (see Changelog format above) |

Mix of content types on a single page is discouraged. If a reference page needs a tutorial, link to the tutorial instead.

---

## Localization

DasFlow documentation is **English-only for the MVP**. This constraint is a CPO decision (see [docs/IA.md](IA.md)).

Writing rules to keep translation costs low when localization is eventually added:

- Avoid idioms, colloquialisms, and culture-specific references ("out of the box", "a la", "off the shelf").
- Avoid contractions in body copy — they are harder to translate accurately. (Contractions are acceptable in callouts and marketing-adjacent copy only if tone demands it.)
- Do not reference slang, internet memes, or humor that does not survive literal translation.
- Prefer short sentences (≤ 20 words) over complex subordinate clauses.
- Do not embed translatable strings inside code blocks.

This section will be removed and replaced with localization tooling guidance when translation begins.

---

## Accessibility

- All images must have descriptive `alt` text. A decorative image uses `alt=""`.
- Avoid conveying information through color alone (e.g., red = error). Pair color with text or an icon.
- Code examples must be copy-paste functional; do not use placeholder strings like `<your-token-here>` without explaining how to obtain the real value.

---

## Review Checklist

Before submitting a page for review, confirm:

- [ ] Follows heading structure (H1 → H2 → H3 only)
- [ ] Uses sentence case for all headings
- [ ] No forbidden words or phrases
- [ ] All DasFlow-specific terms match the glossary
- [ ] All code blocks have a language tag
- [ ] All callouts use only the four approved types
- [ ] Frontmatter is complete and accurate
- [ ] No links to non-existent pages
- [ ] All images have alt text
- [ ] Page is completable in < 10 minutes (for tutorials/how-tos)
