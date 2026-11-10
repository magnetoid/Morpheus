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
    gift_variant_id: str | None = None
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


def _customer_groups(customer) -> set[str]:
    """Group names for ``customer``: a Customer's auth groups, or a dict's list."""
    if customer is None:
        return set()
    if isinstance(customer, dict):
        return {str(g) for g in (customer.get('groups') or [])}
    groups = getattr(customer, 'groups', None)
    if groups is None:
        return set()
    if hasattr(groups, 'values_list'):
        # Customer.groups is a related manager; iterating it raised TypeError,
        # which the cart step swallowed, so every promotion was skipped for a
        # signed-in shopper whenever one rule named a group (until v0.150.0).
        return {str(g) for g in groups.values_list('name', flat=True)}
    return {str(g) for g in groups}


def _is_first_order(customer) -> bool:
    """A signed-in customer with no order that counts. A guest has no history
    the store can check, so a first-order rule never matches one."""
    if customer is None:
        return False
    if isinstance(customer, dict):
        return int(customer.get('order_count') or 0) == 0
    if int(getattr(customer, 'purchase_count', 0) or 0) > 0:
        return False
    orders = getattr(customer, 'orders', None)
    if orders is None:
        return True
    return not orders.exclude(status='cancelled').exists()


def _cart_lines(cart) -> list:
    """Cart lines as model rows (an ``items`` manager) or a plain list."""
    if cart is None:
        return []
    if isinstance(cart, dict):
        return list(cart.get('items') or [])
    items = getattr(cart, 'items', None)
    if items is None:
        return []
    if hasattr(items, 'all'):
        return list(items.select_related('product', 'variant').all())
    return list(items)


def _in_category_slugs(cart, slugs) -> bool:
    """A cart line whose product sits in one of the categories named by
    ``slugs``, or in a category below one (``catalog/category_tree.py``)."""
    from plugins.installed.catalog.category_tree import subtree_ids
    from plugins.installed.catalog.models import Category

    roots = Category.objects.filter(slug__in=[str(s) for s in slugs or []], is_active=True)
    ids = subtree_ids(roots)
    if not ids:
        return False
    for it in _cart_lines(cart):
        product = it.get('product') if isinstance(it, dict) else getattr(it, 'product', None)
        if product is None or isinstance(product, (str, dict)):
            continue
        if product.category_id in ids:
            return True
        if product.additional_categories.filter(pk__in=ids).exists():
            return True
    return False


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
        wanted = {str(g) for g in predicates['customer_groups'] or []}
        if not wanted.intersection(_customer_groups(customer)):
            return False
    if 'product_ids' in predicates:
        cart_pids = set(_cart_product_ids(cart))
        if not cart_pids.intersection(set(str(x) for x in predicates['product_ids'])):
            return False
    if predicates.get('category_slugs') and not _in_category_slugs(
        cart, predicates['category_slugs']
    ):
        return False
    if predicates.get('first_order') and not _is_first_order(customer):  # noqa: SIM103
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
        value = Decimal(str(action.get('value', 0))).quantize(Decimal('0.01'))
        return min(value, subtotal), False, None
    if kind == 'free_shipping':
        return Decimal('0'), True, None
    if kind == 'gift':
        return Decimal('0'), False, str(action.get('product_id') or '')
    if kind == 'bogo':
        return _apply_bogo(action, cart=cart), False, None
    if kind == 'tiered':
        return _apply_tiered(action, subtotal=subtotal, cart=cart), False, None
    return Decimal('0'), False, None


def buy_x_get_y_discount(lines, *, buy_qty: int, free_qty: int, percent=100) -> Decimal:
    """For every ``buy_qty`` units bought, ``free_qty`` more get ``percent`` off.

    The lines' units are pooled and sorted cheapest first, so a shopper can't
    game it by ordering; each full set of ``buy_qty + free_qty`` units makes the
    cheapest ``free_qty`` of the pool discounted. Shared by the ``bogo`` rule and
    the Buy X get Y coupon.
    """
    buy_qty = max(1, int(buy_qty or 1))
    free_qty = max(1, int(free_qty or 1))
    pct = Decimal(str(percent or 0))
    if pct <= 0 or pct > 100:
        pct = Decimal('100')
    units: list[Decimal] = []
    for it in lines:
        unit = Decimal(str(getattr(it.unit_price, 'amount', it.unit_price)))
        units.extend([unit] * int(it.quantity))
    sets = len(units) // (buy_qty + free_qty)
    if not sets:
        return Decimal('0')
    units.sort()  # cheapest first
    free = sum(units[: sets * free_qty], Decimal('0'))
    return (free * pct / Decimal('100')).quantize(Decimal('0.01'))


def _apply_bogo(action: dict, *, cart: Any) -> Decimal:
    """Buy ``buy_qty`` get ``free_qty`` free across the eligible product set
    (``product_ids``, or every line when the list is empty). Cart-less call
    (e.g. tests) returns 0."""
    if cart is None:
        return Decimal('0')
    eligible_ids = {str(x) for x in (action.get('product_ids') or [])}
    lines = [
        it
        for it in _cart_lines(cart)
        if not isinstance(it, dict)
        and (
            not eligible_ids
            or str(getattr(getattr(it, 'product', None), 'id', '') or '') in eligible_ids
        )
    ]
    return buy_x_get_y_discount(
        lines,
        buy_qty=action.get('buy_qty', 2) or 2,
        free_qty=action.get('free_qty', 1) or 1,
        percent=action.get('percent', 100),
    )


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
    coupon_applied: bool = False,
) -> list[AppliedPromotion]:
    """The promotions that apply to ``cart``, lowest priority number first.

    A promotion with ``combinable`` off applies only when nothing applied before
    it and ``coupon_applied`` is False (a code the shopper typed always applies;
    a promotion that the same code unlocks is that code's own and still
    combines), and no promotion after it applies. Each promotion is evaluated on
    its own, so a rule that fails to evaluate skips that promotion only.
    """
    from plugins.installed.promotions.models import Promotion

    now = timezone.now()
    qs = Promotion.objects.filter(is_active=True).prefetch_related('rules')
    qs = qs.filter(models_q_active(now))
    channel_slug = getattr(channel, 'slug', None) if channel is not None else None

    out: list[AppliedPromotion] = []
    subtotal = _cart_subtotal(cart)

    for promo in qs.order_by('priority', 'created_at'):
        if promo.channels and channel_slug and channel_slug not in promo.channels:
            continue
        unlocked_by_coupon = bool(promo.requires_coupon)
        if promo.requires_coupon and (
            not coupon or coupon.lower() != promo.requires_coupon.lower()
        ):
            continue
        if promo.usage_limit and promo.times_used >= promo.usage_limit:
            continue
        exclusive = not promo.combinable
        if exclusive and (out or (coupon_applied and not unlocked_by_coupon)):
            continue
        try:
            applied = _first_matching_rule(
                promo,
                cart=cart,
                channel=channel,
                customer=customer,
                country=country,
                coupon=coupon,
                subtotal=subtotal,
            )
        except Exception as e:  # noqa: BLE001 — one broken rule skips its own promotion
            logger.warning('promotions: %s skipped: %s', promo.slug, e, exc_info=True)
            continue
        if applied is None:
            continue
        out.append(applied)
        if exclusive:
            break
    return out


def _first_matching_rule(promo, *, cart, channel, customer, country, coupon, subtotal):
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
        return AppliedPromotion(
            promotion_id=str(promo.id),
            promotion_name=promo.name,
            rule_id=str(rule.id),
            discount_amount=amount,
            free_shipping=free_ship,
            gift_product_id=gift_pid,
            gift_variant_id=str((rule.action or {}).get('variant_id') or '') or None,
            note=rule.label or '',
        )
    return None


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
