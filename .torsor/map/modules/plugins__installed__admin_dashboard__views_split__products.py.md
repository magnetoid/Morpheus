---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/admin_dashboard/views_split/products.py

Symbols in `plugins/installed/admin_dashboard/views_split/products.py`.

- L52 `products_list(request: HttpRequest)` (function)
- L123 `_product_form_choices()` (function) — Categories (tree-ordered) + vendors for the product form selects.
- L137 `_ordered_categories()` (function) — Return active categories in parent→child tree order, each tagged
- L172 `_seo_field_defaults(product)` (function) — Resolved SEO values the storefront would render for this product
- L215 `product_new(request: HttpRequest)` (function)
- L244 `_save_product_identifiers(product, post)` (function) — Persist the product-identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) from
- L278 `_identifier_fields(product)` (function) — ``[{key, label, placeholder, value}]`` for the editor's codes card.
- L295 `_seo_tokens(product)` (function) — ``[{token, label}]`` for the SEO title/description "Insert field" menu.
- L305 `_collect_product_form_cards(product, request)` (function) — Render plugin-contributed product-form cards (PRODUCT_FORM_CARDS filter).
- L334 `product_edit(request: HttpRequest, product_id: str)` (function)
- L465 `product_delete(request: HttpRequest, product_id: str)` (function)
- L478 `product_archive(request: HttpRequest, product_id: str)` (function) — Soft-archive (or restore) a product — flips status between
- L501 `_get_product(product_id: str)` (function)
- L508 `variant_new(request: HttpRequest, product_id: str)` (function)
- L535 `variant_edit(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L561 `variant_delete(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L576 `image_upload(request: HttpRequest, product_id: str)` (function) — POST-only: accept a multipart upload, attach to product.
- L663 `image_delete(request: HttpRequest, product_id: str, image_id: str)` (function)
- L675 `image_reorder(request: HttpRequest, product_id: str)` (function) — Persist new sort_order for a product's images.
- L720 `video_add(request: HttpRequest, product_id: str)` (function) — Attach a video (YouTube/Vimeo URL, direct mp4, or raw iframe)
- L763 `video_delete(request: HttpRequest, product_id: str, video_id: str)` (function)
- L779 `image_edit(request: HttpRequest, product_id: str, image_id: str)` (function) — Inline metadata edit for a ProductImage — alt_text + description.
- L800 `video_edit(request: HttpRequest, product_id: str, video_id: str)` (function) — Inline metadata edit for a ProductVideo — title + poster_url.
- L826 `image_set_primary(request: HttpRequest, product_id: str, image_id: str)` (function)
- L857 `products_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the products list page.
- L894 `_content_audit_queryset()` (function) — Return products missing any of: short_description, description, category.
- L913 `content_audit(request: HttpRequest)` (function) — List every product missing copy or categorization.
- L954 `content_fill_one(request: HttpRequest, product_id: str)` (function) — Generate missing short + long descriptions for ONE product via the LLM.
