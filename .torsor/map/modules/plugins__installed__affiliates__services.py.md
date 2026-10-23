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

# plugins/installed/affiliates/services.py

Symbols in `plugins/installed/affiliates/services.py`.

- L26 `_hash_ip(ip: str)` (function)
- L32 `HandleUnavailable` (class) — Raised when generate_unique_handle gives up after the retry budget.
- L40 `generate_unique_handle(customer, *, suggested: str='', max_tries: int=50)` (function) — Pick a unique `Affiliate.handle` slug for `customer`.
- L75 `_bare_host(netloc: str)` (function)
- L80 `store_path(raw: str, host: str)` (function) — The site-relative path a tracked link may land on, from what a partner pasted.
- L129 `redirect_target(landing_url: str, host: str)` (function) — Where ``/r/<code>`` sends a visitor: the stored landing page when it is a
- L138 `record_click(*, code: str, referer: str='', user_agent: str='', ip: str='')` (function)
- L165 `_resolve_attribution_link(*, affiliate_code: str, coupon_code: str)` (function) — Resolve the AffiliateLink for an order, returning ``(link, via)``.
- L201 `attribute_order(*, order, affiliate_code: str='', coupon_code: str='')` (function) — Create an AffiliateConversion for ``order``.
- L299 `clawback_on_refund(*, order)` (function) — Reverse an affiliate conversion when its order is refunded.
- L360 `effective_tier(program, approved_conversions: int)` (function) — Highest commission tier the affiliate has reached, or None.
- L385 `_affiliate_flat_override_percent(affiliate)` (function) — Per-affiliate flat % override stored as a Metafield by the dashboard
- L413 `_base_percent(*, program, affiliate)` (function) — The applicable base percent for an affiliate before per-category
- L426 `_next_tier(program, approved: int, percent: Decimal)` (function) — The nearest tier above ``approved`` approved orders that pays more.
- L450 `_category_rates(program)` (function) — The program's per-category rates, named, highest first.
- L468 `commission_summary(affiliate)` (function) — The rate this affiliate earns now and what would lift it.
- L500 `_product_category_slugs(product)` (function) — Lower-cased category slugs a product belongs to (primary first, then
- L518 `_calculate_commission(*, program, order, affiliate=None)` (function) — Commission for ``order`` under ``program`` for ``affiliate``.
- L577 `_safe_decimal(v)` (function)
- L584 `maybe_auto_approve(affiliate)` (function) — Auto-approve a *pending* affiliate once they hit the program's
- L615 `approve_conversion(conversion)` (function)
- L628 `request_payout(*, affiliate, amount: Money, method: str='')` (function)
- L643 `pending_payout_amount(affiliate)` (function) — Sum of approved-but-unpaid conversion commissions for ``affiliate``.
- L666 `program_defaults()` (function) — What a new AffiliateProgram starts from: the three keys on Settings →
- L688 `min_payout_threshold(affiliate)` (function) — The program's ``minimum_payout``, else the settings-panel threshold.
- L705 `has_pending_payout(affiliate)` (function)
- L714 `request_affiliate_payout(affiliate, amount: Money | None=None, method: str='')` (function) — Self-service payout: bundle unpaid approved conversions into one row.
- L770 `mark_payout_paid(payout, *, external_reference: str='')` (function)
- L787 `_affiliate_coupon_taken(code: str)` (function) — True if a coupon code is already an affiliate link's code, or — fail-soft —
- L805 `affiliate_coupon(affiliate, *, claim: bool=False)` (function) — The affiliate's personal coupon code, or '' if none yet.
