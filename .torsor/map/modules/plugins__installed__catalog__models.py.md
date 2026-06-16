---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/catalog/models.py

Symbols in `plugins/installed/catalog/models.py`.

- L25 `Vendor` (class) — Vendor / supplier — lives in catalog to avoid circular migration deps.
- L40 `__str__(self)` (method)
- L44 `Category` (class) — Hierarchical category tree (MPTT for efficient tree queries).
- L68 `__str__(self)` (method)
- L71 `save(self, *args, **kwargs)` (method)
- L77 `Collection` (class) — Curated product collections (e.g. 'Summer Sale', 'New Arrivals').
- L99 `__str__(self)` (method)
- L102 `save(self, *args, **kwargs)` (method)
- L108 `AttributeGroup` (class) — Groups attributes (e.g. 'Clothing Sizes', 'Colors').
- L115 `__str__(self)` (method)
- L119 `Attribute` (class) — Product attribute definition (e.g. 'Size', 'Color', 'Material').
- L142 `__str__(self)` (method)
- L146 `AttributeValue` (class) — Possible values for an attribute (e.g. 'Red', 'XL').
- L160 `__str__(self)` (method)
- L164 `Product` (class) — Core product model.
- L322 `__str__(self)` (method)
- L325 `save(self, *args, **kwargs)` (method)
- L331 `is_on_sale(self)` (method)
- L340 `discount_percentage(self)` (method)
- L347 `display_price(self)` (method) — Storefront-visible price.
- L368 `price_starts_from(self)` (method) — True when display_price reflects the minimum across 2+ active
- L377 `primary_image(self)` (method)
- L381 `average_rating(self)` (method)
- L388 `review_count(self)` (method) — Approved-only count. Storefront PDP renders this next to the
- L394 `ProductAttribute` (class) — Assigns attribute values to a product.
- L405 `ProductImage` (class) — Product images with ordering and alt text.
- L435 `__str__(self)` (method)
- L438 `save(self, *args, **kwargs)` (method)
- L470 `delete(self, *args, **kwargs)` (method)
- L478 `_strip_image_files(instance)` (function) — Remove the underlying media files for a ProductImage.
- L499 `_productimage_pre_delete(sender, instance, **kwargs)` (function) — Cascade/queryset.delete() bypass Model.delete() — so they leak
- L507 `ProductVariant` (class) — A specific purchasable version of a product.
- L615 `__str__(self)` (method)
- L619 `effective_price(self)` (method)
- L623 `Review` (class) — Customer product review with rating.
- L659 `__str__(self)` (method)
- L663 `PriceSchedule` (class) — A planned price change for a product/variant.
