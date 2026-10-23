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

# plugins/installed/agent_core/tools/catalog.py

Symbols in `plugins/installed/agent_core/tools/catalog.py`.

- L21 `find_products_tool(*, query: str, limit: int=8)` (function)
- L63 `get_product_tool(*, slug: str='', sku: str='')` (function)
- L100 `list_categories_tool()` (function)
- L134 `backfill_alt_text_tool(*, slugs: list[str] | None=None, force: bool=False)` (function)
- L206 `publish_digital_product_tool(*, title: str, pdf_url: str, price_amount: str, price_currency: str='USD', description: str='', short_description: str='', author: str='', cover_image_url: str='', category_slug: str='', sku: str='', slug: str='', status: str='active')` (function)
- L258 `catalog_stats_tool()` (function)
- L356 `create_product_tool(*, name: str, price_amount: str, price_currency: str='USD', product_type: str='simple', status: str='draft', **extra)` (function)
- L389 `_refuse_price_change(fields: dict)` (function) — A price edit belongs to products.update_price, never to a generic update.
- L444 `update_product_tool(*, slug: str, **fields)` (function)
- L468 `archive_product_tool(*, slug: str)` (function)
- L491 `restore_product_tool(*, slug: str, status: str='active')` (function)
- L515 `delete_product_tool(*, slug: str)` (function)
- L543 `update_digital_pdf_tool(*, slug: str, pdf_url: str)` (function)
- L573 `add_product_image_tool(*, slug: str, image_url: str, alt_text: str='', is_primary: bool=False, sort_order: int=0)` (function)
- L609 `remove_product_image_tool(*, image_id: str)` (function)
- L629 `set_primary_image_tool(*, image_id: str)` (function)
- L664 `create_category_tool(*, name: str, slug: str='', parent_slug: str='', description: str='', long_description: str='')` (function)
- L713 `update_category_tool(*, slug: str, name: str='', new_slug: str='', parent_slug: str | None=None, description: str | None=None, long_description: str | None=None)` (function)
- L777 `create_variant_tool(*, product_slug: str, name: str, sku: str, **fields)` (function)
- L827 `update_variant_tool(*, sku: str, **fields)` (function)
- L853 `archive_category_tool(*, slug: str)` (function)
