---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/emails/handlers.py

Symbols in `core/emails/handlers.py`.

- L27 `register_handlers()` (function) — Idempotent: subscribe each domain event to its email sender.
- L47 `on_order_placed(order: Any, **kwargs: Any)` (function)
- L66 `on_order_paid(order: Any, **kwargs: Any)` (function)
- L75 `on_order_fulfilled(order: Any, **kwargs: Any)` (function)
- L84 `on_order_cancelled(order: Any, **kwargs: Any)` (function)
- L93 `on_digital_tokens_issued(order: Any=None, tokens: Any=None, **kwargs: Any)` (function) — Send the customer their download links after payment.
- L132 `on_customer_registered(customer: Any=None, **kwargs: Any)` (function)
- L146 `on_payment_refunded(refund: Any=None, order: Any=None, **kwargs: Any)` (function)
- L161 `_order_recipient(order: Any)` (function)
- L165 `send_templated_email(key: str, *, to: str | None, subject: str, ctx: dict | None=None, headers: dict | None=None)` (function) — Send a transactional email by its registry ``key``.
- L188 `_send(*, template_base: str, subject: str, to: str | None, ctx: dict, headers: dict | None=None)` (function)
- L256 `_db_override(template_base: str, ctx: dict)` (function) — Merchant-edited copy for this email, via EMAIL_TEMPLATE_OVERRIDE.
