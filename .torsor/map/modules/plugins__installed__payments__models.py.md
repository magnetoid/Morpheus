---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/payments/models.py

Symbols in `plugins/installed/payments/models.py`.

- L9 `PaymentGateway` (class)
- L29 `__str__(self)` (method)
- L33 `Payment` (class)
- L68 `__str__(self)` (method)
- L72 `StripeWebhookEvent` (class)
- L85 `__str__(self)` (method)
- L89 `PaymentMethod` (class)
- L104 `__str__(self)` (method)
- L108 `PaymentTransaction` (class)
- L124 `__str__(self)` (method)
- L133 `PaymentGatewayConfig` (class) — Per-gateway enable flag + free-form config for the Settings → Payments
- L152 `__str__(self)` (method)
- L156 `is_enabled(slug: str)` (function) — Whether a gateway is enabled. Unconfigured gateways fall back to
