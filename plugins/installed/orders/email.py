"""Transactional emails for the orders plugin (best-effort, fail-soft)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger('morpheus.orders.email')


def send_order_confirmation(order) -> bool:
    """Render + send the customer's order-confirmation email."""
    if not order.email:
        return False
    ctx = {
        'order': order,
        'store_name': getattr(settings, 'STORE_NAME', 'Morpheus'),
        'store_url': getattr(settings, 'STORE_URL', '').rstrip('/'),
    }
    try:
        text_body = render_to_string('orders/email/order_confirmation.txt', ctx)
        html_body = render_to_string('orders/email/order_confirmation.html', ctx)
    except Exception as e:  # noqa: BLE001 — template missing or render error
        logger.error('orders.email: render failed for %s: %s', order.order_number, e, exc_info=True)
        return False

    subject = f'Your order #{order.order_number}'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [order.email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info('orders.email: confirmation sent for %s -> %s', order.order_number, order.email)
        return True
    except Exception as e:  # noqa: BLE001 — SMTP outage, etc.
        logger.warning('orders.email: send failed for %s: %s', order.order_number, e, exc_info=True)
        return False
