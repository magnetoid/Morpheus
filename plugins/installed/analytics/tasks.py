"""Analytics background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.analytics')


@app.task(name='analytics.log_event', ignore_result=True, time_limit=10, soft_time_limit=5)
def log_analytics_event(payload):
    """Back-compat: AnalyticsPlugin.record_event hooks fan out to this.

    Translates the hook payload into a record_event() call.
    """
    try:
        from plugins.installed.analytics.services import record_event
    except Exception:  # noqa: BLE001
        return

    name = payload.get('event') or payload.get('name') or 'hook.event'
    revenue = None
    if payload.get('order'):
        order = payload.get('order')
        revenue = getattr(order, 'total', None)
    record_event(
        name=name,
        kind=_kind_for(name),
        agent_name=payload.get('agent_name', '') or '',
        revenue=revenue,
        payload={k: str(v)[:300] for k, v in payload.items() if k != 'event'},
    )


def _kind_for(name: str) -> str:  # noqa: PLR0911
    # Only order.placed is the canonical money event — payment.captured used
    # to map to 'purchase' too, double-counting revenue in roll_daily.
    if name == 'order.placed':
        return 'purchase'
    if name == 'checkout.started':
        return 'checkout'
    if name == 'product.viewed':
        return 'product_view'
    if name == 'search.performed':
        return 'search'
    if name == 'cart.abandoned':
        return 'cart'
    if name == 'customer.registered':
        return 'signup'
    if name.startswith('agent.'):
        return 'agent_run'
    if name.startswith('refund.'):
        return 'refund'
    return 'custom'


@app.task(name='analytics.roll_daily', ignore_result=True, time_limit=300, soft_time_limit=180)
def roll_daily_task() -> int:
    from plugins.installed.analytics.services import roll_daily

    written = roll_daily()
    logger.info('analytics: rolled %d daily metric rows', written)
    return written


@app.task(name='analytics.trim_old_events', ignore_result=True, time_limit=120, soft_time_limit=60)
def trim_old_events_task(keep_days: int = 90) -> int:
    from plugins.installed.analytics.services import trim_old_events

    n = trim_old_events(keep_days=keep_days)
    logger.info('analytics: trimmed %d old events (keep_days=%d)', n, keep_days)
    return n
