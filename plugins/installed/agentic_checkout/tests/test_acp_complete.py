"""ACP Phase 2 — the money path (``complete`` + eligibility gate).

Stripe is mocked at the ``PaymentService.redeem_delegated_token`` boundary
(the Task-A contract): success / decline come back as dicts, never raises.
Covers the ``payments_enabled`` config gate, order creation + confirmation,
delegation evidence, idempotent retry, validation errors, and the
``agentic.exclude`` per-product eligibility gate (session-create + feed).
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.agentic_checkout.plugin import ACP_API_VERSION
from plugins.installed.agentic_checkout.tests.test_acp import (
    _TOKEN,
    _enable_plugin_and_tokens,
)
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.models import Cart, Order

_REDEEM = 'plugins.installed.payments.services.stripe.PaymentService.redeem_delegated_token'
_SPT = 'spt_test_123'
_OK = {'success': True, 'transaction_id': 1, 'payment_intent_id': 'pi_test_1'}
_DECLINED = {'success': False, 'error': 'Your card was declined.', 'decline_code': 'card_declined'}


def _set_acp_config(**config) -> None:
    from plugins.models import PluginConfig

    row, _ = PluginConfig.objects.get_or_create(plugin_name='agentic_checkout')
    row.config = {**(row.config or {}), **config}
    row.is_enabled = True
    row.save()


class AcpCompleteTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        _set_acp_config(payments_enabled=True)
        self.product = Product.objects.create(
            name='Test Book',
            slug='acp-pay-book',
            sku='ACP-PAY1',
            price=Money(20, 'USD'),
            status='active',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Hardcover',
            sku='ACP-PAY1-HC',
            price=Money(20, 'USD'),
        )
        self.warehouse = Warehouse.objects.create(name='Main', code='ACPPAY', is_default=True)
        StockLevel.objects.create(
            variant=self.variant,
            warehouse=self.warehouse,
            quantity=10,
            reserved_quantity=0,
        )
        self.c = Client()

    # ── helpers ────────────────────────────────────────────────────────────

    def _post(self, path, body=None, token=_TOKEN):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.c.post(
            path,
            data=json.dumps(body or {}),
            content_type='application/json',
            **headers,
        )

    def _create_session(self, *, buyer=True, fulfillment=True):
        body = {
            'currency': 'USD',
            'line_items': [{'id': self.variant.sku, 'quantity': 2}],
        }
        if buyer:
            body['buyer'] = {'email': 'agent@example.com', 'first_name': 'Ada'}
        if fulfillment:
            body['fulfillment_details'] = {
                'address': {
                    'name': 'Ada L',
                    'line_one': '1 Main',
                    'city': 'NYC',
                    'state': 'NY',
                    'country': 'US',
                    'postal_code': '10001',
                }
            }
        return self._post('/acp/checkout_sessions', body)

    def _complete(self, sid, body=None):
        if body is None:
            body = {'payment_data': {'token': _SPT, 'provider': 'stripe'}}
        return self._post(f'/acp/checkout_sessions/{sid}/complete', body)

    @staticmethod
    def _error_codes(session: dict) -> list[str]:
        return [m.get('code') for m in session.get('messages', []) if m.get('type') == 'error']

    # ── config gate ──────────────────────────────────────────────────────────

    def test_payments_disabled_preserves_unsupported(self):
        _set_acp_config(payments_enabled=False)
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            r = self._complete(sid)
        self.assertEqual(r.status_code, 422)
        self.assertIn('unsupported', self._error_codes(r.json()))
        self.assertEqual(Order.objects.count(), 0)
        redeem.assert_not_called()

    # ── success path ─────────────────────────────────────────────────────────

    def test_complete_success_places_paid_order(self):
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            r = self._complete(sid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['API-Version'], ACP_API_VERSION)
        session = r.json()
        self.assertEqual(session['status'], 'completed')
        # Snapshot keeps the purchased line items on the completed session.
        self.assertEqual(len(session['line_items']), 1)

        order = Order.objects.get()
        self.assertEqual(session['order']['id'], str(order.id))
        self.assertEqual(session['order']['checkout_session_id'], sid)
        self.assertTrue(session['order']['permalink_url'].startswith('http'))
        self.assertIn(
            f'/order/confirmation/{order.order_number}/', session['order']['permalink_url']
        )

        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(order.source, 'agent:acp')

        # The ACP session id rode into redeem on the metadata instance attr.
        redeem.assert_called_once()
        order_arg, token_arg = redeem.call_args[0]
        self.assertEqual(token_arg, _SPT)
        self.assertEqual(order_arg.metadata['acp']['session_id'], sid)

        # Cart stamped for idempotent retries.
        cart = Cart.objects.get(id=sid)
        self.assertEqual(cart.metadata.get('acp_order_id'), str(order.id))

    def test_complete_success_records_evidence_metafield(self):
        try:
            from plugins.installed.metafields.models import Metafield
        except ImportError:
            self.skipTest('metafields plugin not installed')
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK):
            r = self._complete(sid)
        self.assertEqual(r.status_code, 200)
        order = Order.objects.get()
        evidence = Metafield.objects.for_obj(order, ns='acp').get('acp.evidence')
        self.assertIsInstance(evidence, dict)
        self.assertEqual(evidence['api_version'], ACP_API_VERSION)
        self.assertEqual(evidence['session_id'], sid)
        self.assertEqual(evidence['spt_last4'], _SPT[-4:])
        self.assertEqual(len(evidence['token_fingerprint']), 16)
        self.assertIn('completed_at', evidence)

    # ── idempotent retry ─────────────────────────────────────────────────────

    def test_retry_after_success_returns_same_order_without_new_charge(self):
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            first = self._complete(sid)
            second = self._complete(sid)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['status'], 'completed')
        self.assertEqual(second.json()['order']['id'], first.json()['order']['id'])
        self.assertEqual(Order.objects.count(), 1)
        redeem.assert_called_once()

    # ── decline path ─────────────────────────────────────────────────────────

    def test_decline_returns_payment_declined_order_unpaid(self):
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_DECLINED):
            r = self._complete(sid)
        self.assertEqual(r.status_code, 422)
        session = r.json()
        self.assertIn('payment_declined', self._error_codes(session))
        err = next(m for m in session['messages'] if m.get('code') == 'payment_declined')
        self.assertEqual(err.get('param'), 'card_declined')
        # Webhook failure convention: order recorded, left pending/unpaid.
        order = Order.objects.get()
        self.assertEqual(order.payment_status, 'unpaid')
        self.assertEqual(order.status, 'pending')
        # No retry stamp — the session is NOT completed.
        cart = Cart.objects.get(id=sid)
        self.assertNotIn('acp_order_id', cart.metadata or {})

    # ── validation ───────────────────────────────────────────────────────────

    def test_missing_email_and_address_rejected(self):
        sid = self._create_session(buyer=False, fulfillment=False).json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            r = self._complete(sid)
        self.assertEqual(r.status_code, 422)
        codes = self._error_codes(r.json())
        self.assertIn('missing', codes)
        params = {m.get('param') for m in r.json()['messages'] if m.get('code') == 'missing'}
        self.assertIn('buyer.email', params)
        self.assertIn('fulfillment_details.address', params)
        self.assertEqual(Order.objects.count(), 0)
        redeem.assert_not_called()

    def test_non_stripe_provider_unsupported(self):
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            r = self._complete(sid, {'payment_data': {'token': _SPT, 'provider': 'paypal'}})
        self.assertEqual(r.status_code, 422)
        self.assertIn('unsupported', self._error_codes(r.json()))
        self.assertEqual(Order.objects.count(), 0)
        redeem.assert_not_called()

    def test_empty_token_invalid(self):
        sid = self._create_session().json()['id']
        with mock.patch(_REDEEM, return_value=_OK) as redeem:
            r = self._complete(sid, {'payment_data': {'token': '', 'provider': 'stripe'}})
        self.assertEqual(r.status_code, 422)
        self.assertIn('invalid', self._error_codes(r.json()))
        redeem.assert_not_called()


class AcpEligibilityTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        self.product = Product.objects.create(
            name='Excluded Book',
            slug='acp-excl-book',
            sku='ACP-EXCL1',
            price=Money(20, 'USD'),
            status='active',
        )
        self.other = Product.objects.create(
            name='Eligible Book',
            slug='acp-elig-book',
            sku='ACP-ELIG1',
            price=Money(15, 'USD'),
            status='active',
        )
        self.c = Client()

    def _exclude(self, product) -> None:
        try:
            from plugins.installed.metafields.models import Metafield
        except ImportError:
            self.skipTest('metafields plugin not installed')
        Metafield.objects.set(product, namespace='agentic', key='exclude', value=True)

    def _post(self, path, body, token=_TOKEN):
        return self.c.post(
            path,
            data=json.dumps(body),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def test_excluded_product_rejected_at_session_create(self):
        self._exclude(self.product)
        r = self._post(
            '/acp/checkout_sessions',
            {'currency': 'USD', 'line_items': [{'id': self.product.sku, 'quantity': 1}]},
        )
        self.assertEqual(r.status_code, 201)
        session = r.json()
        self.assertEqual(session['line_items'], [])
        self.assertTrue(
            any(
                m.get('code') == 'invalid' and m.get('param') == 'line_items'
                for m in session['messages']
            )
        )

    def test_feed_flags_excluded_product_ineligible(self):
        self._exclude(self.product)

        def _fake_map(product, settings):
            return {
                'id': product.sku,
                'title': product.name,
                'description': '',
                'link': '',
                'image_link': 'https://example.com/img.jpg',
                'price': '20.00 USD',
                'availability': 'in_stock',
            }

        with (
            mock.patch(
                'plugins.installed.google_shopping.services.mapping.map_product',
                side_effect=_fake_map,
            ),
            mock.patch(
                'plugins.installed.google_shopping.services.mapping.expand_variants',
                return_value=[],
            ),
        ):
            r = self.c.get('/acp/feed.json', HTTP_AUTHORIZATION=f'Bearer {_TOKEN}')
        self.assertEqual(r.status_code, 200)
        by_id = {item['id']: item for item in r.json()['products']}
        self.assertFalse(by_id[self.product.sku]['is_eligible_checkout'])
        self.assertTrue(by_id[self.other.sku]['is_eligible_checkout'])
