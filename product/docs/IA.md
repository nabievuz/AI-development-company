# DasFlow Documentation — Information Architecture

**Status:** Final — approved by CPO 2026-05-19
**Author:** Technical Writer
**Date:** 2026-05-19

---

## Purpose

This document defines the information architecture for the DasFlow external developer documentation site. It establishes:

- Top-level navigation structure
- Content type inventory
- URL scheme and slug conventions
- Ownership and update cadence

The IA is intentionally scoped to the MVP feature set from [mvp-brief-v0.1](../specs/mvp-brief-v0.1.md). Post-launch sections are placeholders only.

---

## Target Readers

| Persona | Goal |
|---------|------|
| **Indie Studio Founder** | Spin up a coordinated agent workforce in under an hour with no infrastructure work |
| **Early-stage SaaS team** | Understand how to assign entire workflows (PR review, changelog, support) to agents |
| **Self-evaluating developer** | Assess whether DasFlow fits their stack before signing up |

**Implication for the Self-evaluating developer:** Docs must be fully readable without an account. Key evaluation pages — Quick Start and the Agents concept explainer at minimum — must be linkable from the marketing site and publicly accessible from day one. Do not gate any doc page behind auth or a waitlist.

---

## Top-Level Navigation

```
docs.dasflow.dev/
├── getting-started/          # Day-0 onboarding path
├── concepts/                 # Mental model and core primitives
├── guides/                   # Task-oriented how-tos
├── api-reference/            # REST API reference
├── changelog/                # Product changelog
└── support/                  # FAQ, limits, status page links
```

---

## Section Breakdown

### 1. `getting-started/`

Fast path from signup to first agent running a real task. Every page must be completable in < 10 minutes.

| Slug | Title | Content type |
|------|-------|-------------|
| `getting-started/` | Overview | Landing / orientation |
| `getting-started/quick-start` | Quick Start | Tutorial (step-by-step) |
| `getting-started/first-agent` | Create Your First Agent | Tutorial |
| `getting-started/first-task` | Assign Your First Task | Tutorial |
| `getting-started/budget-cap` | Set a Budget Cap | How-to guide |

**Success metric:** A new user following the quick-start can have an agent complete a task within 5 minutes of account creation.

---

### 2. `concepts/`

Explains the mental model. Written for developers who want to understand *why* DasFlow is structured the way it is before exploring features.

| Slug | Title | Content type |
|------|-------|-------------|
| `concepts/` | Overview | Conceptual explainer |
| `concepts/agents` | Agents | Conceptual explainer |
| `concepts/roles-and-hierarchy` | Roles and Reporting Hierarchy | Conceptual explainer |
| `concepts/tasks` | Tasks and the Inbox | Conceptual explainer |
| `concepts/heartbeats` | Heartbeats | Conceptual explainer |
| `concepts/budgets` | Budgets and Spend Control | Conceptual explainer |
| `concepts/comments` | Comments and Collaboration | Conceptual explainer |

---

### 3. `guides/`

Task-oriented how-tos for users past onboarding. Each guide answers one specific "how do I…" question.

| Slug | Title | Content type |
|------|-------|-------------|
| `guides/` | Overview | Index |
| `guides/define-agent-roles` | Define Agent Roles and Prompts | How-to guide |
| `guides/set-reporting-lines` | Set Reporting Lines | How-to guide |
| `guides/create-tasks` | Create and Assign Tasks | How-to guide |
| `guides/monitor-progress` | Monitor Agent Progress | How-to guide |
| `guides/handle-blocked-tasks` | Handle Blocked Tasks | How-to guide |
| `guides/schedule-agents` | Schedule Agent Heartbeats | How-to guide |
| `guides/upgrade-plan` | Upgrade Your Plan | How-to guide |
| `guides/workspace-settings` | Workspace Settings | How-to guide |

---

### 4. `api-reference/`

Machine-generated from OpenAPI spec (owner: Engineering). Technical Writer owns editorial pass and example quality.

| Slug | Title | Content type |
|------|-------|-------------|
| `api-reference/` | Overview | Reference landing |
| `api-reference/authentication` | Authentication | Reference |
| `api-reference/agents` | Agents | Reference |
| `api-reference/tasks` | Tasks | Reference |
| `api-reference/comments` | Comments | Reference |
| `api-reference/budgets` | Budgets | Reference |
| `api-reference/webhooks` | Webhooks *(post-MVP)* | Reference (placeholder) |

---

### 5. `changelog/`

Product changelog maintained jointly by Technical Writer and Senior PM.

| Slug | Title | Content type |
|------|-------|-------------|
| `changelog/` | Changelog | Changelog |

Format: one entry per release, newest first. Each entry: version, date, what changed (user-visible language), and link to relevant spec or guide.

---

### 6. `support/`

| Slug | Title | Content type |
|------|-------|-------------|
| `support/` | Support Overview | Reference |
| `support/faq` | FAQ | Reference |
| `support/limits` | Limits and Quotas | Reference |
| `support/status` | Service Status | External link |

---

## Content Type Definitions

| Type | Definition | Example |
|------|-----------|---------|
| **Tutorial** | Guided sequence with a defined end state. Reader follows exact steps; no decisions required. | Quick Start |
| **How-to guide** | Goal-oriented. Assumes reader knows the concepts; solves a specific problem. | Handle Blocked Tasks |
| **Conceptual explainer** | Explains *what* and *why*. No step-by-step instructions. | Agents, Heartbeats |
| **Reference** | Complete, accurate, dry. API tables, limits, config options. | API reference |
| **Changelog** | Chronological record of shipped changes. | changelog/ |

(Based on Divio documentation system.)

---

## URL Conventions

- **Subdomain:** `docs.dasflow.dev` (not a path prefix under the apex). Cleaner separation from the marketing site; easier to swap doc platforms independently.
- **Pre-launch indexing:** Publicly indexed from day one. No waitlist gate on any doc page. Docs are a top-of-funnel evaluation surface.
- **Localization:** English-only for MVP. Authors must avoid idioms that don't translate. Revisit after first 100 paying customers.
- **API versioning:** Single version (`v1`) only at launch. No parallel version docs until a breaking change ships. Do not add `/v1/` slug prefixes pre-emptively — let the platform handle versioning when it actually becomes necessary.
- All slugs: lowercase, hyphenated, no trailing slash in links.
- API reference: auto-generated slug from OpenAPI `operationId`.
- No date-based URLs (avoids rot).

---

## Ownership and Update Cadence

| Section | Primary owner | Update trigger |
|---------|--------------|----------------|
| Getting started | Technical Writer | Any onboarding flow change |
| Concepts | Technical Writer | Any core primitive change |
| Guides | Technical Writer | Feature shipped |
| API reference | Engineering (generation) + Technical Writer (editorial) | API release |
| Changelog | Technical Writer + Senior PM | Every release |
| Support / FAQ | Technical Writer | User support pattern emerges |

---

