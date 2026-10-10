"""A gateway that cannot capture must say so.

The base ``PaymentGateway.capture()`` returned ``{'success': True}`` without
taking any money. Nothing called it yet, but the first delayed-capture flow
built on the abstraction would have marked unpaid orders captured for every
gateway that never implemented it. A capability the provider lacks fails
closed, like ``refund()`` already does.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.payments.gateway import PaymentGateway


class _NoCapture(PaymentGateway):
    slug = 'nocap'
    label = 'No capture'

    def create_payment_intent(self, *, order, **kwargs) -> dict:
        return {'success': True}


class CaptureBaseTests(SimpleTestCase):
    def test_base_capture_refuses(self):
        result = _NoCapture().capture(transaction=object())
        self.assertFalse(result['success'])
        self.assertIn('capture', result['error'].lower())

    def test_no_shipped_gateway_inherits_a_fake_capture(self):
        from plugins.installed.payments.gateway import gateway_registry

        for gateway in gateway_registry.all():
            with self.subTest(gateway=gateway.slug):
                if type(gateway).capture is PaymentGateway.capture:
                    self.assertFalse(gateway.capture(transaction=object())['success'])
