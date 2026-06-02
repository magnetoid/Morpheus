---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/payments/services/routing.py

Symbols in `plugins/installed/payments/services/routing.py`.

- L33 `picker_gateways()` (function) — Presentation-ready list of enabled gateways for the checkout picker.
- L79 `resolve_gateway(selected_slug: str | None)` (function) — Return the gateway to charge for ``selected_slug``.
- L103 `create_payment_intent_for(order, selected_slug: str | None=None)` (function) — Create a payment intent for ``order`` via the chosen gateway.
- L126 `_record_gateway_slug(order, slug: str)` (function) — Persist the chosen gateway slug on the order (best-effort).
