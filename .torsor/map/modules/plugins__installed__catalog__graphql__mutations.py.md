---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/catalog/graphql/mutations.py

Symbols in `plugins/installed/catalog/graphql/mutations.py`.

- L20 `ProductMutationResult` (class)
- L34 `CategoryMutationResult` (class)
- L43 `ProductImageMutationResult` (class)
- L54 `PublishDigitalProductResult` (class)
- L63 `_is_staff(info)` (function)
- L71 `_check_scope(info, required: list[str])` (function) — Return '' when the request is authorised for the given scope(s),
- L93 `_err_publish(msg: str)` (function)
- L104 `_err_product(msg: str)` (function)
- L119 `_err_category(msg: str)` (function)
- L129 `_from_product_dict(d: dict)` (function)
- L144 `_from_category_dict(d: dict)` (function)
- L154 `_err_image(msg: str)` (function)
- L166 `_from_image_dict(d: dict)` (function)
- L182 `PublishDigitalProductInput` (class)
- L198 `CreateProductInput` (class) — Create a new product. Generic — for digital/PDF books prefer
- L234 `UpdateProductInput` (class) — Update a product by slug. Every field is optional — only fields
- L276 `CreateCategoryInput` (class)
- L284 `CreateVariantInput` (class)
- L303 `UpdateVariantInput` (class)
- L320 `VariantMutationResult` (class)
- L337 `_err_variant(msg: str)` (function)
- L356 `_from_variant_dict(d: dict)` (function)
- L376 `UpdateDigitalPdfInput` (class)
- L382 `AddProductImageInput` (class)
- L391 `UpdateCategoryInput` (class)
- L403 `CatalogMutationExtension` (class)
- L409 `publish_digital_product(self, info: strawberry.Info, input: PublishDigitalProductInput)` (method)
- L455 `create_product(self, info: strawberry.Info, input: CreateProductInput)` (method)
- L510 `update_product(self, info: strawberry.Info, input: UpdateProductInput)` (method)
- L562 `archive_product(self, info: strawberry.Info, slug: str)` (method)
- L574 `restore_product(self, info: strawberry.Info, slug: str, status: str='active')` (method)
- L593 `delete_product(self, info: strawberry.Info, slug: str)` (method)
- L607 `create_variant(self, info: strawberry.Info, input: CreateVariantInput)` (method)
- L646 `update_variant(self, info: strawberry.Info, input: UpdateVariantInput)` (method)
- L684 `update_digital_pdf(self, info: strawberry.Info, input: UpdateDigitalPdfInput)` (method)
- L705 `add_product_image(self, info: strawberry.Info, input: AddProductImageInput)` (method)
- L729 `remove_product_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L747 `set_primary_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L765 `create_category(self, info: strawberry.Info, input: CreateCategoryInput)` (method)
- L788 `update_category(self, info: strawberry.Info, input: UpdateCategoryInput)` (method)
- L814 `archive_category(self, info: strawberry.Info, slug: str)` (method)
