"""The newsletter tick at checkout, and what a ticked order does.

While ``checkout_opt_in`` is on, the checkout asks "Email me news and offers"
(CHECKOUT_FIELDS, core/checkout_fields.py), never ticked in advance. A placed order whose
shopper ticked it subscribes the order's email as ``source='checkout'``, pending until
they click the confirmation link, the same double opt-in as the signup forms. A
signed-in shopper who is already a confirmed subscriber is not asked.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils.translation import gettext as _

from plugins.registry import app_registry

logger = logging.getLogger(__name__)

KEY = 'newsletter_opt_in'


def on_checkout_fields(value, user=None, **kwargs):
    """CHECKOUT_FIELDS: the opt-in, unless the shopper already gets the newsletter."""
    value = list(value or [])
    if not app_registry.config_value('newsletter', 'checkout_opt_in', False):
        return value
    email = getattr(user, 'email', '') if getattr(user, 'is_authenticated', False) else ''
    if email:
        from plugins.installed.newsletter.models import NewsletterSubscriber  # noqa: PLC0415

        if NewsletterSubscriber.objects.filter(email=email.lower(), status='confirmed').exists():
            return value
    value.append(
        {
            'key': KEY,
            'label': _('Email me news and offers. I can unsubscribe at any time.'),
            'kind': 'checkbox',
            'help': _('We first send you a link to confirm.'),
            'order': 80,
        }
    )
    return value


def on_order_placed(order=None, **kwargs):
    """ORDER_PLACED: subscribe the shopper who ticked the box, once the order commits."""
    answers = (getattr(order, 'metadata', None) or {}).get('checkout_fields') or {}
    if not isinstance(answers, dict) or not answers.get(KEY):
        return
    email = order.email
    customer = order.customer

    def subscribe_after_commit():
        from plugins.installed.newsletter.services import subscribe  # noqa: PLC0415

        try:
            subscribe(email, source='checkout', customer=customer)
        except Exception:  # noqa: BLE001 — the order stands whatever the mail does
            logger.exception('newsletter: checkout opt-in for order %s failed', order.pk)

    transaction.on_commit(subscribe_after_commit)
