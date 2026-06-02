---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/admin_dashboard/views_split/products.py

Symbols in `plugins/installed/admin_dashboard/views_split/products.py`.

- L52 `products_list(request: HttpRequest)` (function)
- L123 `_product_form_choices()` (function) — Categories (tree-ordered) + vendors for the product form selects.
- L137 `_ordered_categories()` (function) — Return active categories in parent→child tree order, each tagged
- L172 `_seo_field_defaults(product)` (function) — Resolved SEO values the storefront would render for this product
- L215 `product_new(request: HttpRequest)` (function)
- L245 `product_edit(request: HttpRequest, product_id: str)` (function)
- L342 `product_delete(request: HttpRequest, product_id: str)` (function)
- L355 `product_archive(request: HttpRequest, product_id: str)` (function) — Soft-archive (or restore) a product — flips status between
- L378 `_get_product(product_id: str)` (function)
- L385 `variant_new(request: HttpRequest, product_id: str)` (function)
- L412 `variant_edit(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L438 `variant_delete(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L453 `image_upload(request: HttpRequest, product_id: str)` (function) — POST-only: accept a multipart upload, attach to product.
- L540 `image_delete(request: HttpRequest, product_id: str, image_id: str)` (function)
- L552 `image_reorder(request: HttpRequest, product_id: str)` (function) — Persist new sort_order for a product's images.
- L597 `video_add(request: HttpRequest, product_id: str)` (function) — Attach a video (YouTube/Vimeo URL, direct mp4, or raw iframe)
- L640 `video_delete(request: HttpRequest, product_id: str, video_id: str)` (function)
- L656 `image_edit(request: HttpRequest, product_id: str, image_id: str)` (function) — Inline metadata edit for a ProductImage — alt_text + description.
- L677 `video_edit(request: HttpRequest, product_id: str, video_id: str)` (function) — Inline metadata edit for a ProductVideo — title + poster_url.
- L703 `image_set_primary(request: HttpRequest, product_id: str, image_id: str)` (function)
- L734 `products_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the products list page.
- L771 `_content_audit_queryset()` (function) — Return products missing any of: short_description, description, category.
- L790 `content_audit(request: HttpRequest)` (function) — List every product missing copy or categorization.
- L831 `content_fill_one(request: HttpRequest, product_id: str)` (function) — Generate missing short + long descriptions for ONE product via the LLM.
