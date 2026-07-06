"""cart_context moved core → orders via register_context_processor (arch-debt 8b).

The nav-bar cart count used to live in core/context_processors.py (a core→
orders.Cart import, wired statically in settings). It now lives in the orders
plugin and is contributed through `register_context_processor`; the request-time
aggregator in plugins/context_processors.py:plugin_context merges it in and
skips it when orders is inactive. These tests prove the mechanism (which had
ZERO consumers before this phase) actually works AND is disable-safe.
"""

from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from plugins.context_processors import plugin_context
from plugins.installed.orders.context_processors import cart_context
from plugins.registry import plugin_registry


class CartContextProcessorTests(TestCase):
    def _request(self):
        req = RequestFactory().get('/')
        req.user = AnonymousUser()
        req.session = import_module(settings.SESSION_ENGINE).SessionStore()
        return req

    def test_orders_contributes_cart_context_owned(self):
        pairs = plugin_registry.context_processors()
        self.assertIn(('orders'), [owner for _f, owner in pairs])
        self.assertIn(cart_context, [f for f, owner in pairs if owner == 'orders'])

    def test_core_no_longer_defines_cart_context(self):
        import core.context_processors as core_cp

        self.assertFalse(hasattr(core_cp, 'cart_context'))

    def test_cart_context_not_listed_statically_in_settings(self):
        # It must NOT be a directly-listed TEMPLATES processor anymore — it is
        # merged by the aggregator instead (otherwise it would run even when
        # orders is disabled).
        procs = settings.TEMPLATES[0]['OPTIONS']['context_processors']
        self.assertNotIn('core.context_processors.cart_context', procs)

    def test_aggregator_merges_cart_item_count_when_active(self):
        ctx = plugin_context(self._request())
        self.assertIn('cart_item_count', ctx)
        self.assertEqual(ctx['cart_item_count'], 0)

    def test_cart_item_count_absent_when_orders_disabled(self):
        self.addCleanup(plugin_registry.activate, 'orders')
        self.assertIn('cart_item_count', plugin_context(self._request()))
        plugin_registry.deactivate('orders')
        # The aggregator skips the orders-owned processor → key gone entirely.
        self.assertNotIn('cart_item_count', plugin_context(self._request()))
