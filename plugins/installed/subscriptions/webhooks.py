"""Stripe webhook reconciliation — the subscriptions side of the billing loop.

Subscribed to :data:`core.hooks.MorpheusEvents.STRIPE_WEBHOOK_EVENT` in
``plugin.ready()``. The payments plugin owns the raw webhook endpoint +
signature verification + the ``StripeWebhookEvent`` idempotency guard, and
fires that hook for every Stripe event type it does not handle itself. We react
to the billing subset:

* ``invoice.paid``               → mark the cycle paid, advance the period, activate.
* ``invoice.payment_failed``     → open invoice, ``past_due``, arm dunning.
* ``customer.subscription.updated`` → mirror status + period + cancel flag.
* ``customer.subscription.deleted`` → ``cancelled`` / ``expired``.

Everything reads the event **dict-safely** (the payload is a plain dict off the
wire, not a live ``stripe`` resource) and reuses the adapter's state-map /
period helpers so there is a single source of truth for the Stripe→local
translation. Idempotency: reconciliation keys off ``provider_invoice_id`` /
``provider_subscription_id``, so a re-run is a no-op even if the same billing
fact arrives under a fresh event id. Every handler is fail-soft — a broken row
is logged and swallowed, never raised back into the webhook.

Zero migrations: dunning + pre-renewal markers live in ``Subscription.metadata``
(an existing ``JSONField``); no columns are added this slice.
"""

from __future__ import annotations

import logging

from django.utils import timezone

# Reuse the adapter's Stripe→local translation helpers — one source of truth.
from plugins.installed.subscriptions.billing.stripe_adapter import (
    _get,
    _map_state,
    _period,
    _ts_to_dt,
)

logger = logging.getLogger('morpheus.subscriptions.webhooks')


# ── Public hook entry point ──────────────────────────────────────────────────


def handle_stripe_event(event_type=None, payload=None, **_kwargs) -> None:
    """Reconcile one Stripe webhook event onto the local subscription rows.

    ``payload`` is the full Stripe event dict (the bus reserves ``event`` for
    the event name, so the payments dispatcher passes it as ``payload=``).
    Dispatches the billing subset to a per-type handler; unknown types are
    ignored. Fail-soft: any error is logged and swallowed so a subscriber bug
    never fails the webhook (which would make Stripe retry an already-recorded
    event forever).
    """
    try:
        obj = _event_object(payload)
        if obj is None:
            return
        if event_type == 'invoice.paid':
            _handle_invoice_paid(obj)
        elif event_type == 'invoice.payment_failed':
            _handle_invoice_failed(obj)
        elif event_type == 'customer.subscription.updated':
            _handle_subscription_updated(obj)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(obj)
        # else: not a billing event we own — ignore.
    except Exception:  # noqa: BLE001 — never raise back into the webhook
        logger.warning('subscriptions: stripe webhook %s failed', event_type, exc_info=True)


# ── Per-type handlers ────────────────────────────────────────────────────────


def _handle_invoice_paid(inv) -> None:
    """A billing cycle was paid: upsert a paid invoice + advance the period."""
    from plugins.installed.subscriptions.models import SubscriptionInvoice

    sub = _subscription_for(_get(inv, 'subscription'))
    if sub is None:
        return

    invoice_id = str(_get(inv, 'id') or '')
    existing = _existing_invoice(sub, invoice_id)
    if existing is not None and existing.state == 'paid':
        return  # already reconciled — idempotent on provider_invoice_id

    p_start, p_end = _invoice_period(inv)
    amount = _minor_to_money(_get(inv, 'amount_paid'), _get(inv, 'currency'))
    now = timezone.now()

    if existing is not None:
        existing.state = 'paid'
        existing.paid_at = now
        existing.amount = amount
        if p_start is not None:
            existing.period_start = p_start
        if p_end is not None:
            existing.period_end = p_end
        existing.save(update_fields=['state', 'paid_at', 'amount', 'period_start', 'period_end'])
    else:
        SubscriptionInvoice.objects.create(
            subscription=sub,
            provider_invoice_id=invoice_id,
            period_start=p_start or sub.current_period_start or now,
            period_end=p_end or sub.current_period_end or now,
            amount=amount,
            state='paid',
            paid_at=now,
        )

    if p_start is not None:
        sub.current_period_start = p_start
    if p_end is not None:
        sub.current_period_end = p_end
    sub.state = 'active'
    _clear_dunning(sub)
    sub.save(update_fields=['current_period_start', 'current_period_end', 'state', 'metadata'])


def _handle_invoice_failed(inv) -> None:
    """A charge failed: open the invoice, go ``past_due``, arm dunning.

    Stripe Smart Retries owns the retry ladder — we only mirror state and drip
    our own dunning email; we never re-charge here.
    """
    from plugins.installed.subscriptions.models import SubscriptionInvoice

    sub = _subscription_for(_get(inv, 'subscription'))
    if sub is None:
        return

    invoice_id = str(_get(inv, 'id') or '')
    existing = _existing_invoice(sub, invoice_id)
    p_start, p_end = _invoice_period(inv)
    amount = _minor_to_money(
        _get(inv, 'amount_due') or _get(inv, 'amount_paid'), _get(inv, 'currency')
    )
    now = timezone.now()

    if existing is None:
        SubscriptionInvoice.objects.create(
            subscription=sub,
            provider_invoice_id=invoice_id,
            period_start=p_start or sub.current_period_start or now,
            period_end=p_end or sub.current_period_end or now,
            amount=amount,
            state='open',
        )
    elif existing.state not in ('paid', 'void'):
        existing.state = 'open'
        existing.save(update_fields=['state'])

    _enter_past_due(sub, now)


def _handle_subscription_updated(obj) -> None:
    """Mirror a ``customer.subscription.updated``: status + period + cancel flag."""
    sub = _subscription_for(_get(obj, 'id'))
    if sub is None:
        return

    new_state = _map_state(_get(obj, 'status') or '', default=sub.state)
    start, end = _period(obj)
    now = timezone.now()

    sub.state = new_state
    if start is not None:
        sub.current_period_start = start
    if end is not None:
        sub.current_period_end = end
    cape = _get(obj, 'cancel_at_period_end')
    if cape is not None:
        sub.cancel_at_period_end = bool(cape)

    if new_state == 'past_due':
        _arm_dunning(sub, now)
    else:
        _clear_dunning(sub)

    sub.save(
        update_fields=[
            'state',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'metadata',
        ]
    )


def _handle_subscription_deleted(obj) -> None:
    """A subscription ended: ``cancelled`` (or ``expired``)."""
    sub = _subscription_for(_get(obj, 'id'))
    if sub is None:
        return

    sub.state = _map_state(_get(obj, 'status') or 'canceled', default='cancelled')
    sub.cancelled_at = timezone.now()
    _clear_dunning(sub)
    sub.save(update_fields=['state', 'cancelled_at', 'metadata'])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event_object(event):
    """The ``data.object`` sub-dict of a Stripe event payload (``None`` if absent)."""
    data = _get(event, 'data')
    return _get(data, 'object') if data is not None else None


def _subscription_for(provider_subscription_id):
    """The local ``Subscription`` for a Stripe subscription id (``None`` if unknown)."""
    sub_id = str(provider_subscription_id or '').strip()
    if not sub_id:
        return None
    from plugins.installed.subscriptions.models import Subscription

    return Subscription.objects.filter(provider_subscription_id=sub_id).first()


def _existing_invoice(sub, invoice_id):
    """A local invoice row already recorded for this Stripe invoice id (or ``None``)."""
    if not invoice_id:
        return None
    return sub.invoices.filter(provider_invoice_id=invoice_id).first()


def _invoice_period(inv):
    """``(period_start, period_end)`` for the subscription's next cycle.

    Prefers the subscription line's period (the true billing window on the
    post-basil API), falling back to the invoice-level period.
    """
    lines = _get(inv, 'lines')
    data = _get(lines, 'data') if lines is not None else None
    if data:
        period = _get(data[0], 'period')
        if period is not None:
            start = _ts_to_dt(_get(period, 'start'))
            end = _ts_to_dt(_get(period, 'end'))
            if start is not None or end is not None:
                return start, end
    return _ts_to_dt(_get(inv, 'period_start')), _ts_to_dt(_get(inv, 'period_end'))


def _minor_to_money(minor, currency):
    """Stripe minor units + currency → a :class:`Money` (fail-soft on payments absent)."""
    from decimal import Decimal

    from djmoney.money import Money

    code = (currency or 'usd').upper()
    try:
        from plugins.installed.payments.services.money import minor_unit_exponent

        exp = minor_unit_exponent(code)
    except Exception:  # noqa: BLE001 — payments optional; assume 2-dp
        exp = 2
    amount = Decimal(int(minor or 0)) / (Decimal(10) ** exp)
    return Money(amount, code)


# ── Dunning markers (no migration — live in Subscription.metadata) ───────────
#
# The dunning drip (tasks.py) needs two facts with nowhere to store them on the
# row: WHEN the subscription entered past_due (the step-schedule anchor) and
# WHICH steps have already been sent. Both ride in ``metadata['dunning']`` —
# ``{'anchor': <iso>, 'sent': [<step index>, …]}`` — so this slice adds zero
# columns. The anchor is stamped once on entry and preserved across repeated
# failures; the marker is cleared the moment the subscription leaves past_due.


def _enter_past_due(sub, now) -> None:
    """Set ``past_due`` and arm dunning, persisting the row."""
    _arm_dunning(sub, now)
    sub.state = 'past_due'
    sub.save(update_fields=['state', 'metadata'])


def _arm_dunning(sub, now) -> None:
    """Stamp the dunning anchor (once) into ``metadata`` without saving.

    Fresh only on entry — a repeat failure while already dunning keeps the
    original anchor so the step schedule doesn't restart.
    """
    meta = dict(sub.metadata or {})
    if sub.state != 'past_due' or 'dunning' not in meta:
        meta['dunning'] = {'anchor': now.isoformat(), 'sent': []}
        sub.metadata = meta


def _clear_dunning(sub) -> None:
    """Drop the dunning marker from ``metadata`` without saving."""
    meta = dict(sub.metadata or {})
    if 'dunning' in meta:
        meta.pop('dunning', None)
        sub.metadata = meta
