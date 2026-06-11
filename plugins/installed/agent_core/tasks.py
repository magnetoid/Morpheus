"""Celery tasks for the agent kernel layer."""

from __future__ import annotations

from celery import shared_task

from plugins.installed.agent_core.scheduler import tick


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def background_agents_tick(self) -> int:
    """Run every active BackgroundAgent whose next_run_at <= now."""
    return tick()


@shared_task(bind=True, time_limit=300, soft_time_limit=240)
def generate_daily_digest(self) -> dict:
    """Nightly merchant digest — posted as a MerchantInsight 'report'.

    Pulls yesterday's KPIs, top movers, low-stock alerts and writes a
    single MerchantInsight row that surfaces on /dashboard/ as a Pulse
    card. Skipped when one already exists for today.

    Reads + writes only; never blocks the request path. Failures are
    logged + ignored so a slow analytics query doesn't kill Celery.
    """
    import logging as _logging

    log = _logging.getLogger('morpheus.agent_core.digest')
    try:
        from datetime import timedelta

        from django.utils import timezone

        from plugins.installed.ai_assistant.models import MerchantInsight
    except Exception as exc:  # noqa: BLE001
        log.warning('daily digest skipped — import failed: %s', exc)
        return {'ok': False, 'error': 'import'}

    now = timezone.now()
    today = now.date()
    yday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yday_end = yday_start + timedelta(days=1)

    # Skip if today's digest already exists — idempotent across retries.
    already = MerchantInsight.objects.filter(
        insight_type='report',
        title__startswith="Yesterday's digest",
        created_at__date=today,
    ).exists()
    if already:
        return {'ok': True, 'skipped': 'already exists'}

    bullets = []
    priority = 'low'

    # ── Orders + revenue (yesterday). ─────────────────────────────
    try:
        from plugins.installed.orders.models import Order

        yday = Order.objects.filter(placed_at__gte=yday_start, placed_at__lt=yday_end)
        order_count = yday.count()
        revenue = sum((o.total.amount for o in yday if getattr(o, 'total', None)), 0)
        bullets.append(f'**Orders yesterday:** {order_count} · revenue ≈ {revenue}')
        if order_count == 0:
            priority = 'medium'
    except Exception as exc:  # noqa: BLE001
        log.debug('digest orders failed: %s', exc)

    # ── Low stock alerts. ─────────────────────────────────────────
    try:
        from plugins.installed.inventory.models import StockLevel

        low = list(StockLevel.objects.filter(quantity__lt=5).select_related('variant__product')[:5])
        if low:
            priority = 'high'
            names = ', '.join(
                f'{s.variant.product.name} ({s.quantity})'
                for s in low
                if getattr(s, 'variant', None)
            )
            bullets.append(f'**Low stock:** {names}')
    except Exception as exc:  # noqa: BLE001
        log.debug('digest stock failed: %s', exc)

    # ── Catalogue size for context. ───────────────────────────────
    try:
        from plugins.installed.catalog.models import Product

        active = Product.objects.filter(status='active').count()
        bullets.append(f'**Catalogue:** {active} active products')
    except Exception as exc:  # noqa: BLE001
        log.debug('digest catalog failed: %s', exc)

    body = '\n'.join(bullets) if bullets else 'No notable activity yesterday.'

    MerchantInsight.objects.create(
        insight_type='report',
        priority=priority,
        title=f"Yesterday's digest — {yday_start.date().strftime('%a %b %d')}",
        body=body,
        suggested_action={'label': 'Open analytics', 'url': '/dashboard/analytics/'},
        estimated_impact='Daily snapshot from the agent_core digest task',
    )
    log.info('daily digest posted')
    return {'ok': True, 'bullets': len(bullets), 'priority': priority}
