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

# plugins/installed/cjdropshipping/tests/test_cj.py

Symbols in `plugins/installed/cjdropshipping/tests/test_cj.py`.

- L33 `FakeCJ` (class) — Routes CJ calls by path; records what was sent.
- L36 `__init__(self)` (method)
- L46 `ok(self, method: str, path: str, data)` (method)
- L54 `error(self, method: str, path: str, code: int, message: str, status: int=200)` (method)
- L60 `_respond(self, method, url, params=None, json_body=None)` (method)
- L71 `request(self, method, url, params=None, json=None, headers=None, timeout=None)` (method)
- L74 `post(self, url, json=None, headers=None, timeout=None)` (method)
- L77 `bodies(self, method: str, path: str)` (method)
- L85 `_Resp` (class)
- L86 `__init__(self, body, status)` (method)
- L89 `json(self)` (method)
- L93 `CJTestCase` (class)
- L94 `setUp(self)` (method)
- L114 `product(self, slug='radio', vid='V-RADIO')` (method)
- L128 `paid_order(self, product, qty=2)` (method)
- L151 `ClientTests` (class)
- L152 `test_success_is_http_200_and_code_200(self)` (method)
- L160 `test_a_failure_code_raises_with_the_code(self)` (method)
- L168 `test_a_rejected_token_is_fetched_again_once(self)` (method)
- L185 `WebhookSignatureTests` (class)
- L186 `test_the_docs_test_vector(self)` (method)
- L196 `ImportTests` (class)
- L197 `test_search_reads_the_nested_product_lists(self)` (method)
- L226 `test_import_makes_a_linked_draft_with_marked_up_prices(self)` (method)
- L278 `OrderTests` (class)
- L279 `setUp(self)` (method)
- L284 `_created(self, status='CREATED')` (method)
- L297 `test_a_paid_order_becomes_a_cj_order_with_the_right_body(self)` (method)
- L321 `test_sending_twice_sends_once(self)` (method)
- L330 `test_auto_pay_uses_pay_type_2(self)` (method)
- L339 `test_cheapest_method_when_none_is_set(self)` (method)
- L365 `test_a_refused_order_is_recorded_and_can_be_retried(self)` (method)
- L376 `test_an_order_cj_already_has_is_adopted(self)` (method)
- L388 `test_paying_confirms_then_pays_from_the_balance(self)` (method)
- L401 `test_an_empty_balance_is_reported_not_raised(self)` (method)
- L411 `test_the_sweep_ships_the_order_with_cj_tracking(self)` (method)
- L440 `test_paid_hook_sends_the_order(self)` (method)
- L450 `test_an_order_cancelled_in_the_store_is_deleted_at_cj(self)` (method)
- L467 `WebhookViewTests` (class)
- L468 `_post(self, payload: dict, *, sign: str | None=None)` (method)
- L477 `_sent_order(self)` (method)
- L488 `test_a_signed_logistic_message_ships_the_order(self)` (method)
- L509 `test_an_unsigned_message_is_answered_and_ignored(self)` (method)
- L522 `test_stock_and_price_messages_update_the_link(self)` (method)
- L548 `DashboardTests` (class)
- L549 `setUp(self)` (method)
- L558 `test_the_page_renders_with_search_results(self)` (method)
- L583 `test_the_settings_keys_are_on_a_panel(self)` (method)
- L594 `_png()` (function)
