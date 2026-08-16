"""Stripe Billing adapter — Product/Price sync + subscription lifecycle.

Thin, fail-soft wrapper over the ``stripe`` SDK. Every public method:

* reaches the payments plugin only through its **service layer**
  (:func:`get_or_create_stripe_customer`,
  :meth:`PaymentService.get_stripe_api_key`) via lazy imports, so a merchant
  running manual-only subscriptions without the payments plugin degrades
  gracefully rather than crashing;
* **never raises** into a view/webhook — a missing Stripe key or an SDK error
  comes back as ``''`` (``sync_plan``) or ``{'success': False, 'error': ...}``;
* mirrors the returned Stripe object's status + billing period onto the local
  row, so the rest of the plugin (agent tools, dashboard, membership discount)
  reads a single source of truth.

Zero migrations: every provider column already exists
(``Plan.provider_price_id``, ``Subscription.provider_subscription_id`` /
``current_period_start`` / ``current_period_end``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe

logger = logging.getLogger('morpheus.subscriptions.stripe')


# Stripe ``subscription.status`` → local ``Subscription.state``. Stripe's
# ``canceled`` (one 'l') maps to our ``cancelled``; ``unpaid`` / ``incomplete``
# stay in a recoverable ``past_due`` (dunning territory, Task B);
# ``incomplete_expired`` is terminal → ``expired``.
_STATE_MAP = {
    'trialing': 'trialing',
    'active': 'active',
    'past_due': 'past_due',
    'unpaid': 'past_due',
    'incomplete': 'past_due',
    'incomplete_expired': 'expired',
    'canceled': 'cancelled',
    'paused': 'paused',
}


def _map_state(stripe_status: str, default: str = 'active') -> str:
    """Map a Stripe subscription status to a local state (``default`` if new)."""
    return _STATE_MAP.get((stripe_status or '').strip(), default)


def _stripe_key() -> str:
    """Stripe secret key via the payments plugin's accessor.

    Returns ``''`` when payments is absent / disabled / unconfigured — the
    single signal every method uses to fail soft.
    """
    try:
        from plugins.installed.payments.services.stripe import PaymentService  # noqa: PLC0415

        return (PaymentService.get_stripe_api_key() or '').strip()
    except Exception:  # noqa: BLE001 — payments missing/broken → fail soft
        return ''


def _get(obj, key):
    """Read ``key`` off a Stripe object dict-safely.

    Stripe resources subclass ``dict``, so ``obj.items`` returns
    ``dict.items`` (a bound method), not the subscription items — always read
    by key on a dict.
    """
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _ts_to_dt(ts):
    """Unix seconds → aware UTC datetime (``None`` / ``0`` passes through)."""
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC)


def _period(stripe_sub):
    """``(current_period_start, current_period_end)`` as aware datetimes.

    Reads the billing period from the top-level Subscription; falls back to the
    first subscription item (API version 2025-03-31.basil and later moved the
    period onto items). Either element may be ``None``.
    """
    start = _get(stripe_sub, 'current_period_start')
    end = _get(stripe_sub, 'current_period_end')
    if start is None and end is None:
        items = _get(stripe_sub, 'items')
        data = _get(items, 'data') if items is not None else None
        if data:
            start = _get(data[0], 'current_period_start')
            end = _get(data[0], 'current_period_end')
    return _ts_to_dt(start), _ts_to_dt(end)


class StripeSubscriptionAdapter:
    """Stripe Billing operations for ``Plan(provider='stripe')`` and its subs.

    All classmethods (no per-instance state); mirrors the ``PaymentService``
    service shape. Task B (webhook reconciliation, dunning, pre-renewal) codes
    against these signatures.
    """

    # ── Plan ⇄ Stripe Product + Price ─────────────────────────────────────────
    @classmethod
    def sync_plan(cls, plan) -> str:
        """Ensure a Stripe Product+Price for ``plan``; return its price id.

        Idempotent: a manual plan, or a plan whose ``provider_price_id`` is
        already set, is returned untouched (no Stripe call). A blank id on a
        ``provider='stripe'`` plan triggers a Product+Price create, then stores
        and returns the new price id. Fail soft: Stripe/payments unavailable →
        logged warning, returns ``''``.
        """
        if getattr(plan, 'provider', '') != 'stripe':
            return ''
        existing = (plan.provider_price_id or '').strip()
        if existing:
            return existing

        key = _stripe_key()
        if not key:
            logger.warning('sync_plan: Stripe/payments unavailable — plan %s not synced', plan.pk)
            return ''

        try:
            from plugins.installed.payments.services.money import amount_to_minor  # noqa: PLC0415

            stripe.api_key = key
            currency = plan.price.currency.code.lower()
            unit_amount = amount_to_minor(plan.price.amount, plan.price.currency.code)
            product = stripe.Product.create(name=plan.name, metadata={'plan_id': str(plan.pk)})
            price = stripe.Price.create(
                product=product.id,
                unit_amount=unit_amount,
                currency=currency,
                recurring={'interval': plan.interval, 'interval_count': plan.interval_count},
                metadata={'plan_id': str(plan.pk)},
            )
        except Exception as exc:  # noqa: BLE001 — never raise into a view
            logger.warning('sync_plan: Stripe error for plan %s: %s', plan.pk, exc)
            return ''

        plan.provider_price_id = price.id
        plan.save(update_fields=['provider_price_id'])
        return price.id

    # ── Card collection ───────────────────────────────────────────────────────
    @classmethod
    def payment_method_from_setup_intent(  # noqa: PLR0911 — flat guard clauses, each a refusal
        cls, setup_intent_id: str, customer
    ) -> str:
        """The payment method a *succeeded* SetupIntent collected for ``customer``.

        The storefront hands the browser a SetupIntent, Stripe collects the
        card, and the browser comes back with the SetupIntent id in the URL.
        That id is **caller-supplied**: anyone can paste one. So before it is
        trusted the intent is fetched from Stripe and must (a) be ``succeeded``
        and (b) belong to *this* customer's Stripe vault — otherwise a shopper
        could subscribe with someone else's card. Returns ``''`` on any doubt;
        never raises.
        """
        setup_intent_id = (setup_intent_id or '').strip()
        if not setup_intent_id.startswith('seti_'):
            return ''
        key = _stripe_key()
        if not key:
            return ''
        expected_customer = (getattr(customer, 'stripe_customer_id', '') or '').strip()
        if not expected_customer:
            # A SetupIntent is minted against the customer's vault; a customer
            # with no vault cannot have one that is theirs.
            return ''
        try:
            stripe.api_key = key
            intent = stripe.SetupIntent.retrieve(setup_intent_id)
        except Exception as exc:  # noqa: BLE001 — never raise into a view
            logger.warning('payment_method_from_setup_intent: %s: %s', setup_intent_id, exc)
            return ''
        if _get(intent, 'status') != 'succeeded':
            return ''
        if str(_get(intent, 'customer') or '') != expected_customer:
            logger.warning(
                'payment_method_from_setup_intent: %s belongs to another customer', setup_intent_id
            )
            return ''
        pm = _get(intent, 'payment_method')
        pm_id = _get(pm, 'id') if pm is not None and not isinstance(pm, str) else pm
        return str(pm_id or '')

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    @classmethod
    def start_subscription(cls, subscription, payment_method_id: str) -> dict:
        """Create the Stripe subscription for ``subscription`` and charge it.

        Ensures the customer's Stripe vault, attaches + sets the given payment
        method as the invoice default, syncs the plan's Price, then creates the
        Stripe subscription (trial from ``plan.trial_days``, metadata links back
        to the local row). Stores ``provider_subscription_id`` and mirrors
        status + period onto the local row. Never raises — returns
        ``{'success': True, 'provider_subscription_id': ...}`` or
        ``{'success': False, 'error': ...}``.
        """
        key = _stripe_key()
        if not key:
            logger.warning(
                'start_subscription: Stripe/payments unavailable — subscription %s not started',
                subscription.pk,
            )
            return {'success': False, 'error': 'Stripe billing is unavailable.'}

        price_id = cls.sync_plan(subscription.plan)
        if not price_id:
            return {'success': False, 'error': 'Plan is not a synced Stripe plan.'}

        try:
            from plugins.installed.payments.services.stripe import (  # noqa: PLC0415
                get_or_create_stripe_customer,
            )

            stripe.api_key = key
            customer_id = get_or_create_stripe_customer(subscription.customer)
            if payment_method_id:
                stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={'default_payment_method': payment_method_id},
                )

            params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'metadata': {'subscription_id': str(subscription.pk)},
            }
            if payment_method_id:
                params['default_payment_method'] = payment_method_id
            trial_days = int(getattr(subscription.plan, 'trial_days', 0) or 0)
            if trial_days > 0:
                params['trial_period_days'] = trial_days
            stripe_sub = stripe.Subscription.create(**params)
        except Exception as exc:  # noqa: BLE001 — never raise into a view
            logger.warning(
                'start_subscription: Stripe error for subscription %s: %s', subscription.pk, exc
            )
            return {'success': False, 'error': str(exc)}

        start, end = _period(stripe_sub)
        subscription.provider_subscription_id = stripe_sub.id
        subscription.state = _map_state(getattr(stripe_sub, 'status', ''), default='active')
        if start is not None:
            subscription.current_period_start = start
        if end is not None:
            subscription.current_period_end = end
        subscription.save(
            update_fields=[
                'provider_subscription_id',
                'state',
                'current_period_start',
                'current_period_end',
            ]
        )
        return {'success': True, 'provider_subscription_id': stripe_sub.id}

    @classmethod
    def cancel_subscription(cls, subscription, *, at_period_end: bool = True) -> dict:
        """Cancel the Stripe subscription and mirror the flag locally.

        ``at_period_end=True`` (default) sets ``cancel_at_period_end`` on both
        sides — the customer keeps access until the period ends.
        ``at_period_end=False`` deletes the Stripe subscription immediately and
        flips the local row to ``cancelled``. Never raises; a Stripe error is
        returned as ``{'success': False, ...}`` and the local row is left
        untouched (so we don't cut access on a failed provider call). With no
        Stripe key / provider id (manual sub or payments off) the local row is
        mirrored directly.
        """
        from django.utils import timezone  # noqa: PLC0415

        provider_id = (subscription.provider_subscription_id or '').strip()
        key = _stripe_key()
        if key and provider_id:
            try:
                stripe.api_key = key
                if at_period_end:
                    stripe.Subscription.modify(provider_id, cancel_at_period_end=True)
                else:
                    stripe.Subscription.delete(provider_id)
            except Exception as exc:  # noqa: BLE001 — never raise; don't mirror on failure
                logger.warning(
                    'cancel_subscription: Stripe error for subscription %s: %s',
                    subscription.pk,
                    exc,
                )
                return {'success': False, 'error': str(exc)}

        if at_period_end:
            subscription.cancel_at_period_end = True
            subscription.save(update_fields=['cancel_at_period_end'])
        else:
            subscription.state = 'cancelled'
            subscription.cancel_at_period_end = False
            subscription.cancelled_at = timezone.now()
            subscription.save(update_fields=['state', 'cancel_at_period_end', 'cancelled_at'])
        return {'success': True}

    @classmethod
    def pause_subscription(cls, subscription) -> dict:
        """Pause billing on the Stripe subscription (``pause_collection``) and
        mirror ``state='paused'`` locally. Fail soft."""
        return cls._set_pause(subscription, paused=True)

    @classmethod
    def resume_subscription(cls, subscription) -> dict:
        """Clear the Stripe pause and mirror ``state='active'`` locally. Fail soft."""
        return cls._set_pause(subscription, paused=False)

    @classmethod
    def _set_pause(cls, subscription, *, paused: bool) -> dict:
        provider_id = (subscription.provider_subscription_id or '').strip()
        key = _stripe_key()
        if key and provider_id:
            try:
                stripe.api_key = key
                # An empty ``pause_collection`` clears the pause (Stripe API).
                stripe.Subscription.modify(
                    provider_id,
                    pause_collection={'behavior': 'void'} if paused else '',
                )
            except Exception as exc:  # noqa: BLE001 — never raise; don't mirror on failure
                logger.warning(
                    '%s_subscription: Stripe error for subscription %s: %s',
                    'pause' if paused else 'resume',
                    subscription.pk,
                    exc,
                )
                return {'success': False, 'error': str(exc)}

        subscription.state = 'paused' if paused else 'active'
        subscription.save(update_fields=['state'])
        return {'success': True}
