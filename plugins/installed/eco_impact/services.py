"""eco_impact services — settings resolution, footprint lookup, pledge ledger.

Everything the plugin's hooks, views, and templatetags call lives here so the
manifest and templates stay logic-free. All functions are fail-soft: a green
storefront never breaks over an eco calculation.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from plugins.installed.eco_impact import footprint
from plugins.registry import plugin_registry

logger = logging.getLogger('morpheus.eco_impact')

_PLUGIN = 'eco_impact'
_FACTOR_KEYS = (
    'paper_fraction',
    'wood_factor',
    'co2_per_kg_paper',
    'print_overhead_kg',
    'kg_co2_per_tree',
)


def _cfg(key, default):
    try:
        return plugin_registry.config_value(_PLUGIN, key, default)
    except Exception:  # noqa: BLE001 — settings must never break a render
        return default


def show_on_pdp() -> bool:
    return bool(_cfg('show_on_pdp', True))


def surcharge_amount() -> Decimal:
    """The flat plant-a-tree opt-in price, as a quantised Decimal."""
    try:
        return Decimal(str(_cfg('tree_price', 1.50))).quantize(Decimal('0.01'))
    except Exception:  # noqa: BLE001
        return Decimal('1.50')


def kg_co2_per_tree() -> float:
    try:
        return float(_cfg('kg_co2_per_tree', footprint.DEFAULTS['kg_co2_per_tree']))
    except (TypeError, ValueError):
        return footprint.DEFAULTS['kg_co2_per_tree']


def factors_from_settings() -> dict:
    """Merchant-tuned overrides for the footprint calculator (only set keys)."""
    out: dict = {}
    for k in _FACTOR_KEYS:
        v = _cfg(k, None)
        if v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _book_for(product_id):
    from plugins.installed.book_product.models import BookProduct

    return BookProduct.objects.filter(product_id=product_id).select_related('product').first()


def impact_for_product(product) -> dict | None:
    """Production-footprint dict for a PDP ``product`` (GraphQL dict OR ORM),
    or None when it isn't a book / has no usable physical data.

    PDP blocks receive ``product`` as a GraphQL dict, not an ORM row — resolve
    the id both ways (the audiobooks precedent), never assume ``.pk``.
    """
    if product is None:
        return None
    pid = product.get('id') if isinstance(product, dict) else getattr(product, 'pk', product)
    if not pid:
        return None
    try:
        book = _book_for(pid)
        if book is None:
            return None
        product_weight_kg = None
        w = getattr(getattr(book, 'product', None), 'weight', None)
        if w:
            product_weight_kg = float(w)
        result = footprint.impact(
            weight_g=book.weight_g,
            product_weight_kg=product_weight_kg,
            page_count=book.page_count,
            width_mm=book.width_mm,
            height_mm=book.height_mm,
            print_type=book.print_type,
            factors=factors_from_settings(),
        )
        return result if result.get('has_data') else None
    except Exception as exc:  # noqa: BLE001
        logger.warning('impact_for_product failed for %s: %s', pid, exc, exc_info=True)
        return None


# ── opt-in state (cart-metadata backed, guest + auth) ──────────────────────


def _current_cart(request):
    """The visitor's cart (auth → by customer, guest → by session_key), or None.
    Mirrors the storefront checkout resolution so opt-in works for guests too.
    """
    from plugins.installed.orders.models import Cart

    try:
        if request.user.is_authenticated:
            return Cart.objects.filter(customer=request.user).order_by('-updated_at').first()
        if request.session.session_key:
            return (
                Cart.objects.filter(session_key=request.session.session_key)
                .order_by('-updated_at')
                .first()
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning('current cart resolve failed: %s', exc, exc_info=True)
    return None


def optin_active(request) -> bool:
    cart = _current_cart(request)
    if cart is None:
        return False
    return bool((getattr(cart, 'metadata', None) or {}).get('eco_impact_optin'))


def set_optin(request, on: bool) -> None:
    cart = _current_cart(request)
    if cart is None:
        return
    md = dict(cart.metadata or {})
    if on:
        md['eco_impact_optin'] = True
    else:
        md.pop('eco_impact_optin', None)
    cart.metadata = md
    cart.save(update_fields=['metadata', 'updated_at'])


# ── pledge ledger ──────────────────────────────────────────────────────────


def record_pledge(order, trees: int, amount, currency: str = 'USD'):
    """Idempotently record a tree pledge for a paid order. Returns the new row,
    or None when one already existed (retry-safe via the OneToOne)."""
    from plugins.installed.eco_impact.models import TreePledge

    order_number = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    try:
        amt = Decimal(str(amount)).quantize(Decimal('0.01'))
    except Exception:  # noqa: BLE001
        amt = Decimal('0.00')
    obj, created = TreePledge.objects.get_or_create(
        order=order,
        defaults={
            'order_number': order_number,
            'trees': max(1, int(trees or 1)),
            'amount': amt,
            'currency': currency or 'USD',
        },
    )
    return obj if created else None


def remove_pledge(order) -> None:
    """Void a pledge when its order is cancelled, so store totals stay honest."""
    from plugins.installed.eco_impact.models import TreePledge

    TreePledge.objects.filter(order=order).delete()


def store_totals() -> dict:
    """Aggregate impact for the storefront + dashboard summaries."""
    from django.db.models import Sum

    from plugins.installed.eco_impact.models import TreePledge

    agg = TreePledge.objects.aggregate(trees=Sum('trees'))
    trees = agg['trees'] or 0
    contributors = TreePledge.objects.count()
    return {
        'trees': trees,
        'contributors': contributors,
        # Trees pledged × the offset each is sized to sequester.
        'co2_offset_kg': round(trees * kg_co2_per_tree(), 1),
    }
