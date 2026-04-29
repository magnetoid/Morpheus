"""Cart-abandonment scanner.

Runs on a celery beat schedule. For each cart that:

  * has items,
  * was last updated more than ``abandon_after_minutes`` ago,
  * has not yet been emitted (cart.metadata['abandoned_emitted'] is unset),
  * (optionally) has a reachable email,

we fire ``events.CART_ABANDONED`` and stamp the cart so subsequent runs
skip it. Email + remarketing plugins subscribe to the event.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("morpheus.cart_abandonment")


def _config() -> dict:
    """Read plugin config with sensible defaults if the DB row is absent."""
    try:
        from plugins.registry import plugin_registry
        plugin = plugin_registry.get('cart_abandonment')
        if plugin is not None:
            cfg = plugin.get_config()
            return {
                'abandon_after_minutes': int(cfg.get('abandon_after_minutes', 60)),
                'require_email': bool(cfg.get('require_email', True)),
            }
    except Exception:  # noqa: BLE001 — DB may not be ready
        pass
    return {'abandon_after_minutes': 60, 'require_email': True}


def _cart_email(cart) -> str:
    """Best-effort reach: customer's email, or any session-bound shipping email."""
    customer = getattr(cart, 'customer', None)
    if customer is not None:
        em = getattr(customer, 'email', '')
        if em:
            return em
    return ''


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def scan_abandoned_carts(self) -> dict:
    """Emit ``events.CART_ABANDONED`` once per newly-stale cart."""
    cfg = _config()
    cutoff = timezone.now() - timedelta(minutes=cfg['abandon_after_minutes'])

    try:
        from morpheus import events, hooks
        from plugins.installed.orders.models import Cart
    except Exception as e:  # noqa: BLE001 — plugin missing
        logger.warning('cart_abandonment: imports unavailable: %s', e)
        return {'scanned': 0, 'fired': 0}

    qs = (
        Cart.objects
        .filter(updated_at__lt=cutoff, items__isnull=False)
        .distinct()
    )

    fired = 0
    scanned = 0
    for cart in qs.iterator(chunk_size=200):
        scanned += 1
        meta = dict(getattr(cart, 'metadata', {}) or {})
        if meta.get('abandoned_emitted'):
            continue
        email = _cart_email(cart)
        if cfg['require_email'] and not email:
            continue
        try:
            hooks.fire(events.CART_ABANDONED, cart=cart, email=email or None)
            fired += 1
            meta['abandoned_emitted'] = timezone.now().isoformat()
            cart.metadata = meta
            cart.save(update_fields=['metadata', 'updated_at'])
        except Exception as e:  # noqa: BLE001 — never fail the whole sweep on one cart
            logger.warning('cart_abandonment: cart %s failed: %s', cart.id, e)

    return {'scanned': scanned, 'fired': fired}
