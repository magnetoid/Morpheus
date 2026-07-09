"""Surface takeover — dynamics controls the theme's existing product placeholders.

Storefront views fire ``MorpheusEvents.STOREFRONT_PRODUCTS`` at every product
placeholder (home hero, featured grid, staff picks, PLP ordering, page-builder
sections). When a merchant has bound an enabled ``DynamicBlock`` to that
``surface``, this subscriber answers with the block's picks; otherwise the
view's default stands untouched.

Two modes (see the hook contract in ``core/hooks.py``):

* ``value is None`` — *free pick* (home hero / featured): the block's strategy
  selects from the whole catalog; the view serializes the returned products.
* ``value`` is a list — *reorder-only* (paginated PLP slices, curated grids):
  the block's ranking reorders the given items; pinned ids float to the front,
  excluded ids drop, nothing new is introduced (pagination stays coherent).

Disable-safety comes for free: the hook bus skips handlers whose owning plugin
is inactive (ADR 0023), so disabling dynamics reverts every placeholder.
"""

# ruff: noqa: PLC0415
# Inline imports keep this importable before the app registry is ready.

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.dynamics')


def provide(value, surface: str = '', request=None, limit: int = 12, **kwargs):
    """STOREFRONT_PRODUCTS subscriber. Never raises into a storefront render."""
    try:
        return _provide(value, surface=surface, request=request, limit=limit)
    except Exception:  # noqa: BLE001 — a merchandising bug must never break a page
        logger.warning('dynamics: surface %r takeover failed', surface, exc_info=True)
        return value


def _provide(value, *, surface: str, request, limit: int):
    from plugins.installed.dynamics.models import DynamicBlock
    from plugins.installed.dynamics.services import recommend

    if not surface:
        return value
    block = (
        DynamicBlock.objects.filter(surface=surface, enabled=True)
        .order_by('sort_order')
        .prefetch_related('categories')
        .first()
    )
    if block is None:
        return value

    customer = getattr(request, 'user', None)
    if customer is not None and not getattr(customer, 'is_authenticated', False):
        customer = None

    limit = max(1, min(int(limit or block.limit or 12), 24))

    if value is None:
        # Free pick — strategy selects from the catalog.
        picks = recommend(block, request=request, customer=customer, context_product=None)
        return picks[:limit] or None

    # Reorder-only — rank the given items, never introduce new ones.
    return _reorder(block, list(value), request=request, customer=customer)


def _reorder(block, items: list, *, request, customer) -> list:
    """Reorder ``items`` by the block's ranking. Pins first, excludes dropped."""
    from plugins.installed.dynamics.services import recommend

    ranked = recommend(block, request=request, customer=customer, context_product=None)
    rank_by_pk = {str(p.pk): i for i, p in enumerate(ranked)}

    pinned = [str(x) for x in (block.pinned_product_ids or [])]
    excluded = {str(x) for x in (block.excluded_product_ids or [])}
    pin_pos = {pk: i for i, pk in enumerate(pinned)}

    def _key(pair):
        idx, item = pair
        pk = str(_pk(item))
        if pk in pin_pos:  # pins always outrank the AI ranking
            return (0, pin_pos[pk], idx)
        return (1, rank_by_pk.get(pk, len(rank_by_pk)), idx)

    kept = [(i, it) for i, it in enumerate(items) if str(_pk(it)) not in excluded]
    return [it for _, it in sorted(kept, key=_key)]


def _pk(item):
    """Product pk for either an ORM instance or a GraphQL-shaped dict."""
    if isinstance(item, dict):
        return item.get('id') or item.get('pk') or ''
    return getattr(item, 'pk', '') or getattr(item, 'id', '')
