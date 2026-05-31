"""ORDER_PLACED subscriber — score every new order, stamp metadata."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('morpheus.fraud_rules.handlers')


def on_order_placed(*, order: Any = None, **_: Any) -> None:
    if order is None:
        return
    try:
        from plugins.installed.fraud_rules.services import score_order  # noqa: PLC0415

        result = score_order(order)

        meta = dict(getattr(order, 'metadata', {}) or {})
        meta['fraud_score'] = result.score
        meta['fraud_bucket'] = result.bucket
        meta['fraud_flags'] = result.flags
        if result.detail:
            meta['fraud_detail'] = result.detail
        order.metadata = meta
        order.save(update_fields=['metadata'])

        if result.bucket in ('review', 'reject'):
            logger.warning(
                'fraud_rules: order %s flagged bucket=%s score=%s flags=%s',
                getattr(order, 'order_number', order.pk),
                result.bucket,
                result.score,
                ','.join(result.flags),
            )
    except Exception:  # noqa: BLE001 — never break the order pipeline
        logger.exception('fraud_rules: on_order_placed failed')
