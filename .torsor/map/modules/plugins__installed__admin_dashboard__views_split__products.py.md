---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/admin_dashboard/views_split/products.py

Symbols in `plugins/installed/admin_dashboard/views_split/products.py`.

- L57 `products_list(request: HttpRequest)` (function)
- L124 `_storefront_base()` (function) — The site's public root, as configured in settings — not a placeholder.
- L138 `_product_form_choices()` (function) — Categories (tree-ordered) + vendors for the product form selects.
- L152 `_ordered_categories()` (function) — Return active categories in parent→child tree order, each tagged
- L189 `product_new(request: HttpRequest)` (function)
- L228 `_save_product_identifiers(product, post)` (function) — Persist the product-identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) from
- L266 `_identifier_fields(product)` (function) — ``[{key, label, placeholder, value}]`` for the editor's codes card.
- L287 `_collect_product_form_cards(product, request)` (function) — Render plugin-contributed product-form cards (PRODUCT_FORM_CARDS filter).
- L317 `_fire_product_form_saved(product, request)` (function) — Let plugins persist their own product-form fields (their contributed
- L331 `_collect_product_list_columns(products, request)` (function) — Render plugin-contributed product-list columns (PRODUCT_LIST_COLUMNS filter).
- L367 `product_edit(request: HttpRequest, product_id: str)` (function)
- L446 `product_delete(request: HttpRequest, product_id: str)` (function)
- L460 `product_archive(request: HttpRequest, product_id: str)` (function) — Soft-archive (or restore) a product — flips status between
- L483 `_get_product(product_id: str)` (function)
- L489 `_require_product_videos()` (function) — The video CRUD endpoints belong to the optional product_videos plugin:
- L501 `variant_new(request: HttpRequest, product_id: str)` (function)
- L531 `variant_edit(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L560 `variant_delete(request: HttpRequest, product_id: str, variant_id: str)` (function)
- L576 `image_upload(request: HttpRequest, product_id: str)` (function) — POST-only: accept a multipart upload, attach to product.
- L673 `image_delete(request: HttpRequest, product_id: str, image_id: str)` (function)
- L686 `image_reorder(request: HttpRequest, product_id: str)` (function) — Persist new sort_order for a product's images.
- L732 `video_add(request: HttpRequest, product_id: str)` (function) — Attach a video (YouTube/Vimeo URL, direct mp4, or raw iframe)
- L773 `video_delete(request: HttpRequest, product_id: str, video_id: str)` (function)
- L789 `image_edit(request: HttpRequest, product_id: str, image_id: str)` (function) — Inline metadata edit for a ProductImage — alt_text + description.
- L810 `video_edit(request: HttpRequest, product_id: str, video_id: str)` (function) — Inline metadata edit for a ProductVideo — title + poster_url.
- L835 `image_set_primary(request: HttpRequest, product_id: str, image_id: str)` (function)
- L866 `products_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the products list page.
- L908 `_content_audit_queryset()` (function) — Return products missing any of: short_description, description, category.
- L926 `content_audit_card(request)` (function) — The Content audit card on the Products landing (admin_dashboard/cards.py):
- L946 `content_audit(request: HttpRequest)` (function) — List every product missing copy or categorization.
- L987 `content_fill_one(request: HttpRequest, product_id: str)` (function) — Generate missing short + long descriptions for ONE product via the LLM.
