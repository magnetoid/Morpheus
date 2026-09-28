"""Order FSM side-effects — fire the platform hooks on state transitions.

The order transitions (`fulfill`, `cancel`, …) live on the model and are
invoked from many call sites: the dashboard, agent tools, GraphQL, the
marketplace. Firing the hook from each call site is what let
ORDER_FULFILLED / ORDER_CANCELLED rot into dead events — subscribers
(shipment + cancellation emails, stock-reservation release, affiliate
clawback, conversion pixels) were registered but never invoked.

Wiring one `post_transition` receiver here fixes it centrally: any present
or future caller that runs a transition fires the hook, so it can't be
missed again. We map only the transitions whose hook has real subscribers
and isn't already fired elsewhere — ORDER_CONFIRMED/ORDER_PAID are fired
explicitly by the payment/confirm service paths, so they're deliberately
NOT mapped here (avoids double-firing).
"""

from __future__ import annotations

import logging

from django_fsm.signals import post_transition

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order

logger = logging.getLogger('morpheus.orders')

# Target FSM state → the platform event fired once the order reaches it.
_TARGET_EVENTS = {
    'fulfilled': MorpheusEvents.ORDER_FULFILLED,
    'cancelled': MorpheusEvents.ORDER_CANCELLED,
}


def _on_order_transition(sender, instance, name, source, target, **kwargs):
    """Fire the mapped hook after a tracked Order transition.

    django-fsm has already flipped ``instance.status`` to ``target`` by the
    time this runs, so subscribers reading the passed order see the new
    state. Fail-soft: a hook problem must never block the transition itself.
    """
    event = _TARGET_EVENTS.get(target)
    # Shipping straight from processing skips 'fulfilled' — the dashboard's
    # fulfil form does exactly that — so the order's fulfilment (the "on its
    # way" email with tracking, post-purchase follow-ups, merchant webhooks)
    # happens here. Coming from 'fulfilled', it already fired.
    if target == 'shipped' and source != 'fulfilled':
        event = MorpheusEvents.ORDER_FULFILLED
    if event is None:
        return
    try:
        hook_registry.fire(event, order=instance)
    except Exception:  # noqa: BLE001 — a side-effect must not break the order op
        logger.warning(
            'order %s: %s hook failed', getattr(instance, 'pk', '?'), target, exc_info=True
        )


post_transition.connect(_on_order_transition, sender=Order, dispatch_uid='orders.fsm_hooks')
