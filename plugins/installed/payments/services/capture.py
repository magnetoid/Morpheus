"""When a card payment is taken, and taking or releasing a held one.

The payments setting ``capture_mode`` says when the money is taken:

* ``immediate`` (the default): at checkout, as always;
* ``first_parcel``: the card is authorized at checkout and charged when the
  order's first parcel is recorded;
* ``all_shipped``: charged when its last parcel is recorded;
* ``manual``: charged when the merchant says (the order page's Charge button,
  or Linda's ``payments.capture``).

The mode is decided once per order as its payment starts, through the
``PAYMENT_CAPTURE_MODE`` filter so an app may decide per order, and kept on
``order.metadata['capture_mode']``: a retried payment sends Stripe the same
parameters, and a later settings change never moves an order already placed.
A parcel mode needs something to wait for, so an order with a line that does
not ship (a download) is charged at checkout.

A hold is only ever charged on an open order that nothing has paid yet: one on a
cancelled or refunded order, or a second hold on an order already paid or held
(two payment attempts confirmed, or staff marked it paid), is given back
instead, whoever asks. The order is read again from the database for that
check, and a charge and a release of the same hold never run at once.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.payments.capture')

CAPTURE_MODES = ('immediate', 'first_parcel', 'all_shipped', 'manual')
PARCEL_MODES = ('first_parcel', 'all_shipped')
DEFAULT_MODE = 'immediate'

#: Stripe holds a card authorization for about seven days; the sweep acts a day
#: before, at the latest.
MAX_AUTHORIZATION_DAYS = 6
EXPIRY_ACTIONS = ('capture', 'release')
#: An order in one of these is never charged: its hold is given back.
CLOSED_STATUSES = ('cancelled', 'refunded')
#: An order whose payment status is one of these was paid already, by a
#: gateway or by hand, so a hold on it is a second payment.
PAID_STATUSES = ('paid', 'partially_refunded', 'refunded')


def _setting(key: str, default):
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('payments')
    if plugin is None:
        return default
    try:
        return plugin.get_config_value(key, default)
    except Exception:  # noqa: BLE001 — a config problem keeps the default
        return default


def setting_mode() -> str:
    mode = str(_setting('capture_mode', DEFAULT_MODE) or DEFAULT_MODE)
    return mode if mode in CAPTURE_MODES else DEFAULT_MODE


def authorization_days() -> int:
    """How many days a hold waits before ``authorization_expiry`` acts (1–6)."""
    try:
        days = int(_setting('authorization_days', MAX_AUTHORIZATION_DAYS))
    except (TypeError, ValueError):
        days = MAX_AUTHORIZATION_DAYS
    return min(max(days, 1), MAX_AUTHORIZATION_DAYS)


def expiry_action() -> str:
    action = str(_setting('authorization_expiry', 'capture') or 'capture')
    return action if action in EXPIRY_ACTIONS else 'capture'


def remember(order, **values) -> None:
    """Merge ``values`` into ``order.metadata`` without saving the rest of the order."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    md = order.metadata if isinstance(order.metadata, dict) else {}
    order.metadata = {**md, **values}
    Order.objects.filter(pk=order.pk).update(metadata=order.metadata)


def stored_mode(order) -> str:
    md = order.metadata if isinstance(getattr(order, 'metadata', None), dict) else {}
    mode = md.get('capture_mode')
    return mode if mode in CAPTURE_MODES else DEFAULT_MODE


def capture_mode(order) -> str:
    """When this order's card payment is taken, decided once and kept on the order."""
    md = order.metadata if isinstance(order.metadata, dict) else {}
    if md.get('capture_mode') in CAPTURE_MODES:
        return md['capture_mode']
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    mode = hook_registry.filter(MorpheusEvents.PAYMENT_CAPTURE_MODE, setting_mode(), order=order)
    if mode not in CAPTURE_MODES:
        mode = DEFAULT_MODE
    if mode in PARCEL_MODES and not all(
        line_ships(i) for i in order.items.select_related('product', 'variant')
    ):
        mode = DEFAULT_MODE  # a download has no parcel to wait for
    remember(order, capture_mode=mode)
    return mode


def cart_mode(all_lines_ship: bool) -> str:
    """The mode a cart's order will get from the setting, for a payment sheet
    set up before the order exists (the cart page's wallet buttons). An app
    answering ``PAYMENT_CAPTURE_MODE`` for the order itself may still differ;
    that wallet payment then finishes on the payment page."""
    mode = setting_mode()
    if mode in PARCEL_MODES and not all_lines_ship:
        return DEFAULT_MODE
    return mode


def surplus_reason(order, tx) -> str:
    """Why ``tx``'s hold must be given back rather than charged, or ''.

    A closed order is never charged, and an order is paid once: a hold on an
    order that another payment already paid, or that already holds another, is
    a second payment attempt the shopper confirmed (two tabs, a retry)."""
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415

    if order.status in CLOSED_STATUSES:
        return f'The order is {order.status}, so the held payment was given back'
    others = PaymentTransaction.objects.filter(order=order).exclude(pk=tx.pk)
    if (
        order.payment_status in PAID_STATUSES
        or others.filter(status=PaymentTransaction.Status.SUCCEEDED).exists()
    ):
        return 'The order was already paid, so this second held payment was given back'
    held = others.filter(status=PaymentTransaction.Status.AUTHORIZED)
    if tx.authorized_at is not None:
        held = held.filter(authorized_at__lt=tx.authorized_at)
    if held.exists():
        return 'The order already holds a payment, so this second one was given back'
    return ''


def held_transaction(order):
    """The order's authorized card payment that has not been taken yet, or None
    (the first one held, when a second attempt was confirmed too)."""
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415

    return (
        PaymentTransaction.objects.filter(order=order, status=PaymentTransaction.Status.AUTHORIZED)
        .order_by('authorized_at')
        .first()
    )


def _gateway(tx):
    from plugins.installed.payments.gateway import gateway_registry  # noqa: PLC0415

    return gateway_registry.get(tx.provider)


def _clip(text) -> str:
    from core.errors.services import redact_secrets  # noqa: PLC0415

    return redact_secrets(str(text or ''))[:240]


def _fresh(order):
    """The order as the database has it now, not as the caller loaded it
    (the sweep loads 200 at once; a cancel may land meanwhile)."""
    return type(order).objects.get(pk=order.pk)


def _claim(tx) -> bool:
    """One charge or release at a time per hold: a second request (a double
    click, two parcels' tasks, a cancel's release) while the first is with
    Stripe stops here."""
    from django.core.cache import cache  # noqa: PLC0415

    try:
        return bool(cache.add(f'payments:capture:{tx.pk}', 1, 120))
    except Exception:  # noqa: BLE001 — no cache: Stripe's idempotency key still guards it
        return True


def _unclaim(tx) -> None:
    import contextlib  # noqa: PLC0415

    from django.core.cache import cache  # noqa: PLC0415

    with contextlib.suppress(Exception):  # no cache: the claim lapses on its own
        cache.delete(f'payments:capture:{tx.pk}')


def capture_order(order) -> dict:
    """Take the money the order's card authorization holds.

    ``{'success': True}`` once it is taken (the order is then paid and
    ``ORDER_PAID`` has fired), else ``{'success': False, 'error': …}`` with a
    message fit for the merchant, which also goes on the order's timeline.
    A hold that must not be charged (``surplus_reason``, read from the order
    as it is now) is given back instead.
    """
    order = _fresh(order)
    tx = held_transaction(order)
    if tx is None:
        return {'success': False, 'error': 'Nothing on this order is waiting to be charged.'}
    if not _claim(tx):
        return {'success': False, 'error': 'This payment is already being charged or released.'}
    try:
        order = _fresh(order)  # what the order is now that no release can run
        reason = surplus_reason(order, tx)
        if reason:
            _release(tx, reason)
            return {'success': False, 'error': f'{reason}; nothing was charged.'}
        gateway = _gateway(tx)
        if gateway is None:
            result = {
                'success': False,
                'error': f'The {tx.provider} payment method is not installed.',
            }
        else:
            result = gateway.capture(transaction=tx, idempotency_key=f'capture-{tx.pk}')
    finally:
        _unclaim(tx)
    if result.get('success'):
        order.log_event('PAYMENT_CHARGED', message=f'{tx.amount} taken from the held payment')
        _release_others(order, keep=tx)
        status = _fresh(order).status
        if status in CLOSED_STATUSES:
            # It closed while Stripe was charging the card: the money is taken,
            # so the merchant decides about the refund.
            order.log_event(
                'PAYMENT_CHARGED_AFTER_CLOSE',
                message=f'The order was {status} while its payment was being charged; '
                'refund it if the customer should not pay.',
            )
    else:
        order.log_event('PAYMENT_CAPTURE_FAILED', message=_clip(result.get('error')))
    return result


def _release_others(order, keep) -> None:
    """Give back any other hold on an order just charged."""
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415

    for other in PaymentTransaction.objects.filter(
        order=order, status=PaymentTransaction.Status.AUTHORIZED
    ).exclude(pk=keep.pk):
        release_transaction(
            other, reason='The order was already paid, so this second held payment was given back'
        )


def release_transaction(tx, *, reason: str = '') -> dict:
    """Give one held authorization back without charging it.

    The gateway records the release (and its reason) on the order's timeline;
    a failure is recorded here, and the hourly sweep tries a closed order's
    hold again. A hold being charged right now is left to that charge."""
    if not _claim(tx):
        result = {'success': False, 'error': 'The payment is being charged right now.'}
        tx.order.log_event('PAYMENT_RELEASE_FAILED', message=result['error'])
        return result
    try:
        return _release(tx, reason)
    finally:
        _unclaim(tx)


def _release(tx, reason: str) -> dict:
    gateway = _gateway(tx)
    if gateway is None:
        result = {'success': False, 'error': f'The {tx.provider} payment method is not installed.'}
    else:
        result = gateway.void(transaction=tx, reason=_clip(reason))
    if not result.get('success'):
        tx.order.log_event('PAYMENT_RELEASE_FAILED', message=_clip(result.get('error')))
    return result


def release_order(order, *, reason: str = '') -> dict:
    """Give back every held authorization on the order without charging it."""
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415

    holds = list(
        PaymentTransaction.objects.filter(
            order=order, status=PaymentTransaction.Status.AUTHORIZED
        ).order_by('authorized_at')
    )
    if not holds:
        return {'success': False, 'error': 'Nothing on this order is held.'}
    results = [
        release_transaction(tx, reason=reason or 'The held payment was released') for tx in holds
    ]
    failed = [r for r in results if not r.get('success')]
    return failed[0] if failed else {'success': True}


def schedule_capture(order) -> None:
    """Charge the order's held payment once the current transaction commits."""
    if held_transaction(order) is None:
        return
    from django.db import transaction  # noqa: PLC0415

    from plugins.installed.payments.tasks import capture_held_payment  # noqa: PLC0415

    order_id = str(order.pk)
    transaction.on_commit(lambda: capture_held_payment.delay(order_id))


def schedule_release(order, reason: str, tx=None) -> None:
    """Give back ``tx``'s hold (else the order's) once the current transaction commits."""
    if tx is None and held_transaction(order) is None:
        return
    from django.db import transaction  # noqa: PLC0415

    from plugins.installed.payments.tasks import release_held_payment  # noqa: PLC0415

    order_id = str(order.pk)
    tx_id = str(tx.pk) if tx is not None else ''
    transaction.on_commit(lambda: release_held_payment.delay(order_id, reason, tx_id))
