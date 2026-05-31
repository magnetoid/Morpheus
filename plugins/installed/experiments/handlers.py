"""Hook subscribers — convert tracking events into experiment conversions."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger('morpheus.experiments.handlers')


def on_order_placed(*, order: Any = None, **_: Any) -> None:
    """Every order placed → conversion for every running purchase-goal
    experiment the order's visitor was exposed to."""
    if order is None:
        return
    visitor_id = _visitor_from_order(order)
    if not visitor_id:
        return

    try:
        from plugins.installed.experiments.models import Experiment  # noqa: PLC0415
        from plugins.installed.experiments.services import record_conversion  # noqa: PLC0415

        revenue = _order_revenue(order)
        for exp_key in Experiment.objects.filter(status='running', goal='purchase').values_list(
            'key', flat=True
        ):
            record_conversion(
                experiment_key=exp_key,
                visitor_id=visitor_id,
                revenue=revenue,
            )
    except Exception:  # noqa: BLE001
        logger.exception('experiments: on_order_placed failed')


def on_signup(*, customer: Any = None, **_: Any) -> None:
    if customer is None:
        return
    visitor_id = f'u:{customer.pk}'
    try:
        from plugins.installed.experiments.models import Experiment  # noqa: PLC0415
        from plugins.installed.experiments.services import record_conversion  # noqa: PLC0415

        for exp_key in Experiment.objects.filter(status='running', goal='signup').values_list(
            'key', flat=True
        ):
            record_conversion(experiment_key=exp_key, visitor_id=visitor_id)
    except Exception:  # noqa: BLE001
        logger.exception('experiments: on_signup failed')


def _visitor_from_order(order) -> str | None:
    """Resolve a visitor_id from order metadata or customer FK."""
    if getattr(order, 'customer_id', None):
        return f'u:{order.customer_id}'
    meta = getattr(order, 'metadata', None) or {}
    cookie = meta.get('visitor_id') if isinstance(meta, dict) else None
    if cookie:
        return f'v:{cookie}'
    return None


def _order_revenue(order) -> Decimal | None:
    total = getattr(order, 'total', None)
    if total is None:
        return None
    return Decimal(str(getattr(total, 'amount', total)))
