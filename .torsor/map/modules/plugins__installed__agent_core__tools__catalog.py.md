---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
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
- L427 `update_product_tool(*, slug: str, **fields)` (function)
- L450 `archive_product_tool(*, slug: str)` (function)
- L473 `restore_product_tool(*, slug: str, status: str='active')` (function)
- L497 `delete_product_tool(*, slug: str)` (function)
- L525 `update_digital_pdf_tool(*, slug: str, pdf_url: str)` (function)
- L555 `add_product_image_tool(*, slug: str, image_url: str, alt_text: str='', is_primary: bool=False, sort_order: int=0)` (function)
- L591 `remove_product_image_tool(*, image_id: str)` (function)
- L611 `set_primary_image_tool(*, image_id: str)` (function)
- L636 `create_category_tool(*, name: str, slug: str='', parent_slug: str='', description: str='')` (function)
- L668 `update_category_tool(*, slug: str, name: str='', new_slug: str='', parent_slug: str | None=None, description: str | None=None)` (function)
- L730 `create_variant_tool(*, product_slug: str, name: str, sku: str, **fields)` (function)
- L777 `update_variant_tool(*, sku: str, **fields)` (function)
- L802 `archive_category_tool(*, slug: str)` (function)
