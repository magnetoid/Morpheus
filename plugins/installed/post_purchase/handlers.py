"""Hook subscribers for the post-purchase journey.

Two events drive the entire chain:
  - ORDER_PLACED      → schedule the tracking_sent step (fires when
                        shipment is created; the orders/shipping
                        plugin handles the actual email).
  - ORDER_FULFILLED   → schedule the three follow-up steps
                        (delivered_followup, review_request,
                        nps_survey) at their configured offsets.

Each step is recorded as a JourneyStep row with `due_at` set to when
the email should fire. The Celery beat task (tasks.py) picks them up
on schedule.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('morpheus.post_purchase.handlers')


def on_order_placed(*, order=None, **_) -> None:
    """Schedule the tracking_sent step when shipment is created.

    For Phase 1 we register the step at order-placed time with a
    due_at = order.placed_at; the tracking step will fire as soon as
    a tracking number is attached (we read it from the order at send
    time). This avoids needing a separate SHIPMENT_CREATED hook.
    """
    if order is None:
        return
    cfg = _config()
    if not cfg.get('tracking_email_enabled', True):
        return

    try:
        from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

        JourneyStep.objects.get_or_create(
            order=order,
            step='tracking_sent',
            defaults={'due_at': timezone.now()},
        )
    except Exception:  # noqa: BLE001
        logger.exception('post_purchase: scheduling tracking step failed')


def on_order_fulfilled(*, order=None, **_) -> None:
    """Schedule the three follow-up steps at their configured delays."""
    if order is None:
        return
    cfg = _config()
    now = timezone.now()

    try:
        from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

        schedule = []
        if cfg.get('delivered_followup_enabled', True):
            schedule.append(
                (
                    'delivered_followup',
                    now + timedelta(hours=int(cfg.get('delivered_followup_delay_hours', 24))),
                )
            )
        if cfg.get('review_request_enabled', True):
            schedule.append(
                (
                    'review_request',
                    now + timedelta(days=int(cfg.get('review_request_delay_days', 14))),
                )
            )
        if cfg.get('nps_survey_enabled', True):
            schedule.append(
                (
                    'nps_survey',
                    now + timedelta(days=int(cfg.get('nps_survey_delay_days', 30))),
                )
            )

        for step, due in schedule:
            JourneyStep.objects.get_or_create(order=order, step=step, defaults={'due_at': due})
    except Exception:  # noqa: BLE001
        logger.exception('post_purchase: scheduling fulfilled steps failed')


def _config() -> dict:
    """Resolve PluginConfig['post_purchase']['config'] with sane defaults."""
    try:
        from plugins.models import PluginConfig  # noqa: PLC0415

        row = PluginConfig.objects.filter(plugin_name='post_purchase').first()
        if row and isinstance(row.config, dict):
            return row.config
    except Exception:  # noqa: BLE001, S110
        pass
    return getattr(settings, 'POST_PURCHASE_DEFAULTS', {})
