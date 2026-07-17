# Loyalty redemption — remaining checkout wiring (Wave 1.3)

**Status:** spec'd, not started. Money path — ships as its own focused release
(own tests, own deploy). Do NOT bundle with unrelated changes.

## What already exists (verified 2026-07-18)

- `services_redeem.redeem_points(customer, points, *, order=None, reason='')`
  ([services_redeem.py:124](../../plugins/installed/loyalty_points/services_redeem.py#L124))
  — writes one negative `PointsTransaction(reason='spend_order', order_number=…)`,
  returns the discount `Money`. Raises `ValueError` on non-positive / over-balance.
  **Idempotency is the caller's job** (dedupe on `order_number` before calling).
- `reverse_redemption(customer, points, *, order=None, reason='')`
  ([services_redeem.py:168](../../plugins/installed/loyalty_points/services_redeem.py#L168))
  — the cancel/refund undo.
- `max_redeemable(customer, order_total)` — the cap.
- `on_cart_breakdown` ([plugin.py:152](../../plugins/installed/loyalty_points/plugin.py#L152))
  **already** reads `cart.metadata['loyalty_points_redeem']` (int), converts to a
  discount, and stashes `meta['loyalty_points'] = {'points', 'amount'}`.
  Tested: `tests/test_redeem.py:148`.

So the discount **math + breakdown are done**. The gaps are the two ends:
setting the redeem amount, and consuming it at order time.

## Gap A — cart-side apply/remove endpoints (owner: loyalty_points)

Write `cart.metadata['loyalty_points_redeem']` (int), bounded by
`max_redeemable(customer, order_total)`; `remove` clears it.

- Add to `loyalty_points/urls.py`: `checkout/points/apply/` + `checkout/points/remove/`
  (root-mounted, so disable-safe — 404 when the plugin is off).
- Add `apply_points` / `remove_points` views in `loyalty_points/views.py`.
  Resolve the active cart the way orders' other checkout endpoints do (find the
  cart resolver in `plugins/installed/orders/` — do NOT re-implement it).
  Auth-only (redeem requires an authenticated customer). Clamp to
  `max_redeemable`. Return JSON on both success and failure
  (dashboard-ajax-json-contract landmine) — these are AJAX from the cart.
- Storefront trigger: a `StorefrontBlock(slot='cart_summary_extra')` "use my
  points" control (same slot as the free-shipping bar) OR a checkout control —
  pick the slot the checkout total actually renders, verify with a grep.

## Gap B — order-time debit (the money-critical half; touches orders plugin)

Mirror the gift-card redeem block at
[orders/services.py:474-504](../../plugins/installed/orders/services.py#L474-L504),
immediately after it, inside the same atomic block:

```python
loyalty_meta = (breakdown.get('meta') or {}).get('loyalty_points') or {}
customer = getattr(cart, 'customer', None)
if loyalty_meta and customer is not None:
    try:
        from plugins.installed.loyalty_points.services_redeem import redeem_points
        from plugins.installed.loyalty_points.models import PointsTransaction

        pts = int(loyalty_meta.get('points') or 0)
        already = PointsTransaction.objects.filter(
            customer=customer, reason='spend_order', order_number=order.order_number
        ).exists()
        if pts > 0 and not already:
            redeem_points(customer, pts, order=order, reason=f'Order {order.order_number}')
    except (ValueError, ImportError) as e:
        logger.warning('orders: loyalty redeem failed for order %s: %s',
                       order.order_number, e, exc_info=True)
        raise LoyaltyRedeemFailed(  # new exc, sibling of GiftCardRedeemFailed
            'Your points could not be applied. Please review your cart and try again.'
        ) from e
```

Rationale for raise-not-swallow: the discount is already baked into
`order.total`; if the debit fails we'd charge the discounted amount without
consuming points → money leak. Aborting rolls back the atomic block (same logic
as gift cards). Disable-safe: when loyalty is off its breakdown hook doesn't
fire, so `meta['loyalty_points']` is absent and the block is skipped.

## Gap C — reversal on cancel/refund

Loyalty subscribes to the order-cancelled/refunded hook and calls
`reverse_redemption`. Find the hook orders fires on cancel (the v0.16.0
`account_order_cancel` → `order.cancel()` path). If no suitable hook exists,
that's a small orders-side hook addition. Dedupe the reversal the same way.

## Tests (all `DATABASE_URL='sqlite:///:memory:'`)

- apply endpoint clamps to `max_redeemable`; anon blocked; JSON on both paths.
- remove clears the key.
- order-creation with `meta['loyalty_points']` writes exactly one negative
  `PointsTransaction`; balance drops by the spent points.
- **idempotency**: a second create with the same order_number does NOT
  double-debit.
- insufficient balance at order time → order aborts (rolls back), no charge.
- cancel/refund reverses the spend (one positive txn, balance restored).
- disable test: loyalty off → no `checkout/points/` routes, order-time block skipped.

Every merge bumps `MORPHEUS_VERSION` + release note.
