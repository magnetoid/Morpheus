---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/emails/handlers.py

Symbols in `core/emails/handlers.py`.

- L27 `register_handlers()` (function) — Idempotent: subscribe each domain event to its email sender.
- L46 `on_order_placed(order: Any, **kwargs: Any)` (function)
- L55 `on_order_paid(order: Any, **kwargs: Any)` (function)
- L64 `on_order_fulfilled(order: Any, **kwargs: Any)` (function)
- L73 `on_order_cancelled(order: Any, **kwargs: Any)` (function)
- L82 `on_digital_tokens_issued(order: Any=None, tokens: Any=None, **kwargs: Any)` (function) — Send the customer their download links after payment.
- L121 `on_cart_abandoned(cart: Any=None, email: Any=None, **kwargs: Any)` (function)
- L135 `on_customer_registered(customer: Any=None, **kwargs: Any)` (function)
- L149 `on_payment_refunded(refund: Any=None, order: Any=None, **kwargs: Any)` (function)
- L164 `_order_recipient(order: Any)` (function)
- L168 `_send(*, template_base: str, subject: str, to: str | None, ctx: dict)` (function)
- L207 `_db_override(template_base: str, ctx: dict)` (function) — Merchant-edited copy for this email, via EMAIL_TEMPLATE_OVERRIDE.
