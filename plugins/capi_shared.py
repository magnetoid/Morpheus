"""Shared Conversions-API payload helpers for the ad/commerce channel plugins.

Every server-side conversions integration (Meta CAPI, TikTok Events API,
Pinterest/Reddit/Snapchat CAPI) builds the same two primitives from a Morpheus
order/cart: a ``(value, currency)`` tuple and a ``[(sku, qty)]`` line-item list.
Each channel used to carry its own byte-identical copy, so a fix to either had
to be made in five places.

Lives at the ``plugins`` package root — like ``plugins/feed_mapping`` and
``plugins/context_processors`` — because it is shared *channel* infrastructure:
putting it in one channel would couple the siblings to that channel, and it is
not core-worthy (it exists only for conversions channels).
"""

from __future__ import annotations


def money_tuple(m) -> tuple[float, str]:
    """``(value, currency)`` from a Money-like object; ``(0.0, 'USD')`` when empty."""
    amount = getattr(m, 'amount', None)
    return (float(amount) if amount is not None else 0.0), str(getattr(m, 'currency', '') or 'USD')


def line_items(obj) -> list[tuple[str, int]]:
    """``[(sku, qty)]`` from an order or cart, best-effort.

    ``items``/``lines`` is a reverse-FK RelatedManager on real models — NOT
    directly iterable — so resolve ``.all()`` before looping. (A plain list, as
    in tests, has no ``.all()`` and is used as-is.)
    """
    rel = getattr(obj, 'items', None)
    if rel is None:
        rel = getattr(obj, 'lines', None)
    if hasattr(rel, 'all'):
        rel = list(rel.all())
    out: list[tuple[str, int]] = []
    for line in rel or []:
        sku = (
            getattr(line, 'sku', '')
            or getattr(getattr(line, 'variant', None), 'sku', '')
            or getattr(getattr(line, 'product', None), 'sku', '')
        )
        if sku:
            out.append((sku, int(getattr(line, 'quantity', 1) or 1)))
    return out
