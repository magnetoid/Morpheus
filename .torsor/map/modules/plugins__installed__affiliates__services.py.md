---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/affiliates/services.py

Symbols in `plugins/installed/affiliates/services.py`.

- L25 `_hash_ip(ip: str)` (function)
- L31 `HandleUnavailable` (class) — Raised when generate_unique_handle gives up after the retry budget.
- L39 `generate_unique_handle(customer, *, suggested: str='', max_tries: int=50)` (function) — Pick a unique `Affiliate.handle` slug for `customer`.
- L74 `record_click(*, code: str, referer: str='', user_agent: str='', ip: str='')` (function)
- L101 `_resolve_attribution_link(*, affiliate_code: str, coupon_code: str)` (function) — Resolve the AffiliateLink for an order, returning ``(link, via)``.
- L137 `attribute_order(*, order, affiliate_code: str='', coupon_code: str='')` (function) — Create an AffiliateConversion for ``order``.
- L235 `clawback_on_refund(*, order)` (function) — Reverse an affiliate conversion when its order is refunded.
- L296 `effective_tier(program, approved_conversions: int)` (function) — Highest commission tier the affiliate has reached, or None.
- L321 `_affiliate_flat_override_percent(affiliate)` (function) — Per-affiliate flat % override stored as a Metafield by the dashboard
- L349 `_base_percent(*, program, affiliate)` (function) — The applicable base percent for an affiliate before per-category
- L362 `_product_category_slugs(product)` (function) — Lower-cased category slugs a product belongs to (primary first, then
- L380 `_calculate_commission(*, program, order, affiliate=None)` (function) — Commission for ``order`` under ``program`` for ``affiliate``.
- L439 `_safe_decimal(v)` (function)
- L446 `maybe_auto_approve(affiliate)` (function) — Auto-approve a *pending* affiliate once they hit the program's
- L477 `approve_conversion(conversion)` (function)
- L490 `request_payout(*, affiliate, amount: Money, method: str='')` (function)
- L505 `pending_payout_amount(affiliate)` (function) — Sum of approved-but-unpaid conversion commissions for ``affiliate``.
- L525 `has_pending_payout(affiliate)` (function)
- L534 `request_affiliate_payout(affiliate, amount: Money | None=None, method: str='')` (function) — Self-service payout: bundle unpaid approved conversions into one row.
- L587 `mark_payout_paid(payout, *, external_reference: str='')` (function)
