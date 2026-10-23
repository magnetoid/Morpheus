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

# plugins/installed/catalog/graphql/mutations.py

Symbols in `plugins/installed/catalog/graphql/mutations.py`.

- L24 `ProductMutationResult` (class)
- L38 `CategoryMutationResult` (class)
- L47 `ProductImageMutationResult` (class)
- L58 `PublishDigitalProductResult` (class)
- L67 `_err_publish(msg: str)` (function)
- L78 `_err_product(msg: str)` (function)
- L93 `_err_category(msg: str)` (function)
- L103 `_from_product_dict(d: dict)` (function)
- L118 `_from_category_dict(d: dict)` (function)
- L128 `_err_image(msg: str)` (function)
- L140 `_from_image_dict(d: dict)` (function)
- L156 `PublishDigitalProductInput` (class)
- L172 `CreateProductInput` (class) — Create a new product. Generic — for digital/PDF books prefer
- L208 `UpdateProductInput` (class) — Update a product by slug. Every field is optional — only fields
- L250 `CreateCategoryInput` (class)
- L258 `CreateVariantInput` (class)
- L277 `UpdateVariantInput` (class)
- L294 `VariantMutationResult` (class)
- L311 `_err_variant(msg: str)` (function)
- L330 `_from_variant_dict(d: dict)` (function)
- L350 `UpdateDigitalPdfInput` (class)
- L356 `AddProductImageInput` (class)
- L365 `UpdateCategoryInput` (class)
- L377 `CatalogMutationExtension` (class)
- L383 `publish_digital_product(self, info: strawberry.Info, input: PublishDigitalProductInput)` (method)
- L429 `create_product(self, info: strawberry.Info, input: CreateProductInput)` (method)
- L484 `update_product(self, info: strawberry.Info, input: UpdateProductInput)` (method)
- L536 `archive_product(self, info: strawberry.Info, slug: str)` (method)
- L548 `restore_product(self, info: strawberry.Info, slug: str, status: str='active')` (method)
- L567 `delete_product(self, info: strawberry.Info, slug: str)` (method)
- L581 `create_variant(self, info: strawberry.Info, input: CreateVariantInput)` (method)
- L620 `update_variant(self, info: strawberry.Info, input: UpdateVariantInput)` (method)
- L658 `update_digital_pdf(self, info: strawberry.Info, input: UpdateDigitalPdfInput)` (method)
- L679 `add_product_image(self, info: strawberry.Info, input: AddProductImageInput)` (method)
- L703 `remove_product_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L721 `set_primary_image(self, info: strawberry.Info, image_id: strawberry.ID)` (method)
- L739 `create_category(self, info: strawberry.Info, input: CreateCategoryInput)` (method)
- L762 `update_category(self, info: strawberry.Info, input: UpdateCategoryInput)` (method)
- L788 `archive_category(self, info: strawberry.Info, slug: str)` (method)
