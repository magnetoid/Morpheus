# Storefront UI/UX improvement plan (dot_books, 2026-07)

Consolidated from a 3-track deep analysis (visual, UX flows, a11y/technical) of
`themes/library/dot_books/`. The theme is already well-crafted (dot-stamp
signature, letterpress decode hero, physical cover shadows, focus-visible +
reduced-motion + skip-link done). These are refinements, batched into releases.

## Batch A — Accessibility + feedback (v0.22.0) — highest value, mostly in base.html

- **A1. Mobile nav drawer a11y** (`base.html:915`, JS `:1036`): add `role="dialog"
  aria-modal`, toggle `aria-hidden` + burger `aria-expanded`, move focus in on
  open / restore on close, Escape to close, focus trap, `inert` when closed.
- **A2. Cart drawer a11y** (`_cart_drawer.html:9`, JS `:176/:186`): `role="dialog"
  aria-modal aria-labelledby` the "Your bag" heading; focus `#cart-drawer-close`
  on open; restore focus to trigger on close; trap Tab.
- **A3. Quick-search combobox** (`base.html:719`, JS `:895`): input `role="combobox"
  aria-expanded`; options get `id` + `aria-selected`; set `aria-activedescendant`;
  restore focus to toggle on close.
- **A4. Global live-region + kill alert()** (`base.html` near `#main-content`):
  add `<div role="status" aria-live="polite">` rendering Django `messages`; route
  add-to-cart failure (`_cart_drawer.html:278` `alert()`) + coupon/flash through it.
- **A5. Tap targets ≥44px**: `.icon-btn` 38→44 (`base.html:291`), `.btn-sm`
  (`:338`), cart ± buttons 1.6rem (`cart.html:47,51`).
- **A6. Mega-menu** (`_nav_mega_*`, `base.html:267`): `aria-expanded` + Escape.
- **A7. Checkout field errors** (`checkout_one_page.html:20`): per-field
  `aria-invalid`/`aria-describedby` (labels already associated — good).

## Batch B — Visual consistency + polish (v0.23.0)

- **B1. Consolidate duplicated/conflicting tokens** (the "consistency" core):
  `.display-xl/-l/-m` defined twice w/ different clamps (`base.html:156` vs `296`);
  `.eyebrow` twice (`159` vs `300`); `--sale:#b91c1c` (`product_detail.html:401`)
  ≠ house `--accent-ink:#b62b37`; off-palette indigo/amber/teal variant badges
  (`product_detail.html:382`). Pick one each; unify to the warm two-color system.
- **B2. On-sale ribbon** (`base.html:324`): use the brand accent (the card's only
  merchandising signal, currently paper-on-rule = invisible).
- **B3. Use the unused `.empty-shelf` component** (`base.html:207`): route PLP
  (`product_list.html:156`) + featured-rail (`home.html:812`) empties through it.
- **B4. Product-card hierarchy** (`base.html:325-327`): title 1.45→~1.2rem/500;
  author italic serif to differentiate from the sans excerpt.
- **B5. Add-to-cart reveal-on-hover** (`_product_card.html:45`): tame the black
  button wall on desktop; ALWAYS visible on touch (`hover:none`) + `:focus-within`.
- **B6. Extract repeated inline styles** → `.section-head` (`home.html:799,826`),
  `.input-pill` (`product_list.html:66-89` ×4).
- **B7. Fraunces variation-settings** beyond `.display` (card titles, genre index).
- **B8. Unify divergent card markup**: related (`product_detail.html:696`) +
  recently-viewed (JS) reuse `_product_card.html` shape.

## Batch C — UX quick wins (fold into A/B releases)

- **C1. `account_orders.html:26` `{{ o.total }}` → `|money`** (real formatting bug).
- **C2. Relabel checkout button** "Continue to payment" → "Continue to secure
  payment" (`checkout_one_page.html:147`) — it routes to a separate pay step.
- **C3. Free-shipping progress in the cart DRAWER** (`_cart_drawer.html:24`) — the
  bar exists on the cart page via the shipping plugin block (v0.17.0) but not the
  drawer; subtotal is already in the JSON payload.
- **C4. PLP consistency** (`product_list.html`): result count near the filters
  (not just pagination footer); a clear-facets link; unify apply-vs-auto-submit.
- **C5. Semantic-search loading state** (`search.html:32`).

## Batch D — Technical (larger; note as debt, schedule separately)

- Extract ~700 lines inline CSS (`base.html:21-607,733-821`) to an external hashed
  stylesheet (cacheable across pages; home is ~203KB). Keep critical inline.
- Self-host the two CDN ESM imports: Motion One `motion@10` (`base.html:656`),
  `web-vitals@4` (`:1053`) — supply-chain + CSP `cdn.jsdelivr.net`.
- Add nonces to inline `<script>`/`<style>` → drop CSP `unsafe-inline`.

## Verification (every batch)
Template compile via `get_template()` for each changed `.html`; live curl of the
affected pages after deploy (200 + key markers). base.html is the SITEWIDE shell
— edit surgically, compile-check, and smoke home + PLP + PDP + cart + checkout.
Each release bumps MORPHEUS_VERSION + release note.
