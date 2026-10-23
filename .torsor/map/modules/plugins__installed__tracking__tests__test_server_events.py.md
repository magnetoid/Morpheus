---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/tracking/tests/test_server_events.py

Symbols in `plugins/installed/tracking/tests/test_server_events.py`.

- L32 `_unmanaged_store()` (function) — These tests are about what GA4 receives; consent has its own tests
- L45 `_sent(mock_send, event_name)` (function)
- L49 `ViewItemFromProductPageTests` (class)
- L50 `setUp(self)` (method)
- L61 `test_product_page_sends_view_item_with_its_price(self)` (method)
- L71 `test_variable_product_reports_the_price_the_page_shows(self)` (method)
- L88 `test_crawlers_are_not_sent_to_ga4(self)` (method)
- L98 `test_the_send_is_queued_not_run_in_the_request(self)` (method)
- L105 `ChargedLinePriceTests` (class) — Items carry the price the line was charged, not today's catalog price.
- L108 `setUp(self)` (method)
- L118 `_line(self, unit_price)` (method)
- L123 `test_purchase_items_use_the_line_unit_price(self)` (method)
- L138 `test_begin_checkout_values_the_cart_at_its_line_prices(self)` (method)
