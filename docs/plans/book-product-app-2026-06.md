# Book Product app (product-type extension)

> A `book_product` plugin that turns a catalog Product into a rich book:
> physical attributes (author, print/paper type, page count, …) on a real
> model, a 3D cover-PDF viewer (three.js), the existing live preview, a
> `Settings → Product Types` page, and a dashboard product-edit widget.
> Goal set by the user 2026-06.

## Decisions (autonomous — recorded, not asked)
1. **Dedicated `BookProduct` model**, OneToOne → `catalog.Product`
   (`related_name='book'`). Stronger schema + queryability than loose
   metafields, and the goal explicitly wants book fields "put here" instead of
   meta tags. `has_models = True`, `requires = ['catalog']`.
2. **Move book *attributes* off metafields into the model**: `book.author`,
   `book.pages`, `book.publisher`, `book.synopsis` → model columns, via a data
   migration (don't lose live data). **ISBN/EAN/GTIN identifiers STAY** in the
   `identifiers` metafield namespace (recent feature b11f369, semantically
   "identifiers" not "book attributes") — `BookProduct` cross-references them.
3. **3D preview = cover PDF → three.js**. `cover_pdf` FileField on the model.
   Render PDF page 1 to a canvas via PDF.js, use as the front-cover texture on
   a box-geometry "book", OrbitControls for drag/rotate. three.js + pdf.js via
   esm.sh (no bundler — matches the dashboard's TipTap/esm.sh pattern). Same
   viewer component used in the dashboard widget AND the storefront PDP block.
4. **"Live preview" — reuse, don't move flipbook.** The existing `flipbook`
   plugin already renders a PDF page-flip preview from `Product.digital_file`.
   Physically moving its code would break a shipped plugin. Instead the book
   widget/PDP *surfaces* the preview (link/CTA) alongside the new 3D viewer.
   (If the user really wants flipbook folded in, that's a later phase.)
5. **Product-edit widget = Option A (pragmatic)**, mirroring the bookvault /
   product_videos pattern already in `product_edit()`: a guarded data-fetch in
   the view + a conditional "Book details" card in `product_form.html`. A
   formal `contribute_product_panels()` hook (Option B) is the cleaner
   long-term framework but is a separate architecture task — noted, not in MVP.
6. **`Settings → Product Types`** = a new `SettingsCategory('product_types', …)`
   + a `SettingsPanel(category='product_types')` from this plugin (defaults:
   default print/paper type, enable-3D-preview toggle). Product *types*
   themselves stay model choices; this page configures the book type's defaults.

## Where it integrates (from the system map)
- Product model + types: `catalog/models.py:164-183` (`product_type` choices).
- Book data today (to migrate): metafields ns `book` (`book.author`,
  `book.pages`, `book.publisher`, `book.synopsis`) + identifiers ns
  (`identifiers.isbn13` etc., `metafields/identifiers.py`). Stay: identifiers.
- Product-edit view/template (widget host): `admin_dashboard/views_split/products.py:305-402`
  + `templates/admin_dashboard/product_form.html` (bookvault card is the pattern).
- Settings category list: `admin_dashboard/settings_categories.py:23-35`.
- Cover/PDF storage: `Product.digital_file` (FileField), `ProductImage` (covers).
- Storefront PDP: `themes/library/dot_books/templates/storefront/product_detail.html`
  (slots `pdp_below_price`, `pdp_below_form`); flipbook already uses `pdp_below_form`.
- Plugin registration: `MORPHEUS_DEFAULT_APPS` in `morph/settings.py`.
- three.js: not yet vendored; load `https://esm.sh/three` + `pdfjs-dist` in a
  `<script type=module>` (dashboard + storefront both vanilla-JS).

## Phases (each shippable + verifiable)
1. **Scaffold + model.** plugin-skeleton → `book_product`: apps.py, app.py,
   `BookProduct` model (author, subtitle, contributors json, publisher,
   imprint, publication_date, edition, language, print_type[choices],
   paper_type[choices], binding, page_count, dimensions_mm, weight_g,
   cover_pdf FileField, synopsis, series, series_position), migration,
   register in MORPHEUS_DEFAULT_APPS. Verify: system check + migrate clean.
2. **Product Types settings.** Add the category + a settings panel (defaults).
   Verify: `/dashboard/settings/product_types/` renders.
3. **Data migration.** Copy `book.*` metafields → BookProduct rows (idempotent,
   fail-soft). Verify: a product with book.author metafield gets a BookProduct.
4. **Dashboard widget.** "Book details" card on the product-edit page (Option A)
   — fields + cover-PDF upload + save (data-ajax JSON contract). Verify: edit a
   product, fields persist.
5. **3D viewer.** Reusable `_book_3d.html` partial: three.js box + PDF.js cover
   texture + OrbitControls. Mount in the dashboard widget (preview) AND a
   storefront PDP block. Verify: cover PDF renders as a draggable 3D book.
6. **Storefront + meta cleanup.** Book-details block on the PDP sourced from the
   model; switch book schema.org/meta emission to read the model; stop writing
   the migrated `book.*` metafields. Verify: PDP shows author/pages/etc.
7. **Tests + docs.** Model, data-migration, settings, widget-save, context.
   PLUGIN_DEVELOPMENT note. Update torsor.

## Landmines / rules
- Every model ships its migration in the same commit (prod boot check).
- Data migration must be idempotent + fail-soft (re-runnable, never crashes boot).
- Dashboard `data-ajax` save must return JSON on success AND failure.
- Disable test: disabling `book_product` must remove the widget + PDP block + the
  Product Types panel — contribute, never hard-edit (the widget is the one
  pragmatic exception, guarded by a plugin-enabled check like bookvault).
- Don't break `flipbook` or the `identifiers` metafields feature.
- three.js/PDF.js are CDN ESM — fail-soft if the script fails (no white screen).

## Status log
- 2026-06: spec written; system mapped.
- 2026-06: **P1+P2** (51de7af) — plugin + BookProduct model + migration + register
  + Settings → Product Types category & Books panel. System check clean.
- 2026-06: **P3** (24197fc) — idempotent fail-soft data migration book.* metafields
  → model columns.
- 2026-06: **P4** (book widget) — "Book details" card on the product-edit page
  (book_product.dashboard.book_widget_context + save_book_fields, guarded).
- 2026-06: **P5** (586b9c7) — three.js 3D cover-PDF viewer (_book_3d.html) mounted
  in the dashboard widget; dashboard CSP widened minimally (unpkg connect/worker).
- 2026-06: **P6** — storefront PDP block (_book_pdp.html) shows book details + the
  3D viewer; book_for_product template tag resolves the BookProduct from the
  GraphQL product dict. contribute_storefront_blocks → pdp_below_form.
- **Decision: bookstore_3d is a separate "walkthrough" plugin** (not the per-book
  viewer); flipbook is left intact (we surface, don't move it). Per goal note 4.
- **Deferred (P6b, follow-up): meta-tag removal.** The goal's "maybe remove meta
  tags" is tentative + riskier (touches SEO schema emission). Data already lives
  on the model; the `book.*` metafields remain harmless for now. Switch book
  schema.org/meta to read the model + stop writing book.* in a focused later pass.
- 2026-06: **Full-bleed mega menu + Authors dropdown** (29f4439) — Genres panel
  full-width; new Authors mega from nav_authors (book.author metafields →
  /author/<slug>/). (Also fixed the live mega/drawer overflow regression.)
- 2026-06: **P8 GraphQL + P6b PDP-from-model** (2205e28) — bookProduct query +
  setBookProduct mutation (catalog.write scope); PDP `_book_specs` reads the
  BookProduct model first (metafield fallback); PDP plugin block trimmed to the
  3D viewer. Schema build verified; 4 GraphQL tests pass.
- 2026-06: **ADR 0006** records the product-type-extension pattern (plugin-owned
  OneToOne + contributed surfaces, no catalog edits).
- **GOAL COMPLETE.** Remaining = noted follow-ups (retire book.* metafields once
  author_detail/PLP filters move to the model; optional contribute_product_panels
  hook). Live Playwright verification of book widget/3D pending a real prod book.
