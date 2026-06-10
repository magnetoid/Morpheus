---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/assistant/tools/ecommerce.py

Symbols in `core/assistant/tools/ecommerce.py`.

- L30 `_money_str(value: Any)` (function) — Convert a djmoney Money / Decimal / None into a flat string.
- L38 `_money_amount(value: Any)` (function) — Pull the numeric amount out of a Money / Decimal / numeric value.
- L72 `orders_search_tool(*, status: str='', days_back: int=0, email: str='', order_number: str='', limit: int=20)` (function)
- L119 `orders_get_tool(*, order_number: str)` (function)
- L204 `products_search_tool(*, status: str='', name: str='', sku: str='', category: str='', vendor: str='', limit: int=20)` (function)
- L258 `products_get_tool(*, id: str='', sku: str='', slug: str='')` (function)
- L352 `customers_search_tool(*, email: str='', name: str='', source: str='', limit: int=20)` (function)
- L401 `customers_get_tool(*, id: str='', email: str='')` (function)
- L479 `analytics_summary_tool(*, days_back: int=7)` (function)
- L534 `analytics_top_products_tool(*, days_back: int=30, by: str='revenue', limit: int=10)` (function)
- L580 `cms_pages_tool(*, state: str='', limit: int=50)` (function)
- L616 `email_templates_tool()` (function)
- L647 `settings_list_tool()` (function)
- L694 `media_search_tool(*, kind: str='', filename: str='', tag: str='', limit: int=20)` (function)
- L747 `metafields_list_for_tool(*, model: str, object_id: str)` (function)
- L791 `markets_list_tool()` (function)
- L830 `db_describe_model_tool(*, model: str)` (function)
