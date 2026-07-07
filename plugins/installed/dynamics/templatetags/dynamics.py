"""Template tag that resolves a slot's configured blocks into products.

``{% dynamic_blocks_for slot request product as rendered %}`` returns a
list of ``{'block': DynamicBlock, 'products': [Product, …]}`` dicts for
every enabled block in ``slot`` that produced at least one product. The
storefront ``_slot.html`` loops over it. All work is fail-soft — a bad
query yields an empty list, never an exception into the page.
"""

# ruff: noqa: PLC0415 — lazy imports keep the storefront tag decoupled from
#       model import order and match sibling plugin tag modules.

from __future__ import annotations

import logging

from django import template

logger = logging.getLogger('morpheus.dynamic_products')

register = template.Library()


@register.simple_tag(takes_context=True)
def dynamic_blocks_for(context, slot, request=None, product=None):
    """Resolve enabled DynamicBlocks for ``slot`` into render-ready rows."""
    try:
        from plugins.installed.dynamic_products.models import DynamicBlock
        from plugins.installed.dynamic_products.services import recommend
    except Exception:  # noqa: BLE001 — plugin mid-teardown
        return []

    req = request or context.get('request')
    customer = getattr(req, 'user', None) if req is not None else None

    out = []
    try:
        blocks = DynamicBlock.objects.filter(slot=slot, enabled=True).prefetch_related('categories')
    except Exception:  # noqa: BLE001
        return []

    for block in blocks:
        # PDP-only strategies render nothing off a product page.
        if block.is_pdp_only and product is None:
            continue
        products = recommend(block, request=req, customer=customer, context_product=product)
        if products:
            out.append({'block': block, 'products': products})
    return out
