"""Shipping services — quote rates for a cart given an address."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from djmoney.money import Money

logger = logging.getLogger('morpheus.shipping')


def _matching_zones(country: str, region: str = ''):
    from plugins.installed.shipping.models import ShippingZone
    matches = []
    for zone in ShippingZone.objects.all():
        if zone.matches(country, region):
            matches.append(zone)
    if matches:
        # Specific (regioned) > country-only > catch-all > default
        matches.sort(key=lambda z: (
            -len(z.regions), -len(z.countries), 0 if z.is_default else 1,
        ))
    else:
        matches = list(ShippingZone.objects.filter(is_default=True))
    return matches


def _quote_one(rate, *, subtotal: Money, total_weight_kg: Decimal = Decimal('0')) -> Optional[Money]:
    if not rate.is_active:
        return None
    if rate.computation == 'flat':
        return rate.flat_amount
    if rate.computation == 'free_over':
        if rate.free_threshold and subtotal.amount >= rate.free_threshold.amount:
            return Money(Decimal('0'), str(subtotal.currency))
        return rate.flat_amount
    if rate.computation == 'order_total_tier':
        return _tier_amount(rate.tiers, Decimal(subtotal.amount), str(subtotal.currency))
    if rate.computation == 'weight_tier':
        return _tier_amount(rate.tiers, total_weight_kg, str(subtotal.currency))
    if rate.computation.startswith('carrier_'):
        return _carrier_quote(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
    return None


def _tier_amount(tiers: list, value: Decimal, currency: str) -> Optional[Money]:
    """Walk tiers (sorted ascending by threshold) and return the matching amount."""
    chosen = None
    for tier in sorted(tiers, key=lambda t: Decimal(str(t.get('threshold', 0)))):
        if value >= Decimal(str(tier.get('threshold', 0))):
            chosen = tier
    if not chosen:
        return None
    return Money(Decimal(str(chosen.get('amount', 0))), currency)


def _carrier_quote(rate, *, subtotal: Money, total_weight_kg: Decimal):
    """Stub for carrier integrations. Return None if the adapter isn't configured."""
    logger.debug('shipping: carrier %s not yet implemented; treating as no-quote', rate.computation)
    return None


def list_available_rates(*, cart, country: str, region: str = ''):
    """Return all shippable rates for the cart + address."""
    items = list(cart.items.select_related('product').all())
    if not items:
        return []
    subtotal_amount = sum(
        Decimal(i.unit_price.amount) * i.quantity for i in items
    )
    currency = str(items[0].unit_price.currency)
    subtotal = Money(subtotal_amount, currency)

    def _weight_kg(product) -> Decimal:
        w = getattr(product, 'weight', None)
        if w is None:
            return Decimal('0')
        unit = (getattr(product, 'weight_unit', 'kg') or 'kg').lower()
        try:
            w_d = Decimal(str(w))
        except Exception:  # noqa: BLE001
            return Decimal('0')
        if unit in ('kg', 'kgs'):
            return w_d
        if unit in ('g', 'gram', 'grams'):
            return (w_d / Decimal('1000'))
        if unit in ('lb', 'lbs', 'pound', 'pounds'):
            return (w_d * Decimal('0.453592'))
        return w_d

    total_weight_kg = Decimal('0')
    for i in items:
        total_weight_kg += _weight_kg(i.product) * i.quantity

    out = []
    seen_zones = set()
    for zone in _matching_zones(country, region):
        if zone.id in seen_zones:
            continue
        seen_zones.add(zone.id)
        for rate in zone.rates.filter(is_active=True).order_by('priority'):
            amount = _quote_one(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
            if amount is None:
                continue
            out.append({
                'rate_id': str(rate.id),
                'name': rate.name,
                'amount': amount,
                'estimated_days_min': rate.estimated_days_min,
                'estimated_days_max': rate.estimated_days_max,
                'zone': zone.name,
            })
    return out


def quote_rate(*, cart, rate_id: str, country: str, region: str = ''):
    """Quote a specific rate by id."""
    rates = list_available_rates(cart=cart, country=country, region=region)
    return next((r for r in rates if r['rate_id'] == rate_id), None)
