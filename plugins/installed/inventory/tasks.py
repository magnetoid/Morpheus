"""Inventory background tasks."""

from __future__ import annotations

import logging

from django.utils import timezone

from morph.celery import app

logger = logging.getLogger('morpheus.inventory')

try:
    from plugins.installed.notifications_center.services import notify_all_staff
except ImportError:  # notifications_center not installed

    def notify_all_staff(**kwargs) -> int:  # fail-soft stub
        return 0


@app.task(
    name='inventory.notify_back_in_stock', ignore_result=True, time_limit=60, soft_time_limit=30
)
def notify_back_in_stock(product_id: str) -> int:
    """Email all open BackInStockSubscription rows for this product."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    from plugins.installed.catalog.models import Product
    from plugins.installed.inventory.models import BackInStockSubscription

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return 0

    open_subs = list(
        BackInStockSubscription.objects.filter(
            product=product,
            notified_at__isnull=True,
        )
    )
    if not open_subs:
        return 0

    sent = 0
    subject = f'{product.name} is back in stock'
    host = dj_settings.ALLOWED_HOSTS[0] if dj_settings.ALLOWED_HOSTS else 'example.com'
    body = (
        f'Good news — {product.name} is available again on the shelf.\n\n'
        f'Browse: https://{host}/products/{product.slug}/\n'
    )
    from_email = getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    now = timezone.now()
    for sub in open_subs:
        try:
            send_mail(subject, body, from_email, [sub.email], fail_silently=True)
            sub.notified_at = now
            sub.save(update_fields=['notified_at'])
            sent += 1
        except Exception as e:  # noqa: BLE001
            logger.warning('inventory: notify_back_in_stock email failed: %s', e)
    return sent


@app.task(
    name='inventory.apply_price_schedules', ignore_result=True, time_limit=60, soft_time_limit=30
)
def apply_price_schedules() -> int:
    """Apply any PriceSchedule rows whose effective_at has passed."""
    from plugins.installed.catalog.models import PriceSchedule

    due = list(
        PriceSchedule.objects.filter(
            applied_at__isnull=True,
            effective_at__lte=timezone.now(),
        ).select_related('product', 'variant')
    )
    if not due:
        return 0

    applied = 0
    for sched in due:
        target = sched.variant or sched.product
        target.price = sched.new_price
        update_fields = ['price']
        if sched.new_compare_at is not None and hasattr(target, 'compare_at_price'):
            target.compare_at_price = sched.new_compare_at
            update_fields.append('compare_at_price')
        target.save(update_fields=update_fields)
        sched.applied_at = timezone.now()
        sched.save(update_fields=['applied_at'])
        applied += 1
    return applied


@app.task(
    name='inventory.reconcile_redis_stock', ignore_result=True, time_limit=60, soft_time_limit=30
)
def reconcile_redis_stock() -> dict:
    """Compare Redis stock counters to Postgres source of truth.

    Only runs when the Redis fast-path is in use — when no
    ``stock:*`` keys exist in Redis, returns empty stats and exits.
    Drift > 1% logs a warning at WARNING level.
    """
    try:
        from plugins.installed.inventory.services_redis import reconcile_stock

        return reconcile_stock()
    except Exception as e:  # noqa: BLE001
        logger.debug('inventory: redis reconcile skipped: %s', e)
        return {'checked': 0, 'in_sync': 0, 'drift': []}


# NOTE: abandoned-cart detection lives solely in the cart_abandonment plugin
# (scan_abandoned_carts), which fires CART_ABANDONED exactly once per cart and
# stamps metadata['abandoned_emitted']. inventory used to run a second detector
# with NO idempotency stamp, re-firing CART_ABANDONED for every stale cart on
# every 30-min run — spamming CRM follow-up tasks and recurring LLM recovery
# runs. Removed; there is one owner now.


@app.task(
    name='inventory.run_stockout_forecast', ignore_result=True, time_limit=120, soft_time_limit=90
)
def run_stockout_forecast() -> dict:
    """Daily: reconcile stockout alerts; alert staff for newly opened ones."""
    from plugins.installed.inventory.demand_forecast import sync_stockout_alerts  # noqa: PLC0415

    try:
        result = sync_stockout_alerts()
    except Exception as exc:  # noqa: BLE001 — a beat task must never crash the scheduler
        logger.exception('run_stockout_forecast: sync failed: %s', exc)
        return {'opened': 0, 'resolved': 0, 'error': str(exc)}
    newly = result['opened']
    if newly:
        lines = '\n'.join(
            f'{a.variant} — ~{(a.days_of_cover or 0):.0f}d of cover, reorder {a.suggested_reorder_qty}'
            for a in newly[:10]
        )
        try:
            notify_all_staff(
                kind='inventory.stockout_forecast',
                title=f'{len(newly)} SKU(s) projected to stock out soon',
                body=lines,
                action_url='/dashboard/apps/inventory/stockout-forecast/',
                icon='alert-triangle',
            )
        except Exception as exc:  # noqa: BLE001 — alerting never breaks the job
            logger.warning('run_stockout_forecast: notify failed: %s', exc, exc_info=True)
    # Overstock detection → one batch event for workflows (markdown/promo triggers).
    overstock_count = 0
    try:
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
        from plugins.installed.inventory.demand_forecast import forecast_all  # noqa: PLC0415

        overstock = [r for r in forecast_all() if r.overstocked]
        overstock_count = len(overstock)
        if overstock:
            hook_registry.fire(
                MorpheusEvents.INVENTORY_OVERSTOCK_DETECTED,
                variants=[
                    {
                        'variant_id': r.variant_id,
                        'label': r.variant_label,
                        'available': r.available,
                        'daily_velocity': r.daily_velocity,
                    }
                    for r in overstock
                ],
            )
    except Exception as exc:  # noqa: BLE001 — never break the beat
        logger.warning('run_stockout_forecast: overstock detection failed: %s', exc, exc_info=True)
    return {'opened': len(newly), 'resolved': result['resolved'], 'overstock': overstock_count}
