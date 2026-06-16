---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/agent_tools.py

Symbols in `plugins/installed/inventory/agent_tools.py`.

- L20 `low_stock_report_tool(*, threshold: int=5, limit: int=25)` (function)
- L68 `adjust_stock_tool(*, variant_sku: str, warehouse_code: str, delta: int, reason: str='')` (function)
- L112 `list_back_in_stock_tool(*, limit: int=50)` (function)
- L152 `schedule_price_change_tool(*, slug: str, new_price: float, effective_at_iso: str, currency: str='USD', note: str='')` (function)
- L208 `stockout_forecast_tool(*, threshold_days: int=14, limit: int=25)` (function)
