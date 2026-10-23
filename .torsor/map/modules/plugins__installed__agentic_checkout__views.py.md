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

# plugins/installed/agentic_checkout/views.py

Symbols in `plugins/installed/agentic_checkout/views.py`.

- L53 `_with_version(response: HttpResponse)` (function)
- L58 `_json_body(request: HttpRequest)` (function)
- L66 `_session_ttl_minutes()` (function) — Session lifetime from plugin config (``session_ttl_minutes``).
- L81 `_payments_enabled()` (function) — Money-path opt-in from plugin config (``payments_enabled``, default off).
- L94 `_get_cart(session_id: str)` (function) — Load an ACP-owned cart by session id, or ``None``.
- L116 `_breakdown(cart)` (function)
- L128 `_derive_status(cart, breakdown)` (function) — ACP status from cart state.
- L149 `_availability_messages(cart)` (function) — Surface out_of_stock / low_stock as ACP messages on the session.
- L163 `_stamp_quoted_total(cart, breakdown)` (function) — Persist the minor-units total this response advertises.
- L184 `_serialize(cart, request, *, extra_messages: list[dict] | None=None, breakdown: dict | None=None)` (function)
- L208 `_apply_buyer(cart, buyer: dict | None)` (function)
- L233 `_apply_fulfillment(cart, fulfillment: dict | None)` (function) — Persist only the whitelisted, bounded ``FulfillmentDetails`` fields.
- L260 `_valid_currency(currency: str | None)` (function) — ``True`` iff ``currency`` is a known ISO-4217 code (or unset).
- L269 `_parse_quantity(raw: Any)` (function) — Parse + clamp a quantity. ``None`` means invalid (non-numeric / < 1).
- L280 `_resolve_line_items(line_items: list)` (function) — Validate ACP ``line_items`` WITHOUT mutating the cart.
- L348 `_apply_line_items(cart, resolved: list[dict], currency: str | None)` (function) — Add already-validated line items to the cart; collect any add errors.
- L369 `_add_line_items(cart, line_items: list, currency: str | None)` (function) — Validate + add ACP ``line_items`` to the cart (create path).
- L381 `create_checkout_session(request: HttpRequest)` (function) — POST /acp/checkout_sessions — new Cart from line_items + currency.
- L415 `checkout_session_detail(request: HttpRequest, session_id: str)` (function) — GET → read; POST → update (line items / fulfillment / buyer).
- L462 `cancel_checkout_session(request: HttpRequest, session_id: str)` (function) — POST /acp/checkout_sessions/{id}/cancel — release the cart, status canceled.
- L494 `_order_block(order, cart, request: HttpRequest | None)` (function) — ACP ``Order`` object for a ``CheckoutSessionWithOrder`` response.
- L506 `_order_line_items(order, currency: str)` (function) — ACP ``line_items[]`` rebuilt from persisted ``OrderItem`` rows.
- L543 `_order_snapshot(order, cart, request: HttpRequest | None, *, status: str)` (function) — Session body rebuilt from a persisted ``Order`` (the cart is empty).
- L559 `_claim_fresh(meta: dict)` (function) — ``True`` iff an in-flight completion claim younger than the TTL exists.
- L572 `_clear_claim(cart)` (function) — Release the in-flight claim so the agent can retry this session.
- L586 `_quote_drift_error(cart, breakdown)` (function) — MessageError when the total drifted since it was quoted, else ``None``.
- L605 `_record_delegation_evidence(order, cart, request: HttpRequest, token: str)` (function) — Dispute evidence on the Order via the metafields plugin (zero-migration).
- L636 `_unsupported_response(cart, request: HttpRequest)` (function) — The Phase-1 conformant ``unsupported`` 422 (money path off).
- L652 `_payment_service()` (function) — The payments plugin's ``PaymentService``, or ``None`` when unavailable.
- L661 `_completion_contact(cart)` (function) — (email, shipping_address) accumulated on the cart by ``update`` calls.
- L673 `_missing_messages(cart, email: str, address: dict | None)` (function) — Param-scoped ``missing`` MessageErrors for an incomplete session.
- L697 `_payment_data_error(body: dict)` (function) — Validate ``payment_data`` → (token, MessageError-or-None).
- L718 `_finalize_paid_order(order, cart, request: HttpRequest, token: str)` (function) — Success path — mirror the Stripe webhook's ``_mark_transaction_success``.
- L749 `_create_order_for_completion(cart, request: HttpRequest)` (function) — Validate the session + place the ``Order`` (inside the locked txn).
- L801 `_locked_complete(request: HttpRequest, session_id: str, body: dict)` (function) — The claim/idempotency gate + order creation, under the cart row lock.
- L873 `_payment_failure_message(result: dict)` (function) — Map a redeem failure dict onto a conformant ``MessageError``.
- L891 `complete_checkout_session(request: HttpRequest, session_id: str)` (function) — POST /acp/checkout_sessions/{id}/complete — the money path (Phase 2).
