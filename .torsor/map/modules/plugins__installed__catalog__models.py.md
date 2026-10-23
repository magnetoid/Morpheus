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

# plugins/installed/catalog/models.py

Symbols in `plugins/installed/catalog/models.py`.

- L27 `Vendor` (class) — Vendor / supplier — lives in catalog to avoid circular migration deps.
- L42 `__str__(self)` (method)
- L46 `Category` (class) — Hierarchical category tree (MPTT for efficient tree queries).
- L74 `__str__(self)` (method)
- L77 `save(self, *args, **kwargs)` (method)
- L84 `Collection` (class) — Curated product collections (e.g. 'Summer Sale', 'New Arrivals').
- L106 `__str__(self)` (method)
- L109 `save(self, *args, **kwargs)` (method)
- L115 `TagProfile` (class) — Editorial copy for a product tag.
- L136 `__str__(self)` (method)
- L139 `save(self, *args, **kwargs)` (method)
- L145 `for_tag(cls, value: str)` (method) — Resolve the profile for a ``?tag=`` value (a tag name or slug).
- L157 `AttributeGroup` (class) — Groups attributes (e.g. 'Clothing Sizes', 'Colors').
- L164 `__str__(self)` (method)
- L168 `Attribute` (class) — Product attribute definition (e.g. 'Size', 'Color', 'Material').
- L191 `__str__(self)` (method)
- L195 `AttributeValue` (class) — Possible values for an attribute (e.g. 'Red', 'XL').
- L209 `__str__(self)` (method)
- L213 `UUIDTaggedItem` (class) — Taggit through-model with a UUID ``object_id``.
- L229 `ProductQuerySet` (class)
- L230 `shoppable(self)` (method) — What the shop sells as goods: active, and not a service an app books
- L237 `Product` (class) — Core product model.
- L401 `__str__(self)` (method)
- L404 `save(self, *args, **kwargs)` (method)
- L415 `is_on_sale(self)` (method)
- L424 `discount_percentage(self)` (method)
- L431 `display_price(self)` (method) — Storefront-visible price.
- L452 `price_starts_from(self)` (method) — True when display_price reflects the minimum across 2+ active
- L461 `primary_image(self)` (method)
- L473 `average_rating(self)` (method)
- L480 `review_count(self)` (method) — Approved-only count. Storefront PDP renders this next to the
- L496 `ProductAttribute` (class) — Assigns attribute values to a product.
- L507 `product_image_upload_to(instance, filename: str)` (function) — ``products/<product title>-<6 random hex>.<ext>``: a name that says what the photo is, used once.
- L555 `ProductImage` (class) — Product images with ordering and alt text.
- L585 `__str__(self)` (method)
- L588 `save(self, *args, **kwargs)` (method)
- L620 `delete(self, *args, **kwargs)` (method)
- L628 `_strip_image_files(instance)` (function) — Remove the underlying media files for a ProductImage.
- L649 `_productimage_pre_delete(sender, instance, **kwargs)` (function) — Cascade/queryset.delete() bypass Model.delete() — so they leak
- L657 `ProductVariant` (class) — A specific purchasable version of a product.
- L766 `__str__(self)` (method)
- L770 `effective_price(self)` (method)
- L774 `Review` (class) — Customer product review with rating.
- L810 `__str__(self)` (method)
- L814 `PriceSchedule` (class) — A planned price change for a product/variant.
