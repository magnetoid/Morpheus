"""Checkout/search surfaces flow through the hooks bus, not direct imports.

CHECKOUT_SHIPPING_RATES, CHECKOUT_GATEWAYS, SEARCH_RANKED_IDS and
SIMILAR_PRODUCTS decouple the storefront from the shipping / payments /
ai_assistant plugins: each surface degrades (free-standard rate, empty
picker, backstop search, hidden PDP section) the moment its owner is
disabled — instead of the shell importing a disabled plugin's services
(the ADR 0023 leak class).
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import RequestFactory, TestCase

from core.hooks import MorpheusEvents, hook_registry
from plugins.registry import plugin_registry


def _request_with_cart(cart_id=None):
    request = RequestFactory().get('/checkout/')
    request.session = {}
    if cart_id is not None:
        request.session['cart_id'] = cart_id
    return request


class ShippingRatesHookTests(TestCase):
    def test_no_cart_returns_empty(self):
        from plugins.installed.storefront.views.checkout import _available_shipping_rates

        self.assertEqual(_available_shipping_rates(_request_with_cart(), {}), [])

    def test_rates_flow_from_shipping_subscriber(self):
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.orders.models import Cart
        from plugins.installed.storefront.views.checkout import _available_shipping_rates

        cart = Cart.objects.create()
        raw = [{'rate_id': 'r1', 'name': 'Express', 'amount': Money(12, 'EUR')}]
        with patch(
            'plugins.installed.shipping.services.list_available_rates', return_value=raw
        ):
            rates = _available_shipping_rates(_request_with_cart(cart.id), {'country': 'DE'})
        self.assertEqual(
            rates,
            [{'id': 'r1', 'label': 'Express', 'amount': Decimal('12'), 'currency': 'EUR'}],
        )

    def test_no_matching_zone_falls_back_to_free_standard(self):
        # Stores without configured zones keep today's behaviour: a free
        # 'Standard delivery' option, never an empty picker.
        from plugins.installed.orders.models import Cart
        from plugins.installed.storefront.views.checkout import _available_shipping_rates

        cart = Cart.objects.create()
        with patch(
            'plugins.installed.shipping.services.list_available_rates', return_value=[]
        ):
            rates = _available_shipping_rates(_request_with_cart(cart.id), {'country': 'DE'})
        self.assertEqual(
            rates,
            [{'id': 'standard', 'label': 'Standard delivery', 'amount': 0, 'currency': 'USD'}],
        )

    def test_fallback_when_shipping_disabled(self):
        from plugins.installed.orders.models import Cart
        from plugins.installed.storefront.views.checkout import _available_shipping_rates

        cart = Cart.objects.create()
        self.addCleanup(plugin_registry.activate, 'shipping')
        plugin_registry.deactivate('shipping')
        rates = _available_shipping_rates(_request_with_cart(cart.id), {})
        self.assertEqual(
            rates,
            [{'id': 'standard', 'label': 'Standard delivery', 'amount': 0, 'currency': 'USD'}],
        )


class GatewayPickerHookTests(TestCase):
    def test_gateways_flow_from_payments_subscriber(self):
        from plugins.installed.storefront.views.checkout_one_page import _payment_methods

        fake = [{'slug': 'stripe', 'label': 'Card'}]
        with patch(
            'plugins.installed.payments.services.routing.picker_gateways', return_value=fake
        ):
            self.assertEqual(_payment_methods(), fake)

    def test_picker_empty_when_payments_disabled(self):
        from plugins.installed.storefront.views.checkout_one_page import _payment_methods

        self.addCleanup(plugin_registry.activate, 'payments')
        plugin_registry.deactivate('payments')
        self.assertEqual(_payment_methods(), [])


class SearchRankingHookTests(TestCase):
    def test_ranked_ids_flow_from_ai_assistant(self):
        class _P:
            def __init__(self, pk):
                self.pk = pk

        with patch(
            'plugins.installed.ai_assistant.services.search.hybrid_search',
            return_value=[_P(3), _P(1)],
        ):
            ids = hook_registry.filter(MorpheusEvents.SEARCH_RANKED_IDS, [], query='pan', limit=80)
        self.assertEqual(ids, [3, 1])

    def test_empty_when_ai_assistant_disabled(self):
        self.addCleanup(plugin_registry.activate, 'ai_assistant')
        plugin_registry.deactivate('ai_assistant')
        ids = hook_registry.filter(MorpheusEvents.SEARCH_RANKED_IDS, [], query='pan', limit=80)
        self.assertEqual(ids, [])


class SimilarProductsHookTests(TestCase):
    def test_similars_flow_from_ai_assistant(self):
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product

        p = Product.objects.create(name='Pan', slug='pan', sku='pan', price=Money(9, 'USD'))
        other = Product.objects.create(name='Hook', slug='hook', sku='hook', price=Money(9, 'USD'))
        with patch(
            'plugins.installed.ai_assistant.services.recommendations.similar_to',
            return_value=[other],
        ):
            rows = hook_registry.filter(MorpheusEvents.SIMILAR_PRODUCTS, [], product=p, limit=4)
        self.assertEqual(rows, [other])

    def test_section_hides_when_ai_assistant_disabled(self):
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product
        from plugins.installed.storefront.views.catalog import _related_products

        Product.objects.create(name='Pan', slug='pan', sku='pan', price=Money(9, 'USD'))
        self.addCleanup(plugin_registry.activate, 'ai_assistant')
        plugin_registry.deactivate('ai_assistant')
        self.assertEqual(_related_products('pan'), [])
