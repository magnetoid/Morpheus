"""The gift card a shopper can buy, for a theme's gift-card banner."""

from __future__ import annotations

_CACHE_KEY = 'gift_cards:offer:v1'
_CACHE_TTL = 300


def gift_card_offer(request):
    """`gift_card_offer`: the product that sells gift cards, or None.

    A gift card is sold as a product whose SKU, or one of whose variants' SKUs, is
    in the app's sellable SKUs (Settings → Gift cards). A theme shows its banner
    only when there is one, and links to it: montenegro's banner sent shoppers to an
    empty shop. Cached for five minutes; never fails a page.
    """
    from django.core.cache import cache

    cached = cache.get(_CACHE_KEY)
    if cached is None:
        try:
            cached = _offer() or {}
        except Exception:  # noqa: BLE001 — a banner never breaks a page
            cached = {}
        cache.set(_CACHE_KEY, cached, _CACHE_TTL)
    return {'gift_card_offer': cached or None}


def _offer() -> dict | None:
    from django.db.models import Q

    from plugins.installed.catalog.models import Product, ProductVariant
    from plugins.installed.gift_cards.services import sellable_skus

    skus = sellable_skus()
    if not skus:
        return None
    variants = ProductVariant.objects.filter(sku__in=skus).values_list('product_id', flat=True)
    product = (
        Product.objects.shoppable()
        .filter(Q(sku__in=skus) | Q(pk__in=variants))
        .order_by('created_at')
        .first()
    )
    if product is None:
        return None
    prices = [v.price for v in product.variants.all() if v.price is not None and v.price.amount > 0]
    if not prices and product.price is not None and product.price.amount > 0:
        prices = [product.price]
    prices.sort(key=lambda m: m.amount)
    return {
        'url': f'/products/{product.slug}/',
        'name': product.name,
        'low': prices[0] if prices else None,
        'high': prices[-1] if prices and prices[-1].amount > prices[0].amount else None,
    }
