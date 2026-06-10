---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/agent_core/tools/catalog.py

Symbols in `plugins/installed/agent_core/tools/catalog.py`.

- L20 `find_products_tool(*, query: str, limit: int=8)` (function)
- L61 `get_product_tool(*, slug: str='', sku: str='')` (function)
- L94 `list_categories_tool()` (function)
- L123 `backfill_alt_text_tool(*, slugs: list[str] | None=None, force: bool=False)` (function)
- L174 `publish_digital_product_tool(*, title: str, pdf_url: str, price_amount: str, price_currency: str='USD', description: str='', short_description: str='', author: str='', cover_image_url: str='', category_slug: str='', sku: str='', slug: str='', status: str='active')` (function)
- L218 `catalog_stats_tool()` (function)
- L306 `create_product_tool(*, name: str, price_amount: str, price_currency: str='USD', product_type: str='simple', status: str='draft', **extra)` (function)
- L374 `update_product_tool(*, slug: str, **fields)` (function)
- L396 `archive_product_tool(*, slug: str)` (function)
- L418 `restore_product_tool(*, slug: str, status: str='active')` (function)
- L441 `delete_product_tool(*, slug: str)` (function)
- L468 `update_digital_pdf_tool(*, slug: str, pdf_url: str)` (function)
- L497 `add_product_image_tool(*, slug: str, image_url: str, alt_text: str='', is_primary: bool=False, sort_order: int=0)` (function)
- L525 `remove_product_image_tool(*, image_id: str)` (function)
- L544 `set_primary_image_tool(*, image_id: str)` (function)
- L568 `create_category_tool(*, name: str, slug: str='', parent_slug: str='', description: str='')` (function)
- L595 `update_category_tool(*, slug: str, name: str='', new_slug: str='', parent_slug: str | None=None, description: str | None=None)` (function)
- L639 `create_variant_tool(*, product_slug: str, name: str, sku: str, **fields)` (function)
- L681 `update_variant_tool(*, sku: str, **fields)` (function)
- L705 `archive_category_tool(*, slug: str)` (function)
