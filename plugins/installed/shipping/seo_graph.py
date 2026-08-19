"""What this store actually charges to ship, as structured data.

The SEO app used to synthesise `OfferShippingDetails` from config keys nothing
wrote, so every product page advertised free shipping to the US regardless of
what the cart charged. Shipping rates are this app's data; if anyone is going
to state them to Google, it has to be the app that knows them.

Nothing is emitted unless a real, active rate exists. An absent property costs
a "recommended field" warning in Search Console; a wrong one is a Merchant
Center policy violation and a promise the checkout will break.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.shipping')

# How many destinations to describe. Google reads shippingDetails per region;
# a store with fifty zones does not need fifty blocks in every product page.
_MAX_ZONES = 3


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """`SEO_JSONLD_GRAPH` subscriber: add shipping to the product's offer."""
    try:
        offer = _product_offer(value)
        if offer is None:
            return value
        details = shipping_details(currency=offer.get('priceCurrency') or 'USD')
        if details:
            offer['shippingDetails'] = details if len(details) > 1 else details[0]
    except Exception as e:  # noqa: BLE001 — a graph enricher must never lose the graph
        logger.warning('shipping: JSON-LD enrichment failed: %s', e, exc_info=True)
    return value


def shipping_details(*, currency: str = 'USD') -> list[dict]:
    """`OfferShippingDetails` for the cheapest active rate in each zone.

    The cheapest rate is the honest one to advertise: it is what a shopper can
    actually pay, and quoting an express rate would overstate the cost.
    """
    from plugins.installed.shipping.models import ShippingRate

    # Zones have no active flag — only rates do.
    rates = (
        ShippingRate.objects.filter(is_active=True)
        .select_related('zone')
        .order_by('zone_id', 'priority')
    )
    out: list[dict] = []
    seen_zones: set = set()
    for rate in rates:
        if rate.zone_id in seen_zones:
            continue
        block = _details_for(rate, currency)
        if not block:
            continue
        seen_zones.add(rate.zone_id)
        out.append(block)
        if len(out) >= _MAX_ZONES:
            break
    return out


def _details_for(rate, currency: str) -> dict | None:
    countries = [str(c).strip().upper() for c in (rate.zone.countries or []) if c]
    # '*' means "everywhere", which `DefinedRegion` cannot express as a country
    # list. Describing it as one country would be wrong, so leave the region off
    # and let the rate stand on its own.
    named = [c for c in countries if c != '*']

    amount = _rate_amount(rate)
    if amount is None:
        # A carrier-quoted rate is only known at checkout. Saying nothing is
        # correct; guessing is what this module exists to stop.
        return None

    block: dict = {
        '@type': 'OfferShippingDetails',
        'shippingRate': {
            '@type': 'MonetaryAmount',
            'value': f'{amount:.2f}',
            'currency': currency,
        },
    }
    if named:
        block['shippingDestination'] = {
            '@type': 'DefinedRegion',
            'addressCountry': named if len(named) > 1 else named[0],
        }
    delivery = _delivery_time(rate)
    if delivery:
        block['deliveryTime'] = delivery
    threshold = getattr(rate, 'free_threshold', None)
    if threshold is not None and getattr(threshold, 'amount', None) is not None:
        block['freeShippingThreshold'] = {
            '@type': 'MonetaryAmount',
            'value': f'{threshold.amount:.2f}',
            'currency': str(getattr(threshold, 'currency', currency)),
        }
    return block


def _rate_amount(rate):
    """The advertised price of this rate, or None when it cannot be known."""
    if rate.computation in {'carrier_shippo', 'carrier_easypost', 'carrier_bookvault'}:
        return None
    if rate.computation in {'weight_tier', 'order_total_tier'}:
        # Tiered rates start at the cheapest tier; that is the "from" price a
        # shopper sees, and the only figure that is true for some basket.
        amounts = [
            t.get('amount')
            for t in (rate.tiers or [])
            if isinstance(t, dict) and t.get('amount') is not None
        ]
        if not amounts:
            return None
        try:
            return min(float(a) for a in amounts)
        except (TypeError, ValueError):
            return None
    flat = getattr(rate, 'flat_amount', None)
    if flat is None or getattr(flat, 'amount', None) is None:
        # 'free_over' with no flat amount means free below the threshold too.
        return 0.0 if rate.computation == 'free_over' else None
    return float(flat.amount)


def _delivery_time(rate) -> dict | None:
    lo, hi = rate.estimated_days_min, rate.estimated_days_max
    if lo is None and hi is None:
        return None
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    return {
        '@type': 'ShippingDeliveryTime',
        # Only TRANSIT is claimed. Handling time is a warehouse fact this app
        # does not hold, and the old code invented "0–1 days" for every store.
        'transitTime': {
            '@type': 'QuantitativeValue',
            'minValue': int(lo),
            'maxValue': int(hi),
            'unitCode': 'DAY',
        },
    }


def _product_offer(graph) -> dict | None:
    """The offer on the graph's Product node, when the page has one."""
    if not isinstance(graph, dict):
        return None
    for node in graph.get('@graph') or []:
        if not isinstance(node, dict) or 'Product' not in str(node.get('@type', '')):
            continue
        offer = node.get('offers')
        if isinstance(offer, dict):
            return offer
    return None
