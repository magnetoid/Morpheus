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

# plugins/installed/marketplace/tests/test_portal.py

Symbols in `plugins/installed/marketplace/tests/test_portal.py`.

- L47 `_portal(body: str)` (function)
- L52 `_user(email)` (function)
- L56 `_VendorBase` (class)
- L57 `setUp(self)` (method)
- L71 `_slice(self, *, gross=40, status='pending', paid=True, days_ago=0, vendor=None, items=None)` (method)
- L105 `AccountTileTests` (class)
- L106 `_tile(self, user)` (method)
- L113 `test_an_owner_gets_the_tile(self)` (method)
- L116 `test_an_applicant_gets_the_tile_with_the_application_status(self)` (method)
- L123 `test_anyone_else_gets_nothing(self)` (method)
- L127 `ShellTests` (class)
- L128 `test_a_vendor_without_an_application_gets_their_portal(self)` (method)
- L134 `test_every_page_renders_with_one_robots_tag_saying_noindex(self)` (method)
- L143 `test_no_page_speaks_a_bookshop(self)` (method)
- L150 `test_an_applicant_sees_where_the_application_stands(self)` (method)
- L163 `test_a_paused_vendor_is_told_so(self)` (method)
- L169 `OverviewTests` (class)
- L170 `test_sales_count_only_orders_that_still_stand(self)` (method)
- L179 `test_orders_to_send_show_paid_ones_with_a_ship_form(self)` (method)
- L189 `test_best_sellers_come_from_the_order_snapshots(self)` (method)
- L195 `OrdersTests` (class)
- L196 `test_only_this_vendors_orders_are_listed(self)` (method)
- L207 `test_mark_shipped_from_the_list_comes_back_to_it(self)` (method)
- L222 `test_a_next_off_the_portal_is_ignored(self)` (method)
- L229 `test_the_store_owned_statuses_cannot_be_set(self)` (method)
- L237 `test_a_script_tracking_link_is_refused(self)` (method)
- L246 `test_another_vendors_order_cannot_be_updated(self)` (method)
- L255 `PayoutTests` (class)
- L256 `setUp(self)` (method)
- L262 `test_a_second_request_while_one_is_open_is_refused(self)` (method)
- L269 `test_the_service_refuses_it_too(self)` (method)
- L274 `test_without_a_method_the_page_says_so(self)` (method)
- L282 `StockTests` (class)
- L283 `_stock(self, product, quantity)` (method)
- L295 `test_products_show_the_stock_inventory_reports(self)` (method)
- L312 `test_low_stock_is_flagged_on_the_overview(self)` (method)
- L317 `test_without_inventory_the_page_shows_no_stock_column(self)` (method)
