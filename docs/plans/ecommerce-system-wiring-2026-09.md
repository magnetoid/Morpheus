# Ecommerce system wiring — development plan (2026-09)

> Snapshot of `magnetoid/morpheus` `main` after `c925d8b8` (supernatural_shop square cards).
> This is the working order to make the OS a real multi-brand shop, not a bookstore with extra plugins.

**Goal:** One buy path, one journal, one SEO owner, themes that do not assume books — so DotBooks and general shops (Supernatural) both complete a purchase and rank.

**Not this plan:** RBAC coverage, open-core packaging, TikTok/Pinterest channels (see `docs/plans/roadmap-2026-execution.md`).

---

## What already works

- Catalog → cart → `/checkout/` or `/checkout/quick/` → `completeOrder` → Stripe Payment Element is the live money path (`storefront/views/checkout.py`, `orders/graphql/mutations.py`, `payments/services/stripe.py`).
- Stock reserve on order create, decrement on `ORDER_PAID` (webhook).
- Tax and shipping subscribe to `CART_CALCULATE_BREAKDOWN` (local rates).
- Storefront `<head>` is owned by the SEO plugin (`STOREFRONT_HEAD` → `seo/head/builder.py`). `SeoMeta` is the intended single owner; native catalog columns are fallback only.
- Commands already exist: `seo_backfill_meta`, `seo_rebuild_titles`, `regenerate_sitemap`.

---

## Live evidence (2026-09-13)

| Surface | Result |
|---|---|
| `supernatural-shop.com` home | 200, `supernatural_shop` active, Nature’s Gift featured (Abyssinian Oil…), 1:1 covers after `c925d8b8` |
| `/journal/` | CMS `Page` journal posts (oils), not `journal.Post` |
| `/products/pink-grapefruit/` | 200 |
| `/products/ginseng-root-coins/` | **500** — leftover bookstore PDP contract (`book_extras` / GraphQL dict vs `.book`) |
| Dual catalog | ~487 `ng-*` SKUs + leftover `SN-*` curios/books mixed |

---

## P0 — Stop 500s and bookstore leaks on general shops

### 0.1 Gate `book_product` off the generic PLP

**File:** `plugins/installed/storefront/views/catalog.py` (~117–122)

`?genre=` / `?topic=` always `qs.filter(book__genres__slug=…)`. Author/publisher filters are already `is_active('book_product')`-gated (~153). Mirror that guard.

**Test:** PLP with `book_product` disabled must 200, not `FieldError`.

### 0.2 Stop themes loading sibling plugin templates

**Files:**

- `themes/library/{dot_books,supernatural_shop}/templates/storefront/{product_detail.html,product_list.html,_product_card.html}`
- `{% load book_extras %}`, `{% book_language_editions %}`, `{% include "product_gallery/_pdp_hero_slider.html" %}`

If `book_product` or `product_gallery` is uninstalled: `TemplateSyntaxError` / `TemplateDoesNotExist` on every PDP.

**Wire-up:**

1. `product_gallery` contributes hero via `StorefrontBlock(slot='pdp_gallery')`.
2. Theme uses `{% storefront_blocks "pdp_gallery" %}` plus a plain `<img>` fallback.
3. Move `first_sentence` / language-editions into a core/storefront tag library **or** `dot_books.requires_plugins = ['book_product', 'product_gallery']` and strip those loads from `supernatural_shop`.

### 0.3 Kill leftover `product.book` on `dot_books` PDP

**File:** `themes/library/dot_books/templates/storefront/product_detail.html` (~36, ~63)

PDP `product` is a GraphQL **dict**. `.book` is dead. Use `book_product`’s existing `pdp_below_form` block.

`supernatural_shop` already uses `product.category`. Re-test leftover `SN-*` PDPs after 0.2 — ginseng 500 is the canary.

### 0.4 One journal

| Path | Status |
|---|---|
| `cms.Page` `metadata.category='journal'` | **Live** storefront + sitemap + feeds |
| `journal.Post` + `journal.Block` | Models only — no URLs, no dashboard, no GraphQL |
| `_JOURNAL_ENTRIES` in `storefront/views/content.py:51-93` | Bookstore fallback (Cusk/Sebald) if CMS is empty |

**Decision (do A, not both):** keep CMS as the journal. Delete or archive the `journal` plugin slot allow-list (`core/tests/test_slot_parity.py` already skips it). Delete `_JOURNAL_ENTRIES`. About/Contact SEO strings in `content.py` must come from CMS `STOREFRONT_PAGE_INTRO` / `StoreSettings`, not “dot books is an independent bookshop”.

---

## P1 — Theme contract: bookstore vs general shop

Both themes today:

```
supports_plugins = ['storefront', 'catalog', 'orders']
requires_plugins = []   # unused, unenforced
```

Both still ship Genres / Topics / Authors mega-nav (`base.html` default nav, `_nav_mega_genres.html`, `_nav_mega_authors.html`).

**Do:**

1. `dot_books.requires_plugins += ['book_product']`. Enforce `requires_plugins` at boot (fail loud in `DEBUG`, log in prod).
2. `supernatural_shop` default nav: Shop / categories / Journal / Staff picks. No genre/author mega menus.
3. Move `nav_genres` / `nav_topics` / `nav_authors` off `morph/settings.py:369-374` onto `register_context_processor` so disable removes them.
4. Move `/author/<slug>/` (`storefront/urls.py:57`) into `book_product` (storefront already 404-gates the view).
5. Strip cloned bookstore copy still in `supernatural_shop` (`vendors.html`, `marketplace_landing.html`, About).

---

## P1 — SEO inside the ecommerce OS (owner + populate)

Rendered metadata is already the SEO plugin. The gap is **writes** and **empty fields**.

### Source of truth

1. `SeoMeta` (generic FK) — dashboard / agent / `upsertSeoMeta`
2. Native `Product.meta_*` / `og_*` / `twitter_*` / `noindex` — catalog GraphQL still writes **only these**
3. `SeoTemplate` `empty_only` — render-time, no row writes (safest)
4. View/theme fallbacks

**Landmine:** `PRODUCT_CREATED` autofills `SeoMeta(auto_filled=True)`. After that, native `Product.noindex` is ignored unless copied into `SeoMeta.robots`. After a merchant edit (`auto_filled=False`), catalog GraphQL SEO **silently stops affecting the page**.

### Platform wiring (code)

| Gap | File | Fix |
|---|---|---|
| Catalog mutations write native columns, not SeoMeta | `catalog/graphql/mutations.py` | Dual-write SeoMeta with `provenance='catalog.graphql'`; do not clobber `auto_filled=False` |
| `upsertSeoMeta` partial + empty-overwrite | `seo/graphql/` | Patch semantics; add og_title, twitter_*, focus_keyword |
| Agent/bulk-meta = product title/desc only | `seo/agent_tools.py`, `seo/views.py` | Category, collection, CMS page, journal |
| No autofill for category/collection/page | `seo` product-created hook | Same empty-only stamp |
| Vendor in sitemap, no SEO card | `seo/app.py` form-card loop | Add vendor |
| IndexNow maps every CMS page to `/journal/{slug}/` | `seo` `_URL_TEMPLATES['cms.page']` | `/p/{slug}/` unless `metadata.category=='journal'` |
| `llms.txt` category URLs `/products/?category=` | crawler files | `/category/{slug}/` |
| `checkout_experience` not SEO | n/a | ignore; not the buy path |

### Shop populate (data — run per instance)

Order (never overwrite merchant-typed SeoMeta):

1. `SeoTemplate` `empty_only` for `product` / `listing` / `article` / `page` title+description.
2. `python manage.py seo_backfill_meta` then `seo_rebuild_titles --dry-run`.
3. Fill empty product descriptions from stripped HTML `description` / `short_description` (≤160–300 chars) into **empty** `SeoMeta.description` only.
4. Category/collection: `{name}` title, first 160 chars of description.
5. CMS journal pages: title + excerpt → SeoMeta kind article.
6. `SiteSeoSettings.organization_name` + `llms_txt_intro` from `STORE_NAME`.
7. Verify: view-source PDP `og:title` / `og:description` / canonical; `/sitemap.xml`; `/llms.txt`; `/ai/products.json`.

DotBooks: run the same commands only after Marko confirms — that catalog is already merchant-edited.

---

## P1 — Buy path: finish the money, ignore the overlay

Canonical path stays storefront checkout. **Do not** make `checkout_experience` own `/checkout/` until its JS matches the GraphQL schema (today it posts `full_name`, wrong rate shape, and redirects to `/orders/{n}/confirmation/` which does not exist).

### Must-fix for a real charge

1. Fire `PAYMENT_FAILED` from `_mark_transaction_failed` (`payments/services/stripe.py` ~463). Today DB-only; analytics/email never see a decline.
2. Fire `CART_CREATED` / `CART_UPDATED` from `CartService` (`core/hooks.py:435-436` never produced; observability counters stay 0).
3. Document instance env: `STRIPE_SECRET_KEY` **and** `STRIPE_PUBLIC_KEY` (public is **env only**, dashboard secret is not enough) **and** `STRIPE_WEBHOOK_SECRET` hitting `POST /payments/webhooks/stripe/`. Missing webhook = money taken, order unpaid, stock not decremented, no paid email.
4. Tax/shipping address: checkout stores `state`, breakdown reads `region` → US tax often $0. Use `region or state` in `tax/services.py` and `shipping` `on_cart_breakdown`.
5. Tax shipping: tax priority 20 vs shipping 30 → shipping never taxed. Either tax after shipping or document “shipping ex-tax”.
6. Confirmation page should wait for `payment_status=paid` (or poll webhook), not treat Stripe `redirect_status` as paid.

### Move URLs out of storefront

| Today | Owner |
|---|---|
| `/affiliates/terms/` `storefront/urls.py` | `affiliates` |
| Gift-card apply/remove + `applyGiftCard` in `orders/graphql` | `gift_cards` |
| `/journal/`, `/staff-picks/` | CMS / catalog collections |
| `/author/` | `book_product` |

`experiments/app.py` registers hooks without `plugin=` → disable gating skipped. Use `self.register_hook`.

---

## P2 — Empty GraphQL and dead plugins

Delete or implement (do not leave empty packages):

- `storefront/graphql`, `wishlist/graphql`, `reviews/graphql`, `loyalty_points/graphql` — empty `__init__.py` only
- `payments/graphql/queries.py` — stub comment
- `journal` plugin if CMS remains the journal
- `checkout_experience` overlay until schema-aligned, or quarantine behind a feature flag default off

Hooks declared never fired (besides CART_*/PAYMENT_FAILED): `AI_DESCRIPTION_GENERATED`, `AI_RECOMMENDATION_REQUESTED`, `INVENTORY_OVERSTOCK_DETECTED`. Either produce them or drop from `MorpheusEvents`.

---

## P2 — Catalog hygiene (instance, not OS)

Supernatural mix of Nature’s Gift + leftover books/curios. OS should not special-case SKU prefixes, but the shop needs:

1. Archive or unpublish leftover `SN-*` (or a “Books” collection only) so PLP is oils.
2. Strip `GC/MS Analysis:` / `Batch No: TH-*` from long descriptions (asked, not done).
3. Image pipeline still does not crop; square is CSS. Optional later: crop mode in `catalog/image_pipeline.py` when W=H.

---

## Suggested build order (weeks)

| Week | Work | Verify |
|---|---|---|
| 1 | 0.1–0.3 (book gates + theme includes) | ginseng PDP 200; PLP without book_product 200; `pytest plugins/installed/storefront/tests plugins/installed/book_product/tests` |
| 1 | SEO templates + backfill on supernatural-shop | PDP has unique `og:description`; `/sitemap.xml` 200 |
| 2 | 0.4 journal CMS-only; About/Contact from CMS | empty CMS ≠ Cusk essays on a general shop |
| 2 | Theme nav split + context processors | supernatural nav has no Genres/Authors |
| 3 | PAYMENT_FAILED, CART_*, state/region tax, webhook runbook | decline fires hook; US address quotes tax; paid order decrements stock |
| 3 | Catalog GraphQL dual-write SeoMeta | `updateProduct` meta shows in view-source after `auto_filled=True` only |
| 4 | URL ownership moves; empty GraphQL delete/implement | `pytest` slot parity + url reverse |
| later | checkout_experience rewrite or delete; vendor SEO card; IndexNow/llms URL fixes | |

---

## Files likely to change

- `plugins/installed/storefront/views/catalog.py`
- `plugins/installed/storefront/views/content.py` (delete `_JOURNAL_ENTRIES`)
- `themes/library/supernatural_shop/templates/storefront/*.html`
- `themes/library/dot_books/templates/storefront/product_detail.html`
- `themes/library/{dot_books,supernatural_shop}/theme.py`
- `morph/settings.py` (context processors)
- `plugins/installed/product_gallery/app.py`
- `plugins/installed/payments/services/stripe.py`
- `plugins/installed/orders/services.py` (cart events)
- `plugins/installed/tax/services.py`, `plugins/installed/shipping/`
- `plugins/installed/catalog/graphql/mutations.py`
- `plugins/installed/seo/graphql/`, `agent_tools.py`, URL templates

**Do not** commit `MORPHEUS_ACTIVE_THEME`. Theme files on `main` are OK; activation stays Coolify env. Shop deploy UUID `z10xg4j7yq8x1htipw12a368`. DotBooks UUID `ghtnqf6lw2bg5229lv1sf4h9` auto-deploys `main` — keep buy-path/SEO **code** on a branch until Marko asks to deploy DotBooks.

---

## Out of scope until asked

- Archiving leftover books on supernatural-shop (needs a yes)
- CSS 1:1 already shipped in `c925d8b8`
- GC/MS strip (separate catalog mutation)
- Woo/Omnisend into Roveki
- Making `checkout_experience` the primary checkout
