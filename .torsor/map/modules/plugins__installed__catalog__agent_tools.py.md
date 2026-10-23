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

# plugins/installed/catalog/agent_tools.py

Symbols in `plugins/installed/catalog/agent_tools.py`.

- L37 `_enforce_price_delta(old_amount, new_amount: Decimal, max_pct: float)` (function) — Refuse an agent price change whose magnitude exceeds the merchant's
- L59 `_in_category(category: str)` (function) — Products in the categories matching ``category`` (slug, or part of the name)
- L94 `products_search_tool(*, status: str='', name: str='', sku: str='', category: str='', vendor: str='', limit: int=20)` (function)
- L159 `products_count_tool(*, status: str='', category: str='', vendor: str='')` (function)
- L195 `products_get_tool(*, id: str='', sku: str='', slug: str='')` (function)
- L304 `translate_product_tool(*, slug: str, language_code: str, name: str='', short_description: str='', description: str='')` (function)
- L340 `list_translations_tool(*, slug: str)` (function)
- L375 `products_update_status_tool(*, status: str, id: str='', sku: str='', slug: str='', confirmed: bool=False, context: dict | None=None)` (function)
- L449 `products_update_price_tool(*, price: str, id: str='', sku: str='', slug: str='', variant_id: str='', confirmed: bool=False, context: dict | None=None)` (function)
