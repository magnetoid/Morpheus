---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/orders/agent_tools.py

Symbols in `plugins/installed/orders/agent_tools.py`.

- L72 `orders_search_tool(*, status: str='', days_back: int=0, email: str='', order_number: str='', limit: int=20)` (function)
- L130 `orders_get_tool(*, order_number: str)` (function)
- L228 `refund_order_tool(*, order_number: str, amount: float | None=None, reason: str='customer_request', notes: str='', confirmed: bool=False, hard_gate_ack: str='', echo: str='')` (function)
- L309 `orders_update_status_tool(*, order_number: str, status: str, confirmed: bool=False, context: dict | None=None)` (function)
- L376 `orders_cancel_tool(*, order_number: str, reason: str='', confirmed: bool=False, context: dict | None=None)` (function)
- L443 `orders_add_note_tool(*, order_number: str, note: str, confirmed: bool=False, context: dict | None=None)` (function)
- L511 `list_returns_tool(*, state: str='', limit: int=20)` (function)
- L552 `approve_return_tool(*, rma_number: str, refund_amount: float | None=None)` (function)
- L582 `_currency_label(currencies: list[str])` (function) — One currency code, or a warning when the summed orders mix currencies.
- L606 `analytics_summary_tool(*, days_back: int=7)` (function)
- L670 `analytics_top_products_tool(*, days_back: int=30, by: str='revenue', limit: int=10)` (function)
