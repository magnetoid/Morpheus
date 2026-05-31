"""Hook subscribers for loyalty extensions (referral qualification)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('morpheus.loyalty.handlers')


def on_order_placed_for_referrals(*, order: Any = None, **_: Any) -> None:
    if order is None:
        return
    try:
        from plugins.installed.loyalty_points.services_referrals import (  # noqa: PLC0415
            qualify_on_order,
        )

        qualify_on_order(order)
    except Exception:  # noqa: BLE001 — referral processing must never break order pipeline
        logger.exception('loyalty: on_order_placed_for_referrals failed')
