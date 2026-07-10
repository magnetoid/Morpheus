# Dashboard UX roadmap — 2026-07

Source: web research on 2025–2026 SaaS admin UX (Shopify Polaris, Linear,
Stripe) + a full audit of the Morpheus dashboard design system. The **visual
design-system hardening pass shipped separately** (Inter loading, one focus
ring, sentence-case tables/KPIs, one accent blue, theme-blind color fixes,
button-size normalization, empty-state consolidation). This plan tracks the
*interaction* work — each item is an independent PR.

Priority order (highest ROI first, per the research):

## 1. Contextual save bar + unsaved-changes guard
The defining Shopify-admin pattern. A sticky bar appears only when a form is
dirty ("Unsaved changes — Save / Discard"), plus a navigation guard so edits
can't be lost. Wire into the existing `data-ajax` form machinery in
`dashboard.js` (dirty-tracking via `input` events + `beforeunload` +
htmx `hx-confirm` on boosted nav). Bind **Cmd/Ctrl+S** to submit the dirty
form. Apply first to product_form, then settings panels.

## 2. Table upgrade: URL-persisted filters + bulk-action bar + saved views
- Filter pills over the table (add-filter → refine), state encoded in the URL
  so filtered views are shareable/resumable.
- On row-select, a contextual bulk-action toolbar appears (products list
  already has a basic one — generalize the pattern into a partial).
- Saved views ("Active", "Low stock", "Unfulfilled") as pinned tabs above
  index tables. Persist per-user (localStorage first; model later).
- Pagination stays (correct for admin data), add per-page selector.

## 3. Keyboard layer: g-nav + shortcut cheat sheet
- `g` then `o`/`p`/`c`/`s` → orders/products/customers/settings (Linear/GitHub
  pattern). The Cmd+K palette already ships; g-nav covers the muscle-memory tier.
- `?` opens a shortcut cheat-sheet modal.
- Focus management audit: trap in modals/palette, return focus on close.

## 4. Undo toasts on destructive actions
Toast with an Undo action (5s window) for archive/delete on products,
collections, discounts. Requires soft-delete or deferred-commit on those
endpoints. Never auto-dismiss a toast that carries an action.

## 5. Sidebar IA: section labels + pinned favorites
17 top-level items exceeds the ~7±2 consensus. Group under muted section
labels ("Sell", "Grow", "Manage", "Build") and add pin-to-top favorites
(localStorage). Push rarely-used pages to the palette long tail.

## 6. Teaching empty states
The consolidated `_empty_state.html` partial now supports first-run vs
no-results. Sweep list pages that still hand-roll `.empty-state` markup
(analytics, segments, release_notes, dynamics preview) onto the partial, and
give first-run states a one-line "why this matters" + primary CTA.

## Done (shipped with the design-system pass)
- Inter variable font actually loads (was silent system-ui fallback).
- One focus-ring language (brand ring on inputs, matches :focus-visible).
- Sentence-case table headers + KPI labels; `.num` right-align helper.
- Tremor palette aliased to semantic tokens (one blue; dead
  `data-color-mode` branch removed).
- Theme-blind hardcoded colors fixed (home pulse dots, updates pill,
  media-uploader COVER pill, rte links, stray wrong-value fallbacks).
- `btn text-xs` combos normalized to a real size step.
- `_empty_state.html` uses the `.empty-state` primitive (one system).
