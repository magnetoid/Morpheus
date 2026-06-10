---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/catalog/services/products.py

Symbols in `plugins/installed/catalog/services/products.py`.

- L43 `publish_digital_product(*, title: str, pdf_url: str, price_amount: Any, price_currency: str='USD', description: str='', short_description: str='', author: str='', cover_image_url: str='', category_slug: str='', sku: str='', slug: str='', status: str='active')` (function) — Create a digital-product Product from external URLs.
- L158 `create_product(*, name: str, price_amount: Any, price_currency: str='USD', product_type: str='simple', status: str='draft', sku: str='', slug: str='', short_description: str='', description: str='', category_slug: str='', cover_image_url: str='', **extra)` (function) — Create a new product. Generic create — for digital/PDF-specific
- L279 `update_product(*, slug: str, **fields)` (function) — Update an existing product by slug. Only fields present in `fields`
- L394 `archive_product(*, slug: str)` (function)
- L405 `restore_product(*, slug: str, status: str='active')` (function)
- L418 `delete_product(*, slug: str)` (function) — Hard-delete a product. Use archive_product unless you really need
- L431 `update_digital_pdf(*, slug: str, pdf_url: str)` (function) — Replace the digital_file on an existing product by downloading
