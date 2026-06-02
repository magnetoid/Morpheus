---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/emails/handlers.py

Symbols in `core/emails/handlers.py`.

- L26 `register_handlers()` (function) — Idempotent: subscribe each domain event to its email sender.
- L45 `on_order_placed(order: Any, **kwargs: Any)` (function)
- L54 `on_order_paid(order: Any, **kwargs: Any)` (function)
- L63 `on_order_fulfilled(order: Any, **kwargs: Any)` (function)
- L72 `on_order_cancelled(order: Any, **kwargs: Any)` (function)
- L81 `on_digital_tokens_issued(order: Any=None, tokens: Any=None, **kwargs: Any)` (function) — Send the customer their download links after payment.
- L125 `on_cart_abandoned(cart: Any=None, email: Any=None, **kwargs: Any)` (function)
- L139 `on_customer_registered(customer: Any=None, **kwargs: Any)` (function)
- L153 `on_payment_refunded(refund: Any=None, order: Any=None, **kwargs: Any)` (function)
- L168 `_order_recipient(order: Any)` (function)
- L172 `_send(*, template_base: str, subject: str, to: str | None, ctx: dict)` (function)
- L211 `_db_override(template_base: str, ctx: dict)` (function) — Look up an active EmailTemplate by key. Returns
