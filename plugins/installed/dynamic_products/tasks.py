"""dynamic_products — background recomputation of the propensity grid.

`services.calculate_grid_probabilities()` scores the whole active catalog from
sales / view / inventory signals, so it runs as a **nightly** Celery-beat job
(wired in `plugin.ready()`) plus a **throttled** refresh right after an order —
so `DynamicGridItem.purchase_probability` stays current with zero merchant
effort. Under tests `CELERY_TASK_ALWAYS_EAGER` runs these inline.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.dynamic_products')

# Debounce the (catalog-wide) recompute so an order burst can't stampede it.
_REFRESH_LOCK_KEY = 'dynamic_products:recompute:throttle'
_REFRESH_THROTTLE_SECONDS = 15 * 60


@shared_task(name='dynamic_products.recompute_probabilities')
def recompute_probabilities() -> dict:
    """Full recompute of every active product's purchase probability (nightly)."""
    from plugins.installed.dynamic_products.services import calculate_grid_probabilities

    result = calculate_grid_probabilities()
    logger.info('dynamic_products: recomputed %s grid probabilities', result.get('updated'))
    return result


@shared_task(name='dynamic_products.refresh_probabilities_throttled')
def refresh_probabilities_throttled() -> dict:
    """Event-driven refresh (fired after an order). Debounced via a short cache
    lock so a spike of orders triggers at most one recompute per window."""
    from django.core.cache import cache

    # cache.add is False when the key already exists → a refresh ran recently.
    if not cache.add(_REFRESH_LOCK_KEY, '1', timeout=_REFRESH_THROTTLE_SECONDS):
        return {'skipped': 'throttled'}
    return recompute_probabilities()
