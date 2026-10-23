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

# plugins/installed/agentic_checkout/serializers.py

Symbols in `plugins/installed/agentic_checkout/serializers.py`.

- L48 `minor_unit_exponent(currency: str)` (function)
- L52 `amount_to_minor(amount: Decimal, currency: str)` (function) — Decimal major units → integer minor units for ``currency``.
- L60 `money_to_minor(money: Money | None, fallback_currency: str='USD')` (function) — ``Money`` → integer minor units. ``None`` → 0.
- L67 `_total(total_type: str, display_text: str, amount: int)` (function) — One ACP ``Total`` row.
- L72 `breakdown_to_totals(breakdown: dict, currency: str)` (function) — ACP ``totals[]`` from an ``OrderService.calculate_cart_breakdown`` dict.
- L100 `_availability_status(item)` (function) — ACP ``availability_status`` for a cart line.
- L129 `line_item_to_acp(item, currency: str)` (function) — One ``CartItem`` → ACP ``LineItem``.
- L159 `_links(request)` (function) — ACP ``links[]`` — terms / privacy / return policy from settings/CMS.
- L175 `capabilities()` (function) — ACP ``Capabilities`` (REQUIRED on every ``CheckoutSession``).
- L195 `serialize_session(cart, *, status: str, breakdown: dict, request=None, messages: list[dict] | None=None)` (function) — Build a conformant ACP ``CheckoutSession`` from a ``Cart``.
- L236 `message_error(code: str, message: str, param: str='')` (function) — One ACP ``MessageError`` — ``type='error'`` + closed-enum ``code``.
- L254 `message_info(message: str)` (function) — One ACP ``MessageInfo`` — ``type='info'`` with NO ``code``.
- L259 `error_response(code: str, message: str, *, status: int=400)` (function) — ACP top-level ``Error`` envelope (used for auth + request errors).
