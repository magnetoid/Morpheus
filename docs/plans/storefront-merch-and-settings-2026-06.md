# Master backlog — DotBooks storefront, catalog & settings (2026-06)

Captured from a rapid-fire planning session so it survives context compaction.
**Execution order = the user's stated phases below (Phase 1 first).** Each item
has a verifiable success check + KPI. Tick + commit per item; smoke each
storefront/dashboard change against the live URL.

Standing rules: batch local commits, push at logical boundaries; plugins own
their own code (contribute, don't edit other layers). See `CLAUDE.md`,
ADR 0003 + 0004.

---

## PHASE 1 — Fastest wins, highest revenue impact (DO FIRST)

### 1.1 Product image completeness  ⟵ STARTING HERE
- [ ] Backfill missing cover images (KPI: coverage **6.3% → 95%+**).
- [ ] Ensure every listing card shows an image (fallback cover when missing).
- [ ] Align feed images, page (PDP) images, and OG images — one source of truth.
- Success: ≥95% live products have a cover; cards never show a blank; OG image
  coverage 100% for live products.

### 1.2 Homepage for conversion
- [ ] Stronger CTA hierarchy — primary "Shop featured book", secondary
      "Browse all books".
- [ ] More visible product rails higher on the page; more "shop now" pathways.
- [ ] Less editorial-reading dependency before purchase; visible pricing in modules.
- Success: above-the-fold has a clear shop CTA + ≥1 shoppable rail w/ prices
  before manifesto/journal content.

### 1.3 Category page merchandising
- [ ] Denser, more scannable grids; image-complete cards.
- [ ] Clearer prices + format labels (Digital / Print).
- [ ] Visible sorting/filtering where useful; consistent card metadata.
- Success: fiction grid shows complete cards (image+price+format), visible
  sort/filter, badges where applicable.

### 1.4 Standardize metadata & branding
- [ ] Change "Morpheus" title suffixes → **DotBooks** branding sitewide.
- [ ] Complete social metadata (OG/Twitter) for all live products.
- [ ] Improve cart/home template title structure.
- Success: no "Morpheus" in public <title>; OG complete; cart/home titles sane.

## PHASE 2 — Catalog cleanup & commercial consistency

### 2.1 Catalog quality sprint
- [ ] Uncategorized products **74 → 0**.
- [ ] Expand short descriptions (descriptions <120 chars → near zero).
- [ ] Normalize card content quality; fix low-information products.

### 2.2 Standardize format/variant model
- [ ] If both digital + print intended for many books, complete that rollout
      consistently; uniform shopper experience across catalog pages.

## PHASE 3 — Revenue optimization (after foundation)

### 3.1 Higher-converting merchandising modules — **COLLECTIONS, delivered as apps**
Use the Collection system (NOT bespoke hardcoded modules). **Implement in the
EXISTING advanced-ecommerce app (one app — do NOT scatter into new plugins).**
**Surface them across the storefront as collections + sliders/carousels** (these
also feed the Phase 1.2 homepage rails). Confirm exact shape at Phase 3:
- [ ] Bestsellers, New this week, Under $10, Staff picks, Giftable editions,
      Themed collections, First-time buyer shelf.

### 3.2 Trust / conversion proof
- [ ] Secure-checkout reassurance; visible shipping/returns near conversion.
- [ ] Curated badges; editorial or customer proof where appropriate.

---

## Cross-cutting catalog/SEO items (fold into the phases above)

- **Metafields: UNIFY + attach to ALL products** (user: "i think that is
  better"). Books already carry a `book` namespace (author, isbn, gutenberg_id,
  format, language, pages, published_year, publisher). Ensure every product has
  the unified metafield set; surface + edit on the product editor.
- **ISBN / EAN / codes** = via **metafields, NOT new model columns** (user
  preference). `book.isbn` already exists; add `book.ean`/etc as metafields;
  show on PDP + JSON-LD (`isbn`, `gtin13`). (supports 2.x)
- **SEO title formatting**: separate page vs product title templates; product
  title format supports **metafield** tokens. (supports 1.4)

## PARKED — settings unification (ADR 0004), resume after Phase 1

Domain page = single home; absorbs sibling-plugin panels; suppress page-owned
category nav for `{shipping, taxes}` only (broad suppression would orphan
marketing/ai/developer panels — verified). Design in ADR 0004. Tax already
done (90a06c9). Remaining: registry `settings_panel_cards(category)` helper,
shared `_settings_panel_cards.html` partial, shipping page absorbs bookvault.

---

## KPI targets (definition of "improved")
- Image coverage 6.3% → 95%+ ; OG image 100% live products.
- Uncategorized 74 → 0 ; descriptions <120 chars → ~0.
- Every category card: cover + title + price + clean excerpt.
- Homepage: multiple shoppable modules above editorial depth.
- Lift product CTR from home + category; add-to-cart on long-tail;
  category-page conversion (not only PDP).

### Progress log
- 2026-06-03: plan created; ADR 0004 recorded; settings unification parked;
  pivoting to Phase 1.1 (image completeness) per user's "Phase 1 first".
