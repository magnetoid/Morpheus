"""MCP cart / checkout clusters — conformance + disable-safety.

The agent_mcp cart/checkout clusters expose the buyer-agent build+quote tools
(cart.create/add_item/get, checkout.get_session/set_buyer) that live in this
plugin. They are public (no Bearer) like the ACP surface, and reuse the same
cart-session flow. Completion is NOT exposed here — it stays on /acp/. These
tests drive a full create → add → quote flow over JSON-RPC and lock the
disable-safety contract (agentic_checkout off → clusters empty, UCP manifest
cart/checkout=false).
"""

from __future__ import annotations

import json

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse

CART = '/mcp/cart/v1/'
CHECKOUT = '/mcp/checkout/v1/'


def _rpc(method, params=None, _id=1):
    return json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params or {}})


# tools/call on any cluster (incl. the public cart/checkout ones) requires a
# valid Bearer token — the server-level require_auth=False only lets anonymous
# discovery (tools/list) through. This token carries the cart scopes.
_TOKEN = 'mcp-cart-tok'


def _enable() -> None:
    from plugins.models import PluginConfig
    from plugins.registry import app_registry

    PluginConfig.objects.update_or_create(
        plugin_name='agent_mcp',
        defaults={
            'config': {
                'public_keys': [{'token': _TOKEN, 'mcp_scopes': ['cart.read', 'cart.write']}]
            }
        },
    )
    PluginConfig.objects.update_or_create(
        plugin_name='agentic_checkout', defaults={'is_enabled': True}
    )
    app_registry.activate('agentic_checkout')


class McpCartClusterTests(TestCase):
    def setUp(self) -> None:
        _enable()
        self.addCleanup(self._restore)
        self.product = Product.objects.create(
            name='MCP Book', slug='mcp-book', sku='MCP-B1', price=Money(20, 'USD'), status='active'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='HC', sku='MCP-B1-HC', price=Money(20, 'USD')
        )
        self.warehouse = Warehouse.objects.create(name='Main', code='MCPMAIN', is_default=True)
        StockLevel.objects.create(
            variant=self.variant, warehouse=self.warehouse, quantity=10, reserved_quantity=0
        )
        self.c = Client()

    def _restore(self):
        from plugins.registry import app_registry

        app_registry.activate('agentic_checkout')

    def _call(self, url, name, arguments=None):
        r = self.c.post(
            url,
            data=_rpc('tools/call', {'name': name, 'arguments': arguments or {}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {_TOKEN}',
        )
        return r

    def _session(self, resp):
        body = resp.json()
        self.assertNotIn('error', body, msg=body)
        return json.loads(body['result']['content'][0]['text'])

    # ── conformance: full create → add → quote flow ──────────────────────
    def test_cart_create_add_get_flow(self):
        session = self._session(self._call(CART, 'cart.create'))
        sid = session['id']
        self.assertEqual(session['status'], 'not_ready_for_payment')
        self.assertEqual(session['line_items'], [])

        added = self._session(
            self._call(CART, 'cart.add_item', {'session_id': sid, 'id': 'MCP-B1', 'quantity': 2})
        )
        self.assertEqual(len(added['line_items']), 1)
        self.assertEqual(added['line_items'][0]['quantity'], 2)

        got = self._session(self._call(CART, 'cart.get', {'session_id': sid}))
        self.assertEqual(got['id'], sid)
        self.assertEqual(len(got['line_items']), 1)
        # Totals present (subtotal from 2 × $20).
        total_types = {t['type'] for t in got['totals']}
        self.assertIn('items_base_amount', total_types)

    def test_checkout_set_buyer_quotes_with_address(self):
        sid = self._session(self._call(CART, 'cart.create'))['id']
        self._call(CART, 'cart.add_item', {'session_id': sid, 'id': 'MCP-B1', 'quantity': 1})
        quoted = self._session(
            self._call(
                CHECKOUT,
                'checkout.set_buyer',
                {
                    'session_id': sid,
                    'email': 'buyer@example.com',
                    'shipping_address': {
                        'name': 'A Buyer',
                        'line_one': '1 Main St',
                        'city': 'Lisbon',
                        'country': 'PT',
                        'postal_code': '1000',
                    },
                },
            )
        )
        self.assertEqual(quoted['buyer']['email'], 'buyer@example.com')

    def test_unknown_session_is_a_clean_error(self):
        body = self._call(CART, 'cart.get', {'session_id': 'ffffffff-0000-0000-0000-000000000000'})
        self.assertIn('error', body.json())

    # ── disable-safety: agentic_checkout off → clusters empty + manifest false
    def test_cluster_lists_cart_tools_when_enabled(self):
        r = self.c.post(CART, data=_rpc('tools/list'), content_type='application/json')
        names = {t['name'] for t in r.json()['result']['tools']}
        self.assertIn('cart.create', names)
        self.assertIn('cart.add_item', names)

    def test_disabled_plugin_empties_cluster(self):
        from plugins.registry import app_registry

        app_registry.deactivate('agentic_checkout')
        r = self.c.post(CART, data=_rpc('tools/list'), content_type='application/json')
        names = {t['name'] for t in r.json()['result']['tools']}
        self.assertNotIn('cart.create', names)
        # And a direct call is method-not-found, not a silent success.
        self.assertIn('error', self._call(CART, 'cart.create').json())

    def test_ucp_manifest_capabilities_track_enabled_state(self):
        on = self.c.get('/.well-known/ucp.json').json()['capabilities']
        self.assertTrue(on['cart'])
        self.assertTrue(on['checkout'])

        from plugins.registry import app_registry

        app_registry.deactivate('agentic_checkout')
        off = self.c.get('/.well-known/ucp.json').json()['capabilities']
        self.assertFalse(off['cart'])
        self.assertFalse(off['checkout'])
