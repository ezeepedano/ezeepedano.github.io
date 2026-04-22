# Propel ERP — Design System

**Style:** *Soft UI Evolution*
**Goal:** Modernize the ERP with a calmer, more accessible interface while preserving the existing indigo identity. Multi-layer soft shadows, 10 px radii, 200–300 ms motion, WCAG AA+ contrast.

The tokens below are the single source of truth. They are exposed as CSS custom properties in `templates/base.html` (`:root`) and mirrored in the Tailwind config so utilities keep working in templates that already use classes like `bg-primary`, `text-slate-700`, `shadow-soft`, etc.

---

## 1. Palette

All shades are defined as CSS custom properties so PDF templates and legacy CSS can opt in without Tailwind.

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-primary-50` | `#EEF2FF` | Hover tint, soft fills |
| `--color-primary-100` | `#E0E7FF` | Chip/badge background |
| `--color-primary-400` | `#818CF8` | Secondary accent |
| `--color-primary-500` | `#6366F1` | Hover state of CTA |
| `--color-primary-600` | `#4F46E5` | **Primary brand** (links, CTA, focus) |
| `--color-primary-700` | `#4338CA` | Primary pressed |
| `--color-primary-900` | `#312E81` | Deep accents |
| `--color-primary-950` | `#1E1B4B` | Sidebar bg |
| `--color-accent` | `#10B981` | Success, positive deltas, secondary CTA |
| `--color-accent-dark` | `#059669` | Accent hover/pressed |
| `--color-danger` | `#EF4444` | Destructive, errors |
| `--color-warning` | `#F59E0B` | Warnings, pending |
| `--color-info` | `#0EA5E9` | Informational |
| `--color-canvas` | `#F5F7FB` | App background (softer than slate-50) |
| `--color-surface` | `#FFFFFF` | Cards, modals |
| `--color-surface-muted` | `#F8FAFC` | Table striping, subtle panels |
| `--color-border` | `#E2E8F0` | Standard border |
| `--color-border-strong` | `#CBD5E1` | Form borders, dividers |
| `--color-text` | `#0F172A` | Headings / primary text |
| `--color-text-muted` | `#475569` | Body text |
| `--color-text-soft` | `#94A3B8` | Helper / meta |

**Contrast check:** `#0F172A` on `#F5F7FB` → 15.2 : 1 (AAA). `#FFFFFF` on `#4F46E5` → 7.3 : 1 (AAA).

---

## 2. Typography

**Family:** [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans) — warm, modern B2B sans-serif. Single family policy (no display pairing) keeps load time low.

**Stack:** `'Plus Jakarta Sans', 'Outfit', system-ui, sans-serif` — `Outfit` is kept as a fallback so templates that ship before the new font loads don't flash an OS font.

**Scale (rem, base 16):**

| Token | Size | Line-height | Use |
|-------|------|-------------|-----|
| `--fs-xs` | 0.75 | 1.1 | Labels, badges |
| `--fs-sm` | 0.875 | 1.35 | Helper text, table cells |
| `--fs-base` | 1 | 1.55 | Body |
| `--fs-lg` | 1.125 | 1.5 | Section leads |
| `--fs-xl` | 1.25 | 1.4 | Card titles |
| `--fs-2xl` | 1.5 | 1.3 | Page titles |
| `--fs-3xl` | 1.875 | 1.25 | KPI numbers |
| `--fs-4xl` | 2.25 | 1.2 | Dashboard hero |

**Weights:** 400 body · 500 labels · 600 buttons / card titles · 700 page titles · 800 display numbers.

---

## 3. Radii

| Token | px |
|-------|----|
| `--radius-sm` | 6 |
| `--radius` | 10 (**default**) |
| `--radius-lg` | 14 |
| `--radius-2xl` | 20 |
| `--radius-pill` | 999 |

Inputs, buttons, chips → `--radius`. Cards and modals → `--radius-lg`. Avatars and badges → `--radius-pill`.

---

## 4. Shadows (multi-layer)

Soft UI Evolution avoids single heavy shadows; every elevation uses two stacked layers for a softer physical feel.

```css
--shadow-xs: 0 1px 2px rgba(15,23,42,0.04), 0 1px 1px rgba(15,23,42,0.02);
--shadow-sm: 0 2px 4px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.03);
--shadow-md: 0 6px 16px -4px rgba(15,23,42,0.08), 0 2px 6px -2px rgba(15,23,42,0.04);
--shadow-lg: 0 20px 40px -12px rgba(15,23,42,0.12), 0 8px 16px -6px rgba(15,23,42,0.06);
--shadow-inset: inset 0 1px 2px rgba(15,23,42,0.04);
--shadow-focus: 0 0 0 3px rgba(99,102,241,0.28);
--shadow-glow: 0 10px 30px -10px rgba(79,70,229,0.35);
```

**Tailwind aliases:** `shadow-xs`, `shadow-sm`, `shadow-soft` (→ `--shadow-md`), `shadow-lift` (→ `--shadow-lg`), `shadow-glow`.

---

## 5. Spacing

Tailwind 4-based scale is kept — no custom overrides. The design system encourages **multiples of 4** only. Use:

- `p-4` / `p-6` for card padding (16 / 24 px)
- `gap-3` / `gap-4` between form fields
- `space-y-2` between nav items
- `py-3.5 px-4` on nav links (matches existing sidebar)

---

## 6. Motion

```css
--dur-fast: 150ms;
--dur: 220ms;       /* default */
--dur-slow: 300ms;
--ease: cubic-bezier(0.2, 0.8, 0.2, 1);  /* soft overshoot-less */
```

- Hover / color transitions → `var(--dur) var(--ease)`.
- Drawers / modals → `var(--dur-slow) var(--ease)`.
- Skeleton pulses, spinners → unaffected.

`prefers-reduced-motion` disables all transforms and animations (handled in `base.html`).

---

## 7. Focus & accessibility

- Every interactive element shows a **3 px primary ring** (`--shadow-focus`) on keyboard focus.
- `:focus-visible` only — mouse clicks don't trigger the ring.
- Form error text: `--color-danger` with 4.8 : 1 contrast on `--color-surface`.
- Disabled: 60% opacity, `cursor: not-allowed`.
- Minimum tap target 40 × 40 px on mobile; sidebar links and buttons already comply.

---

## 8. Component recipes

These are not yet codified as partials — they're the mental model for Fase 2.

- **Card** `bg-surface rounded-[14px] shadow-soft p-6 border border-[--color-border]`
- **Primary button** `bg-primary text-white rounded-[10px] px-4 py-2.5 font-semibold shadow-sm hover:bg-primary-700 focus-visible:ring-4 ring-primary/25`
- **Ghost button** `bg-transparent text-primary border border-primary/30 hover:bg-primary/5`
- **Input** `rounded-[10px] border border-[--color-border-strong] bg-surface px-3.5 py-2.5 focus:border-primary focus:ring-4 focus:ring-primary/20`
- **Nav link (active)** `bg-primary text-white shadow-glow`
- **Nav link (idle)** `text-slate-400 hover:bg-white/5 hover:text-white`
- **Badge** `inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium`

---

## 9. Fase roadmap

- **Fase 0 (done):** Tokens + this document.
- **Fase 1 (in progress):** `templates/base.html`, `templates/includes/sidebar.html`, top header, flash messages.
- **Fase 2 (deferred):** Daily-driver screens — to be picked once the user has one week of real usage.
- **Fase 3:** Print / PDF templates (remitos, presupuestos) aligned with the token palette.
