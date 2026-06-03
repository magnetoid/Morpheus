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

### 1.1 Product image completeness  ⟵ READY TO BUILD (spec below)

**Audit (prod, 2026-06-03):** 859 active products; **55 (6.4%) have a
ProductImage**; **1 (0.1%) has og_image**. They are Project Gutenberg books
with a `book` metafield namespace: `author, isbn, gutenberg_id, format,
language, pages, published_year, publisher`. Card template already has a weak
`.placeholder` (truncated name) — that's the "low-information cards" issue.

**Build — `catalog/management/commands/backfill_book_covers.py`:**
- qs = `Product.objects.filter(status='active', images__isnull=True).distinct()`.
- per product: `meta = Metafield.objects.for_obj(p)` →
  `author = meta.get('book.author')`, `gid = meta.get('book.gutenberg_id')`.
- if `--gutenberg` and gid: GET
  `https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.cover.medium.jpg`
  (timeout 10s, accept only if 200 + image + >2KB). **TEST first** whether
  Gutenberg serves covers for our ids (curl a couple).
- else: generate a styled JPEG (Pillow, 800×1200): deterministic bg colour from
  `hash(slug)`, serif **title** wrapped, **author**, "DOTBOOKS CLASSICS" label.
  Font: try candidate paths (DejaVuSerif / Georgia / `/usr/share/fonts/...`),
  fall back to `ImageFont.load_default()`. (Pillow is available — see
  `catalog/image_pipeline.py`.)
- save `ProductImage(product, is_primary=True, sort_order=0, alt_text=...)` via
  `pi.image.save('cover-<slug>.jpg', ContentFile(bytes))` (webp auto-generates
  in `ProductImage.save`); also set `product.og_image` to the same bytes →
  OG/feed completeness in one pass.
- flags: `--limit N`, `--gutenberg`, `--dry-run`; idempotent (skips products
  that already have an image). Log every 25.
- **Run on prod:** `python manage.py backfill_book_covers --gutenberg`
  (batch via `--limit` first to sanity-check output).

**Also (interim/safety):** upgrade theme `.placeholder` (category_detail.html
:43 + home/search) into a real classic-cover look (serif title + DotBooks
imprint) so even pre-backfill cards read as covers, not weak boxes.

- Success: re-run the audit → coverage ≥95%, OG ≥95%; Playwright category page
  shows covers, not text boxes. Align feed/PDP/OG (all use primary_image + the
  new og_image).

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

### 1.4 Standardize metadata & branding  ✅ MOSTLY DONE (d391374, ffeb2bf — live)
- [x] Title suffix was already "Dot Books" (Fiction/Cart/etc). Footer
      "Made on Morpheus." → "Made by readers, for readers." + modern
      `mobile-web-app-capable` meta.
- [x] Improve cart/home titles → home `<title>` now "Dot Books — an independent
      bookshop" (+ meta description); cart "Your cart — Dot Books".
- [ ] Complete OG/Twitter for all live products — **blocked on og_image**
      (Phase 1.1 images, skipped). Product OG title/desc/url already emit via
      `{% seo_product_og %}`; only the image is missing.
- **Landmine learned:** the storefront `<title>` is emitted ONLY by
      `{% seo_meta %}` (base.html:7-9, `fallback_title=seo_title|default:"dot
      books."`). `{% block title %}{% seo_title %}` in child templates is
      VESTIGIAL — never rendered. To set a page title, set the `seo_title`
      context var OR override `{% block seo %}` with a `fallback_title`.
- (Admin dashboard `<title>` still "· Morpheus" — staff-only, left as-is.)

## PHASE 2 — Catalog cleanup & commercial consistency

### 2.1 Catalog quality sprint
- [x] **Uncategorized 73 → 0** (2026-06-03, prod data change). Classified the 73
      `category=None` classics by hand (only 7 had gutenberg_id; no subject
      metafield) → 63 Fiction, 5 Non-fiction, 3 Children, 1 Poetry, 1 Essays.
      Verified `REMAINING_UNCAT = 0`.
- [ ] Expand short descriptions (descriptions <120 chars → near zero).
- [ ] Normalize card content quality; fix low-information products.
- [ ] **Format/variant standardization (2.2)** — THIS unblocks the deferred 1.3
      Digital/Print labels + format badges (today 695/859 are product_type
      'simple', book.format on only 64).

### 2.2 Standardize format/variant model
- [ ] If both digital + print intended for many books, complete that rollout
      consistently; uniform shopper experience across catalog pages.

## PHASE 3 — Revenue optimization (after foundation)

### 3.1 Higher-converting merchandising modules — **COLLECTIONS, delivered as apps**
Use the Collection system (NOT bespoke hardcoded modules). **Implement in the
EXISTING advanced-ecommerce app (one app — do NOT scatter into new plugins).**
**Surface them across the storefront as collections + sliders/carousels** (these
also feed the Phase 1.2 homepage rails).

- [x] **Featured-collection rails on the homepage** (2026-06-03). advanced_ecommerce
      contributes a `home_after_rails` storefront block (new generic slot in
      home.html, placed with the shoppable rails before editorial) that renders
      each `Collection.is_featured` set as a slider linking to `/collection/<slug>/`.
      De-duped against the Staff-picks collection the home view already shows
      (reads `staff_picks_collection.slug` from context — no hardcoding). Caps +
      on/off in the plugin settings panel (`enable_collection_rails`,
      `collection_rail_products`, `max_collection_rails`). Disabling the plugin
      removes the rails. Surfaces `reading-the-spring` (50 books), previously
      invisible. Merchants curate via the existing Collections admin.
- **Data reality (prod 2026-06-03, checked before building):** "Under $10" and
      "Bestsellers" rails are **NOT viable here** — 829/859 books sit in $5–10
      (min 4.50, max 18.99) so "under $10" = the whole catalog, and there are
      **0 OrderItems** so bestsellers is empty. Skipped rather than ship empty/
      undifferentiated rails. Revisit when price variety + order history exist.
- [ ] Future rail types once data supports them: New-this-week, Giftable
      editions, Themed collections, First-time buyer shelf. (A smart/rule-based
      Collection engine would generalise these — deferred; manual `is_featured`
      collections cover today's need.)

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
  preference). ✅ DONE (2026-06-03). Canonical registry
  `plugins/installed/metafields/identifiers.py:PRODUCT_IDENTIFIERS`
  (isbn13, isbn10, ean13, upc, gtin14, mpn, asin, barcode) stored in the
  generic **`identifiers`** namespace (future-proof — not book-bound).
  `product_identifiers(obj)` (legacy fallback: `book.isbn` → isbn13) drives
  all three surfaces from one source: PDP "Product codes" block
  (`product_codes` ctx), schema.org Product JSON-LD
  (`seo/services/jsonld.py` → isbn/gtin13/gtin12/gtin14/mpn/asin), and the
  product editor's "Identifiers / product codes" card (writes via
  `Metafield.objects.set`, gated on the `identifiers_present` marker).
- **SEO title formatting**: product title/description support **metafield +
  field tokens**. ✅ DONE (2026-06-03). `seo/services/tokens.py:expand_tokens`
  replaces `{name}/{sku}/{category}/{price}` + any metafield (`{author}`,
  `{isbn13}`, …) at render time inside `resolve_meta` (so it works for any
  object, incl. pages). The product editor's Meta title + Meta description get
  an "Insert field ▾" dropdown (`_seo_token_select.html`, fed by
  `available_tokens()`) that inserts a token at the cursor. 5 tests.
  Follow-up: add the same dropdown to the page/collection editors (reuse the
  partial + pass `seo_tokens`). Store-level page vs product title *patterns*
  still live in `SiteSeoSettings.title_template` ({title}/{site_name}).

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
