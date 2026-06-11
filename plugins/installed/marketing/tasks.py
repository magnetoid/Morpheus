"""Marketing background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.marketing')


@app.task(
    name='marketing.trigger_cart_recovery_sequence',
    ignore_result=True,
    time_limit=60,
    soft_time_limit=30,
)
def trigger_cart_recovery_sequence(cart_id: str) -> str:
    """Send a single cart-recovery email to a recoverable cart.

    Idempotent: stamps `cart.metadata['recovery_sent_at']` so a re-fire
    of `cart.abandoned` doesn't double-send.
    """
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail
    from django.utils import timezone

    try:
        from plugins.installed.orders.models import Cart
    except ImportError:
        return 'orders-plugin-missing'
    try:
        cart = Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        return 'cart-missing'

    if (getattr(cart, 'metadata', None) or {}).get('recovery_sent_at'):
        return 'already-sent'

    email = ''
    if cart.customer_id and getattr(cart.customer, 'email', None):
        email = cart.customer.email
    if not email:
        return 'no-email-on-cart'

    item_lines = '\n'.join(
        f'  - {it.product.name} × {it.quantity}'
        for it in cart.items.select_related('product').all()
    )
    host = dj_settings.ALLOWED_HOSTS[0] if dj_settings.ALLOWED_HOSTS else 'example.com'
    subject = 'Still thinking about your cart?'
    body = (
        f'You left these in your cart:\n\n{item_lines}\n\n'
        f'Pick up where you left off: https://{host}/cart/\n'
    )
    from_email = getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    try:
        send_mail(subject, body, from_email, [email], fail_silently=True)
    except Exception as e:  # noqa: BLE001
        logger.warning('marketing: cart recovery email failed: %s', e)
        return 'send-failed'

    md = dict(getattr(cart, 'metadata', {}) or {})
    md['recovery_sent_at'] = timezone.now().isoformat()
    if hasattr(cart, 'metadata'):
        cart.metadata = md
        try:  # noqa: SIM105
            cart.save(update_fields=['metadata'])
        except Exception:  # noqa: BLE001, S110
            pass
    return 'sent'
