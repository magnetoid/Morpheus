"""Manual gateway — offline payments (bank transfer, COD, etc.). Always available."""

from __future__ import annotations

from plugins.installed.payments.gateway import PaymentGateway


class ManualGateway(PaymentGateway):
    slug = 'manual'
    label = 'Manual / offline'
    supports_refunds = False
    supports_webhooks = False

    def is_configured(self) -> bool:
        """Offered only once the merchant has written how to pay (bank details):
        without them a shopper who picks it is told nothing."""
        from plugins.installed.payments.models import PaymentGatewayConfig

        row = PaymentGatewayConfig.objects.filter(slug=self.slug).first()
        config = row.config if row and isinstance(row.config, dict) else {}
        return bool(str(config.get('instructions') or '').strip())

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        return {
            'success': True,
            'transaction_id': str(order.id),
            'note': 'Awaiting offline payment confirmation.',
        }
