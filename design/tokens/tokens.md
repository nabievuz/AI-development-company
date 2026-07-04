# DasLab Design Tokens

**Version:** 0.1.0 | **Updated:** 2026-05-18 | **Source:** `tokens/tokens.json`

Design tokens are the single source of truth for all visual decisions in DasLab products. They follow the [W3C Design Tokens Community Group](https://design-tokens.github.io/community-group/format/) draft format: each token carries `$value`, `$type`, and an optional `$description`. Alias tokens (e.g. `{color.brand.500}`) are resolved at build time.

---

## Color

### Brand Palette

Base: **sky-500 `#0ea5e9`** — the DasLab primary identity color.

| Token | Value | Swatch |
|---|---|---|
| `color.brand.50` | `#f0f9ff` | Lightest tint — page backgrounds, hover states |
| `color.brand.100` | `#e0f2fe` | Subtle fills |
| `color.brand.200` | `#bae6fd` | Light fills |
| `color.brand.300` | `#7dd3fc` | Light accents |
| `color.brand.400` | `#38bdf8` | Medium accents |
| `color.brand.500` | `#0ea5e9` | **Primary — buttons, links, focus rings** |
| `color.brand.600` | `#0284c7` | Hover state on primary |
| `color.brand.700` | `#0369a1` | Active / pressed |
| `color.brand.800` | `#075985` | Dark brand fills |
| `color.brand.900` | `#0c4a6e` | Darkest brand |
| `color.brand.950` | `#082f49` | Near-black brand |

### Neutral Palette

Slate-based neutral scale for text, borders, and surfaces.

| Token | Value | Use |
|---|---|---|
| `color.neutral.0`    | `#ffffff` | White — surface background |
| `color.neutral.50`   | `#f8fafc` | Page background |
| `color.neutral.100`  | `#f1f5f9` | Overlay / alternate row |
| `color.neutral.200`  | `#e2e8f0` | Default border |
| `color.neutral.300`  | `#cbd5e1` | Dividers |
| `color.neutral.400`  | `#94a3b8` | Placeholder / disabled text |
| `color.neutral.500`  | `#64748b` | Secondary text |
| `color.neutral.600`  | `#475569` | Body text (secondary) |
| `color.neutral.700`  | `#334155` | Body text (primary, dark mode bg) |
| `color.neutral.800`  | `#1e293b` | Strong text, dark surfaces |
| `color.neutral.900`  | `#0f172a` | Headings, primary text |
| `color.neutral.950`  | `#020617` | Near-black |
| `color.neutral.1000` | `#000000` | True black |

### Semantic Status Colors

| Group | 50 (bg tint) | 500 (icon/fill) | 700 (text/border) |
|---|---|---|---|
| Success | `#f0fdf4` | `#22c55e` | `#15803d` |
| Warning | `#fffbeb` | `#f59e0b` | `#b45309` |
| Danger  | `#fff1f2` | `#ef4444` | `#b91c1c` |
| Info    | `#eff6ff` | `#3b82f6` | `#1d4ed8` |

### Semantic Aliases

These are the tokens UI components must reference. Never hard-code a raw palette value in a component — always use a semantic alias.

**Backgrounds**

| Token | Resolves to | Use |
|---|---|---|
| `color.semantic.bg.page`    | `neutral.50`  | Page / canvas background |
| `color.semantic.bg.surface` | `neutral.0`   | Card, panel, modal surface |
| `color.semantic.bg.overlay` | `neutral.100` | Dropdown, popover background |
| `color.semantic.bg.inverse` | `neutral.900` | Dark-mode or inverse surface |

**Text**

| Token | Resolves to | Use |
|---|---|---|
| `color.semantic.text.primary`   | `neutral.900` | Main body text, headings |
| `color.semantic.text.secondary` | `neutral.600` | Supporting / meta text |
| `color.semantic.text.disabled`  | `neutral.400` | Disabled state text |
| `color.semantic.text.inverse`   | `neutral.0`   | Text on dark backgrounds |
| `color.semantic.text.link`      | `brand.600`   | Hyperlinks |
| `color.semantic.text.link-hover`| `brand.700`   | Hyperlink hover |

**Borders**

| Token | Resolves to | Use |
|---|---|---|
| `color.semantic.border.default` | `neutral.200` | Default input/card borders |
| `color.semantic.border.strong`  | `neutral.400` | Emphasized borders |
| `color.semantic.border.focus`   | `brand.500`   | Focus ring (3px outline) |

**Actions (buttons, CTAs)**

| Token | Resolves to | Use |
|---|---|---|
| `color.semantic.action.primary`        | `brand.500` | Button fill |
| `color.semantic.action.primary-hover`  | `brand.600` | Button fill on hover |
| `color.semantic.action.primary-active` | `brand.700` | Button fill on press |
| `color.semantic.action.primary-text`   | `neutral.0` | Button label on primary fill |

---

## Typography

### Font Families

| Token | Stack | Use |
|---|---|---|
| `typography.fontFamily.sans`  | Inter → system-ui → sans-serif | All UI text (default) |
| `typography.fontFamily.mono`  | JetBrains Mono → Fira Code → monospace | Code, terminal output, identifiers |
| `typography.fontFamily.serif` | Georgia → serif | Long-form editorial content (rare) |

### Font Sizes

| Token | rem | px equiv | Use |
|---|---|---|---|
| `typography.fontSize.xs`   | 0.75rem  | 12px | Captions, badges, micro labels |
| `typography.fontSize.sm`   | 0.875rem | 14px | Secondary body, labels |
| `typography.fontSize.base` | 1rem     | 16px | Default body text |
| `typography.fontSize.lg`   | 1.125rem | 18px | Emphasized body |
| `typography.fontSize.xl`   | 1.25rem  | 20px | Small headings |
| `typography.fontSize.2xl`  | 1.5rem   | 24px | Section headings |
| `typography.fontSize.3xl`  | 1.875rem | 30px | Page headings |
| `typography.fontSize.4xl`  | 2.25rem  | 36px | Display (small) |
| `typography.fontSize.5xl`  | 3rem     | 48px | Display (large) |
| `typography.fontSize.6xl`  | 3.75rem  | 60px | Hero / marketing |

### Font Weights

| Token | Value | Use |
|---|---|---|
| `typography.fontWeight.regular`   | 400 | Body text |
| `typography.fontWeight.medium`    | 500 | Labels, nav items |
| `typography.fontWeight.semibold`  | 600 | Headings (h3–h5), buttons |
| `typography.fontWeight.bold`      | 700 | Headings (h1–h2), emphasis |
| `typography.fontWeight.extrabold` | 800 | Display, hero copy |

### Line Heights

| Token | Ratio | Best for |
|---|---|---|
| `typography.lineHeight.none`    | 1.0   | Single-line UI elements, icons |
| `typography.lineHeight.tight`   | 1.25  | Large display text |
| `typography.lineHeight.snug`    | 1.375 | Headings (h1–h3) |
| `typography.lineHeight.normal`  | 1.5   | Body text |
| `typography.lineHeight.relaxed` | 1.625 | Longer paragraphs |
| `typography.lineHeight.loose`   | 2.0   | Spaced lists |

### Letter Spacing

| Token | Value | Use |
|---|---|---|
| `typography.letterSpacing.tighter` | −0.05em | Large display text (optional) |
| `typography.letterSpacing.tight`   | −0.025em| Headings |
| `typography.letterSpacing.normal`  | 0em     | Body text (default) |
| `typography.letterSpacing.wide`    | 0.025em | Small uppercase labels |
| `typography.letterSpacing.wider`   | 0.05em  | All-caps micro labels |
| `typography.letterSpacing.widest`  | 0.1em   | Decorative caps |

### Composite Text Styles

Pre-composed styles for common roles. Use these on components rather than assembling individual tokens.

| Style key | Size | Weight | Line height | Use |
|---|---|---|---|---|
| `display-lg`  | 5xl (48px) | bold | tight | Hero sections |
| `display-sm`  | 4xl (36px) | bold | tight | Sub-hero, marketing |
| `heading-xl`  | 3xl (30px) | semibold | snug | Page title (h1) |
| `heading-lg`  | 2xl (24px) | semibold | snug | Section heading (h2) |
| `heading-md`  | xl (20px)  | semibold | normal | Sub-section (h3) |
| `heading-sm`  | lg (18px)  | medium | normal | Minor heading (h4–h5) |
| `body-lg`     | lg (18px)  | regular | relaxed | Lead / introductory text |
| `body-md`     | base (16px)| regular | relaxed | Default body copy |
| `body-sm`     | sm (14px)  | regular | normal | Secondary copy, hints |
| `label-lg`    | sm (14px)  | medium | normal | Form labels, nav items |
| `label-sm`    | xs (12px)  | medium + wide tracking | normal | Badges, status chips |
| `code`        | sm (14px)  | regular | relaxed | Inline/block code |

---

## Spacing

4px base unit. All values are multiples of 4px (exceptions: `px` = 1px, `0.5` = 2px).

| Token | rem | px | Use examples |
|---|---|---|---|
| `spacing.0`   | 0       | 0px  | Reset |
| `spacing.px`  | —       | 1px  | Hairline borders |
| `spacing.0.5` | 0.125   | 2px  | Tight icon padding |
| `spacing.1`   | 0.25    | 4px  | Compact gaps |
| `spacing.2`   | 0.5     | 8px  | Icon gap, tag padding |
| `spacing.3`   | 0.75    | 12px | Small padding |
| `spacing.4`   | 1.0     | 16px | Default component padding |
| `spacing.5`   | 1.25    | 20px | Card padding (compact) |
| `spacing.6`   | 1.5     | 24px | Card padding (default) |
| `spacing.8`   | 2.0     | 32px | Section gap |
| `spacing.10`  | 2.5     | 40px | Large component gap |
| `spacing.12`  | 3.0     | 48px | Panel padding |
| `spacing.16`  | 4.0     | 64px | Section vertical rhythm |
| `spacing.20`  | 5.0     | 80px | Large section gap |
| `spacing.24`  | 6.0     | 96px | Page section padding |

Full scale (0 → 96) in `tokens.json`.

---

## Border Radius

| Token | Value | Use |
|---|---|---|
| `borderRadius.none` | 0px     | Sharp elements, tables |
| `borderRadius.sm`   | 2px     | Subtle rounding (badges) |
| `borderRadius.base` | 4px     | Default inputs, small buttons |
| `borderRadius.md`   | 6px     | Buttons, pills |
| `borderRadius.lg`   | 8px     | Cards, dropdowns |
| `borderRadius.xl`   | 12px    | Modal dialogs |
| `borderRadius.2xl`  | 16px    | Large panels |
| `borderRadius.3xl`  | 24px    | Full-rounded sections |
| `borderRadius.full` | 9999px  | Avatars, toggle, circular buttons |

---

## Shadows

| Token | Use |
|---|---|
| `shadow.xs`    | Subtle lift — buttons on surface |
| `shadow.sm`    | Card, input focus |
| `shadow.md`    | Dropdown, popover |
| `shadow.lg`    | Floating panel |
| `shadow.xl`    | Modal overlay shadow |
| `shadow.2xl`   | Full-screen modal, drawer |
| `shadow.inner` | Pressed input, inset well |
| `shadow.none`  | Explicitly no shadow |

---

## Motion

### Duration

| Token | Value | Use |
|---|---|---|
| `motion.duration.instant` | 50ms  | Tooltip appear, micro feedback |
| `motion.duration.fast`    | 100ms | Button press, toggle |
| `motion.duration.normal`  | 200ms | Most transitions (default) |
| `motion.duration.slow`    | 300ms | Drawer slide, modal fade |
| `motion.duration.slower`  | 500ms | Page transitions, complex reveals |

### Easing

| Token | Curve | Use |
|---|---|---|
| `motion.easing.linear`      | linear | Progress bars, spinners |
| `motion.easing.ease-in`     | cubic-bezier(0.4,0,1,1) | Elements leaving screen |
| `motion.easing.ease-out`    | cubic-bezier(0,0,0.2,1) | Elements entering screen (default) |
| `motion.easing.ease-in-out` | cubic-bezier(0.4,0,0.2,1) | Elements staying on screen |
| `motion.easing.spring`      | cubic-bezier(0.34,1.56,0.64,1) | Playful pop, badge count |

---

## Z-Index

| Token | Value | Layer |
|---|---|---|
| `zIndex.base`     | 0   | Default flow |
| `zIndex.raised`   | 10  | Elevated cards |
| `zIndex.dropdown` | 100 | Select menus, auto-complete |
| `zIndex.sticky`   | 200 | Sticky header / sidebar |
| `zIndex.overlay`  | 300 | Lightbox overlay |
| `zIndex.modal`    | 400 | Dialog / modal |
| `zIndex.toast`    | 500 | Toast notifications |
| `zIndex.tooltip`  | 600 | Tooltips (always on top) |

---

## Usage Rules

1. **Always use semantic aliases in components.** Raw palette tokens (`color.brand.500`) are for building semantic aliases only — never reference them directly in component code.
2. **No magic values.** Every numeric CSS value in a component must map to a token. Open a token PR if a value is missing.
3. **WCAG AA compliance is required.** The ratio between `color.semantic.text.primary` (`neutral.900`) and `color.semantic.bg.surface` (`neutral.0`) is 19.9:1 (passes AA and AAA). All new color combinations must pass 4.5:1 for normal text and 3:1 for large text.
4. **Dark mode.** Semantic aliases are the extension point for dark mode. A future `tokens-dark.json` will redefine semantic aliases — raw palette values stay unchanged.
5. **Token changes go through design review.** Changing a base palette color is a breaking change. Always bump the version and notify the CDO.

---

## Accessibility Contrast Reference

| Pair | Ratio | WCAG |
|---|---|---|
| `text.primary` on `bg.surface`   | 19.9:1 | AAA |
| `text.secondary` on `bg.surface` | 5.9:1  | AA |
| `text.link` on `bg.surface`      | 4.8:1  | AA |
| `action.primary-text` on `action.primary` | 3.0:1 | AA large |
| `text.disabled` on `bg.surface`  | 3.0:1  | AA large only — do not use for normal-size text |
