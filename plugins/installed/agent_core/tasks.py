"""Celery tasks for the agent kernel layer."""

from __future__ import annotations

from celery import shared_task

from plugins.installed.agent_core.scheduler import RUN_LOCK_S, tick


@shared_task(bind=True, time_limit=600, soft_time_limit=540)
def background_agents_tick(self) -> int:
    """Run every active BackgroundAgent whose next_run_at <= now."""
    return tick()


@shared_task(
    bind=True,
    name='agent_core.run_linda_automation',
    time_limit=RUN_LOCK_S,
    soft_time_limit=RUN_LOCK_S - 30,
)
def run_linda_automation(self, automation_id: str) -> str:
    """One Linda automation run (a Janus turn, up to the turn limit plus margin).

    The hard limit is also how long the automation's run lock lives
    (``scheduler.RUN_LOCK_S``), so a worker that dies mid-turn frees it."""
    from plugins.installed.agent_core.linda_automations import run_by_id

    return run_by_id(automation_id)


@shared_task(bind=True, time_limit=120, soft_time_limit=90)
def sweep_stuck_runs(self, older_than_minutes: int = 15) -> dict:
    """Fail AgentRuns wedged in a non-terminal state after their worker died.

    Every transition off 'running'/'queued' happens in-process (the timeout
    guard, the crash guard, the normal-completion save). None of those run if
    the OS process is killed — a Coolify redeploy (`--force-recreate`), an OOM
    kill, or the celery hard time-limit leaves the row `running`/`queued`,
    `ended_at=NULL` forever, shown as perpetually-running in the dashboard and
    skewing run counts. This reaper closes them. `awaiting_approval` is
    EXCLUDED — that's a legitimate long-lived pause on a human decision, not a
    stuck run.
    """
    from datetime import timedelta

    from django.utils import timezone

    from plugins.installed.agent_core.models import AgentRun

    cutoff = timezone.now() - timedelta(minutes=max(1, int(older_than_minutes)))
    swept = AgentRun.objects.filter(
        state__in=('queued', 'running'),
        started_at__lt=cutoff,
    ).update(
        state='failed',
        error='orphaned: worker died before the run reached a terminal state',
        ended_at=timezone.now(),
    )
    return {'ok': True, 'swept': swept}


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
