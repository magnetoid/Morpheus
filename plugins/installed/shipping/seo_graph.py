"""What this store actually charges to ship, as structured data.

The SEO app used to synthesise `OfferShippingDetails` from config keys nothing
wrote, so every product page advertised free shipping to the US regardless of
what the cart charged. Shipping rates are this app's data; if anyone is going
to state them to Google, it has to be the app that knows them.

Nothing is emitted unless a real, active rate exists. An absent property costs
a "recommended field" warning in Search Console; a wrong one is a Merchant
Center policy violation and a promise the checkout will break.

The store's own node carries the same rates as its shipping policy
(`hasShippingService`, which Google reads for every product the store sells),
built only from fixed-price rates: a tiered or carrier-quoted price is not one
amount. Handling time is the merchant's own statement on the Shipping page;
unset, no handling time is claimed anywhere.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.shipping')

# How many destinations to describe. Google reads shippingDetails per region;
# a store with fifty zones does not need fifty blocks in every product page.
_MAX_ZONES = 3


# The fixed-price rate kinds: one amount whatever the basket weighs.
_FIXED = {'flat', 'free_over'}
_HANDLING_MAX_DAYS = 30

# Google reads `DefinedRegion.addressRegion` (an ISO 3166-2 code without the
# country prefix) only for these countries; a zone limited to regions anywhere
# else cannot be stated, so its rate is left out rather than claimed nationwide.
_REGION_COUNTRIES = {'US', 'AU', 'JP'}
_UNSTATABLE = object()


def _destination(zone):
    """The `DefinedRegion` a zone ships to, None for everywhere, or `_UNSTATABLE`.

    It follows `ShippingZone.matches`: '*' is everywhere whatever the regions say,
    and a zone with regions takes only those regions of its country. A region list
    on a zone of several countries, or in a country Google reads no regions for,
    cannot be written down, and publishing the country alone would promise the
    rate where checkout refuses it.
    """
    countries = [str(c).strip().upper() for c in (zone.countries or []) if c]
    if '*' in countries:
        return None
    named = [c for c in countries if c]
    if not named:
        return None
    region: dict = {
        '@type': 'DefinedRegion',
        'addressCountry': named if len(named) > 1 else named[0],
    }
    regions = [str(r).strip().upper() for r in (zone.regions or []) if str(r).strip()]
    if regions:
        if len(named) != 1 or named[0] not in _REGION_COUNTRIES:
            return _UNSTATABLE
        prefix = f'{named[0]}-'
        codes = [r[len(prefix) :] if r.startswith(prefix) else r for r in regions]
        region['addressRegion'] = codes if len(codes) > 1 else codes[0]
    return region


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """`SEO_JSONLD_GRAPH` subscriber: shipping on the product's offer and the store.

    The offer gets it only for a product that ships: a booked experience or a
    download has no delivery to describe. The store's node gets it while the
    store sells something that ships.
    """
    try:
        offers = _product_offers(value) if _ships(page) else []
        handling = handling_days() if offers else None
        for offer in offers:
            details = shipping_details(
                currency=offer.get('priceCurrency') or 'USD', handling=handling
            )
            if details:
                offer['shippingDetails'] = details if len(details) > 1 else details[0]
        store = _store_node(value)
        if store is not None and _store_ships_goods():
            services = shipping_services()
            if services:
                store['hasShippingService'] = services if len(services) > 1 else services[0]
    except Exception as e:  # noqa: BLE001 — a graph enricher must never lose the graph
        logger.warning('shipping: JSON-LD enrichment failed: %s', e, exc_info=True)
    return value


def _store_ships_goods() -> bool:
    """Whether the store sells anything that goes out in a parcel."""
    from plugins.installed.catalog.models import Product

    try:
        return Product.objects.shoppable().filter(requires_shipping=True).exists()
    except Exception:  # noqa: BLE001 — an unmigrated DB during a deploy
        return False


def _store_node(graph) -> dict | None:
    """The graph's node for the store itself (seo names it `…#organization`)."""
    if not isinstance(graph, dict):
        return None
    for node in graph.get('@graph') or []:
        if isinstance(node, dict) and str(node.get('@id', '')).endswith('#organization'):
            return node
    return None


def clean_handling(lo, hi, cutoff) -> dict:
    """The Shipping page's handling-time fields, checked; raises ValueError for the merchant.

    Blank means "not stated" (stored as ''). One number alone is both ends.
    """

    def days(raw, label):
        text = '' if raw is None else str(raw).strip()
        if not text:
            return ''
        try:
            n = int(text)
        except ValueError as exc:
            raise ValueError(f'{label} must be a whole number of days.') from exc
        if not 0 <= n <= _HANDLING_MAX_DAYS:
            raise ValueError(f'{label} must be between 0 and {_HANDLING_MAX_DAYS} days.')
        return n

    lo = days(lo, 'Handling time (at least)')
    hi = days(hi, 'Handling time (at most)')
    if lo == '' and hi != '':
        lo = hi
    if hi == '' and lo != '':
        hi = lo
    if lo != '' and hi < lo:
        raise ValueError('Handling time: "at most" cannot be below "at least".')
    time = (str(cutoff or '')).strip()[:5]
    if time:
        try:
            hours, minutes = (int(part) for part in time.split(':'))
        except ValueError as exc:
            raise ValueError('The cut-off is a time of day, like 14:00.') from exc
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError('The cut-off is a time of day, like 14:00.')
        time = f'{hours:02d}:{minutes:02d}'
    return {'handling_days_min': lo, 'handling_days_max': hi, 'handling_cutoff_time': time}


def handling_days() -> tuple[int, int] | None:
    """The handling time the merchant stated on the Shipping page, or None."""
    from plugins.installed.shipping.services import _shipping_config

    cfg = _shipping_config()
    try:
        cleaned = clean_handling(
            cfg.get('handling_days_min'),
            cfg.get('handling_days_max'),
            cfg.get('handling_cutoff_time'),
        )
    except ValueError:
        return None
    if cleaned['handling_days_min'] == '':
        return None
    return cleaned['handling_days_min'], cleaned['handling_days_max']


def handling_cutoff() -> str:
    """The same-day cut-off as an ISO 8601 time on the store clock ('14:00:00+01:00'), or ''."""
    from django.utils import timezone

    from plugins.installed.shipping.services import _shipping_config

    raw = str(_shipping_config().get('handling_cutoff_time') or '').strip()
    try:
        time = clean_handling('', '', raw)['handling_cutoff_time']
    except ValueError:
        return ''
    if not time:
        return ''
    from core.utils.site import store_timezone

    offset = timezone.localtime(timezone=store_timezone()).strftime('%z')  # '+0100'
    return f'{time}:00{offset[:3]}:{offset[3:]}' if offset else f'{time}:00'


def shipping_services() -> list[dict]:
    """The store's shipping policy: a `ShippingService` per zone's cheapest fixed-price rate.

    Google reads it on the Organization for every product the store sells
    (developers.google.com/search/docs/appearance/structured-data/shipping-policy).
    """
    from plugins.installed.shipping.models import ShippingRate

    currency = _store_currency()
    handling = _handling_period()
    rates = (
        ShippingRate.objects.filter(is_active=True, computation__in=_FIXED)
        .select_related('zone')
        .order_by('zone_id', 'priority')
    )
    out: list[dict] = []
    seen_zones: set = set()
    for rate in rates:
        if rate.zone_id in seen_zones:
            continue
        conditions = _conditions_for(rate, currency)
        if not conditions:
            continue
        seen_zones.add(rate.zone_id)
        service: dict = {
            '@type': 'ShippingService',
            'name': rate.name,
            'fulfillmentType': 'https://schema.org/FulfillmentTypeDelivery',
            'shippingConditions': conditions if len(conditions) > 1 else conditions[0],
        }
        if handling:
            service['handlingTime'] = handling
        out.append(service)
        if len(out) >= _MAX_ZONES:
            break
    return out


def _conditions_for(rate, currency: str) -> list[dict]:
    """`ShippingConditions` for one fixed-price rate: one, or two either side of
    the free-shipping threshold (Google reads `orderValue` ranges for that)."""
    amount = _rate_amount(rate)
    if amount is None:
        return []
    destination = _destination(rate.zone)
    if destination is _UNSTATABLE:
        return []
    base: dict = {'@type': 'ShippingConditions'}
    if destination:
        base['shippingDestination'] = destination
    transit = _transit_period(rate)
    if transit:
        base['transitTime'] = transit

    def priced(value: float, order_value: dict | None = None) -> dict:
        block = dict(base)
        if order_value:
            block['orderValue'] = {'@type': 'MonetaryAmount', 'currency': currency, **order_value}
        block['shippingRate'] = {
            '@type': 'MonetaryAmount',
            'value': f'{value:.2f}',
            'currency': currency,
        }
        return block

    threshold = getattr(getattr(rate, 'free_threshold', None), 'amount', None)
    if rate.computation == 'free_over' and threshold is not None and amount > 0:
        limit = float(threshold)
        return [
            priced(amount, {'minValue': 0, 'maxValue': round(max(limit - 0.01, 0), 2)}),
            priced(0.0, {'minValue': round(limit, 2)}),
        ]
    return [priced(amount)]


def _days(lo, hi) -> dict:
    return {
        '@type': 'QuantitativeValue',
        'minValue': int(lo),
        'maxValue': int(hi),
        'unitCode': 'DAY',
    }


def _transit_days(rate) -> tuple[int, int] | None:
    lo, hi = rate.estimated_days_min, rate.estimated_days_max
    if lo is None and hi is None:
        return None
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    return int(lo), int(hi)


def _transit_period(rate) -> dict | None:
    days = _transit_days(rate)
    return {'@type': 'ServicePeriod', 'duration': _days(*days)} if days else None


def _handling_period() -> dict | None:
    days = handling_days()
    if days is None:
        return None
    period: dict = {'@type': 'ServicePeriod', 'duration': _days(*days)}
    cutoff = handling_cutoff()
    if cutoff:
        period['cutoffTime'] = cutoff
    return period


def _store_currency() -> str:
    from plugins.installed.shipping.rates import store_currency

    return store_currency()


def _ships(page) -> bool:
    obj = getattr(page, 'obj', None)
    if obj is None or getattr(obj, 'product_type', '') == 'service':
        return False
    return bool(getattr(obj, 'requires_shipping', False))


def shipping_details(*, currency: str = 'USD', handling=...) -> list[dict]:
    """`OfferShippingDetails` for the cheapest active rate in each zone.

    The cheapest rate is the honest one to advertise: it is what a shopper can
    actually pay, and quoting an express rate would overstate the cost.
    `handling` is the merchant's handling time ((min, max) days, or None),
    read from the settings when not passed.
    """
    if handling is ...:
        handling = handling_days()
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
        block = _details_for(rate, currency, handling)
        if not block:
            continue
        seen_zones.add(rate.zone_id)
        out.append(block)
        if len(out) >= _MAX_ZONES:
            break
    return out


def _details_for(rate, currency: str, handling=None) -> dict | None:
    # '*' means "everywhere", which `DefinedRegion` cannot express as a country
    # list, so the rate stands on its own; a zone limited to regions Google cannot
    # read is left out (`_destination`).
    destination = _destination(rate.zone)
    if destination is _UNSTATABLE:
        return None

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
    if destination:
        block['shippingDestination'] = destination
    delivery = _delivery_time(rate, handling)
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
    # A carrier quotes at checkout; a pickup is not shipping (stated as a
    # shipping rate, a free pickup would read as free delivery).
    if rate.computation in {'carrier_shippo', 'carrier_easypost', 'carrier_bookvault', 'pickup'}:
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


def _delivery_time(rate, handling=None) -> dict | None:
    """Transit from the rate's estimate, handling from the merchant's own
    statement (the old code invented "0–1 days" for every store)."""
    block: dict = {'@type': 'ShippingDeliveryTime'}
    if handling is not None:
        block['handlingTime'] = _days(*handling)
    transit = _transit_days(rate)
    if transit is not None:
        block['transitTime'] = _days(*transit)
    return block if len(block) > 1 else None


def _product_offers(graph) -> list[dict]:
    """Every offer on the graph's Product nodes, variants' included.

    A product with several editions is a ProductGroup whose offers sit on its
    `hasVariant` members, not on the group.
    """
    if not isinstance(graph, dict):
        return []
    found: list[dict] = []

    def collect(node):
        offers = node.get('offers')
        for offer in offers if isinstance(offers, list) else [offers]:
            if isinstance(offer, dict):
                found.append(offer)
        for member in node.get('hasVariant') or []:
            if isinstance(member, dict):
                collect(member)

    for node in graph.get('@graph') or []:
        if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
            collect(node)
    return found
