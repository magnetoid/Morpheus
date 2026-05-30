"""Bridge allauth signup signals onto the Morpheus hook bus.

When allauth fires ``user_signed_up`` (after a successful signup, before
email confirmation), we re-emit ``events.CUSTOMER_REGISTERED`` so any
plugin or core handler subscribed to that event picks it up — including
the transactional-email layer in ``core/emails``.
"""

from __future__ import annotations

import logging

from allauth.account.signals import user_signed_up
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from core.hooks import MorpheusEvents, hook_registry
from morpheus import events, hooks
from plugins.installed.orders.models import Cart
from plugins.installed.orders.services import merge_carts

logger = logging.getLogger('morpheus.customers')


@receiver(user_signed_up)
def _on_user_signed_up(request, user, **kwargs):
    try:
        hooks.fire(events.CUSTOMER_REGISTERED, customer=user)
    except Exception as e:  # noqa: BLE001 — never block signup
        logger.warning('CUSTOMER_REGISTERED fire failed: %s', e, exc_info=True)


@receiver(user_logged_in)
def _on_user_logged_in(sender, request, user, **kwargs):
    try:
        hook_registry.fire(MorpheusEvents.CUSTOMER_LOGIN, customer=user, request=request)
    except Exception as e:  # noqa: BLE001 — never block login
        logger.warning('CUSTOMER_LOGIN fire failed: %s', e, exc_info=True)

    # Cart hand-off: the user just authenticated, so any cart they built
    # as a guest in this session should follow them onto their account.
    # Wrapped end-to-end so a cart hiccup never breaks the login itself.
    try:
        _merge_session_cart_on_login(request, user)
    except Exception as e:  # noqa: BLE001 — never block login
        logger.warning('cart merge on login failed: %s', e, exc_info=True)


def _merge_session_cart_on_login(request, user) -> None:
    """Reconcile the anonymous-session cart with the customer's cart.

    Cart has no ``status`` field — there's at most one (customer, ) cart
    per user today, so we just match on ``customer=user``. Both lookups
    use ``.first()`` because neither side is guaranteed to exist.
    """
    session_key = getattr(getattr(request, 'session', None), 'session_key', '') or ''
    if not session_key:
        return

    session_cart = Cart.objects.filter(session_key=session_key, customer=None).first()
    if session_cart is None:
        return

    customer_cart = Cart.objects.filter(customer=user).first()

    if customer_cart is None:
        # No existing customer cart — adopt the session cart wholesale.
        session_cart.customer = user
        session_cart.session_key = ''
        session_cart.save(update_fields=['customer', 'session_key', 'updated_at'])
        return

    if session_cart.pk == customer_cart.pk:
        return

    merge_carts(source_cart=session_cart, target_cart=customer_cart)
