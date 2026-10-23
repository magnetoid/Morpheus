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

# plugins/installed/aliexpress/tests/test_aliexpress.py

Symbols in `plugins/installed/aliexpress/tests/test_aliexpress.py`.

- L54 `_now_ms()` (function)
- L58 `_Resp` (class)
- L59 `__init__(self, body, status=200)` (method)
- L62 `json(self)` (method)
- L66 `_Raw` (class) — A route answered exactly as given (no ``<method>_response`` envelope).
- L69 `__init__(self, body)` (method)
- L73 `FakeAE` (class) — Routes AliExpress calls by method name (or system path); checks signatures.
- L76 `__init__(self)` (method)
- L80 `ok(self, target: str, body)` (method)
- L83 `error(self, target: str, sub_msg: str, sub_code: str='isv.error')` (method)
- L96 `post(self, url, data=None, timeout=None)` (method)
- L120 `sent(self, target: str)` (method)
- L123 `sent_json(self, target: str, name: str)` (method)
- L127 `_product_detail(*, skus: int=2)` (function)
- L169 `AETestCase` (class)
- L170 `setUp(self)` (method)
- L198 `product(self, slug='lantern', *, sku_attr='14:193#Black', sku_id='120001')` (method)
- L218 `paid_order(self, product, qty=2)` (method)
- L240 `placed(self, *ids: int)` (method)
- L247 `SignTests` (class) — The official vectors from the AliExpress Open Platform signature guide.
- L250 `test_the_business_method_vector(self)` (method)
- L266 `test_the_system_method_vector_puts_the_path_first(self)` (method)
- L280 `test_empty_values_are_not_signed(self)` (method)
- L287 `UnwrapTests` (class)
- L288 `test_the_response_envelope_and_list_wrappers_go(self)` (method)
- L302 `test_a_result_or_data_list_keeps_its_name(self)` (method)
- L309 `ClientTests` (class)
- L310 `test_a_call_is_signed_and_carries_the_merchant_token(self)` (method)
- L323 `test_an_error_response_raises_with_its_sub_code(self)` (method)
- L332 `test_the_token_is_refreshed_when_under_two_days_are_left(self)` (method)
- L353 `test_without_the_app_keys_nothing_is_sent(self)` (method)
- L362 `StaffClientMixin` (class)
- L363 `staff_client(self)` (method)
- L373 `OAuthTests` (class)
- L374 `setUp(self)` (method)
- L381 `_start(self)` (method)
- L391 `test_start_sends_the_merchant_to_aliexpress_with_a_state(self)` (method)
- L400 `test_a_callback_with_another_state_is_refused(self)` (method)
- L413 `test_the_callback_exchanges_the_code_and_stores_the_tokens(self)` (method)
- L437 `test_disconnect_forgets_the_tokens(self)` (method)
- L446 `ImportTests` (class)
- L447 `test_search_reads_the_product_list(self)` (method)
- L480 `test_import_makes_a_linked_draft_with_marked_up_prices(self)` (method)
- L506 `test_a_single_sku_product_stays_simple_and_orders_without_sku_attr(self)` (method)
- L519 `OrderTests` (class)
- L520 `test_a_paid_order_is_placed_with_the_right_request(self)` (method)
- L554 `test_placing_twice_places_once(self)` (method)
- L563 `test_auto_pay_asks_aliexpress_to_pay_by_paypal(self)` (method)
- L574 `test_the_cheapest_delivery_when_none_is_chosen(self)` (method)
- L619 `test_a_refused_order_is_recorded_and_can_be_tried_again(self)` (method)
- L640 `test_a_gateway_error_is_recorded(self)` (method)
- L647 `test_the_payment_deadline_comes_from_aliexpress(self)` (method)
- L665 `test_the_order_ships_once_every_aliexpress_order_has_tracking(self)` (method)
- L708 `test_the_paid_hook_places_the_order(self)` (method)
- L717 `test_a_store_cancellation_is_flagged_for_a_cancel_in_aliexpress(self)` (method)
- L733 `ProductCardTests` (class)
- L734 `test_the_card_links_and_unlinks_a_product(self)` (method)
- L760 `test_the_card_renders_on_the_product_form(self)` (method)
- L768 `DashboardTests` (class)
- L771 `test_without_an_app_the_page_shows_the_setup_steps(self)` (method)
- L778 `test_the_connected_page_searches_and_lists_orders_to_pay(self)` (method)
- L805 `test_the_settings_keys_are_on_a_panel(self)` (method)
- L815 `SweepTaskTests` (class)
- L816 `test_nothing_is_sent_until_the_account_is_connected(self)` (method)
- L824 `test_the_sweep_places_missed_orders_and_reads_open_ones(self)` (method)
