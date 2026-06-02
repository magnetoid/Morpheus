---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/shipping/services.py

Symbols in `plugins/installed/shipping/services.py`.

- L13 `_matching_zones(country: str, region: str='')` (function)
- L29 `_quote_one(rate, *, subtotal: Money, total_weight_kg: Decimal=Decimal('0'))` (function)
- L47 `_tier_amount(tiers: list, value: Decimal, currency: str)` (function) — Walk tiers (sorted ascending by threshold) and return the matching amount.
- L58 `_carrier_quote(rate, *, subtotal: Money, total_weight_kg: Decimal)` (function) — Carrier-API quote. Routes by rate.computation:
- L84 `_shipping_config()` (function) — Resolve the shipping plugin's PluginConfig.config_data, fail-soft.
- L94 `_shippo_quote(rate, *, subtotal: Money, total_weight_kg: Decimal)` (function) — Live rate from Shippo's REST API. ~1 RTT, cached at the cart layer.
- L193 `_easypost_quote(rate, *, subtotal: Money, total_weight_kg: Decimal)` (function) — Live rate from EasyPost. Mirrors Shippo's shape — same envelope,
- L277 `_bookvault_quote(rate, *, subtotal: Money, total_weight_kg: Decimal)` (function) — Live rate from Bookvault's POD shipping API.
- L329 `list_available_rates(*, cart, country: str, region: str='')` (function) — Return all shippable rates for the cart + address.
- L389 `quote_rate(*, cart, rate_id: str, country: str, region: str='')` (function) — Quote a specific rate by id.
