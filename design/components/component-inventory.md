# Component Library — Inventory

**Status:** Audit complete — 0 components implemented; 41 components specified.
**Audit date:** 2026-05-18
**Author:** Design Lead

---

## What exists

| Artefact | File | Status |
|---|---|---|
| Design tokens v0.1.0 | `tokens/tokens.json` + `tokens/tokens.md` | Done |
| Visual principles v1.0 | `visual-principles.md` | Done |
| Component specs | — | **None** |
| Figma component library | — | **None** |
| Mockups archive | `mockups/` | **Directory missing** |

**Component count: 0 / 0 defined.**

---

## What is missing — v0 target list

### Priority 1 — Foundations (must ship in v0)

These are the primitives every other component builds on. No product surface can be built without them.

| Component | Category | Token surface | Notes |
|---|---|---|---|
| `Button` | Action | `action.*`, `borderRadius.md`, `spacing.*`, `shadow.xs` | Variants: primary, secondary, ghost, destructive, link. Sizes: sm / md / lg. |
| `IconButton` | Action | Same as Button | Square, icon-only button. |
| `Link` | Action | `text.link`, `text.link-hover` | Inline text link with hover + focus state. |
| `TextInput` | Form | `border.*`, `bg.surface`, `text.*`, `borderRadius.base` | States: default, focus, error, disabled. |
| `Textarea` | Form | Same as TextInput | Resizable; same states. |
| `Select` | Form | Same as TextInput + `zIndex.dropdown` | Native + custom variant. |
| `Checkbox` | Form | `action.primary`, `border.default` | Indeterminate state required. |
| `RadioGroup` | Form | `action.primary`, `border.default` | — |
| `Toggle` / Switch | Form | `action.primary`, `borderRadius.full` | On/off only. |
| `Badge` / Tag | Display | `label-sm` style, semantic colors | Semantic variants: success / warning / danger / info / neutral. |
| `Alert` / Banner | Feedback | Semantic colors, `bg.*`, `border.*` | Inline contextual message. Closeable. |
| `Toast` | Feedback | `zIndex.toast`, `shadow.lg` | 4 variants mirroring Badge. Auto-dismiss. |
| `Spinner` | Feedback | `action.primary` | Indeterminate loading. Sizes: sm / md / lg. |
| `Skeleton` | Feedback | `bg.overlay` | Matches layout of replaced content. |
| `Tooltip` | Overlay | `bg.inverse`, `text.inverse`, `zIndex.tooltip` | Hover + focus-triggered. Max 200px wide. |
| `Card` | Container | `bg.surface`, `border.default`, `shadow.sm`, `borderRadius.lg` | Padded surface. Optional header/footer slots. |
| `Modal` / Dialog | Overlay | `bg.surface`, `shadow.2xl`, `zIndex.modal`, `borderRadius.xl` | Focus trap. `aria-modal`. |
| `Tabs` | Navigation | `action.primary`, `border.default` | Line + boxed variants. |
| `Avatar` | Display | `borderRadius.full`, semantic colors | Image + initials fallback. Sizes: xs / sm / md / lg. |
| `Empty State` | Feedback | `text.secondary`, `bg.surface` | Icon + heading + optional CTA. |
| `Divider` | Layout | `border.default` | Horizontal and vertical. |

**Priority 1 total: 20 components**

---

### Priority 2 — Product core (v0.x or v1)

Required to build most DasLab product surfaces; can follow the Priority 1 wave.

| Component | Category | Notes |
|---|---|---|
| `ButtonGroup` | Action | Segmented control / split button. |
| `SearchInput` | Form | TextInput + search icon + clear button. |
| `NumberInput` | Form | Stepper arrows, min/max/step. |
| `Breadcrumb` | Navigation | 4-item max before truncation. |
| `Pagination` | Navigation | Page-based + cursor-based variants. |
| `Accordion` | Container | Single / multi expand. |
| `Drawer` / Sheet | Overlay | Right / bottom; focus trap. |
| `Popover` | Overlay | Richer tooltip; interactive content. |
| `DropdownMenu` | Overlay | Triggered by Button; keyboard nav. |
| `Table` / DataGrid | Display | Sortable columns, sticky header, row selection. High priority for DasLab. |
| `Code Block` | Display | Monospace, syntax highlight, copy button. |
| `Stat` / KPI Card | Display | Number + label + delta chip. Matches "Show the number" principle. |
| `ProgressBar` | Feedback | Determinate + indeterminate. |

**Priority 2 total: 13 components**

---

### Priority 3 — Extended (v1+)

| Component | Category | Notes |
|---|---|---|
| `MultiSelect` | Form | Chip-based selection. |
| `DatePicker` | Form | Calendar overlay. |
| `Slider` | Form | Range input. |
| `FileUpload` | Form | Drag-and-drop zone. |
| `ContextMenu` | Overlay | Right-click triggered. |
| `List` / `ListItem` | Display | Virtualised for long lists. |
| `Timeline` | Display | Event history; relevant for agent runs. |
| `Callout` | Feedback | Heavier than Alert; inline content sections. |

**Priority 3 total: 8 components**

---

## Summary

| Priority | Count | Target milestone |
|---|---|---|
| P1 — Foundations | 20 | v0 |
| P2 — Product core | 13 | v0.x |
| P3 — Extended | 8 | v1 |
| **Total** | **41** | — |

To reach the success metric of **≥90% of UI primitives** covered, P1 + P2 (33 components) must be completed.

---

## Spec format (for component authors)

Each component will live at `components/{ComponentName}/spec.md` with:

```
# ComponentName
**Status:** draft / review / stable
**Tokens used:** list
**Variants:** list
**States:** list
**A11y:** keyboard nav, ARIA roles, contrast pairs
**Usage examples**
**Do / Don't**
```

Figma sources archived to `mockups/{ComponentName}.fig` or a Figma file link per CLAUDE.md success metrics.
