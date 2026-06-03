"""Shipping services — quote rates for a cart given an address."""

from __future__ import annotations

import logging
from decimal import Decimal

from djmoney.money import Money

logger = logging.getLogger('morpheus.shipping')


def _matching_zones(country: str, region: str = ''):
    from plugins.installed.shipping.models import ShippingZone  # noqa: PLC0415

    matches = []
    for zone in ShippingZone.objects.all():
        if zone.matches(country, region):
            matches.append(zone)
    if matches:
        # Specific (regioned) > country-only > catch-all > default
        matches.sort(
            key=lambda z: (
                -len(z.regions),
                -len(z.countries),
                0 if z.is_default else 1,
            )
        )
    else:
        matches = list(ShippingZone.objects.filter(is_default=True))
    return matches


def _quote_one(rate, *, subtotal: Money, total_weight_kg: Decimal = Decimal('0')) -> Money | None:  # noqa: PLR0911
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


def _tier_amount(tiers: list, value: Decimal, currency: str) -> Money | None:
    """Walk tiers (sorted ascending by threshold) and return the matching amount."""
    chosen = None
    for tier in sorted(tiers, key=lambda t: Decimal(str(t.get('threshold', 0)))):
        if value >= Decimal(str(tier.get('threshold', 0))):
            chosen = tier
    if not chosen:
        return None
    return Money(Decimal(str(chosen.get('amount', 0))), currency)


def _carrier_quote(rate, *, subtotal: Money, total_weight_kg: Decimal):
    """Carrier-API quote. Routes by rate.computation:

      * carrier_shippo   → Shippo (https://goshippo.com)
      * carrier_easypost → EasyPost (https://easypost.com)
      * any other        → no quote (returns None)

    All adapters fail-soft — missing API key, network error, malformed
    response → log + return None. The caller treats no-quote as "this
    rate is unavailable for this cart" and skips it.

    Carrier credentials come from the shipping plugin's config:
      shipping.config:
        shippo_api_key, shippo_default_address (origin),
        easypost_api_key, easypost_default_address.
    """
    if rate.computation == 'carrier_shippo':
        return _shippo_quote(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
    if rate.computation == 'carrier_easypost':
        return _easypost_quote(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
    if rate.computation == 'carrier_bookvault':
        return _bookvault_quote(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
    logger.debug('shipping: unknown carrier rule %s', rate.computation)
    return None


def _shipping_config() -> dict:
    """Resolve the shipping plugin's PluginConfig.config, fail-soft."""
    try:
        from plugins.models import PluginConfig  # noqa: PLC0415

        cfg = PluginConfig.objects.filter(plugin_name='shipping').first()
        return dict(cfg.config or {}) if cfg else {}
    except Exception:  # noqa: BLE001
        return {}


def _shippo_quote(rate, *, subtotal: Money, total_weight_kg: Decimal):  # noqa: PLR0911
    """Live rate from Shippo's REST API. ~1 RTT, cached at the cart layer.

    Each ShippingRate row carries the Shippo `servicelevel.token` it
    represents (e.g. ``usps_priority``) in `metadata`. We send a single
    Shipment to Shippo and return the matching rate. If the row's token
    is empty, we return the cheapest available rate from any carrier.
    """
    cfg = _shipping_config()
    api_key = (cfg.get('shippo_api_key') or '').strip()
    if not api_key:
        logger.debug('shippo: no api key configured')
        return None
    origin = cfg.get('shippo_default_address') or {}
    if not (origin.get('country') and origin.get('zip')):
        logger.debug('shippo: origin address missing country/zip')
        return None

    metadata = getattr(rate, 'metadata', None) or {}
    token = (metadata.get('shippo_servicelevel') or '').strip()

    try:
        import requests  # noqa: PLC0415
    except ImportError:
        logger.warning('shippo: `requests` not installed')
        return None

    # Customer address must come from the cart shipping address; we
    # accept either pre-resolved on the cart metadata or a fallback to
    # the rate's zone country (cheap, but a real rate needs an actual
    # postcode + city).
    cart_meta = getattr(getattr(rate, '_cart', None), 'metadata', None) or {}
    dest = cart_meta.get('shipping_address') or {}
    if not (dest.get('country') and dest.get('zip', dest.get('postal_code'))):
        logger.debug('shippo: destination missing country + zip')
        return None

    weight_kg = max(total_weight_kg, Decimal('0.05'))  # Shippo rejects 0
    weight_g = int(weight_kg * Decimal('1000'))

    payload = {
        'address_from': {
            'name': origin.get('name', 'Warehouse'),
            'street1': origin.get('street1', origin.get('line1', '')),
            'city': origin.get('city', ''),
            'state': origin.get('state', ''),
            'zip': origin.get('zip', origin.get('postal_code', '')),
            'country': origin.get('country', 'US'),
        },
        'address_to': {
            'name': dest.get('name', 'Customer'),
            'street1': dest.get('street1', dest.get('line1', '')),
            'city': dest.get('city', ''),
            'state': dest.get('state', ''),
            'zip': dest.get('zip', dest.get('postal_code', '')),
            'country': dest.get('country', ''),
        },
        'parcels': [
            {
                'length': '10',
                'width': '10',
                'height': '10',
                'distance_unit': 'cm',
                'weight': str(weight_g),
                'mass_unit': 'g',
            }
        ],
        'async': False,
    }
    try:
        resp = requests.post(
            'https://api.goshippo.com/shipments/',
            json=payload,
            headers={'Authorization': f'ShippoToken {api_key}'},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001 — log + soft-fail
        logger.warning('shippo: API call failed: %s', e)
        return None

    rates_returned = data.get('rates') or []
    if not rates_returned:
        return None

    # Filter to the merchant-selected service level if one is bound.
    if token:
        rates_returned = [
            r for r in rates_returned if (r.get('servicelevel') or {}).get('token') == token
        ]
        if not rates_returned:
            return None

    cheapest = min(rates_returned, key=lambda r: Decimal(str(r.get('amount') or '0')))
    try:
        amount = Decimal(str(cheapest.get('amount') or '0'))
    except Exception:  # noqa: BLE001
        return None
    currency = cheapest.get('currency') or str(subtotal.currency)
    return Money(amount, currency)


def _easypost_quote(rate, *, subtotal: Money, total_weight_kg: Decimal):  # noqa: PLR0911
    """Live rate from EasyPost. Mirrors Shippo's shape — same envelope,
    different endpoint + auth.
    """
    cfg = _shipping_config()
    api_key = (cfg.get('easypost_api_key') or '').strip()
    if not api_key:
        return None
    origin = cfg.get('easypost_default_address') or cfg.get('shippo_default_address') or {}
    if not (origin.get('country') and origin.get('zip', origin.get('postal_code'))):
        return None

    try:
        import requests  # noqa: PLC0415
    except ImportError:
        return None

    cart_meta = getattr(getattr(rate, '_cart', None), 'metadata', None) or {}
    dest = cart_meta.get('shipping_address') or {}
    if not (dest.get('country') and dest.get('zip', dest.get('postal_code'))):
        return None

    weight_kg = max(total_weight_kg, Decimal('0.05'))
    weight_oz = float(weight_kg * Decimal('35.274'))

    metadata = getattr(rate, 'metadata', None) or {}
    target_carrier = (metadata.get('easypost_carrier') or '').strip().lower()
    target_service = (metadata.get('easypost_service') or '').strip().lower()

    try:
        resp = requests.post(
            'https://api.easypost.com/v2/shipments',
            auth=(api_key, ''),
            json={
                'shipment': {
                    'to_address': {
                        'street1': dest.get('street1', dest.get('line1', '')),
                        'city': dest.get('city', ''),
                        'state': dest.get('state', ''),
                        'zip': dest.get('zip', dest.get('postal_code', '')),
                        'country': dest.get('country', ''),
                    },
                    'from_address': {
                        'street1': origin.get('street1', origin.get('line1', '')),
                        'city': origin.get('city', ''),
                        'state': origin.get('state', ''),
                        'zip': origin.get('zip', origin.get('postal_code', '')),
                        'country': origin.get('country', 'US'),
                    },
                    'parcel': {
                        'length': 6,
                        'width': 4,
                        'height': 2,
                        'weight': weight_oz,
                    },
                },
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning('easypost: API call failed: %s', e)
        return None

    rates_returned = data.get('rates') or []
    if not rates_returned:
        return None
    if target_carrier:
        rates_returned = [
            r for r in rates_returned if (r.get('carrier') or '').lower() == target_carrier
        ]
    if target_service:
        rates_returned = [
            r for r in rates_returned if (r.get('service') or '').lower() == target_service
        ]
    if not rates_returned:
        return None

    cheapest = min(rates_returned, key=lambda r: Decimal(str(r.get('rate') or '0')))
    try:
        amount = Decimal(str(cheapest.get('rate') or '0'))
    except Exception:  # noqa: BLE001
        return None
    currency = cheapest.get('currency') or str(subtotal.currency)
    return Money(amount, currency)


def _bookvault_quote(rate, *, subtotal: Money, total_weight_kg: Decimal):
    """Live rate from Bookvault's POD shipping API.

    Cart-aware (uses ISBN-13 line items + destination country/postcode)
    and binding-aware (if ``rate.metadata['bookvault_servid']`` is set,
    we return the matching BV service; otherwise the cheapest).

    Returns ``None`` when:
      * Bookvault isn't configured (no token/storeID)
      * the cart has no ISBN-13 lines (= not a book-fulfilment cart)
      * the destination country isn't on the rate's zone
      * BV's API is down / returns no services
    """
    cart = getattr(rate, '_cart', None)
    if cart is None:
        return None
    country = getattr(rate, '_country', '') or ''
    if not country:
        return None

    # Destination postcode — prefer cart.metadata.shipping_address.zip,
    # but BV's API accepts an empty postcode for international quotes
    # so we soft-fall-through if absent.
    cart_meta = getattr(cart, 'metadata', None) or {}
    dest = cart_meta.get('shipping_address') or {}
    postcode = dest.get('zip') or dest.get('postal_code') or ''

    try:
        from plugins.installed.bookvault.services import get_shipping_rates  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        logger.warning('bookvault: import failed: %s', e)
        return None

    services = get_shipping_rates(
        cart=cart,
        country_code=country,
        postcode=postcode,
    )
    if not services:
        return None

    # If the merchant pinned a specific BV service ID on the rate row,
    # honour it; else return the cheapest BV service.
    metadata = getattr(rate, 'metadata', None) or {}
    target_servid = (metadata.get('bookvault_servid') or '').strip()
    if target_servid:
        services = [s for s in services if s['id'] == target_servid]
        if not services:
            return None

    cheapest = min(services, key=lambda s: s['amount'])
    return Money(cheapest['amount'], str(subtotal.currency))


def list_available_rates(*, cart, country: str, region: str = ''):
    """Return all shippable rates for the cart + address."""
    items = list(cart.items.select_related('product').all())
    if not items:
        return []
    subtotal_amount = sum(Decimal(i.unit_price.amount) * i.quantity for i in items)
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
            return w_d / Decimal('1000')
        if unit in ('lb', 'lbs', 'pound', 'pounds'):
            return w_d * Decimal('0.453592')
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
            # Carrier adapters (Shippo, EasyPost, Bookvault) read these
            # transient attributes off the rate instance. Setting them
            # here is the only place the cart + destination cross the
            # function boundary into _quote_one → _carrier_quote.
            rate._cart = cart
            rate._country = country
            rate._region = region
            amount = _quote_one(rate, subtotal=subtotal, total_weight_kg=total_weight_kg)
            if amount is None:
                continue
            out.append(
                {
                    'rate_id': str(rate.id),
                    'name': rate.name,
                    'amount': amount,
                    'estimated_days_min': rate.estimated_days_min,
                    'estimated_days_max': rate.estimated_days_max,
                    'zone': zone.name,
                }
            )
    return out


def quote_rate(*, cart, rate_id: str, country: str, region: str = ''):
    """Quote a specific rate by id."""
    rates = list_available_rates(cart=cart, country=country, region=region)
    return next((r for r in rates if r['rate_id'] == rate_id), None)
