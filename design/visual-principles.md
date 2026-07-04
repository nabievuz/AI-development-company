# Visual Principles — DasLab

**Status:** Aligned with Marketing brand voice.
**Owner:** CDO. **Reviewers:** Design Lead (token + component mapping), CMO (voice fidelity).
**Voice in a sentence:** *Clear. Credible. Fast to the point.*

## Purpose
Translate DasLab's brand voice into a small set of decisions designers can apply when building components, layouts, and marketing surfaces. These principles are the bridge between Marketing's three pillars — **Clarity at Scale**, **Trusted by Builders**, **Speed Without Sacrifice** — and the pixels Design ships.

The audience behind every surface: a senior data engineer who values their time.

## The principles

### 1. Calm before contrast — *Clarity at Scale*
Restraint is the default. High-contrast colour, motion, and weight are budgeted and earned by hierarchy, not decoration. A page should read before it performs.

**Looks like:** neutral surfaces, one accent per view, motion only on user-initiated state changes, no decorative gradients.
**Fails when:** every CTA shouts; nothing does.

### 2. Structure is the brand — *Clarity at Scale*
Grid, rhythm, and alignment do the heavy lifting. Illustration and ornament are secondary to a disciplined system.

**Looks like:** 8pt spacing scale, consistent radii, predictable component anatomy across surfaces.
**Fails when:** bespoke layout per page; designers reinventing spacing.

### 3. Show the number — *Trusted by Builders*
Concrete outcomes outrank adjectives. When a surface makes a claim, the claim is a number, a chart, or a code sample — never "world-class", "best-in-class", or "robust". If we cannot show it, we do not say it.

**Looks like:** hero numbers paired with units and context ("3× faster on 10TB"), inline code in product copy, real query/result screenshots over abstract illustration.
**Fails when:** stock-photo abstractions stand in for the actual product.

### 4. Typography carries voice — *Clear. Credible.*
Type is the loudest brand signal we ship. One display family, one text family, a small set of sizes. Voice shows up in weight choices and line-length discipline, not in novelty.

**Looks like:** ≤6 type roles, body line-length 60–75ch, monospace reserved for code and data, no all-caps headlines outside small labels.
**Fails when:** a "fun" headline weight starts appearing in product UI.

### 5. Speed shown, not claimed — *Speed Without Sacrifice*
Whenever a surface implies speed, pair it with a quality or safety signal in the same eye-line. Perceived performance is a visual problem: skeletons, optimistic state, and fast first paint matter as much as the claim itself.

**Looks like:** "Ship in minutes" sits next to an SLO badge or a test-coverage chip; loading states arrive within 100ms; skeletons match final layout.
**Fails when:** marketing brags about speed while the product spinner hangs.

### 6. Show the work — *Trusted by Builders*
Honesty over imagined polish. When a system is mid-build, label it. Beta tags, draft watermarks on mockups, visible state for in-progress agents. We acknowledge hard problems; we do not oversell ease.

**Looks like:** explicit status chips, empty states that name what is missing, no placeholder lorem in shipped surfaces, changelogs visible in-product.
**Fails when:** a feature ships looking finished while half its paths 404.

### 7. Accessibility is the floor — *Clarity at Scale*
WCAG AA is a baseline, not a target. Contrast, focus state, motion-reduce, and keyboard parity are validated before review, not after. Information is never conveyed by colour alone.

**Looks like:** ≥4.5:1 text contrast, visible focus rings on every interactive, `prefers-reduced-motion` honoured, semantic colour paired with icon or label.
**Fails when:** the only signal that a row is "error" is that it turned red.

### 8. One voice across surfaces — *Clear. Credible.*
Marketing pages, product UI, and internal tools share tokens. A button on the landing page and a button in the agent dashboard are the same button. Divergence requires CDO sign-off.

**Looks like:** shared token set, single component library consumed by web + product, the same primary action style end to end.
**Fails when:** the landing page hero looks nothing like the dashboard it links to.

### 9. Edit to 80% — *Clear. Credible.*
Borrowed directly from Marketing's tone rules: cut to 80% of the first draft. Density is a feature for senior engineers; every removed element raises the signal of what remains.

**Looks like:** one chart per insight, captions trimmed of qualifiers, dashboards that pass a "what would I remove?" pass before review.
**Fails when:** UI grows a "tips" panel, a hero illustration, *and* a sidebar to explain the chart.

## How to apply
- **Reviewing a mockup?** Walk it against principles 1–9. Cite the principle number in comments.
- **Proposing a new component?** Name which principles it advances and which it stresses. If it stresses one, defend the trade.
- **Writing UI copy?** Defer to `brand-guide.md` tone rules; this doc inherits them.
- **Disagreeing with a principle?** Open a ticket against this file; CDO arbitrates with CMO.

## Maps to Marketing pillars

| Pillar | Principles |
|---|---|
| Clarity at Scale | 1, 2, 7 |
| Trusted by Builders | 3, 6 |
| Speed Without Sacrifice | 5 |
| Voice-wide (all pillars) | 4, 8, 9 |

