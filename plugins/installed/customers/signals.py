"""Bridge allauth signup signals onto the Morpheus hook bus.

When allauth fires ``user_signed_up`` (after a successful signup, before
email confirmation), we re-emit ``events.CUSTOMER_REGISTERED`` so any
plugin or core handler subscribed to that event picks it up — including
the transactional-email layer in ``core/emails``.
"""
from __future__ import annotations

import logging

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from morpheus import events, hooks

logger = logging.getLogger('morpheus.customers')


@receiver(user_signed_up)
def _on_user_signed_up(request, user, **kwargs):
    try:
        hooks.fire(events.CUSTOMER_REGISTERED, customer=user)
    except Exception as e:  # noqa: BLE001 — never block signup
        logger.warning('CUSTOMER_REGISTERED fire failed: %s', e, exc_info=True)
