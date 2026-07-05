import logging

import stripe
from django.conf import settings

from plugins.installed.payments.models import PaymentTransaction
from plugins.installed.payments.services.money import amount_to_minor
from plugins.registry import plugin_registry

logger = logging.getLogger('morpheus.payments.stripe')


# ── Saved-card vault helpers ──────────────────────────────────────────────────
#
# Stripe stores cards against a Customer object. We mint one lazily the
# first time a logged-in shopper needs a vault (saved cards on
# checkout, the /account/payment-methods/ page, an off-session retry, …)
# and stash its id on Customer.stripe_customer_id so every future call
# is idempotent. We never delete this even if the customer detaches
# every card — re-using the same `cus_…` keeps Stripe-side analytics
# stable.


def _ensure_api_key():
    stripe.api_key = PaymentService.get_stripe_api_key()


def get_or_create_stripe_customer(customer) -> str:
    """Return the Stripe Customer id for this user, creating one if needed.

    Idempotent: a non-empty `customer.stripe_customer_id` is returned
    untouched. The metadata link back to the Morpheus customer pk lets
    Stripe-side support pivot between the two systems.
    """
    if not customer or not getattr(customer, 'is_authenticated', True):
        raise ValueError('Anonymous customers cannot save payment methods.')
    existing = (getattr(customer, 'stripe_customer_id', '') or '').strip()
    if existing:
        return existing
    _ensure_api_key()
    sc = stripe.Customer.create(
        email=getattr(customer, 'email', '') or '',
        name=getattr(customer, 'full_name', '') or getattr(customer, 'email', '') or '',
        metadata={'morpheus_customer_id': str(customer.pk)},
    )
    customer.stripe_customer_id = sc.id
    customer.save(update_fields=['stripe_customer_id'])
    return sc.id


def create_setup_intent(customer) -> str:
    """Mint a SetupIntent for collecting a card without an immediate charge.

    Returns the `client_secret` the front end mounts in a Stripe Element.
    """
    cus_id = get_or_create_stripe_customer(customer)
    _ensure_api_key()
    si = stripe.SetupIntent.create(
        customer=cus_id,
        payment_method_types=['card'],
        usage='off_session',
        metadata={'morpheus_customer_id': str(customer.pk)},
    )
    return si.client_secret


def list_payment_methods(customer) -> list:
    """Return the customer's saved cards from Stripe (empty list if none).

    Fail-soft: returns [] if the customer has no `stripe_customer_id`
    yet — there's nothing to list, no need to round-trip to Stripe."""
    sc_id = (getattr(customer, 'stripe_customer_id', '') or '').strip()
    if not sc_id:
        return []
    _ensure_api_key()
    resp = stripe.PaymentMethod.list(customer=sc_id, type='card')
    return list(getattr(resp, 'data', []) or [])


def detach_payment_method(payment_method_id: str, customer) -> bool:
    """Detach a card from this customer's vault after verifying ownership.

    The ownership check defeats a CSRF or guessed-id attack: even if an
    attacker submits a valid `pm_…` they don't own, Stripe-side it'd
    belong to a different Customer and we refuse to detach.
    """
    sc_id = (getattr(customer, 'stripe_customer_id', '') or '').strip()
    if not (sc_id and payment_method_id):
        return False
    _ensure_api_key()
    pm = stripe.PaymentMethod.retrieve(payment_method_id)
    if (getattr(pm, 'customer', '') or '') != sc_id:
        return False
    stripe.PaymentMethod.detach(payment_method_id)
    return True


def _maybe_attach_to_saved_cards(order, payment_intent_id: str) -> None:
    """After a PaymentIntent confirms, attach the card to the customer's
    Stripe vault IF the shopper opted in (`order.metadata.save_card`).

    Lives here (and not in the customers plugin) so the side effect
    rides on the existing webhook idempotency guarantees. Failures are
    logged and swallowed: a vault attach failure must not poison the
    success path of a paid order.
    """
    try:
        customer = getattr(order, 'customer', None)
        if customer is None or not payment_intent_id:
            return
        md = getattr(order, 'metadata', None) or {}
        flag = md.get('save_card') if isinstance(md, dict) else None
        if not flag:
            return
        cus_id = get_or_create_stripe_customer(customer)
        _ensure_api_key()
        pi = stripe.PaymentIntent.retrieve(payment_intent_id)
        pm_id = getattr(pi, 'payment_method', '') or ''
        if not pm_id:
            return
        pm = stripe.PaymentMethod.retrieve(pm_id)
        # Already attached to this customer? Nothing to do.
        if (getattr(pm, 'customer', '') or '') == cus_id:
            return
        stripe.PaymentMethod.attach(pm_id, customer=cus_id)
    except Exception:  # noqa: BLE001 — never break ORDER_PAID over a vault hiccup
        logger.warning(
            'save-card attach failed for order %s',
            getattr(order, 'pk', '?'),
            exc_info=True,
        )


class PaymentService:
    """
    Law 5: Business Logic Lives in Services
    Handles interactions with Stripe and internal transaction records.
    """

    @classmethod
    def get_stripe_api_key(cls):
        plugin = plugin_registry.get('payments')
        if plugin:
            return plugin.get_config_value('stripe_secret_key', settings.STRIPE_SECRET_KEY)
        return settings.STRIPE_SECRET_KEY

    @classmethod
    def create_payment_intent(cls, order):
        """
        Creates a Stripe PaymentIntent for a given Order.
        """
        stripe.api_key = cls.get_stripe_api_key()

        # Amount in the currency's minor units (cents for USD; JPY has none).
        amount_minor = amount_to_minor(order.total.amount, order.total.currency.code)

        try:
            # idempotency_key prevents duplicate intents on retry — if Stripe
            # has already seen the same key + amount, it returns the original
            # intent instead of charging twice.
            intent = stripe.PaymentIntent.create(
                amount=amount_minor,
                currency=order.total.currency.code.lower(),
                metadata={'order_id': str(order.id), 'order_number': order.order_number},
                # Let Stripe enable every payment method the merchant has
                # turned on in the dashboard (cards, Apple Pay, Google Pay,
                # Link, Klarna, …). Required for the Express Checkout +
                # Payment Element combo to render wallets.
                automatic_payment_methods={'enabled': True},
                idempotency_key=f'pi-{order.id}-{amount_minor}',
            )

            # Record the pending transaction
            tx = PaymentTransaction.objects.create(
                order=order,
                amount=order.total,
                status=PaymentTransaction.Status.PENDING,
                provider='stripe',
                provider_transaction_id=intent.id,
            )

            return {'success': True, 'client_secret': intent.client_secret, 'transaction_id': tx.id}
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def redeem_delegated_token(cls, order, token):
        """Charge an ACP Shared Payment Token off-session for `order`.

        The agent already collected the card; we confirm in one shot
        (`confirm=True, off_session=True`) — no client secret, no 3DS
        challenge surface. The idempotency key is scoped to the ACP
        *session* (not the order/attempt) and the create params are
        attempt-stable, so a retried ``complete`` — including one after an
        ambiguous connection error — replays the original PaymentIntent
        instead of double-charging. Order linkage is attached afterwards via
        ``PaymentIntent.modify`` so it never destabilises the replayed
        params. Never raises: declines and Stripe errors come back as
        ``{'success': False, ...}`` (plus ``retryable: True`` for
        interrupted/processing outcomes) so the ACP view can map them to a
        conformant 422.
        """
        stripe.api_key = cls.get_stripe_api_key()

        amount_minor = amount_to_minor(order.total.amount, order.total.currency.code)
        # The ACP session id is attached by the ACP view (Order has no
        # metadata column — it rides as an instance attr; read fail-soft).
        md = getattr(order, 'metadata', None) or {}
        acp = md.get('acp') if isinstance(md, dict) else None
        acp_session = str((acp or {}).get('session_id') or '')
        if acp_session:
            idempotency_key = f'acp-{acp_session}'
        else:
            logger.warning(
                'redeem_delegated_token: order %s has no ACP session id; '
                'falling back to an order-scoped idempotency key',
                order.pk,
            )
            idempotency_key = f'acp-{order.id}'

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_minor,
                currency=order.total.currency.code.lower(),
                payment_method=token,
                confirm=True,
                off_session=True,
                metadata={'acp_session': acp_session},
                idempotency_key=idempotency_key,
            )
        except stripe.error.CardError as e:
            message = e.user_message or 'Payment was declined.'
            PaymentTransaction.objects.create(
                order=order,
                amount=order.total,
                status=PaymentTransaction.Status.FAILED,
                provider='stripe',
                error_message=message,
            )
            return {'success': False, 'error': message, 'decline_code': e.code or ''}
        except stripe.error.APIConnectionError as e:
            # Ambiguous outcome — the charge may or may not have reached
            # Stripe (timeouts land here too; stripe-python wraps them in
            # APIConnectionError). No intent id is known so no transaction
            # row; the caller retries the SAME session and the session-scoped
            # idempotency key makes the replay safe.
            logger.warning('redeem_delegated_token: connection error for order %s: %s', order.pk, e)
            return {
                'success': False,
                'error': 'Payment processing was interrupted — retry this completion.',
                'retryable': True,
            }
        except stripe.error.StripeError as e:
            # Log the raw error server-side; never leak Stripe internals to
            # the agent-facing surface.
            logger.error(
                'redeem_delegated_token: stripe error for order %s: %s',
                order.pk,
                e,
                exc_info=True,
            )
            return {'success': False, 'error': 'Payment could not be processed.'}

        # Order linkage lives OUTSIDE the idempotent create so a replayed
        # retry sends byte-identical create params. Best-effort: a linkage
        # hiccup must never fail an already-confirmed charge.
        try:
            stripe.PaymentIntent.modify(
                intent.id,
                metadata={
                    'acp_session': acp_session,
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                },
            )
        except Exception:  # noqa: BLE001 — linkage is best-effort
            logger.warning(
                'redeem_delegated_token: metadata linkage failed for intent %s', intent.id
            )

        if intent.status == 'processing':
            # Asynchronous confirmation — not failed, not yet paid. The
            # payment_intent.succeeded webhook promotes this PENDING row
            # when the charge settles.
            PaymentTransaction.objects.create(
                order=order,
                amount=order.total,
                status=PaymentTransaction.Status.PENDING,
                provider='stripe',
                provider_transaction_id=intent.id,
            )
            return {
                'success': False,
                'error': 'Payment is processing.',
                'decline_code': 'processing',
                'retryable': True,
            }

        if intent.status != 'succeeded':
            # requires_action & friends — agents can't drive a 3DS
            # challenge in v1, so treat it as a decline.
            message = 'Payment requires additional authentication'
            PaymentTransaction.objects.create(
                order=order,
                amount=order.total,
                status=PaymentTransaction.Status.FAILED,
                provider='stripe',
                provider_transaction_id=intent.id,
                error_message=message,
            )
            return {'success': False, 'error': message, 'decline_code': 'authentication_required'}

        tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.SUCCEEDED,
            provider='stripe',
            provider_transaction_id=intent.id,
        )
        return {'success': True, 'transaction_id': tx.id, 'payment_intent_id': intent.id}

    @classmethod
    def process_webhook(cls, payload, sig_header):
        """
        Processes a Stripe webhook to update transaction statuses.

        Idempotent. Every Stripe event carries a unique ``event.id`` and
        Stripe retries the endpoint aggressively until it sees 2xx, so
        the same event arrives multiple times in normal operation. The
        first thing we do is insert a ``StripeWebhookEvent`` row; the
        unique constraint on ``stripe_event_id`` turns concurrent /
        retried deliveries into an ``IntegrityError`` we treat as
        "already processed, return success".
        """
        from django.db import IntegrityError  # noqa: PLC0415
        from django.db import transaction as db_tx  # noqa: PLC0415
        from django.utils import timezone  # noqa: PLC0415

        from plugins.installed.payments.models import StripeWebhookEvent  # noqa: PLC0415

        plugin = plugin_registry.get('payments')
        webhook_secret = plugin.get_config_value(
            'stripe_webhook_secret', settings.STRIPE_WEBHOOK_SECRET
        )
        stripe.api_key = cls.get_stripe_api_key()

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError as e:
            raise Exception('Invalid payload') from e
        except stripe.error.SignatureVerificationError as e:
            raise Exception('Invalid signature') from e

        try:
            # The savepoint matters: without it, the failed INSERT poisons
            # any enclosing transaction (tests, ATOMIC_REQUESTS) and every
            # later query raises TransactionManagementError.
            with db_tx.atomic():
                event_row = StripeWebhookEvent.objects.create(
                    stripe_event_id=event.id,
                    event_type=event.type,
                    payload=event.to_dict() if hasattr(event, 'to_dict') else dict(event),
                )
        except IntegrityError:
            # Duplicate event id — Stripe retried while the first
            # delivery was still in flight (or completed). The original
            # handler owns the side effects.
            return True

        try:
            if event.type == 'payment_intent.succeeded':
                payment_intent = event.data.object
                cls._mark_transaction_success(payment_intent.id)
            elif event.type == 'payment_intent.payment_failed':
                payment_intent = event.data.object
                cls._mark_transaction_failed(
                    payment_intent.id, payment_intent.last_payment_error.message
                )
        except Exception as exc:  # noqa: BLE001 — record + re-raise so Stripe retries
            event_row.error = str(exc)[:5000]
            event_row.save(update_fields=['error'])
            raise
        event_row.is_processed = True
        event_row.processed_at = timezone.now()
        event_row.save(update_fields=['is_processed', 'processed_at'])
        return True

    @classmethod
    def _mark_transaction_success(cls, intent_id):
        """Idempotent — the `select_for_update` + status check guarantees
        ORDER_PAID fires exactly once per payment, even if Stripe retries
        the webhook concurrently (it does, aggressively)."""
        from django.db import transaction as db_tx  # noqa: PLC0415

        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        with db_tx.atomic():
            tx = (
                PaymentTransaction.objects.select_for_update()
                .filter(provider_transaction_id=intent_id)
                .first()
            )
            if not tx or tx.status == PaymentTransaction.Status.SUCCEEDED:
                return  # already processed — webhook retry, ignore

            tx.status = PaymentTransaction.Status.SUCCEEDED
            tx.save(update_fields=['status'])

            # Advance both Order columns. Status was previously left at
            # 'pending' so the dashboard kept showing paid orders as
            # unpaid; flip to 'confirmed' so the order list, fulfillment
            # queue, and analytics all see the correct state.
            # Order.status is a protected FSMField — direct assignment
            # raises AttributeError — so go through the confirm()
            # transition, which also logs the ORDER_CONFIRMED event.
            order = tx.order
            order.payment_status = 'paid'
            if order.status == 'pending':
                order.confirm()
                order.save(update_fields=['payment_status', 'status'])
            else:
                order.save(update_fields=['payment_status'])

        # Saved-card vault: if the shopper opted in at checkout (stored
        # on order.metadata.save_card), attach the card they just used
        # to their Stripe Customer so it's available for off-session
        # reuse. Runs OUTSIDE the DB transaction — a Stripe RTT inside a
        # locked row would hold the lock far longer than necessary.
        _maybe_attach_to_saved_cards(order, intent_id)

        # Fire AFTER the transaction commits so subscribers see the new
        # row state and don't have to worry about partial writes.
        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)

    @classmethod
    def _mark_transaction_failed(cls, intent_id, error_msg):
        """Atomic + select_for_update to mirror _mark_transaction_success.

        Without the lock, a concurrent webhook retry + a manual admin
        update can torn-write `status` and `error_message` on the same
        row. Also short-circuits when the transaction is already in a
        terminal state so a re-delivery doesn't overwrite a later
        success-then-refund history.
        """
        from django.db import transaction as db_tx  # noqa: PLC0415

        with db_tx.atomic():
            tx = (
                PaymentTransaction.objects.select_for_update()
                .filter(provider_transaction_id=intent_id)
                .first()
            )
            if not tx or tx.status in (
                PaymentTransaction.Status.FAILED,
                PaymentTransaction.Status.SUCCEEDED,
            ):
                return
            tx.status = PaymentTransaction.Status.FAILED
            tx.error_message = error_msg
            tx.save(update_fields=['status', 'error_message'])
