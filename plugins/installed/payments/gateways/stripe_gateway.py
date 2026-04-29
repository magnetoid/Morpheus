"""Stripe gateway — wraps the existing PaymentService into the new abstraction."""
from __future__ import annotations

import logging

from plugins.installed.payments.gateway import PaymentGateway

logger = logging.getLogger('morpheus.payments.stripe')


class StripeGateway(PaymentGateway):
    slug = 'stripe'
    label = 'Stripe'
    supports_refunds = True
    supports_webhooks = True

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        from plugins.installed.payments.services.stripe import PaymentService
        return PaymentService.create_payment_intent(order)

    def refund(self, *, transaction, amount, **kwargs) -> dict:
        """Issue a Stripe refund against the transaction's PaymentIntent.

        We don't store the charge_id on PaymentTransaction (no schema change
        needed) — instead we retrieve the intent at refund time and read
        ``latest_charge``. Idempotency key is bound to the local transaction
        so retries don't double-refund.
        """
        try:
            import stripe
            from plugins.installed.payments.services.stripe import PaymentService
            stripe.api_key = PaymentService.get_stripe_api_key()
            if not stripe.api_key:
                return {'success': False, 'error': 'STRIPE_SECRET_KEY missing'}
            intent_id = getattr(transaction, 'provider_transaction_id', '') if transaction else ''
            if not intent_id:
                return {'success': False, 'error': 'no payment intent id on transaction'}
            try:
                intent = stripe.PaymentIntent.retrieve(intent_id)
            except Exception as e:  # noqa: BLE001
                return {'success': False, 'error': f'intent retrieve failed: {e}'}
            charge_id = getattr(intent, 'latest_charge', None)
            if not charge_id and getattr(intent, 'charges', None) and intent.charges.data:
                charge_id = intent.charges.data[0].id
            if not charge_id:
                return {'success': False, 'error': 'no charge on intent (uncaptured?)'}

            from decimal import Decimal
            stripe.Refund.create(
                charge=charge_id,
                amount=int(Decimal(str(amount.amount)) * 100),
                idempotency_key=f'morph-refund-{transaction.id}',
            )
            return {'success': True}
        except Exception as e:  # noqa: BLE001
            logger.warning('stripe refund failed: %s', e)
            return {'success': False, 'error': str(e)[:200]}

    def webhook_verify(self, *, body: bytes, signature: str):
        try:
            from plugins.installed.payments.services.stripe import PaymentService
            event = PaymentService.verify_webhook(body, signature)
            return {'type': event.type, 'data': event.data.object} if event else None
        except Exception as e:  # noqa: BLE001
            logger.warning('stripe webhook verify failed: %s', e)
            return None
