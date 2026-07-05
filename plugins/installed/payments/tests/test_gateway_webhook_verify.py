"""Regression tests for the Stripe gateway's webhook verification path.

``StripeGateway.webhook_verify`` used to call a non-existent
``PaymentService.verify_webhook``; it now resolves to a real classmethod that
shares ``process_webhook``'s construct-event logic. The ``stripe`` SDK is
mocked at the ``construct_event`` boundary — these exercise the gateway wiring,
not Stripe's HMAC.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import TestCase

from plugins.installed.payments.gateways.stripe_gateway import StripeGateway
from plugins.installed.payments.services.stripe import PaymentService


class GatewayWebhookVerifyTests(TestCase):
    def test_verify_webhook_classmethod_exists(self):
        # The dangling reference is gone: the method the gateway calls is real.
        self.assertTrue(callable(PaymentService.verify_webhook))

    def test_gateway_returns_type_and_object_on_valid_signature(self):
        event = SimpleNamespace(type='invoice.paid', data=SimpleNamespace(object={'id': 'in_1'}))
        with mock.patch('stripe.Webhook.construct_event', return_value=event) as construct:
            result = StripeGateway().webhook_verify(body=b'{"x": 1}', signature='sig_header')

        construct.assert_called_once()
        self.assertEqual(result, {'type': 'invoice.paid', 'data': {'id': 'in_1'}})

    def test_gateway_returns_none_on_bad_signature(self):
        err = stripe.error.SignatureVerificationError('bad sig', 'sig_header')
        with mock.patch('stripe.Webhook.construct_event', side_effect=err):
            result = StripeGateway().webhook_verify(body=b'{}', signature='sig_header')

        self.assertIsNone(result)
