---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/installed/admin_dashboard/forms/products.py

Symbols in `plugins/installed/admin_dashboard/forms/products.py`.

- L20 `_currency_of(product)` (function) — The currency a product's prices are kept in: its own, or the store's for a new one.
- L30 `ProductForm` (class) — Create/edit a `catalog.Product`. Variants/images live in their own flows.
- L120 `_is_service(self)` (method)
- L123 `__init__(self, *args, instance=None, **kwargs)` (method)
- L167 `clean_structured_data(self)` (method)
- L181 `clean_sku(self)` (method)
- L194 `clean_slug(self)` (method)
- L207 `clean(self)` (method) — Variable products: per-variant price/weight/shipping is canonical.
- L224 `save(self)` (method)
- L318 `VariantForm` (class) — Create/edit a `catalog.ProductVariant` for a given product.
- L392 `__init__(self, *args, instance=None, product=None, **kwargs)` (method)
- L418 `clean_sku(self)` (method)
- L429 `clean(self)` (method)
- L439 `save(self)` (method)
