"""PayPal gateway tests — REST contract, redirect flow, mark-paid idempotency.

The REST layer is mocked at the ``requests`` boundary (the real HTTP
interface), not our own wrappers — assertions check the exact payloads
PayPal would receive.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order
from plugins.installed.payments.gateway import gateway_registry
from plugins.installed.payments.models import PaymentGatewayConfig, PaymentTransaction
from plugins.installed.payments.services import paypal, routing
from plugins.installed.payments.views import paypal_return, paypal_webhook


def _make_order(amount='42'):
    return Order.objects.create(
        email='shopper@example.com',
        subtotal=Money(Decimal(amount), 'USD'),
        total=Money(Decimal(amount), 'USD'),
    )


def _resp(json_data, status=200):
    r = mock.Mock()
    r.json.return_value = json_data
    r.status_code = status
    r.raise_for_status.return_value = None
    return r


_CONFIG = {
    'client_id': 'cid',
    'client_secret': 'csecret',
    'mode': 'sandbox',
    'webhook_id': 'WH-1',
    'enabled': True,
}

_CREATE_ORDER_JSON = {
    'id': 'PPORDER1',
    'status': 'PAYER_ACTION_REQUIRED',
    'links': [
        {'rel': 'self', 'href': 'https://api.sandbox.paypal.com/x'},
        {
            'rel': 'payer-action',
            'href': 'https://www.sandbox.paypal.com/checkoutnow?token=PPORDER1',
        },
    ],
}

_CAPTURE_JSON = {
    'id': 'PPORDER1',
    'status': 'COMPLETED',
    'purchase_units': [{'payments': {'captures': [{'id': 'CAP1'}]}}],
}


class PayPalGatewayTests(TestCase):
    def setUp(self):
        cache.clear()
        PaymentGatewayConfig.objects.update_or_create(slug='paypal', defaults={'enabled': True})

    def _mock_post(self, responses):
        """Patch requests.post to return canned responses per URL substring."""

        def side_effect(url, **kwargs):
            for frag, data in responses.items():
                if frag in url:
                    return _resp(data)
            raise AssertionError(f'unexpected POST {url}')

        return mock.patch.object(paypal.requests, 'post', side_effect=side_effect)

    def test_create_intent_maps_amount_and_returns_approval_url(self):
        order = _make_order('19.99')
        captured = {}

        def side_effect(url, **kwargs):
            if 'oauth2/token' in url:
                return _resp({'access_token': 'tok', 'expires_in': 32400})
            if '/v2/checkout/orders' in url:
                captured['body'] = kwargs['json']
                return _resp(_CREATE_ORDER_JSON)
            raise AssertionError(url)

        with (
            mock.patch.object(paypal.requests, 'post', side_effect=side_effect),
            mock.patch.object(paypal, 'get_config', return_value=_CONFIG),
        ):
            result = routing.create_payment_intent_for(order, 'paypal')

        self.assertTrue(result['success'])
        self.assertEqual(
            result['approval_url'], 'https://www.sandbox.paypal.com/checkoutnow?token=PPORDER1'
        )
        # Exact amount/currency mapping in the PayPal payload.
        unit = captured['body']['purchase_units'][0]
        self.assertEqual(unit['amount'], {'currency_code': 'USD', 'value': '19.99'})
        self.assertEqual(unit['invoice_id'], order.order_number)
        # Pending transaction recorded with the PayPal order id.
        tx = PaymentTransaction.objects.get(order=order, provider='paypal')
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(tx.provider_transaction_id, 'PPORDER1')
        # Routing recorded the gateway on the order.
        self.assertEqual(
            Order.objects.values_list('payment_gateway', flat=True).get(pk=order.pk), 'paypal'
        )

    def test_create_intent_failure_bubbles_error(self):
        order = _make_order()

        def side_effect(url, **kwargs):
            if 'oauth2/token' in url:
                return _resp({'access_token': 'tok', 'expires_in': 32400})
            raise OSError('paypal down')

        with (
            mock.patch.object(paypal.requests, 'post', side_effect=side_effect),
            mock.patch.object(paypal, 'get_config', return_value=_CONFIG),
        ):
            result = routing.create_payment_intent_for(order, 'paypal')
        self.assertFalse(result['success'])
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 0)


class PayPalReturnFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()
        self.order = _make_order('10')
        self.tx = PaymentTransaction.objects.create(
            order=self.order,
            amount=self.order.total,
            status=PaymentTransaction.Status.PENDING,
            provider='paypal',
            provider_transaction_id='PPORDER1',
        )

    def _return(self, token='PPORDER1'):
        req = self.rf.get(f'/payments/paypal/return/?token={token}')
        # messages framework needs a session/middleware stand-in
        req.session = mock.MagicMock()
        req._messages = mock.MagicMock()
        return paypal_return(req)

    def test_return_captures_marks_paid_and_fires_order_paid_once(self):
        seen = []
        hook_registry.register(MorpheusEvents.ORDER_PAID, lambda **kw: seen.append(kw['order'].pk))

        with (
            mock.patch.object(
                paypal, 'capture_order', return_value={'success': True, 'capture_id': 'CAP1'}
            ) as cap,
            mock.patch.object(paypal, 'get_config', return_value=_CONFIG),
        ):
            resp = self._return()
            # Second hit (refresh) — must not fire ORDER_PAID again.
            self._return()

        self.assertEqual(resp.status_code, 302)
        self.assertIn(f'/order/confirmation/{self.order.order_number}/', resp['Location'])
        self.assertEqual(seen.count(self.order.pk), 1)
        cap.assert_called_once()  # second hit short-circuits on SUCCEEDED tx
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.SUCCEEDED)
        self.assertEqual(
            Order.objects.values_list('payment_status', flat=True).get(pk=self.order.pk), 'paid'
        )

    def test_return_capture_failure_bounces_to_checkout(self):
        with (
            mock.patch.object(
                paypal, 'capture_order', return_value={'success': False, 'error': 'DECLINED'}
            ),
            mock.patch.object(paypal, 'get_config', return_value=_CONFIG),
        ):
            resp = self._return()
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/checkout/', resp['Location'])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentTransaction.Status.PENDING)

    def test_return_with_unknown_token_bounces(self):
        resp = self._return('NOPE')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/checkout/', resp['Location'])


class PayPalRefundTests(TestCase):
    def test_refund_looks_up_capture_and_posts_amount(self):
        gw = gateway_registry.get('paypal')
        self.assertIsNotNone(gw)
        order = _make_order('30')
        tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.SUCCEEDED,
            provider='paypal',
            provider_transaction_id='PPORDER9',
        )
        sent = {}

        def post_side_effect(url, **kwargs):
            if 'oauth2/token' in url:
                return _resp({'access_token': 'tok', 'expires_in': 32400})
            if '/refund' in url:
                sent['url'] = url
                sent['body'] = kwargs['json']
                return _resp({'status': 'COMPLETED'})
            raise AssertionError(url)

        def get_side_effect(url, **kwargs):
            assert 'PPORDER9' in url
            return _resp(_CAPTURE_JSON)

        with (
            mock.patch.object(paypal.requests, 'post', side_effect=post_side_effect),
            mock.patch.object(paypal.requests, 'get', side_effect=get_side_effect),
            mock.patch.object(paypal, 'get_config', return_value=_CONFIG),
        ):
            result = gw.refund(transaction=tx, amount=Money(Decimal('12.50'), 'USD'))

        self.assertTrue(result['success'])
        self.assertIn('/v2/payments/captures/CAP1/refund', sent['url'])
        self.assertEqual(sent['body']['amount'], {'currency_code': 'USD', 'value': '12.50'})


class PayPalWebhookTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()

    def _post(self, body=b'{}'):
        return self.rf.post(
            '/payments/webhooks/paypal/', data=body, content_type='application/json'
        )

    def test_unverified_webhook_rejected(self):
        with mock.patch.object(paypal, 'verify_webhook', return_value=None):
            resp = paypal_webhook(self._post())
        self.assertEqual(resp.status_code, 400)

    def test_capture_completed_marks_paid_idempotently(self):
        order = _make_order('5')
        PaymentTransaction.objects.create(
            order=order,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
            provider='paypal',
            provider_transaction_id='PPORDER7',
        )
        event = {
            'event_type': 'PAYMENT.CAPTURE.COMPLETED',
            'resource': {
                'id': 'CAP7',
                'supplementary_data': {'related_ids': {'order_id': 'PPORDER7'}},
            },
        }
        seen = []
        hook_registry.register(MorpheusEvents.ORDER_PAID, lambda **kw: seen.append(kw['order'].pk))
        with mock.patch.object(paypal, 'verify_webhook', return_value=event):
            resp1 = paypal_webhook(self._post())
            resp2 = paypal_webhook(self._post())  # PayPal retries aggressively
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(seen.count(order.pk), 1)

    def test_other_event_types_acked_without_side_effects(self):
        with mock.patch.object(
            paypal, 'verify_webhook', return_value={'event_type': 'OTHER.EVENT'}
        ):
            resp = paypal_webhook(self._post())
        self.assertEqual(resp.status_code, 200)


class ApplePayDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()

    def test_serves_and_caches_stripe_file(self):
        from plugins.installed.payments import views

        with mock.patch('requests.get', return_value=_resp(None)) as rg:
            rg.return_value.content = b'APPLE-PAY-BLOB'
            r1 = views.apple_pay_domain_association(self.rf.get('/x'))
            r2 = views.apple_pay_domain_association(self.rf.get('/x'))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.content, b'APPLE-PAY-BLOB')
        self.assertEqual(r2.content, b'APPLE-PAY-BLOB')
        rg.assert_called_once()  # second hit served from cache

    def test_fetch_failure_is_404(self):
        from plugins.installed.payments import views

        with mock.patch('requests.get', side_effect=OSError('down')):
            resp = views.apple_pay_domain_association(self.rf.get('/x'))
        self.assertEqual(resp.status_code, 404)


class PayPalPickerTests(TestCase):
    def test_disabled_paypal_not_in_picker(self):
        PaymentGatewayConfig.objects.update_or_create(slug='paypal', defaults={'enabled': False})
        slugs = [g['slug'] for g in routing.picker_gateways()]
        self.assertNotIn('paypal', slugs)

    def test_enabled_paypal_in_picker(self):
        PaymentGatewayConfig.objects.update_or_create(slug='paypal', defaults={'enabled': True})
        slugs = [g['slug'] for g in routing.picker_gateways()]
        self.assertIn('paypal', slugs)

    def test_sync_gateway_row_projects_toggle_and_credentials(self):
        with mock.patch.object(paypal, 'get_config', return_value=dict(_CONFIG)):
            paypal.sync_gateway_row()
        self.assertTrue(PaymentGatewayConfig.objects.get(slug='paypal').enabled)
        # Toggle on but credentials missing → projected OFF.
        broken = dict(_CONFIG, client_secret='')
        with mock.patch.object(paypal, 'get_config', return_value=broken):
            paypal.sync_gateway_row()
        self.assertFalse(PaymentGatewayConfig.objects.get(slug='paypal').enabled)
