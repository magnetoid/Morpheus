---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/tools/ecommerce.py

Symbols in `core/assistant/tools/ecommerce.py`.

- L31 `_money_str(value: Any)` (function) — Convert a djmoney Money / Decimal / None into a flat string.
- L39 `_money_amount(value: Any)` (function) — Pull the numeric amount out of a Money / Decimal / numeric value.
- L73 `orders_search_tool(*, status: str='', days_back: int=0, email: str='', order_number: str='', limit: int=20)` (function)
- L125 `orders_get_tool(*, order_number: str)` (function)
- L211 `products_search_tool(*, status: str='', name: str='', sku: str='', category: str='', vendor: str='', limit: int=20)` (function)
- L274 `products_get_tool(*, id: str='', sku: str='', slug: str='')` (function)
- L377 `customers_search_tool(*, email: str='', name: str='', source: str='', limit: int=20)` (function)
- L429 `customers_get_tool(*, id: str='', email: str='')` (function)
- L515 `analytics_summary_tool(*, days_back: int=7)` (function)
- L577 `analytics_top_products_tool(*, days_back: int=30, by: str='revenue', limit: int=10)` (function)
- L626 `cms_pages_tool(*, state: str='', limit: int=50)` (function)
- L662 `email_templates_tool()` (function)
- L693 `settings_list_tool()` (function)
- L741 `media_search_tool(*, kind: str='', filename: str='', tag: str='', limit: int=20)` (function)
- L798 `metafields_list_for_tool(*, model: str, object_id: str)` (function)
- L846 `markets_list_tool()` (function)
- L886 `db_describe_model_tool(*, model: str)` (function)
