"""Test payment gateway — a sandbox method that always succeeds.

Lets a merchant run checkout end-to-end without a real processor (QA,
demos, first-run setup). Off by default in production — gate it behind
the plugin's ``test_enabled`` config before exposing it at checkout.
Mirrors the PaymentGateway ABC in the payments plugin.
"""

from __future__ import annotations

from plugins.installed.payments.gateway import PaymentGateway


class TestPaymentGateway(PaymentGateway):
    slug = 'test'
    label = 'Test payment (sandbox)'
    supports_refunds = True
    supports_webhooks = False
    # Offered to signed-in staff only, so a merchant can test checkout on a
    # live store without shoppers seeing a method that takes no money.
    staff_only = True

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        return {
            'success': True,
            'transaction_id': f'test_{order.id}',
            'note': 'Sandbox payment — no real charge was made.',
        }

    def refund(self, *, transaction, amount, **kwargs) -> dict:
        return {'success': True, 'note': 'Sandbox refund — no real money moved.'}
