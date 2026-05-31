"""cart_abandon collector — subscribes to MorpheusEvents.CART_ABANDONED.

Fired by `plugins/installed/cart_abandonment/tasks.py:80` when a cart's
abandonment threshold passes. We turn each fire into an
`si_signal(source='cart_abandon')` row keyed on the cart's pk so a
single cart isn't counted multiple times across recovery runs.

Subscriber form (not Collector form) because the event is push-driven,
not scheduled. The hook handler is wired in
`core/self_improvement/apps.py:ready()`.
"""

from __future__ import annotations

import logging
from typing import Any

from core.self_improvement.services import emit_signal, fingerprint_for

logger = logging.getLogger('morpheus.self_improvement.cart_abandon')

SOURCE = 'cart_abandon'


def on_cart_abandoned(*, cart: Any = None, email: str | None = None, **_: Any) -> None:
    """Hook handler — kwargs match `MorpheusEvents.CART_ABANDONED`.

    Keeps imports lazy because this is wired at app-ready time before
    every plugin's models are fully loaded.
    """
    if cart is None:
        return

    cart_pk = getattr(cart, 'pk', None) or getattr(cart, 'id', None)
    if cart_pk is None:
        logger.debug('cart_abandon: cart without pk; dropping')
        return

    # Cart-scoped fingerprint — one signal per cart, even if abandonment
    # fires twice (e.g. recovery email-1 + email-2 phases).
    fp = fingerprint_for(SOURCE, str(cart_pk))

    try:
        emit_signal(
            source=SOURCE,
            fingerprint=fp,
            severity=40,  # informational — low-stakes per-cart event
            payload={
                'cart_id': str(cart_pk),
                'has_email': bool(email),
                'item_count': _safe_item_count(cart),
            },
        )
    except Exception:  # noqa: BLE001 — never let a signal write break the cart pipeline
        logger.exception('cart_abandon: emit_signal failed for cart=%s', cart_pk)


def _safe_item_count(cart: Any) -> int:
    """Return cart.items.count() if available, else 0. Defensive — the
    cart model varies across plugins, so we don't assume a shape."""
    items = getattr(cart, 'items', None)
    if items is None:
        return 0
    try:
        return int(items.count())
    except Exception:  # noqa: BLE001 — never break on a count-call
        return 0
