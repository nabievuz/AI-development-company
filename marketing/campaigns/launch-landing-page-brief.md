# Launch Landing Page Brief

_Owner: CMO · Status: Draft — pending CEO approval · Date: 2026-05-18 · Issue: DAS-40_

## 1. Purpose
Single conversion-focused landing page for DasLab's launch moment (Product Hunt + Show HN). Goal: turn burst traffic into qualified signups and an owned email list. No design or code yet — this brief defines scope, audience, message, and success criteria.

## 2. Audience
- **Primary:** Senior data engineers and data platform leads at Series A–C startups who own pipeline reliability.
- **Secondary:** Founding engineers and CTOs evaluating data infra tooling.
- **Not the audience:** Non-technical analysts, enterprise procurement.

## 3. Goals & Success Metrics
| Metric | Target (launch week) |
|---|---|
| Unique visitors | 8–15k |
| Signup conversion rate | ≥ 4% |
| Email captures (no signup) | ≥ 6% of remaining traffic |
| Bounce rate | < 55% |
| Time-to-first-CTA-click (median) | < 25s |

## 4. Message Hierarchy
Derived from `brand-guide.md` pillars: Clarity at Scale · Trusted by Builders · Speed Without Sacrifice.

1. **Hero (Pillar 1 — Clarity at Scale)**
   - Headline candidate: "Your data pipeline, demystified."
   - Subhead: One sentence naming the concrete pain (debugging opaque pipelines) and the outcome (answers, not more dashboards).
   - Primary CTA: "Start free" → signup. Secondary CTA: "See how it works" → product tour anchor.
2. **Proof strip (Pillar 2 — Trusted by Builders)**
   - 3–5 logos OR, if not ready, 2 named engineer quotes with role + company.
   - One technical credibility line (stack, scale number, or shipping cadence).
3. **Problem → outcome (Pillars 1 + 3)**
   - 3 problem cards, each paired with a concrete outcome and a number (e.g., "3× faster", "half the queries").
4. **How it works (Pillar 2)**
   - 3 steps, plain imperative verbs. No "magic" framing. Brief enough to skim in 15s.
5. **Speed + safety (Pillar 3)**
   - Every speed claim paired with a reliability/transparency signal (observability, rollback, audit).
6. **Founder note (Pillar 2)**
   - 80–120 words, first-person, names a real problem the team hit. Signed.
7. **Final CTA block**
   - Repeat primary CTA. Add email-only capture for visitors not ready to sign up (newsletter promise: one technical post / month, no spam).

## 5. Voice & Copy Rules (must-follow)
- Active voice, present tense.
- Edit each section to ~80% of first draft length.
- Banned: "leverage", "best-in-class", "world-class", "robust", "seamless".
- One exclamation point maximum on the page.
- Say "your team" / "you" — never "users".
- Every feature mention links to an outcome.
- Oxford comma. Short sentences. Split on semicolons.

## 6. Required Page Modules (top → bottom)
1. Nav (logo, Product, Docs, Pricing, Sign in, Start free)
2. Hero (headline, subhead, primary + secondary CTA, optional product screenshot)
3. Proof strip (logos or quotes)
4. Problem → outcome (3 cards)
5. How it works (3 steps)
6. Speed + safety (paired claims)
7. Founder note
8. FAQ (5 questions max — pricing, security, migration, integrations, support)
9. Final CTA + email capture
10. Footer (legal, status page, security, careers, social)

## 7. Assets Needed
- Logo (final mark + wordmark, SVG)
- 1 hero visual (product screenshot or schematic — not stock illustration)
- 3–5 customer logos OR 2 engineer quotes with permission
- Founder photo (optional, square crop)
- OG image (1200×630) — headline + brand color block
- Favicon set

## 8. Technical Requirements (engineering handoff, not in scope here)
- LCP < 2.0s on 4G; CLS < 0.05.
- Email capture posts to newsletter provider (TBD — Growth Marketer to choose).
- UTM-aware: PH and HN traffic must be distinguishable in analytics.
- Mobile-first; renders cleanly at 320px width.
- Accessibility: WCAG 2.1 AA, real focus states, semantic headings.
- Analytics events: page-load, CTA clicks (primary + secondary), scroll depth (25/50/75/100), email submit, signup submit.

## 9. SEO Baseline
- Title tag ≤ 60 chars, leads with primary keyword + brand.
- Meta description ≤ 155 chars, includes primary outcome and CTA verb.
- One H1, hierarchical H2s, no skipped levels.
- Structured data: `Organization` + `SoftwareApplication`.
- SEO Specialist confirms target keyword and on-page checklist before copy lock.

## 10. Out of Scope
- Pricing page (separate brief).
- Docs IA.
- Authenticated product UI.
- Localization — English only at launch.

## 11. Timeline & Owners
| Step | Owner | Due |
|---|---|---|
| Brief approved | CEO | +2 days |
| Copy v1 (all sections) | Content Lead | +5 days |
| Visual direction + hero asset | CMO + design (TBH) | +7 days |
| SEO on-page review | SEO Specialist | +8 days |
| Engineering handoff | CMO → eng lead | +9 days |
| Page live (staging) | Eng | +14 days |
| Launch day | Growth Marketer | TBD (Tuesday) |

## 12. Open Questions
- Do we have launch-day customer logos cleared, or do we lean on quotes?
- Newsletter provider decision (blocks email capture wiring).
- Final hero headline — pillar 1 framing is the default; needs CEO sign-off.
- Founder note: who signs — CEO alone, or CEO + CTO?

## 13. Approval
Requires CEO sign-off before copy work begins. Once approved, Content Lead picks up copy v1 (new issue) and DAS-40 closes.
