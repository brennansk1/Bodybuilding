# Viltrum UI Theme

The single source of truth for all design tokens, type, color, and motion conventions used across the app. Mirrors `frontend/tailwind.config.ts` and `frontend/src/app/globals.css`.

## 1 — Brand

**Viltrum** — a marble-and-blood editorial aesthetic. Light limestone surfaces, oxidized iron type, single Viltrumite-red accent for action, gold/laurel/blue for categorical state. Typography pairs a stenciled display face with a literary serif.

## 2 — Color tokens

All tokens are defined under the `viltrum-*` namespace in tailwind. Flat aliases (`obsidian`, `iron`, etc.) exist for legacy and shorthand use — prefer `viltrum-*` in new code.

### Surfaces (warm-grey marble palette)

| Token | Hex | Role |
|---|---|---|
| `viltrum-bone` | `#F5F4F1` | Page base background |
| `viltrum-alabaster` | `#FAFAF8` | Card hover / inset surface |
| `viltrum-limestone` | `#F0EFEC` | Default card background |
| `viltrum-ash` | `#E2E0DC` | Borders, dividers |
| `viltrum-pumice` | `#D0CFC8` | Hover-border, secondary stroke |

### Type (oxidized iron, descending contrast)

| Token | Hex | Use |
|---|---|---|
| `viltrum-obsidian` | `#1A1816` | Primary text, headlines, dense data |
| `viltrum-iron` | `#5C5750` | Body copy, secondary labels |
| `viltrum-travertine` | `#8A857D` | Tertiary copy, captions, axis labels |
| `viltrum-pewter` | `#C4C0B9` | Disabled, separators, placeholder |

### Accents — categorical state

| Token | Hex | Role |
|---|---|---|
| `viltrum-legion` | `#C44040` | **Primary action** — buttons, CTAs, "Viltrumite red" |
| `viltrum-legion-hover` | `#B33838` | Hover for primary |
| `viltrum-centurion` | `#8B2B2B` | Critical / "far" status / error text |
| `viltrum-terracotta` | `#E8B4B4` | Subtle action accent, alert border |
| `viltrum-blush` | `#FAF0F0` | Critical-info background tint |
| `viltrum-laurel` | `#2D7A45` | Met / success / positive trend |
| `viltrum-laurel-bg` | `#EDF7F0` | Success surface tint |
| `viltrum-aureus` | `#C48820` | Close / warning / approaching |
| `viltrum-aureus-bg` | `#FBF5E8` | Warning surface tint |
| `viltrum-adriatic` | `#2E6B9C` | Developing / informational / neutral data |
| `viltrum-adriatic-bg` | `#EBF3FA` | Info surface tint |

### Categorical use rules

- **Red (`legion`)** is reserved for *primary actions* and *Viltrum brand identity*. Don't use it for "bad" — that's `centurion` (deeper, less saturated).
- **Status quartet** (laurel / aureus / adriatic / centurion) maps directly to the Tier Readiness 4-tier classification:
  - Met → laurel ✓
  - Close → aureus ◐
  - Developing → adriatic ◔
  - Far → centurion ○
- Use `*-bg` variants (50/95 lightness) for filled surfaces, plain tokens for text/icons/strokes. Never use a saturated accent as a large fill.

## 3 — Typography

### Font families (loaded via `next/font` in `app/layout.tsx`)

| Font | Variable | Use |
|---|---|---|
| Contrail One | `--font-display` | Display headlines, page titles, brand wordmark |
| Crimson Pro | `--font-serif` | Body prose, coaching copy, italic tooltips |
| Inter | `--font-sans` | UI, labels, dense data, forms, navigation |

Tegaki (custom animated stencil for hero titles) — see `components/PageTitle.tsx`. Used for page-level `h1` titles only.

### Type scale (utility classes from `globals.css`)

| Class | Use |
|---|---|
| `h-display-lg` | Hero / landing display |
| `h-display-sm` | Section display, modal titles |
| `h-card` | Card titles |
| `h-section` | Small uppercase eyebrow labels (tracking-wide) |
| `body-serif-sm` | Italic Crimson Pro for explanatory copy / quotes |

Inline rules:
- All-caps eyebrow text → `text-[10px] uppercase tracking-[2px] text-viltrum-travertine`
- Tabular numbers (always for measurements, currencies, %s) → `tabular-nums` + `font-mono` for tightest grids

## 4 — Card & component styles

- `card` (utility) — limestone surface, ash border, rounded-card, shadow-card. The default container.
- `ChartCard` (component, inline in `dashboard/page.tsx` ~L2616) — title + subtitle + info button + tier badge wrapper. The dashboard widget container.
- `btn-primary` — legion fill, white text. One per modal/page.
- `btn-secondary` — limestone fill, ash border, obsidian text.
- `btn-accent` — aureus fill, white text. Use for CTAs that aren't the primary action (e.g. "Browse shows" on stage-ready).

## 5 — Spacing + layout

Tailwind defaults (4px base). Layouts default to `container-app` (max-width container with edge padding). Cards use `space-y-3` or `space-y-4` for stacked content. Avoid arbitrary `space-y-7` / `space-y-9`.

## 6 — Iconography

- Icon set: `lucide-react` only. Custom icons go in `frontend/src/components/icons.tsx`.
- Sizing: `w-3 h-3` (inline), `w-4 h-4` (button), `w-5 h-5` (card header), `w-6 h-6` (hero / loader).
- Inline SVG should use `currentColor` for fill/stroke so it inherits Tailwind text color tokens.

## 7 — Motion

- Page-transition loader: `ViltrumLoader` (`components/ViltrumLoader.tsx`). Uses spinning logo SVG; respects `prefers-reduced-motion`.
- Tegaki page-title animation: handled by the `PageTitle` component; one-shot stroke-draw on mount.
- All hover transitions: `transition-colors` only — never animate layout (`transition-all` is forbidden).
- Reduce-motion fallback always present for any animation > 200 ms.

## 8 — Status indicators (Tier Readiness)

Per-gate status icons + colors, used on `TierReadinessCard` and any future place that needs the same vocabulary:

| Status | Glyph | Text class | Bar class |
|---|---|---|---|
| Met | ✓ | `text-viltrum-laurel` | `bg-viltrum-laurel` |
| Close | ◐ | `text-viltrum-aureus` | `bg-viltrum-aureus` |
| Developing | ◔ | `text-viltrum-adriatic` | `bg-viltrum-adriatic` |
| Far | ○ | `text-viltrum-centurion` | `bg-viltrum-centurion` |

Defined as `STATUS_COPY` in `components/TierReadinessCard.tsx`. Re-use this constant rather than duplicating colors when adding new status-aware widgets.

## 9 — Source files

| Concern | File |
|---|---|
| Tailwind tokens | `frontend/tailwind.config.ts` |
| CSS variables + utilities | `frontend/src/app/globals.css` |
| Font loading | `frontend/src/app/layout.tsx` |
| Brand assets | `frontend/public/viltrum-logo.png`, `viltrum-city-bg.webp`, `favicon.png`, `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` |
| Typography components | `frontend/src/components/PageTitle.tsx`, `Logo.tsx` |
| Reusable cards | `frontend/src/app/dashboard/page.tsx::ChartCard`, `frontend/src/components/PPMCards.tsx`, `frontend/src/components/V3InsightCards.tsx` |
| Status vocabulary | `frontend/src/components/TierReadinessCard.tsx::STATUS_COPY` |
| Iconography | `frontend/src/components/icons.tsx` |
| Loader | `frontend/src/components/ViltrumLoader.tsx` |

## 10 — Accessibility

- Min contrast ratio 4.5:1 for body text against any surface — verified for `iron` on `limestone` (passes WCAG AA).
- Status colors must always pair with a glyph (✓ / ◐ / ◔ / ○) so colorblind users can disambiguate.
- All interactive elements have `:focus-visible` outline (default Tailwind ring on `viltrum-centurion`).
- Modals: `role="dialog"` + `aria-modal="true"` + Escape-key close (see `ScoreInfoModal.tsx`).

---

*Last updated 2026-04-23. Aligned with frontend revision `7f82631`.*
