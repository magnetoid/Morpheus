---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/admin_dashboard/forms/products.py

Symbols in `plugins/installed/admin_dashboard/forms/products.py`.

- L20 `ProductForm` (class) — Create/edit a `catalog.Product`. Variants/images live in their own flows.
- L120 `__init__(self, *args, instance=None, **kwargs)` (method)
- L171 `clean_structured_data(self)` (method)
- L185 `clean_sku(self)` (method)
- L198 `clean_slug(self)` (method)
- L211 `clean(self)` (method) — Variable products: per-variant price/weight/shipping is canonical.
- L228 `save(self)` (method)
- L325 `VariantForm` (class) — Create/edit a `catalog.ProductVariant` for a given product.
- L399 `__init__(self, *args, instance=None, product=None, **kwargs)` (method)
- L425 `clean_sku(self)` (method)
- L436 `clean(self)` (method)
- L446 `save(self)` (method)
