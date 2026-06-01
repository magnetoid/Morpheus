"""Cash on delivery — pay when the product arrives by mail or courier.

No online charge: the order is placed and left awaiting payment, which is
collected on delivery. Merchant-facing instructions (what the courier
collects, any COD fee note) come from the plugin's ``cod_instructions``
config. No refunds/webhooks — reconciliation is offline.
Mirrors the PaymentGateway ABC in the payments plugin.
"""

from __future__ import annotations

from plugins.installed.payments.gateway import PaymentGateway


class CashOnDeliveryGateway(PaymentGateway):
    slug = 'cod'
    label = 'Cash on delivery'
    supports_refunds = False
    supports_webhooks = False

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        # Order is accepted now; payment is collected by the courier on
        # arrival. The orders FSM keeps it awaiting-payment until then.
        return {
            'success': True,
            'transaction_id': f'cod_{order.id}',
            'note': 'Cash on delivery — payment collected when the order arrives.',
        }
