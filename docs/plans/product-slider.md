# Spec — Product slider, video slides, and image defaults

> Draft. Pillar 1 — write the plan before the code. Update this file
> as the implementation diverges from the original intent; do not let
> the doc and the code drift apart.

## 1. Project Overview

- **Name:** Product slider (catalog gallery v2)
- **Goal:** Replace the single-cover hero on the storefront PDP with
  a horizontal slider that shows multiple portrait images, optional
  video slides (uploaded mp4/webm or embedded YouTube/Vimeo), and —
  for digital products — optional auto-rendered PDF interior pages.
  Add a store-wide image defaults panel so the merchant picks the
  format + sizes used everywhere on the storefront.
- **Target users:** Merchants selling books (the dominant case),
  apparel, and any other product where customers want to see more
  than one angle before buying. External agents that publish products
  via MCP / GraphQL also benefit (more slots to populate via
  `addProductImage`).
- **Why now:** The current dashboard already supports a "front cover
  / back cover" two-slot pattern (commit 1368559) but the storefront
  PDP only renders the single primary image. Customers viewing a
  book on dotbooks.store can't see the back cover, interior pages, or
  any merchant-uploaded extras. This is the biggest visible gap on
  the live shop right now.

## 2. Tech Stack & Dependencies

- **Language:** Python 3.12, JS (vanilla, no framework)
- **Framework:** Django + Strawberry GraphQL
- **Styling:** Tailwind (CDN) + storefront theme's CSS variables
- **Database:** Postgres (via pgbouncer)
- **Test runner:** pytest
- **Package manager:** poetry-managed (`requirements*.txt` flat files)
- **Key libraries:**
  - **Pillow** — already vendored; image resize + format conversion.
  - **pypdfium2** (or `pdf2image`) — render a PDF page to a JPEG. New
    dep for the auto-pages feature. Slopsquat-check: pypdfium2 is on
    PyPI, maintained by `bblanchon`, currently 4.x. We'd pin
    `pypdfium2>=4.30,<5`. (Verify before committing.)
  - **Existing:** `product_gallery` plugin (slot contributions),
    `product_videos` plugin (video model — repurpose for embed URLs).

## 3. Data Models / Schemas

### 3.1 Reuse existing tables, extend where needed

- **`catalog.ProductImage`** — already has the right shape:
  `image`, `webp_image`, `alt_text`, `is_primary`, `sort_order`.
  Cap at 15 slots per product. No schema change.
- **`product_videos.ProductVideo`** — currently only does uploaded
  mp4. Add:
  - `embed_url` (URLField, blank=True) — YouTube/Vimeo URL.
  - `provider` (CharField, choices=['upload', 'youtube', 'vimeo']).
  - `poster_image` (ImageField, blank=True) — for the slider
    placeholder before the user clicks play.
  Migration required.

### 3.2 New: PDF-page rendering opt-in (per product)

- **New field on `catalog.Product`** (or a new
  `catalog.ProductImageSettings` 1-1 if we want to keep `Product`
  thin):
  - `auto_render_pdf_pages` (CharField, choices=['off', 'replace', 'append'],
    default='off')
    - `off`: only manually-uploaded images appear.
    - `replace`: ignore manual images; show first N PDF pages.
    - `append`: show manual images first, then PDF pages.
  - `pdf_pages_to_render` (PositiveIntegerField, default=5,
    validators=[MinValueValidator(1), MaxValueValidator(15)]).
  Migration required.

### 3.3 New: store-wide image defaults

- **`storefront.SiteSettings`** (or a new
  `catalog.ImageDefaultsPanel`) — a `SettingsPanel`-style schema on
  the storefront plugin, no model change. Persisted in
  `PluginConfig['catalog']`:
  - `default_image_format`: 'webp' | 'avif' | 'jpg' (default 'webp')
  - `pdp_image_width`: int (default 800, range 400-1600)
  - `pdp_image_height`: int (default 1200, range 600-2400) — portrait
    aspect for books; merchant can flatten by setting equal values.
  - `grid_image_width`: int (default 400)
  - `grid_image_height`: int (default 600)
  - `og_image_width`: int (default 1200) — for OG / social
  - `lazy_load`: bool (default True) — adds `loading="lazy"` below the fold.
  - `enable_avif`: bool (default False) — opt-in, AVIF still flaky on
    older Safari.

### 3.4 Derived assets — `ProductImage` variants

Today the model stores `image` + `webp_image`. To support multiple
sizes + formats without forking the model:
- Add `variants` (JSONField, default=dict):
  `{"pdp": {"webp": "products/variants/<id>_pdp.webp", "jpg": "..."},
    "grid": {"webp": "...", "jpg": "..."}}`
- Pre-generate the variants at upload time (Pillow). Storefront looks
  up the right key by slot.
- For on-demand resizing (a custom width / a one-off ad campaign),
  add `/media/r/<image_id>/?w=600&fmt=webp` — a thumbnailer view
  that generates + caches the variant.

## 4. Key Features & Acceptance Criteria

### Phase 1 — vertical slice (this PR)

- [ ] **Storefront slider on PDP**
  - Replaces the single hero image with a horizontal carousel
    showing all `ProductImage` rows ordered by `sort_order`.
  - Left/right arrows + swipe on touch. Thumbnail strip below as
    a quick jump.
  - *Acceptance:* On a product with 3+ images, the storefront PDP
    shows the slider with all images reachable via arrows + dots;
    clicking a thumbnail jumps to that slide.

- [ ] **Backend uploads up to 15 portrait images**
  - Drag-and-drop into a 15-slot grid on `/dashboard/products/<id>/`.
  - Reorder by dragging slots. `sort_order` persists.
  - Slot 0 is the primary (`is_primary=True`) — drives the OG image
    + storefront grid thumbnail.
  - *Acceptance:* On a fresh product, drag 5 images in; reload;
    they appear in the same order on storefront PDP.

- [ ] **No regression on existing two-slot cover UI**
  - The hardcoded "front cover / back cover" pattern still works for
    products that only have 1-2 images; the new slider just adapts.

### Phase 2 — video slides (separate PR)

- [ ] **Video slides** — both uploaded files AND embed URLs
  - Backend: same 15-slot grid but slots can be video kind. Field
    distinguishes upload vs embed URL.
  - Storefront: slider auto-detects the slide type and renders
    `<video>` (upload) or `<iframe>` (embed). Poster image shown
    until the user clicks play.
  - *Acceptance:* A product with 1 image + 1 YouTube embed + 1 mp4
    upload renders all three on the slider in order; play controls
    work; audio doesn't auto-start.

### Phase 3 — auto-render PDF pages (separate PR)

- [ ] **Per-product PDF page rendering toggle**
  - On the product edit page: 3-option select (off / replace /
    append) + N pages slider (1-15).
  - On save (or via a Celery task if PDF > 5 MB), render the chosen
    pages to portrait JPEGs and store them as `ProductImage` rows
    flagged `source='pdf'` so future reruns can replace them
    cleanly.
  - *Acceptance:* On a digital product with `auto_render_pdf_pages=append`
    and 3 pages, after save the slider shows manual images first
    then the first 3 PDF pages.

### Phase 4 — image defaults panel (separate PR)

- [ ] **Settings → General → Image defaults**
  - Form with format / size / lazy-load / AVIF fields.
  - On save, queue a background re-encode of existing images that
    don't have the new variant.
  - *Acceptance:* Setting `default_image_format=avif` regenerates
    AVIF variants for every existing image; storefront PDP serves
    `.avif` (with `<picture>` + `<source type="image/webp">`
    fallback).

## 5. Architectural Constraints

- **Slider must work without JS.** Fallback: render every slide
  vertically stacked. Critical because product PDPs are SEO targets
  and crawlers don't always run JS. Achieve via CSS scroll-snap
  + a tiny JS layer for arrows.
- **Mobile-first.** Slider takes the full viewport width on
  ≤ 768 px; thumbnail strip becomes dots; videos respect
  `prefers-reduced-motion`.
- **No new heavyweight JS libs.** No Swiper, no Glide. Hand-rolled
  HTML/CSS + ~80 lines of JS.
- **`enctype="multipart/form-data"`** stays on the product form;
  the existing `Morph.ajaxForm` helper handles file uploads via
  `FormData()`.

## 6. Non-Functional Requirements

- **Performance:** PDP LCP < 1.5 s on the slowest slide
  (uploaded mp4 with poster). Image variants pre-generated; AVIF
  optional.
- **Reliability:** Failed variant generation must not block the
  upload — the original always saves; variants are best-effort
  with a retry queue.
- **Accessibility:** WCAG 2.2 AA. Arrows are real `<button>`s with
  `aria-label`; thumbnails have `aria-controls`; video `<iframe>`s
  have `title`.
- **Internationalization:** Captions/alt text honour
  `Product.localized_translations`.

## 7. Security & Privacy

- **HTTPS-only embed URL validation.** YouTube and Vimeo URLs must
  match an allowlist of hosts; arbitrary iframe sources rejected.
- **MIME sniff** on uploaded videos: reject anything that isn't
  `video/mp4` / `video/webm`. 100 MB cap per slide.
- **Per-product DoS guard:** auto-PDF rendering capped at 15 pages,
  files > 50 MB queued through Celery (don't block the request).

## 8. Observability

- Log every variant generation: image id, source size, destination
  size, format, duration. Sample at 10% to keep volume sane.
- Add a Pulse card: "N products with broken or missing image
  variants" so the merchant can spot stale assets after a settings
  change.

## 9. Rollout

- Phase 1 ships behind no flag — it's a strict UX improvement on a
  page that already has images.
- Phase 2 + 3 + 4 each ship as separate PRs and each behind a
  feature flag in the storefront plugin
  (`enable_video_slides`, `enable_pdf_page_render`,
  `enable_avif_default`). Default OFF; merchant flips per store.

## 10. Open questions

- Should the slider hero ALSO replace the small cover-slot UI in
  the dashboard, or do we keep the two-slot front/back convention
  as a "quick edit" shortcut and the 15-slot grid as the full
  editor? Recommendation: keep both — front/back is a 2-second
  edit; the full grid is the deep edit. The slot UI just becomes a
  read-out of slots 0 + 1 from the grid.
- For embedded YouTube/Vimeo — do we honour the merchant's chosen
  privacy mode (`youtube-nocookie.com`)? Default yes.
- Variant generation: Celery task or inline? Inline for the first
  3 images (PDP + grid + OG); rest deferred to Celery. (Decision:
  pre-generate the 3 hot variants at upload time; defer extras.)

## 11. Out of scope

- 360° spin gallery (separate plugin if/when).
- AR / VR preview.
- Per-variant images (each ProductVariant having its own slider) —
  Phase 5 maybe.
