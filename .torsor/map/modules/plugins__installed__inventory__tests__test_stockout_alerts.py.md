---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/tests/test_stockout_alerts.py

Symbols in `plugins/installed/inventory/tests/test_stockout_alerts.py`.

- L13 `_variant(sku: str)` (function)
- L20 `StockoutAlertModelTests` (class)
- L21 `test_open_alert_defaults_and_str(self)` (method)
- L30 `test_one_open_alert_per_variant_enforced(self)` (method)
- L36 `test_resolved_does_not_block_a_new_open(self)` (method)
- L47 `_make_at_risk(sku: str, *, on_hand: int, sold: int)` (function) — A variant with `on_hand` stock and `sold` units of 'sale' movements in
- L63 `SyncStockoutAlertsTests` (class)
- L64 `test_opens_one_alert_for_a_newly_at_risk_variant(self)` (method)
- L72 `test_rerun_is_idempotent_no_duplicate_alert(self)` (method)
- L82 `test_resolves_when_restocked(self)` (method)
- L94 `RunStockoutForecastTaskTests` (class)
- L95 `test_notifies_staff_only_for_newly_opened(self)` (method)
- L112 `StockoutForecastToolTests` (class)
- L113 `test_tool_returns_at_risk_rows(self)` (method)
- L121 `test_tool_registered_and_worker_visible(self)` (method)
- L130 `StockoutForecastPageTests` (class)
- L131 `setUp(self)` (method)
- L138 `test_page_lists_open_alerts(self)` (method)
- L146 `test_page_requires_staff(self)` (method)
- L150 `test_dashboard_page_contributed(self)` (method)
- L157 `StockoutAlertsEdgeCaseTests` (class)
- L158 `test_zero_velocity_variant_is_not_alerted(self)` (method)
- L169 `test_opens_multiple_alerts_in_one_sync(self)` (method)
- L178 `test_forecast_uses_available_not_on_hand(self)` (method)
- L198 `test_tool_clamps_threshold_days(self)` (method)
