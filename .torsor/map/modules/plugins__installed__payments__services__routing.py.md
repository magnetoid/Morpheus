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

# plugins/installed/payments/services/routing.py

Symbols in `plugins/installed/payments/services/routing.py`.

- L33 `picker_gateways(user=None)` (function) — Presentation-ready list of enabled gateways for the checkout picker.
- L79 `resolve_gateway(selected_slug: str | None, *, user=None)` (function) — Return the gateway to charge for ``selected_slug``.
- L103 `create_payment_intent_for(order, selected_slug: str | None=None)` (function) — Create a payment intent for ``order`` via the chosen gateway.
- L129 `_record_gateway_slug(order, slug: str)` (function) — Persist the chosen gateway slug on the order (best-effort).
