---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/catalog/graphql/mutations.py

Symbols in `plugins/installed/catalog/graphql/mutations.py`.

- L22 `ProductMutationResult` (class)
- L36 `CategoryMutationResult` (class)
- L45 `ProductImageMutationResult` (class)
- L56 `PublishDigitalProductResult` (class)
- L65 `_is_staff(info)` (function)
- L73 `_check_scope(info, required: list[str])` (function) — Return '' when the request is authorised for the given scope(s),
- L94 `_err_publish(msg: str)` (function)
- L100 `_err_product(msg: str)` (function)
- L107 `_err_category(msg: str)` (function)
- L113 `_from_product_dict(d: dict)` (function)
- L122 `_from_category_dict(d: dict)` (function)
- L129 `_err_image(msg: str)` (function)
- L136 `_from_image_dict(d: dict)` (function)
- L150 `PublishDigitalProductInput` (class)
- L166 `CreateProductInput` (class) — Create a new product. Generic — for digital/PDF books prefer
- L201 `UpdateProductInput` (class) — Update a product by slug. Every field is optional — only fields
- L242 `CreateCategoryInput` (class)
- L250 `CreateVariantInput` (class)
- L269 `UpdateVariantInput` (class)
- L286 `VariantMutationResult` (class)
- L303 `_err_variant(msg: str)` (function)
- L313 `_from_variant_dict(d: dict)` (function)
- L329 `UpdateDigitalPdfInput` (class)
- L335 `AddProductImageInput` (class)
- L344 `UpdateCategoryInput` (class)
- L356 `CatalogMutationExtension` (class)
- L363 `publish_digital_product(self, info: strawberry.Info, input: PublishDigitalProductInput)` (method)
- L399 `create_product(self, info: strawberry.Info, input: CreateProductInput)` (method)
- L444 `update_product(self, info: strawberry.Info, input: UpdateProductInput)` (method)
- L488 `archive_product(self, info: strawberry.Info, slug: str)` (method)
- L499 `restore_product(self, info: strawberry.Info, slug: str, status: str='active')` (method)
- L514 `delete_product(self, info: strawberry.Info, slug: str)` (method)
- L527 `create_variant(self, info: strawberry.Info, input: CreateVariantInput)` (method)
- L558 `update_variant(self, info: strawberry.Info, input: UpdateVariantInput)` (method)
- L591 `update_digital_pdf(self, info: strawberry.Info, input: UpdateDigitalPdfInput)` (method)
- L609 `add_product_image(self, info: strawberry.Info, input: AddProductImageInput)` (method)
- L626 `remove_product_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L641 `set_primary_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L656 `create_category(self, info: strawberry.Info, input: CreateCategoryInput)` (method)
- L672 `update_category(self, info: strawberry.Info, input: UpdateCategoryInput)` (method)
- L693 `archive_category(self, info: strawberry.Info, slug: str)` (method)
