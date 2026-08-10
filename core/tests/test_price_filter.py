"""``PRODUCT_CALCULATE_PRICE`` must actually fire, and fire consistently.

Two plugins subscribed this filter — ai_assistant's AI dynamic pricing and
functions' merchant pricing rules — and **nothing ever fired it**. Every pricing
rule a merchant configured was silently inert: the dashboard accepted the rule,
the plugin reported itself enabled, and the price never moved.

The dangerous half of fixing that is divergence: fire it on the displayed price
but not the charged one and the shopper is quoted $8 and billed $10. These tests
pin both sides to the same helper.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from core.pricing import apply_price_filter
from morpheus.core import MorpheusEvents, hook_registry


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


class _Sub:
    """Temporarily subscribe a pricing handler for the duration of a test."""

    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        hook_registry.register(MorpheusEvents.PRODUCT_CALCULATE_PRICE, self.fn, priority=10)
        return self

    def __exit__(self, *exc):
        hook_registry.unregister(MorpheusEvents.PRODUCT_CALCULATE_PRICE, self.fn)


class PriceFilterGuardTests(TestCase):
    def test_handler_adjusts_price(self):
        with _Sub(lambda value, **kw: _usd(8)):
            self.assertEqual(apply_price_filter(_usd(10)).amount, Decimal('8'))

    def test_no_subscriber_is_a_passthrough(self):
        self.assertEqual(apply_price_filter(_usd(10)).amount, Decimal('10'))

    def test_broken_handler_keeps_the_original_price(self):
        def _boom(value, **kw):
            raise RuntimeError('bad rule')

        with _Sub(_boom):
            self.assertEqual(apply_price_filter(_usd(10)).amount, Decimal('10'))

    def test_non_money_return_is_ignored(self):
        # A handler that forgets to return `value` would otherwise poison the
        # price with None and 500 the product page.
        with _Sub(lambda value, **kw: None):
            self.assertEqual(apply_price_filter(_usd(10)).amount, Decimal('10'))

    def test_negative_price_is_ignored(self):
        with _Sub(lambda value, **kw: _usd(-5)):
            self.assertEqual(apply_price_filter(_usd(10)).amount, Decimal('10'))

    def test_currency_swap_is_ignored(self):
        # Would breach the single-currency cart invariant add_item enforces.
        with _Sub(lambda value, **kw: Money(Decimal('9'), 'EUR')):
            got = apply_price_filter(_usd(10))
            self.assertEqual(str(got.currency), 'USD')
            self.assertEqual(got.amount, Decimal('10'))


class DisplayMatchesChargeTests(TestCase):
    """The seam fires on BOTH the displayed and the charged price."""

    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Widget', slug='widget-pf', sku='PF-1', status='active', price=10
        )

    def test_cart_add_uses_the_adjusted_price(self):
        from plugins.installed.orders.services import CartService

        with _Sub(lambda value, **kw: _usd(8)):
            cart = CartService.get_or_create_cart(session_key='s-pricefilter')
            item = CartService.add_item(cart, str(self.product.id), quantity=1)
        self.assertEqual(item.unit_price.amount, Decimal('8'))

    def test_displayed_price_uses_the_adjusted_price(self):
        from plugins.installed.catalog.graphql.types import ProductType

        resolver = ProductType.price
        fn = getattr(resolver, 'base_resolver', None) or resolver
        wrapped = getattr(fn, 'wrapped_func', None) or getattr(fn, 'func', None)
        with _Sub(lambda value, **kw: _usd(8)):
            shown = (wrapped or fn)(self.product)
        self.assertEqual(str(shown.amount), '8')


class ListingMatchesPdpTests(TestCase):
    """The shelf must quote the same price as the PDP and the cart.

    v0.38 wired the seam into the PDP resolver and the charge path and claimed
    they could not diverge — but the listing surfaces render
    `Product.display_price` straight off the ORM row, which never runs the
    filter. With a pricing rule active the shelf showed the list price while
    the PDP and cart showed the adjusted one.
    """

    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Shelf Book', slug='shelf-book', sku='SB-1', status='active', price=10
        )

    def _card_price(self):
        from django.template import Context, Template

        tpl = Template('{% load pricing %}{% storefront_price product as p %}{{ p.amount }}')
        return Decimal(tpl.render(Context({'product': self.product})).strip())

    def test_card_price_uses_the_seam(self):
        with _Sub(lambda value, **kw: _usd(8)):
            self.assertEqual(self._card_price(), Decimal('8'))

    def test_the_real_product_card_template_uses_the_seam(self):
        """Render the actual card, not a stand-in.

        Testing the tag alone passes even if the template stops calling it —
        which is exactly the no-op a mutation check caught here. This renders
        `_product_card.html` itself so removing the tag fails the build.
        """
        from django.template.loader import render_to_string

        with _Sub(lambda value, **kw: _usd(8)):
            html = render_to_string('storefront/_product_card.html', {'product': self.product})
        self.assertIn('8', html)
        self.assertNotIn('$10', html)

    def test_card_price_unfiltered_without_a_rule(self):
        self.assertEqual(self._card_price(), Decimal('10'))

    def test_home_serialisation_uses_the_seam(self):
        from plugins.installed.storefront.views.home import _serialize_product

        with _Sub(lambda value, **kw: _usd(8)):
            self.assertEqual(_serialize_product(self.product)['price']['amount'], 8.0)

    def test_graphql_dict_is_not_double_filtered(self):
        # The PDP/home dict shape is already filtered upstream.
        from django.template import Context, Template

        tpl = Template('{% load pricing %}{% storefront_price product as p %}{{ p }}')
        out = tpl.render(Context({'product': {'price': '£9'}})).strip()
        self.assertEqual(out, '£9')
