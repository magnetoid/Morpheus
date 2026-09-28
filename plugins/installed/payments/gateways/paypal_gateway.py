"""PayPal gateway — redirect/approval flow on the PaymentGateway abstraction."""

from __future__ import annotations

import logging

from plugins.installed.payments.gateway import PaymentGateway

logger = logging.getLogger('morpheus.payments.paypal')


class PayPalGateway(PaymentGateway):
    slug = 'paypal'
    label = 'PayPal'
    supports_refunds = True
    supports_webhooks = True

    def is_configured(self) -> bool:
        from plugins.installed.payments.services import paypal

        return paypal.is_configured()

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        """Create a PayPal order; the shopper approves at ``approval_url``.

        No ``client_secret`` — checkout redirects to PayPal instead; the
        return view captures and marks the order paid.
        """
        from plugins.installed.payments.models import PaymentTransaction
        from plugins.installed.payments.services import paypal

        result = paypal.create_order(order)
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'PayPal error')}

        tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
            provider='paypal',
            provider_transaction_id=result['paypal_order_id'],
        )
        return {
            'success': True,
            'transaction_id': tx.id,
            'approval_url': result['approval_url'],
        }

    def refund(self, *, transaction, amount, **kwargs) -> dict:
        """Refund via the capture behind this PayPal order.

        The capture id isn't persisted (Stripe pattern) — look it up on the
        PayPal order at refund time.
        """
        from plugins.installed.payments.services import paypal

        paypal_order_id = getattr(transaction, 'provider_transaction_id', '') or ''
        if not paypal_order_id:
            return {'success': False, 'error': 'no PayPal order id on transaction'}
        capture_id = paypal.get_capture_id(paypal_order_id)
        if not capture_id:
            return {'success': False, 'error': 'no capture on PayPal order (unapproved?)'}
        return paypal.refund_capture(capture_id, amount)

    def webhook_verify(self, *, body: bytes, signature: str) -> dict | None:
        """PayPal verification needs the full header set, not one signature —
        the webhook view calls ``services.paypal.verify_webhook`` directly."""
        return None
