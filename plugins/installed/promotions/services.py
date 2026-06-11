"""Promotion evaluator.

Public surface:

    evaluate(cart, *, channel=None, customer=None, country=None, coupon=None)
        → list[AppliedPromotion]

Each AppliedPromotion carries the matched Promotion, the rule, the
discount amount, and a free_shipping flag. Callers (cart-total hook,
checkout, draft orders) decide how to apply.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils import timezone

logger = logging.getLogger('morpheus.promotions')


@dataclass
class AppliedPromotion:
    promotion_id: str
    promotion_name: str
    rule_id: str | None
    discount_amount: Decimal = Decimal('0')
    free_shipping: bool = False
    gift_product_id: str | None = None
    note: str = ''


def _cart_subtotal(cart) -> Decimal:
    """Best-effort subtotal extraction from arbitrary cart-like objects."""
    if cart is None:
        return Decimal('0')
    for attr in ('subtotal_amount', 'subtotal', 'total_amount', 'total'):
        v = getattr(cart, attr, None)
        if v is None:
            continue
        amount = getattr(v, 'amount', v)
        try:
            return Decimal(str(amount))
        except Exception:  # noqa: BLE001, S112
            continue
    items = cart.get('items', []) if isinstance(cart, dict) else getattr(cart, 'items', None)
    total = Decimal('0')
    for it in items or []:
        price = it.get('price') if isinstance(it, dict) else getattr(it, 'price', None)
        qty = it.get('quantity', 1) if isinstance(it, dict) else getattr(it, 'quantity', 1)
        amount = getattr(price, 'amount', price) if price is not None else 0
        try:
            total += Decimal(str(amount)) * Decimal(str(qty or 1))
        except Exception:  # noqa: BLE001, S112
            continue
    return total


def _cart_currency(cart, default: str = 'USD') -> str:
    for attr in ('currency', 'currency_code'):
        v = getattr(cart, attr, None)
        if v:
            return str(v)
    if isinstance(cart, dict):
        return str(cart.get('currency') or default)
    return default


def _cart_product_ids(cart) -> list[str]:
    items = cart.get('items', []) if isinstance(cart, dict) else getattr(cart, 'items', None)
    out: list[str] = []
    for it in items or []:
        if isinstance(it, dict):
            pid = it.get('product_id')
        else:
            pid = getattr(it, 'product_id', None)
            if not pid and getattr(it, 'product', None):
                pid = str(getattr(it.product, 'id', ''))
        if pid:
            out.append(str(pid))
    return out


def _matches(predicates: dict, *, cart, channel, customer, country, coupon) -> bool:  # noqa: PLR0911
    if not predicates:
        return True
    subtotal = _cart_subtotal(cart)
    currency = _cart_currency(cart)

    if 'min_subtotal' in predicates and subtotal < Decimal(str(predicates['min_subtotal'])):
        return False
    if 'max_subtotal' in predicates and subtotal > Decimal(str(predicates['max_subtotal'])):
        return False
    if 'currencies' in predicates and currency not in predicates['currencies']:
        return False
    if 'countries' in predicates and (country or '').upper() not in [
        c.upper() for c in predicates['countries']
    ]:
        return False
    if 'customer_groups' in predicates:
        groups = list(getattr(customer, 'groups', []) or [])
        if isinstance(customer, dict):
            groups = list(customer.get('groups') or [])
        if not any(g in predicates['customer_groups'] for g in (str(x) for x in groups)):
            return False
    if 'product_ids' in predicates:
        cart_pids = set(_cart_product_ids(cart))
        if not cart_pids.intersection(set(str(x) for x in predicates['product_ids'])):
            return False
    if predicates.get('first_order') and getattr(customer, 'order_count', 0) > 0:  # noqa: SIM103
        return False
    return True


def _apply_action(  # noqa: PLR0911
    action: dict,
    *,
    subtotal: Decimal,
    cart: Any = None,
) -> tuple[Decimal, bool, str | None]:
    """Compute the discount amount + flags for one rule action.

    Returns ``(discount, free_shipping, gift_product_id)`` where the
    discount is positive (caller subtracts).

    Supported kinds:

    - ``percent_off`` ``{"kind": "percent_off", "value": 10}`` —
      flat 10% off subtotal.
    - ``fixed_off`` ``{"kind": "fixed_off", "value": 5}`` — flat $5 off.
    - ``free_shipping`` ``{"kind": "free_shipping"}``.
    - ``gift`` ``{"kind": "gift", "product_id": "…"}`` — customer gets
      a free product (caller adds the line item).
    - ``bogo`` ``{"kind": "bogo", "buy_qty": 2, "free_qty": 1,
      "product_ids": ["…"]}`` — for every ``buy_qty`` of any listed
      product, ``free_qty`` of the cheapest line item among them is
      free. Defaults: buy 2 free 1, all products eligible if no
      product_ids supplied.
    - ``tiered`` ``{"kind": "tiered", "tiers": [
        {"min_qty": 3, "percent": 10},
        {"min_qty": 5, "percent": 15},
      ]}`` — buy-more-save-more; matches the highest-min_qty tier
      whose threshold the cart satisfies. ``min_qty`` is total cart
      item count.

    Threshold ("free shipping over $X") is expressible today via the
    rule's `predicates.min_subtotal` + a `free_shipping` action — no
    new kind needed.
    """
    kind = (action or {}).get('kind')
    if kind == 'percent_off':
        pct = Decimal(str(action.get('value', 0)))
        return (subtotal * pct / Decimal('100')).quantize(Decimal('0.01')), False, None
    if kind == 'fixed_off':
        return Decimal(str(action.get('value', 0))).quantize(Decimal('0.01')), False, None
    if kind == 'free_shipping':
        return Decimal('0'), True, None
    if kind == 'gift':
        return Decimal('0'), False, str(action.get('product_id') or '')
    if kind == 'bogo':
        return _apply_bogo(action, cart=cart), False, None
    if kind == 'tiered':
        return _apply_tiered(action, subtotal=subtotal, cart=cart), False, None
    return Decimal('0'), False, None


def _apply_bogo(action: dict, *, cart: Any) -> Decimal:
    """Buy ``buy_qty`` get ``free_qty`` free across the eligible product set.

    Algorithm:
      1. Filter cart line items to those in ``product_ids`` (or all if
         the list is empty/missing).
      2. Expand each line into per-unit prices (cheaper units come
         first so the customer doesn't get gamed by ordering).
      3. Total qualifying units = sum of quantities.
      4. Sets = total // (buy_qty + free_qty); the cheapest
         ``sets * free_qty`` units are discounted at full price.

    Cart-less call (e.g. tests) returns 0.
    """
    if cart is None:
        return Decimal('0')
    buy_qty = max(1, int(action.get('buy_qty', 2) or 2))
    free_qty = max(1, int(action.get('free_qty', 1) or 1))
    eligible_ids = {str(x) for x in (action.get('product_ids') or [])}

    units: list[Decimal] = []
    try:
        items = cart.items.all() if hasattr(cart, 'items') else []
    except Exception:  # noqa: BLE001
        items = []
    for it in items:
        pid = str(getattr(getattr(it, 'product', None), 'id', '') or '')
        if eligible_ids and pid not in eligible_ids:
            continue
        unit = Decimal(str(getattr(it.unit_price, 'amount', it.unit_price)))
        for _ in range(int(it.quantity)):
            units.append(unit)
    if not units:
        return Decimal('0')
    units.sort()  # cheapest first
    bundle_size = buy_qty + free_qty
    sets = len(units) // bundle_size
    if sets == 0:
        return Decimal('0')
    free_units = sets * free_qty
    discount = sum(units[:free_units], Decimal('0'))
    return discount.quantize(Decimal('0.01'))


def _apply_tiered(action: dict, *, subtotal: Decimal, cart: Any) -> Decimal:
    """Find the highest tier whose `min_qty` the cart satisfies and
    apply its percent off the subtotal."""
    tiers = action.get('tiers') or []
    if not tiers:
        return Decimal('0')
    total_qty = 0
    try:
        for it in cart.items.all() if cart and hasattr(cart, 'items') else []:
            total_qty += int(it.quantity)
    except Exception:  # noqa: BLE001
        total_qty = 0
    best_pct = Decimal('0')
    for tier in tiers:
        min_qty = int(tier.get('min_qty', 0) or 0)
        pct = Decimal(str(tier.get('percent', 0)))
        if total_qty >= min_qty and pct > best_pct:
            best_pct = pct
    if best_pct <= 0:
        return Decimal('0')
    return (subtotal * best_pct / Decimal('100')).quantize(Decimal('0.01'))


def evaluate(
    cart,
    *,
    channel: Any = None,
    customer: Any = None,
    country: str | None = None,
    coupon: str | None = None,
) -> list[AppliedPromotion]:
    from plugins.installed.promotions.models import Promotion

    now = timezone.now()
    qs = Promotion.objects.filter(is_active=True).prefetch_related('rules')
    qs = qs.filter(models_q_active(now))
    channel_slug = getattr(channel, 'slug', None) if channel is not None else None

    out: list[AppliedPromotion] = []
    subtotal = _cart_subtotal(cart)

    for promo in qs.order_by('priority'):
        if promo.channels and channel_slug and channel_slug not in promo.channels:
            continue
        if promo.requires_coupon and (
            not coupon or coupon.lower() != promo.requires_coupon.lower()
        ):
            continue
        if promo.usage_limit and promo.times_used >= promo.usage_limit:
            continue
        for rule in promo.rules.all():
            if not _matches(
                rule.predicates or {},
                cart=cart,
                channel=channel,
                customer=customer,
                country=country,
                coupon=coupon,
            ):
                continue
            amount, free_ship, gift_pid = _apply_action(
                rule.action or {},
                subtotal=subtotal,
                cart=cart,
            )
            out.append(
                AppliedPromotion(
                    promotion_id=str(promo.id),
                    promotion_name=promo.name,
                    rule_id=str(rule.id),
                    discount_amount=amount,
                    free_shipping=free_ship,
                    gift_product_id=gift_pid,
                    note=rule.label or '',
                )
            )
            break  # one rule per promo
    return out


def models_q_active(now):
    """Promotions where (starts_at is null or starts_at <= now) AND (ends_at is null or ends_at > now)."""
    from django.db.models import Q

    return (Q(starts_at__isnull=True) | Q(starts_at__lte=now)) & (
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    )


def record_application(
    applied: AppliedPromotion, *, order_id: str = '', customer_id: str = '', currency: str = 'USD'
) -> None:
    """Persist a PromotionApplication + bump times_used atomically.

    Lock the Promotion row inside an atomic block so two concurrent
    checkouts that both read `times_used=N, limit=N+1` can't both pass
    the limit check and both increment. The lock is short (one
    INSERT + one UPDATE on a single row) and only contends when the
    same promo fires for multiple orders in the same instant — for
    high-traffic flash sales, exactly the case where bypassing the
    limit matters.
    """
    from django.db import transaction as db_tx

    from plugins.installed.promotions.models import Promotion, PromotionApplication

    try:
        with db_tx.atomic():
            promo = Promotion.objects.select_for_update().filter(id=applied.promotion_id).first()
            if promo is None:
                return
            if promo.usage_limit and promo.times_used >= promo.usage_limit:
                # Lost the race — another checkout claimed the last slot.
                # Record the attempt without bumping the counter so audits
                # can surface why this customer didn't get the discount.
                logger.info(
                    'promotions: usage_limit reached for %s under concurrency; '
                    'discount NOT applied to order=%s',
                    applied.promotion_id,
                    order_id,
                )
                return
            PromotionApplication.objects.create(
                promotion_id=applied.promotion_id,
                rule_id=applied.rule_id,
                order_id=order_id,
                customer_id=customer_id,
                discount_amount=applied.discount_amount,
                currency=currency,
            )
            promo.times_used = (promo.times_used or 0) + 1
            promo.save(update_fields=['times_used'])
    except Exception as e:  # noqa: BLE001
        logger.warning('promotions: record_application failed: %s', e, exc_info=True)


def models_f_inc(field_name):
    from django.db.models import F

    return F(field_name) + 1
