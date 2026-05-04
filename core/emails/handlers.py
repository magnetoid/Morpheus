"""Hook → email mapping for the core transactional flow.

Each handler is wrapped with a try/except so a missing template, a typo
in a model field, or a flaky SMTP host can't bring down order placement.
SMTP failures still get logged so they're discoverable in observability.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from core.hooks import hook_registry
from morpheus import events

logger = logging.getLogger('morpheus.emails')

_REGISTERED = False


def register_handlers() -> None:
    """Idempotent: subscribe each domain event to its email sender."""
    global _REGISTERED
    if _REGISTERED:
        return
    hook_registry.register(events.ORDER_PLACED, on_order_placed, priority=70)
    hook_registry.register(events.ORDER_PAID, on_order_paid, priority=70)
    hook_registry.register(events.ORDER_FULFILLED, on_order_fulfilled, priority=70)
    hook_registry.register(events.ORDER_CANCELLED, on_order_cancelled, priority=70)
    hook_registry.register(events.PAYMENT_REFUNDED, on_payment_refunded, priority=70)
    hook_registry.register(events.CUSTOMER_REGISTERED, on_customer_registered, priority=70)
    hook_registry.register(events.CART_ABANDONED, on_cart_abandoned, priority=70)
    hook_registry.register('digital.tokens_issued', on_digital_tokens_issued, priority=70)
    _REGISTERED = True


# ── Senders ──────────────────────────────────────────────────────────────────


def on_order_placed(order: Any, **kwargs: Any) -> None:
    _send(
        template_base='emails/order_placed',
        subject=f'Order #{order.order_number} received',
        to=_order_recipient(order),
        ctx={'order': order},
    )


def on_order_paid(order: Any, **kwargs: Any) -> None:
    _send(
        template_base='emails/order_paid',
        subject=f'Payment confirmed for order #{order.order_number}',
        to=_order_recipient(order),
        ctx={'order': order},
    )


def on_order_fulfilled(order: Any, **kwargs: Any) -> None:
    _send(
        template_base='emails/order_fulfilled',
        subject=f'Order #{order.order_number} is on its way',
        to=_order_recipient(order),
        ctx={'order': order},
    )


def on_order_cancelled(order: Any, **kwargs: Any) -> None:
    _send(
        template_base='emails/order_cancelled',
        subject=f'Order #{order.order_number} cancelled',
        to=_order_recipient(order),
        ctx={'order': order},
    )


def on_digital_tokens_issued(order: Any = None, tokens: Any = None, **kwargs: Any) -> None:
    """Send the customer their download links after payment."""
    if order is None or not tokens:
        return
    to = getattr(order, 'email', None) or getattr(getattr(order, 'customer', None), 'email', None)
    if not to:
        return
    base = ''
    try:
        from plugins.installed.seo.services import _site_base_url
        base = _site_base_url() or ''
    except Exception:  # noqa: BLE001
        pass
    download_links = [
        {
            'product_name': t.product.name,
            'url': f'{base.rstrip("/")}/digital/download/{t.token}/',
            'expires_at': t.expires_at,
            'max_downloads': t.max_downloads,
        }
        for t in tokens
    ]
    _send(
        template_base='emails/digital_download',
        subject=f'Your downloads — order #{order.order_number}',
        to=to,
        ctx={'order': order, 'links': download_links},
    )


def on_cart_abandoned(cart: Any = None, email: Any = None, **kwargs: Any) -> None:
    if cart is None:
        return
    to = email or getattr(getattr(cart, 'customer', None), 'email', None)
    if not to:
        return
    _send(
        template_base='emails/cart_abandoned',
        subject='You left items in your cart',
        to=to,
        ctx={'cart': cart},
    )


def on_customer_registered(customer: Any = None, **kwargs: Any) -> None:
    if customer is None:
        return
    to = getattr(customer, 'email', None)
    if not to:
        return
    _send(
        template_base='emails/welcome',
        subject='Welcome',
        to=to,
        ctx={'customer': customer},
    )


def on_payment_refunded(refund: Any = None, order: Any = None, **kwargs: Any) -> None:
    target = order or getattr(refund, 'order', None)
    if target is None:
        return
    _send(
        template_base='emails/refund_issued',
        subject=f'Refund issued for order #{target.order_number}',
        to=_order_recipient(target),
        ctx={'order': target, 'refund': refund},
    )


# ── Internals ────────────────────────────────────────────────────────────────


def _order_recipient(order: Any) -> str | None:
    return (
        getattr(order, 'email', None)
        or getattr(getattr(order, 'customer', None), 'email', None)
    )


def _send(*, template_base: str, subject: str, to: str | None, ctx: dict) -> None:
    if not to:
        return
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    if not from_email:
        logger.debug('emails: DEFAULT_FROM_EMAIL not set, skipping %s', template_base)
        return
    try:
        text_body = render_to_string(f'{template_base}.txt', ctx)
    except Exception as e:  # noqa: BLE001 — missing template is a soft failure
        logger.warning('emails: text template %s missing: %s', template_base, e)
        return
    try:
        html_body = render_to_string(f'{template_base}.html', ctx)
    except Exception:  # noqa: BLE001 — HTML version is optional
        html_body = None

    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to])
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:  # noqa: BLE001
        logger.warning('emails: send for %s to %s failed: %s', template_base, to, e)
