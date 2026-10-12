# Merchandising, product page and discovery apps (26 apps)

Store order in rows is dotbooks / supernatural / montenegro / irving. Two kinds of evidence back these findings:
- **Code reading**, including local renders of the block templates with the GraphQL-shaped `product`/`cart` dicts the real views pass.
- **Live checks** with GET requests to dotbooks.store and montenegro-experience.me (2026-10-12).

The main pattern is that 10 of the 26 apps came from the 2026-06-12 "vibe-coding roadmap" batch (see the `morph/settings.py` comment block above `immersive_pdp`). Nine of them are scaffolds: a manifest, models that nothing writes, and block templates that wait for context variables no view supplies. The one exception is `product_stories`, which is real code. Every scaffold app has 0 rows on all four stores.

## Per-app verdicts

| App | What it really does today | Real / stub | Verdict | Key improvements |
|---|---|---|---|---|
| **product_gallery** | Its one live surface is `_pdp_hero_slider.html`, which **three themes `{% include %}` directly** (not as a block). The contributed `pdp_above_long_description` block (`_slider.html`) never renders on a real PDP. `_carousel.html` and `_main_cover.html` are included by nothing. Rows: no models. | Real (one template); the rest is dead | **Keep as the target of merge M1** (product media and product-page app) | Delete the dead templates. Declare the `product_videos` dependency, or absorb that app. Because the themes include the template directly, a disable does not remove the gallery, and removing the app breaks every PDP. Either mark the app `protected`, or have the themes fall back. |
| **immersive_pdp** | Sticky "add to bag" bar on the PDP plus a JS runtime. The bar is gated on `variants`, which the PDP view never puts in context, so it **has never rendered**. `buybox.js` still loads on every storefront page (checked live on dotbooks and montenegro). | Stub in practice | **Delete** (or rebuild inside M1 reading `product.variants`) | Its test passes `variants` explicitly, so it proves nothing about the real view. The "Edition" label is book vocabulary. |
| **product_stories** | Per-product "why you'll love it" story blocks (heading, body, image URL) on the PDP. Has a dashboard editor and 2 tools (`stories.list_blocks`, `stories.add_block`). Rows 0/0/0/0. | Real | **Merge into product_gallery (M1)** | Images are pasted URLs, not the dashboard's one media uploader. No update, delete or reorder tools. Book copy: `aria-label="More about this book"`. |
| **product_videos** | `ProductVideo` model (rows 0/0/0/0) plus YouTube/Vimeo ID filters. The CRUD lives in **admin_dashboard** (`views_split/products.py:401,489`), the query in the **storefront** view, and the display in **product_gallery**'s hero slider. Its own PDP block never renders. | Real model; its own surfaces are dead | **Merge into product_gallery (M1)** | Move the CRUD out of admin_dashboard into a `PRODUCT_FORM_CARDS` contribution, which repays 2 boundary-baseline pairs. Add a tool (`products.add_video`). No tests. |
| **media** | Dashboard asset library (Content → Media). It is a read-time union of `MediaAsset`, `ProductImage` and digital files, plus upload, alt-text edit and a picker modal used by metafields. 1 tool (`media.search`). Rows 3/0/12/0. | Real | **Keep**; absorb `brand_kit.Asset` (M8) | Tools for setting alt text, uploading from a URL and deleting (alt text is SEO work Janus could do). The library caps at 300+300 rows with no pagination (`views.py:252-300`). Missing the `has_models`/apps-structure flag (baseline `media:structure.apps`). |
| **media_3d** | `Asset3D` and `ShoppableVideo` models. Nothing creates them: no admin, dashboard or tool. Both blocks wait for `asset` and `shoppable_video` context that nothing supplies, and there is no JS behind the "View in your space" button. Rows 0. | Stub | **Delete** | The manifest claims a GraphQL extension that does not exist (`app.py:10-11`). Its "tests" are pytest-style functions in `tests/__init__.py`, which the Django runner never collects. |
| **lookbook** | `Look`/`LookItem` models and a `/looks/<slug>/` page. Nothing can create a Look: no admin, dashboard or tool. The PDP "Worn with" block needs `in_this_look`/`parent_look`, which nothing supplies. Rows 0. | Stub (a page with no way to fill it) | **Delete**; a catalog `Collection` (name, slug, description, image, products) is the same concept | This is a parallel table to `catalog.Collection` ("one concept, one owner"). The claimed "add the look to cart" and "AI auto-look" do not exist. `requires=['personalisation']` is never used. "All books" link in `look_detail.html:8`. |
| **flipbook** | `/p/<slug>/flipbook/` renders the product's PDF with PDF.js and StPageFlip. A CTA block sits under the buy form. Active on dotbooks and **montenegro**. | Real, but **leaks paid files** (see Notable problems) | **Merge into digital_products (M6)**; book/digital vertical, opt-in | Serve a sample, never the paid file. Fix the CTA condition. The `enabled` setting duplicates the app toggle. `max_preview_pages=0` ("full book") is impossible (`views.py:67`). |
| **bookstore_3d** | `/walkthrough/` three.js 3D bookshop with catalog products on the shelves, plus a footer link. Active on dotbooks and **montenegro**: the travel store's footer shows "3D store" (live). | Real (a gimmick) | **Merge into book_product (M6)**; out of the default list | The `enabled` setting duplicates the app toggle. No measure of whether anyone uses it. |
| **lumina** | `/create/` marketing page for dotbooks' "Lumina Book Creator". The default URL `https://lumina.dotbooks.store` is hardcoded (`views.py:17`). Active on montenegro: its footer shows "Write a book" and `/create/` says "sell it on dot books" (live). | Real, but store-specific content | **Delete from the platform**; recreate it as a CMS page on dotbooks | It overrides `{% block seo %}` with the legacy `{% seo_meta %}`, which bypasses `{% storefront_head %}`. |
| **motion** | Adds an opacity fade class to `<html>` and a press class to buttons, plus a skeleton class nobody uses (no template has `data-skeleton`). | Real but thin; settings are dead | **Delete** (move the few lines of CSS into the themes that want them) | `intensity` (including "off") and `reduced_motion_default` are read by nothing. The claimed "scroll-snap story progress" does not exist. The fade is applied from a deferred script, so it runs after content can already be painted. |
| **richtext** | Self-hosted Lexical editor bundle plus the `{% richtext_field %}` tag. Used by the admin_dashboard product form and the CMS page form. | Real infrastructure | **Merge into admin_dashboard (M7)**, beside the one media uploader | Nothing beyond the move; it works. |
| **rails** | Renders an **empty "Trending with shoppers like you" heading in every cart summary** and an **empty "Looks like you" heading on every checkout** on all four stores (confirmed by local render; the themes emit both slots). The `CuratedRail` model has no editor. Rows 0. | Stub that leaks visible markup | **Delete** (dynamics already does all of this) | The description claims five rails; two are contributed and both are empty. `recently_viewed.html` is never contributed. Its `requires` (personalisation, analytics, consent) are never used. |
| **dynamics** | The real merchandising engine: 13 strategies (smart, for you, related, bought-together, recently viewed, trending, best sellers, …), surface takeover of home/PLP lists, a bandit reranker, nightly propensity, and an AI-merchandiser proposal queue with a dashboard. 86 tests. Rows 4425/3398/1/102. | Real | **Keep as the target of merge M2** | **No Janus tools** although the merchant creates blocks and approves proposals here. Add `dynamics.list_blocks`, `create_block`, `update_block`, `approve_proposal` and `reject_proposal`. Its import from personalisation is undeclared in `requires` (`services.py:832`). |
| **personalisation** | Nightly co-purchase table (`CoPurchaseScore`, rows **0 on all four stores**) plus a `PRODUCT_LIST_REORDER` subscriber that reorders listings per visitor. The PDP block is retired. Its template tags `frequently_bought` and `pairs_with` are used nowhere. | Real signal code; its own surface is retired | **Merge into dynamics (M2)** | Dynamics already falls back to a live co-purchase scan, and it reorders the same PLP through a second seam right after this one (`storefront/views/catalog.py:251-258`). Missing the `has_models` flag. |
| **discovery_quiz** | Five models (Quiz, Question, Option, ResultTemplate, Submission) and one checkout block waiting for `result_template`. No quiz page, view, editor or tool. Rows 0. | Stub | **Delete** | "Skin type" example copy. Its `requires` (metafields, consent) are never used. |
| **ai_stylist** | Two models and a settings panel under Settings → AI with three inert fields (persona, welcome message, consent). The widget is deliberately not contributed (`app.py:36-44`). Active on 3 stores. | Stub (says so itself) | **Delete**; a shopper assistant should be a Janus door, not a second chat stack | The merchant sees AI settings that do nothing. |
| **drops** | `Drop`, `DropTicket` and `Waitlist` models plus a PDP block waiting for `drop_for_product`. No admin, view, JS, task or tool. Rows 0. | Stub | **Delete** | `Waitlist` is a parallel table to `inventory.BackInStockSubscription` (`inventory/models.py:118`). |
| **save_for_later** | Three models and a cart block. Off on all four stores (`enabled_by_default=False`). Rendered with a real cart, the "Save this" buttons get `data-product-id=""` and have no script or endpoint. Rows 0. | Stub | **Delete / merge the idea into wishlist (M5)** | `SharedWishlist` duplicates `Wishlist.share_token`. The back-in-stock feature duplicates inventory. |
| **wishlist** | Customer/guest wishlists: `/wishlist/` pages, sharing, a PDP "Save to wishlist" button, GDPR export/erase, 2 shopper tools. Rows 8/4/20/2. | Real | **Keep**; absorbs save_for_later (M5) | The button text is not translated (`save_button.html:6`). No merchant view or tool for "most-wished products". Empty `graphql/` package. |
| **trust_signals** | PDP strip: star rating (≥N reviews), verified-buyer %, "X ordered in last 72h". It works on the GraphQL dict. | Real, but **its settings are unreachable** and one signal can never show | **Merge into reviews (M4)** | The settings schema lacks the `properties` wrapper, so the panel renders zero fields (`app.py:51` vs `admin_dashboard/views_split/settings.py:47`). Verified share needs `is_verified_purchase`, which nothing ever sets. The CSS class `trust-strip` collides with dot_books' own hardcoded strip. |
| **reviews** | Storefront write form and endpoint for `catalog.Review`, the dashboard moderation list, an activity-feed entry and 3 tools (list pending, approve, delete). | Real | **Keep as the target of merge M4** | Reviews are auto-approved and never verified (see Notable problems). Book copy ("Loved it… Didn't connect", "What did you take from it?", "a reader"). Add a `reviews.reply` tool. The `models.py` docstring still says moderation is in catalog admin. |
| **ugc_reviews** | `ReviewMedia` and `CreatorInvite` models with no writer. Two blocks render **empty `<section>` wrappers on every PDP** (live on dotbooks `/products/a-princess-of-mars/`). Rows 0. | Stub that leaks markup | **Delete**; add photo reviews to reviews when built | It claims to use a `reviews.ugc_for_product` filter that does not exist. Its `requires` includes post_purchase, which is never used. |
| **advanced_ecommerce** | A 2026 demo "bundle". It contains: a featured-collection rails block (home), a recently-viewed rail (home), a **broken free-shipping bar** (cart), a low-stock badge (PDP), a dead `low_stock_view`, and a duplicate `product.viewed` session writer. `inventory/services.py:444-453` reads its `low_stock_threshold`. | Mixed: two real blocks, one broken, one dead | **Dissolve (M3)** | The free-shipping bar always says "Almost there — 40 USD unlocks free shipping" (see Notable problems). `views.py` has no `urls.py` behind it. The recently-viewed rail is N+1 (one query per slug). |
| **webstories** | Auto-generated AMP Web Story per product, `/stories/` index, PDP player embed, rebuilt on product and image save. 48 tests. Rows 861/587/17/21. | Real | **Keep** | No dashboard list and no tool to unpublish or rebuild a story; `is_published` is only reachable in the DB. Add `webstories.rebuild` and `webstories.set_published`. Missing the `has_models` flag. |
| **live_commerce** | Live-shopping events: dashboard CRUD, `/live/` and `/live/<slug>/`, home teaser, UTM links, status hooks (fired, no subscribers). 14 tests. Rows 0/0/0/0. | Real MVP, unused | **Keep, but opt-in** (out of `MORPHEUS_DEFAULT_APPS`) | Its storefront templates use Tailwind utilities that only the montenegro theme loads, so they are unstyled on the other three stores. An empty `/live/` answers `index, follow` (live on dotbooks and montenegro), which is a soft 404. No tools (`live.create_event`, `live.set_status`, `live.pin_product`). |

Outcome: 26 apps become **7** (product_gallery, media, dynamics, wishlist, reviews, webstories, live_commerce [opt-in]). Of the rest:
- 3 fold into apps outside the cluster: richtext → admin_dashboard, flipbook → digital_products, bookstore_3d → book_product.
- 16 are deleted or absorbed.

## Merges

Every model listed below has **0 rows on all four stores**, so no merge moves customer data. Two mechanics to respect:
- **Removing an app that has migrations** takes two releases: ship a `DeleteModel` migration in the app, deploy it, then drop the app from `MORPHEUS_DEFAULT_APPS`. Otherwise its tables stay as harmless orphans.
- **Moving a model** with its table intact uses the ADR 0034 pattern (`SeparateDatabaseAndState`, keep `db_table`), which changes no SQL.

1. **M1: fold product_videos, product_stories, immersive_pdp and media_3d into product_gallery** (one "product page media and content" app).
   - *Why:* they are four apps for one PDP surface. The hero slider already renders the videos and already `{% load product_videos %}`s.
   - *What moves:* `ProductVideo` (keep its `db_table`), `ProductStoryBlock` (keep its `db_table`), and the `stories.*` tool names (tool names are a stable API). The video CRUD moves from `admin_dashboard/views_split/products.py` into a `PRODUCT_FORM_CARDS` card in this app, which repays the `admin_dashboard→product_videos` and `storefront→product_videos` baseline pairs.
   - *What is deleted:* immersive_pdp and media_3d (never rendered, no data), plus `_carousel.html`, `_main_cover.html`, `_slider.html` and `pdp_videos.html`.
   - *Risk:* low. Keep the template path `product_gallery/_pdp_hero_slider.html` (three themes include it). Rename the `product_videos` template-tag library in the same change. Keep the `related_name`s `videos` and `story_blocks`.

2. **M2: fold personalisation, rails and discovery_quiz into dynamics** (one recommendation and ranking engine).
   - *Why:* dynamics already implements trending, recently viewed, bought-together and curated (manual and pinned) strategies, and it already calls personalisation's `related_to`. The PLP is reordered twice, by two seams in a row.
   - *What moves:* `CoPurchaseScore` (it already has an explicit `db_table='copurchase_score'`, so the move is zero-SQL); the nightly task, keeping its **registered name** `personalisation.recompute_copurchases` or updating the beat entry in the same change (the beat-name landmine); the `PRODUCT_LIST_REORDER` subscriber, merged with `_surface_reorder` into one ranking pass.
   - *What is deleted:* `CuratedRail`, the rails blocks (they render empty headings today), and all discovery_quiz models.
   - *Risk:* low to medium. Keep personalisation's consent gating exactly as it is. lookbook's and rails' `requires` on personalisation disappear with them.

3. **M3: dissolve advanced_ecommerce.**
   - *Low-stock badge* and `low_stock_threshold` move to **inventory**, which owns stock and already reads that setting. Copy each store's one config key in a data migration. Compute "Only N left" from `inventory.product_availability`, not a raw `StockLevel` sum.
   - *Free-shipping bar* is deleted: **shipping** already contributes a correct one in the same slot at the same priority (`shipping/app.py:163-175`).
   - *Recently viewed* and *featured-collection rails* become dynamics block presets, provisioned by migration so supernatural's home rail (`home.html:492`) does not vanish. Its duplicate `product.viewed` subscriber is dropped.
   - *Dead* `views.py` and `dashboard/low_stock.html` are deleted.
   - *Risk:* medium (home-page rails must be re-provisioned before removal).

4. **M4: fold trust_signals and ugc_reviews into reviews** (one "reviews and social proof" app).
   - *Why:* rating and verified share are review-derived. ugc_reviews is a stub layered on `catalog.Review`.
   - *What moves:* trust_signals' services, tag and template (no models). Fix the settings schema on the way.
   - *What is deleted:* `ReviewMedia` and `CreatorInvite` (0 rows). Re-add photo reviews inside reviews when they are actually built.
   - *Risk:* low. The order-derived "recent purchases" signal can live in reviews as social proof, or move to orders.

5. **M5: fold save_for_later into wishlist.**
   - *Why:* it is off everywhere and a stub, `SharedWishlist` duplicates `Wishlist.share_token`, and back-in-stock duplicates inventory.
   - *What moves:* nothing. Delete the 3 models. If wanted, build "move from cart to saved" and price-drop alerts inside wishlist.
   - *Risk:* none.

6. **M6: take the book vertical out of the defaults.**
   - **flipbook moves into digital_products**, which owns the protected digital file and its download tokens; the preview must come from the owner of the access rules.
   - **bookstore_3d moves into book_product**, which is already opt-out on non-book stores.
   - **lumina is deleted** from the platform and recreated as a CMS page on dotbooks. It is one store's marketing copy, with that store's domain hardcoded.
   - *Risk:* montenegro loses "Write a book" and "3D store", which is the fix. Create dotbooks' `/create/` CMS page before removing lumina.

7. **M7: fold richtext into admin_dashboard.**
   - *Why:* it is a dashboard form widget used only by the product and CMS-page forms. The dashboard's one media uploader already lives there by convention.
   - *What moves:* the static bundle and template tag. No models.
   - *Risk:* low; update static paths and move `test_bundle_current`.

8. **M8 (cross-cluster): move `brand_kit.Asset` into `media.MediaAsset`** as a kind or tag.
   - *Why:* it is a second asset table next to the asset manager (brand_kit already `requires` media).
   - *Rows:* 0.
   - *Risk:* low.

**Delete outright** (all 0 rows on all four stores): media_3d, lookbook, motion, ai_stylist, drops, discovery_quiz, rails, ugc_reviews, save_for_later, immersive_pdp, lumina. Most are covered in the merges above.

**Out of the default list (opt-in):** live_commerce, plus flipbook and bookstore_3d through the book vertical.

## Notable problems

1. **flipbook publishes the paid PDF.**
   - `flipbook/views.py:44-47` puts `product.digital_file.url` into the page, and `reader.html:121` exposes it as `const SRC`. `max_preview_pages` limits only client-side rendering.
   - Live: `https://dotbooks.store/p/a-princess-of-mars/flipbook/` names `/media/digital/a-princess-of-mars_dotbooks_digital_edition.pdf`, which answers **200 `application/pdf`, 424 KB, no auth**. The product sells for $8.
   - This title is public-domain, but the same path applies to every digital product, which digital_products otherwise gates behind download tokens.
   - The CTA condition (`_flipbook_cta.html:2`) reads snake_case keys that the GraphQL dict does not have, then falls through to `product.variants`. So it shows on any product with a variant, and the page 404s unless a PDF exists.
2. **The free-shipping bar is a false promise on every cart.**
   - `advanced_ecommerce/.../free_shipping_progress.html:6` compares `cart.subtotal`, which is a `{amount, currency}` dict, with a number. The comparison fails, so the bar always reads "Almost there — 40 USD unlocks free shipping", even at a 100 USD subtotal (local render). `widthratio` (line 15) yields an empty width.
   - The 40 USD default (`app.py:152-162`) is not read from shipping's `free_over` rate. On montenegro it is USD on a € store selling bookings.
   - shipping's own bar sits in the same slot, so a configured store can show both.
   - Related, outside this cluster: dot_books hardcodes "Free shipping over $40" (`product_detail.html:409`, `cart.html:86`), and montenegro hardcodes "Free shipping over €40." (`cart.html:115`).
3. **Empty markup on every page.**
   - rails: `trending_with_you.html:2` puts an empty "Trending with shoppers like you" `<h2>` in every cart summary, and `looks_like_you.html:2` puts an empty "Looks like you" `<h2>` on every checkout.
   - ugc_reviews: `ugc_gallery.html:1` and `ugc_highlights.html:1` render two empty sections on every PDP (live on dotbooks).
4. **Blocks that can never render on a real PDP**, because the PDP passes `product` as a GraphQL dict (`storefront/views/catalog.py:468-469, 658`) and never passes `variants`:
   - `product_gallery/_slider.html:15` (`product.images.all`)
   - `product_videos/blocks/pdp_videos.html:3` (`product.videos.all`)
   - `immersive_pdp/blocks/sticky_buybox.html:3` (`variants`)
   - Blocks waiting for context nothing supplies: `media_3d/blocks/viewer.html:1`, `lookbook/blocks/in_this_look.html:1`, `drops/blocks/drop_indicator.html:1`, `discovery_quiz/blocks/personalised_results.html:1`.
   - The immersive_pdp test (`tests/test_buybox.py:24`) supplies `variants` itself, so it passes while the real page never shows the bar.
5. **Book apps on the travel store (live).** montenegro-experience.me's footer links "Write a book" (`/create/`, which pitches "sell it on dot books") and "3D store" (`/walkthrough/`). Both apps are default and active there; nothing ties them to the book bundle that `MORPHEUS_DISABLED_APPS` removes.
6. **trust_signals settings are unreachable.**
   - `trust_signals/app.py:51` passes the properties without the `{'type':'object','properties':…}` wrapper, and the renderer iterates `schema.get('properties')` (`admin_dashboard/views_split/settings.py:47`). The panel therefore shows zero fields, and all six knobs keep their defaults.
   - Nothing ever sets `catalog.Review.is_verified_purchase` (`catalog/models.py:752`), so "% verified buyers" can never appear.
7. **Reviews make a public claim without evidence.**
   - `reviews/views.py:32` auto-approves any signed-in account's review; signup does not verify the email.
   - Approved reviews feed `aggregateRating` (`seo/services/jsonld.py:549`). This is the evidence-free rating claim that the booking_marketplace landmine forbids.
   - Fix: hold unverified reviews for moderation, and set `is_verified_purchase` from a paid order at submit time.
8. **Dead settings that pass the readers guard.** `test_settings_keys_have_readers` accepts a bare word in a template, so these keys look "read" while nothing reads them:
   - `motion`: `styles.html:2-3` writes `intensity` and `reduced_motion_default` into data attributes no CSS or JS reads.
   - `media_3d`: `viewer.html:4`, `shoppable_video.html:6`.
   - `ai_stylist`: `widget.html:3-5`, in a template that is not even contributed.
   - The storefront has no `settings` context variable, so every `{{ settings.x }}` above is empty.
   - Also unread: `rails.require_consent` and `discovery_quiz.require_consent`.
9. **Undeclared hard dependencies.**
   - `_pdp_hero_slider.html:1` does `{% load product_videos %}`, but product_gallery's `requires=['catalog']`. Removing product_videos via `MORPHEUS_DISABLED_APPS` would make every PDP on dot_books, supernatural and irving raise a template error.
   - The three themes include `product_gallery/_pdp_hero_slider.html` directly (e.g. `dot_books/.../product_detail.html:294`), so a runtime disable of product_gallery removes nothing (litmus test 2).
   - `dynamics/services.py:832` imports personalisation without declaring it.
10. **Phantom `requires`.** These declared requirements are never used, but disabling the target logs a boot ERROR forever: lookbook→personalisation, rails→personalisation/analytics/consent, ugc_reviews→post_purchase, drops→pwa/inventory, discovery_quiz→metafields.
11. **Misleading manifests.**
    - `product_videos/app.py:15` says "Edit via Django admin"; the editor is in admin_dashboard.
    - `media_3d/app.py:10-11` claims a GraphQL extension that does not exist.
    - `rails/app.py:28` claims five rails.
    - `lookbook/app.py:3-10` claims a cart line and an "AI auto-look".
    - `ugc_reviews/app.py:13-16` names a nonexistent `reviews.ugc_for_product` filter.
    - `advanced_ecommerce/app.py:107-114` says "the underlying URLs still exist"; there is no `urls.py`.
    - `motion/app.py:7` claims "scroll-snap story progress".
12. **Two writers, one concept.**
    - Two `product.viewed` subscribers write the same `session['recently_viewed']` (`advanced_ecommerce/app.py:58`, `dynamics/app.py:126`).
    - Two per-visitor reorder seams run back to back on the PLP (`storefront/views/catalog.py:251-258`).
    - Parallel tables: `drops.Waitlist` beside `inventory.BackInStockSubscription`; `lookbook.Look` beside `catalog.Collection`; `save_for_later.SharedWishlist` beside `Wishlist.share_token`; `brand_kit.Asset` beside `media.MediaAsset`.
13. **Tests that never run.** media_3d, rails, discovery_quiz, ai_stylist, drops, save_for_later and ugc_reviews keep pytest-style functions in `tests/__init__.py`, which the Django runner does not collect. They are in the plugin-standard baseline as `tests.missing`; product_videos has no tests at all.
14. **live_commerce on non-Tailwind themes.** `list.html`, `event.html` and `upcoming_teaser.html` use Tailwind utilities that only the montenegro theme loads. The empty `/live/` index answers `index, follow`.
15. **Missing Janus tools for merchant actions** (the CLAUDE.md rule):
    - dynamics: blocks and proposals (0 tools for the cluster's most-used app)
    - webstories: publish and rebuild
    - live_commerce: events
    - product videos: add and remove
    - media: alt text and upload
    - reviews: reply
    - product_stories: update and delete
