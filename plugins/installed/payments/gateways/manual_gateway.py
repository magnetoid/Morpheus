"""Manual gateway — offline payments (bank transfer, COD, etc.). Always available."""

from __future__ import annotations

from plugins.installed.payments.gateway import PaymentGateway


class ManualGateway(PaymentGateway):
    slug = 'manual'
    label = 'Manual / offline'
    supports_refunds = False
    supports_webhooks = False

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        return {
            'success': True,
            'transaction_id': str(order.id),
            'note': 'Awaiting offline payment confirmation.',
        }
