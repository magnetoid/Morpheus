"""Inventory background tasks."""

from __future__ import annotations

import logging

from django.utils import timezone

from morph.celery import app

logger = logging.getLogger('morpheus.inventory')


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


@app.task(
    name='inventory.find_abandoned_carts', ignore_result=True, time_limit=120, soft_time_limit=60
)
def find_abandoned_carts() -> int:
    """Mark carts > 1h old as abandoned and fire the cart.abandoned event."""
    from datetime import timedelta

    from core.hooks import MorpheusEvents, hook_registry

    try:
        from plugins.installed.orders.models import Cart
    except ImportError:
        return 0
    threshold = timezone.now() - timedelta(hours=1)
    candidates = (
        Cart.objects.filter(
            updated_at__lt=threshold,
        )
        .exclude(items__isnull=True)
        .distinct()[:200]
    )
    fired = 0
    for cart in candidates:
        try:
            # Standard CART_ABANDONED contract: every fire site passes
            # both `cart=` AND `email=` so subscribers (recovery email,
            # CRM, AI) can opt to use either without crashing.
            email = getattr(getattr(cart, 'customer', None), 'email', '') or ''
            hook_registry.fire(
                MorpheusEvents.CART_ABANDONED,
                cart=cart,
                email=email or None,
            )
            fired += 1
        except Exception as e:  # noqa: BLE001
            logger.warning('inventory: cart.abandoned fire failed: %s', e)
    return fired
