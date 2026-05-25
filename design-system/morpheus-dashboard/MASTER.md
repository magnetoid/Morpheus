# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Morpheus Dashboard
**Generated:** 2026-05-25 00:33:51
**Category:** Analytics Dashboard

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#1E40AF` | `--color-primary` |
| Secondary | `#3B82F6` | `--color-secondary` |
| CTA/Accent | `#F59E0B` | `--color-cta` |
| Background | `#F8FAFC` | `--color-background` |
| Text | `#1E3A8A` | `--color-text` |

**Color Notes:** Blue data + amber highlights

### Typography

- **Heading Font:** Fira Code
- **Body Font:** Fira Sans
- **Mood:** dashboard, data, analytics, code, technical, precise
- **Google Fonts:** [Fira Code + Fira Sans](https://fonts.google.com/share?selection.family=Fira+Code:wght@400;500;600;700|Fira+Sans:wght@300;400;500;600;700)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #F59E0B;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #1E40AF;
  border: 2px solid #1E40AF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #1E40AF;
  outline: none;
  box-shadow: 0 0 0 3px #1E40AF20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Data-Dense Dashboard

**Keywords:** Multiple charts/widgets, data tables, KPI cards, minimal padding, grid layout, space-efficient, maximum data visibility

**Best For:** Business intelligence dashboards, financial analytics, enterprise reporting, operational dashboards, data warehousing

**Key Effects:** Hover tooltips, chart zoom on click, row highlighting on hover, smooth filter animations, data loading spinners

### Page Pattern

**Pattern Name:** Data-Dense + Drill-Down

- **CTA Placement:** Above fold
- **Section Order:** Hero > Features > CTA

---

## Anti-Patterns (Do NOT Use)

- ❌ Ornate design
- ❌ No filtering

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile

---

## Tremor-inspired Utility Classes (visual-style adoption)

After research into Tremor (the dashboard component library Vercel
acquired in 2024), we adopted its visual recipe inside the existing
Django/CSS dashboard. **No React, no build pipeline** — utility classes
live in `admin_dashboard/base.html` next to `.btn` / `.card` / `.pill`.

Use these when building new dashboard pages. They compose with the
existing utility set; nothing in the older system was changed.

### KPI tile

```html
<div class="card card-padded kpi">
  <div class="flex items-center justify-between">
    <span class="kpi__label">Revenue (7d)</span>
    <i data-lucide="dollar-sign" class="h-4 w-4" aria-hidden="true"></i>
  </div>
  <div class="kpi__value">$12,480</div>
  <div class="kpi__delta kpi__delta--up">
    <i data-lucide="trending-up" class="h-3.5 w-3.5" aria-hidden="true"></i>
    +12.4% vs previous
  </div>
</div>
```

`.kpi__value` uses `font-variant-numeric: tabular-nums` so dashboards
don't jitter when figures change.

### Callout

```html
<div class="callout callout-warn">
  <i data-lucide="alert-triangle" class="h-4 w-4 callout__icon" aria-hidden="true"></i>
  <div class="callout__body">
    <p class="callout__title">No API keys configured</p>
    Linda falls back to offline mode until you add keys.
  </div>
</div>
```

Variants: `.callout-info`, `.callout-success`, `.callout-warn`,
`.callout-error`. The left-edge stripe is the visual signature.

### Soft Badge

`.badge-soft` companion to the existing solid `.pill`. Use when you
want the lighter opacity-tinted look (Tremor default) instead of
the firmer `.pill` block colour.

```html
<span class="badge-soft badge-soft-success">Active</span>
<span class="badge-soft badge-soft-warn">Low stock</span>
```

Variants: `.badge-soft-info`, `-success`, `-warn`, `-error`, `-neutral`.

### Tab list

Underline-only sub-navigation (no pill backgrounds — doesn't compete
with the topbar):

```html
<nav class="tab-list">
  <a href="?tab=overview" class="tab is-active">Overview</a>
  <a href="?tab=variants" class="tab">Variants</a>
  <a href="?tab=seo" class="tab">SEO</a>
</nav>
```

### Color tokens

Tremor accent tokens (do **not** override the existing Morpheus
ink-on-paper palette):

| Token | Light | Dark |
|---|---|---|
| `--tremor-blue` | `#3b82f6` | inherited |
| `--tremor-blue-bg` | `rgba(59,130,246,.08)` | inherited |
| `--tremor-blue-fg` | `#1d4ed8` | `#93c5fd` |
| `--tremor-emerald-bg/fg` | tinted bg + `#047857` | bg + `#6ee7b7` |
| `--tremor-amber-bg/fg`   | tinted bg + `#b45309` | bg + `#fcd34d` |
| `--tremor-red-bg/fg`     | tinted bg + `#b91c1c` | bg + `#fca5a5` |

### What we deliberately did NOT adopt

- **Tremor's font** (Inter is already in use; no swap needed).
- **Tremor's React `<Card>` / `<Badge>` / `<Callout>` components** — the
  Morpheus dashboard is Django templates; a full React port is a
  multi-week initiative outside the visual-style scope.
- **Tremor's blue primary** as the brand color. The dashboard's
  ink-on-paper aesthetic stays; the blue is reserved for callouts /
  focus rings / data emphasis.
