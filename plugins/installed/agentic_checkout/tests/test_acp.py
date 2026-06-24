"""ACP (Agentic Commerce Protocol) Phase 1 — checkout sessions + discovery.

Covers the conformant ``CheckoutSession`` shape, the Cart-backed
create/get/cancel/update flow, the Bearer/scope auth boundary, the
``/.well-known/acp.json`` manifest, and the ``complete`` ``unsupported``
``MessageError``.

The plugin ships OFF by default, so ``setUp`` enables + activates it (which
mounts its ``/acp/`` URLs via the registry) before the Client hits the routes.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.agentic_checkout.plugin import ACP_API_VERSION
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.models import Cart

_TOKEN = 'acp-tok'
_TOKEN_NO_SCOPE = 'acp-tok-noscope'


def _enable_plugin_and_tokens() -> None:
    from plugins.models import PluginConfig
    from plugins.registry import plugin_registry

    # A scoped token + an under-scoped token, both valid Bearer tokens.
    PluginConfig.objects.update_or_create(
        plugin_name='agent_mcp',
        defaults={
            'config': {
                'public_keys': [
                    {'token': _TOKEN, 'acp_scopes': ['acp.checkout', 'catalog.read']},
                    {'token': _TOKEN_NO_SCOPE, 'acp_scopes': ['orders.read']},
                ]
            }
        },
    )
    PluginConfig.objects.update_or_create(
        plugin_name='agentic_checkout',
        defaults={'is_enabled': True},
    )
    # Mount the /acp/ URLs (the plugin is OFF by default so ready() hasn't run).
    plugin_registry.activate('agentic_checkout')


class AcpCheckoutTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        self.product = Product.objects.create(
            name='Test Book',
            slug='acp-test-book',
            sku='ACP-TB1',
            price=Money(20, 'USD'),
            status='active',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Hardcover',
            sku='ACP-TB1-HC',
            price=Money(20, 'USD'),
        )
        self.warehouse = Warehouse.objects.create(name='Main', code='ACPMAIN', is_default=True)
        self.stock = StockLevel.objects.create(
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

    def _get(self, path, token=_TOKEN):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.c.get(path, **headers)

    def _create_session(self, quantity=2):
        return self._post(
            '/acp/checkout_sessions',
            {
                'currency': 'USD',
                'line_items': [
                    {'id': self.variant.sku, 'quantity': quantity},
                ],
                'buyer': {'email': 'agent@example.com', 'first_name': 'Ada'},
                'fulfillment_details': {
                    'address': {
                        'name': 'Ada L',
                        'line_one': '1 Main',
                        'city': 'NYC',
                        'state': 'NY',
                        'country': 'US',
                        'postal_code': '10001',
                    }
                },
            },
        )

    def _assert_conformant(self, session: dict) -> None:
        for key in (
            'id',
            'status',
            'currency',
            'line_items',
            'totals',
            'fulfillment_options',
            'capabilities',
            'messages',
            'links',
            'created_at',
            'updated_at',
        ):
            self.assertIn(key, session, f'CheckoutSession missing {key!r}')
        # capabilities is REQUIRED and must carry a payment.handlers list.
        self.assertIn('payment', session['capabilities'])
        self.assertIsInstance(session['capabilities']['payment']['handlers'], list)
        self.assertIsInstance(session['line_items'], list)
        self.assertIsInstance(session['totals'], list)
        for li in session['line_items']:
            for key in (
                'id',
                'item',
                'quantity',
                'sku',
                'product_id',
                'variant_id',
                'availability_status',
                'totals',
            ):
                self.assertIn(key, li, f'LineItem missing {key!r}')
            for key in ('id', 'name', 'unit_amount'):
                self.assertIn(key, li['item'])
            self.assertIsInstance(li['item']['unit_amount'], int)
        for total in session['totals']:
            for key in ('type', 'display_text', 'amount'):
                self.assertIn(key, total)
            self.assertIsInstance(total['amount'], int)

    # ── create ─────────────────────────────────────────────────────────────

    def test_create_session_returns_conformant_shape(self):
        r = self._create_session(quantity=2)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r['API-Version'], ACP_API_VERSION)
        session = r.json()
        self._assert_conformant(session)
        # The session id IS a Cart id.
        self.assertTrue(Cart.objects.filter(id=session['id']).exists())
        self.assertEqual(len(session['line_items']), 1)
        li = session['line_items'][0]
        self.assertEqual(li['quantity'], 2)
        self.assertEqual(li['sku'], self.variant.sku)
        # 20.00 USD → 2000 minor units; line subtotal = 4000.
        self.assertEqual(li['item']['unit_amount'], 2000)
        self.assertEqual(li['availability_status'], 'in_stock')
        # Buyer + address present → ready_for_payment.
        self.assertEqual(session['status'], 'ready_for_payment')
        total = next(t for t in session['totals'] if t['type'] == 'total')
        self.assertEqual(total['amount'], 4000)

    def test_create_without_buyer_is_not_ready(self):
        r = self._post(
            '/acp/checkout_sessions',
            {'currency': 'USD', 'line_items': [{'id': self.variant.sku, 'quantity': 1}]},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['status'], 'not_ready_for_payment')

    # ── get ────────────────────────────────────────────────────────────────

    def test_get_session(self):
        sid = self._create_session().json()['id']
        r = self._get(f'/acp/checkout_sessions/{sid}')
        self.assertEqual(r.status_code, 200)
        session = r.json()
        self._assert_conformant(session)
        self.assertEqual(session['id'], sid)

    def test_get_unknown_session_404(self):
        r = self._get('/acp/checkout_sessions/00000000-0000-0000-0000-000000000000')
        self.assertEqual(r.status_code, 404)

    # ── update ─────────────────────────────────────────────────────────────

    def test_update_replaces_line_items(self):
        sid = self._create_session(quantity=2).json()['id']
        r = self._post(
            f'/acp/checkout_sessions/{sid}',
            {'line_items': [{'id': self.variant.sku, 'quantity': 5}]},
        )
        self.assertEqual(r.status_code, 200)
        session = r.json()
        self._assert_conformant(session)
        self.assertEqual(session['line_items'][0]['quantity'], 5)
        total = next(t for t in session['totals'] if t['type'] == 'total')
        self.assertEqual(total['amount'], 10000)  # 5 × 2000

    # ── cancel ─────────────────────────────────────────────────────────────

    def test_cancel_session(self):
        sid = self._create_session().json()['id']
        r = self._post(f'/acp/checkout_sessions/{sid}/cancel')
        self.assertEqual(r.status_code, 200)
        session = r.json()
        self.assertEqual(session['status'], 'canceled')
        self.assertEqual(session['line_items'], [])
        # Cart emptied.
        cart = Cart.objects.get(id=sid)
        self.assertEqual(cart.items.count(), 0)

    # ── complete (Phase 2 stub) ──────────────────────────────────────────────

    def test_complete_returns_unsupported_message_error(self):
        sid = self._create_session().json()['id']
        r = self._post(f'/acp/checkout_sessions/{sid}/complete')
        # A 200 would imply CheckoutSessionWithOrder; Phase 1 makes no order, so
        # the unsupported stub MUST come back under a non-200 status.
        self.assertEqual(r.status_code, 422)
        session = r.json()
        self._assert_conformant(session)
        errors = [m for m in session['messages'] if m.get('type') == 'error']
        self.assertTrue(any(m.get('code') == 'unsupported' for m in errors))
        # MessageError shape: content_type + content, NO `message` key.
        err = next(m for m in errors if m.get('code') == 'unsupported')
        self.assertEqual(err['content_type'], 'plain')
        self.assertIn('content', err)
        self.assertNotIn('message', err)

    # ── auth boundary ────────────────────────────────────────────────────────

    def test_no_bearer_rejected(self):
        r = self._post('/acp/checkout_sessions', {'line_items': []}, token=None)
        self.assertEqual(r.status_code, 401)

    def test_invalid_bearer_rejected(self):
        r = self._post('/acp/checkout_sessions', {'line_items': []}, token='nope')
        self.assertEqual(r.status_code, 401)

    def test_valid_token_missing_scope_forbidden(self):
        r = self._post('/acp/checkout_sessions', {'line_items': []}, token=_TOKEN_NO_SCOPE)
        self.assertEqual(r.status_code, 403)

    def test_valid_token_with_scope_allowed(self):
        r = self._post(
            '/acp/checkout_sessions',
            {'currency': 'USD', 'line_items': [{'id': self.variant.sku, 'quantity': 1}]},
            token=_TOKEN,
        )
        self.assertEqual(r.status_code, 201)

    # ── availability messaging ───────────────────────────────────────────────

    def test_out_of_stock_surfaces_message(self):
        self.stock.quantity = 0
        self.stock.save(update_fields=['quantity'])
        r = self._create_session(quantity=1)
        session = r.json()
        li = session['line_items'][0]
        self.assertEqual(li['availability_status'], 'out_of_stock')
        self.assertTrue(
            any(m.get('code') == 'out_of_stock' for m in session['messages']),
        )

    # ── IDOR: cross-cart access is blocked ───────────────────────────────────

    def test_plain_storefront_cart_not_accessible(self):
        """A Cart without the acp_session marker is invisible (404), so an
        acp.checkout token can never read/mutate/cancel a real shopper's cart."""
        plain = Cart.objects.create()  # no acp_session marker
        cid = str(plain.id)
        self.assertEqual(self._get(f'/acp/checkout_sessions/{cid}').status_code, 404)
        self.assertEqual(
            self._post(
                f'/acp/checkout_sessions/{cid}',
                {'line_items': [{'id': self.variant.sku, 'quantity': 1}]},
            ).status_code,
            404,
        )
        self.assertEqual(self._post(f'/acp/checkout_sessions/{cid}/cancel').status_code, 404)
        self.assertEqual(self._post(f'/acp/checkout_sessions/{cid}/complete').status_code, 404)
        # The plain cart was not touched.
        self.assertTrue(Cart.objects.filter(id=cid).exists())

    def test_acp_created_cart_is_retrievable(self):
        sid = self._create_session().json()['id']
        # The marker is persisted on the cart.
        self.assertTrue(Cart.objects.filter(id=sid, metadata__acp_session=True).exists())
        self.assertEqual(self._get(f'/acp/checkout_sessions/{sid}').status_code, 200)

    def test_expired_session_not_found(self):
        from datetime import timedelta

        from django.utils import timezone

        sid = self._create_session().json()['id']
        # Age the cart past the default 60-minute TTL.
        old = timezone.now() - timedelta(minutes=120)
        Cart.objects.filter(id=sid).update(updated_at=old)
        self.assertEqual(self._get(f'/acp/checkout_sessions/{sid}').status_code, 404)

    # ── input validation ─────────────────────────────────────────────────────

    def test_non_numeric_quantity_yields_message_not_500(self):
        r = self._post(
            '/acp/checkout_sessions',
            {'currency': 'USD', 'line_items': [{'id': self.variant.sku, 'quantity': 'lots'}]},
        )
        self.assertEqual(r.status_code, 201)
        session = r.json()
        self.assertEqual(session['line_items'], [])
        self.assertTrue(any(m.get('code') == 'invalid' for m in session['messages']))

    def test_unknown_currency_yields_message_not_charge(self):
        r = self._post(
            '/acp/checkout_sessions',
            {'currency': 'ZZZ', 'line_items': [{'id': self.variant.sku, 'quantity': 1}]},
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(
            any(
                m.get('code') == 'invalid' and m.get('param') == 'currency'
                for m in r.json()['messages']
            )
        )

    def test_update_with_bad_quantity_does_not_empty_cart(self):
        sid = self._create_session(quantity=2).json()['id']
        r = self._post(
            f'/acp/checkout_sessions/{sid}',
            {'line_items': [{'id': self.variant.sku, 'quantity': 'oops'}]},
        )
        self.assertEqual(r.status_code, 200)
        # Bad input must not silently empty the existing cart: the original
        # line (qty 2) survives unchanged.
        cart = Cart.objects.get(id=sid)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.items.first().quantity, 2)
        self.assertTrue(any(m.get('code') == 'invalid' for m in r.json()['messages']))


class AcpManifestTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        self.c = Client()

    def test_acp_manifest_renders(self):
        r = self.c.get('/.well-known/acp.json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['protocolVersion'], ACP_API_VERSION)
        self.assertIn('checkout', data)
        self.assertIn('feed', data)
        self.assertIn('acp.checkout', data['auth']['scopes'])
        self.assertIn('stripe_shared_payment_token', data['capabilities']['payment_handlers'])


class AcpFeedTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        self.c = Client()

    def _get(self, path, token=_TOKEN):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.c.get(path, **headers)

    def test_feed_renders(self):
        r = self._get('/acp/feed.json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['version'], ACP_API_VERSION)
        self.assertIn('products', data)
        self.assertEqual(data['count'], len(data['products']))

    def test_feed_empty_when_google_shopping_unavailable(self):
        """If google_shopping's mapping import fails, the feed serves a valid,
        empty, typed payload instead of a 500."""
        import builtins

        real_import = builtins.__import__

        def _boom(name, *args, **kwargs):
            if name == 'plugins.installed.google_shopping.services.mapping':
                raise ImportError('google_shopping disabled')
            return real_import(name, *args, **kwargs)

        with mock.patch('builtins.__import__', side_effect=_boom):
            r = self._get('/acp/feed.json')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['products'], [])
        self.assertEqual(data['count'], 0)
