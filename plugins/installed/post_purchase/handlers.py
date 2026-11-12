"""Hook subscribers for the post-purchase journey.

These events drive the entire chain:
  - ORDER_PLACED      → schedule the tracking_sent step (fires when
                        shipment is created; the orders/shipping
                        plugin handles the actual email).
  - ORDER_FULFILLED   → schedule the three follow-up steps
                        (delivered_followup, review_request,
                        nps_survey) at their configured offsets.
  - ORDER_DELIVERED   → count those offsets again from the delivery.

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


def _followup_schedule(cfg: dict, anchor) -> list[tuple]:
    """``[(step, due_at)]`` for the switched-on follow-ups, counted from ``anchor``."""
    schedule = []
    if cfg.get('delivered_followup_enabled', True):
        hours = int(cfg.get('delivered_followup_delay_hours', 24))
        schedule.append(('delivered_followup', anchor + timedelta(hours=hours)))
    if cfg.get('review_request_enabled', True):
        days = int(cfg.get('review_request_delay_days', 14))
        schedule.append(('review_request', anchor + timedelta(days=days)))
    if cfg.get('nps_survey_enabled', True):
        days = int(cfg.get('nps_survey_delay_days', 30))
        schedule.append(('nps_survey', anchor + timedelta(days=days)))
    return schedule


def on_order_fulfilled(*, order=None, **_) -> None:
    """Schedule the three follow-up steps at their configured delays."""
    if order is None:
        return
    try:
        from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

        for step, due in _followup_schedule(_config(), timezone.now()):
            JourneyStep.objects.get_or_create(order=order, step=step, defaults={'due_at': due})
    except Exception:  # noqa: BLE001
        logger.exception('post_purchase: scheduling fulfilled steps failed')


def on_order_delivered(*, order=None, **_) -> None:
    """Re-time the follow-ups from the delivery (ORDER_DELIVERED).

    Shipping starts the clock as a guess; the parcel's arrival is when a
    delivery follow-up, a review request and a survey make sense. A step that
    already went out (or was skipped) is left alone.
    """
    if order is None:
        return
    try:
        from plugins.installed.post_purchase.models import JourneyStep  # noqa: PLC0415

        for step, due in _followup_schedule(_config(), timezone.now()):
            row, created = JourneyStep.objects.get_or_create(
                order=order, step=step, defaults={'due_at': due}
            )
            if not created and row.status == 'queued':
                row.due_at = due
                row.save(update_fields=['due_at', 'updated_at'])
    except Exception:  # noqa: BLE001
        logger.exception('post_purchase: re-timing delivered steps failed')


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
