"""The storefront concierge can put things in the shopper's cart.

``cart.add_by_slug`` and ``cart.summary`` looked the cart up by a ``status``
field Cart has never had, so every call raised FieldError — and the add wrote
the line directly, skipping the price seam and the cart's own checks. Both now
go through CartService, like the storefront.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from morpheus.core import ToolError
from plugins.installed.agent_core.tools.cart import add_to_cart_tool, get_cart_summary_tool
from plugins.installed.catalog.models import Product


def _product(slug, price):
    return Product.objects.create(
        name=slug, slug=slug, sku=slug.upper(), price=Money(Decimal(price), 'USD'), status='active'
    )


class ConciergeCartTests(TestCase):
    def setUp(self):
        request = RequestFactory().get('/')
        request.session = SessionStore()
        request.session.create()
        self.context = {'request': request}

    def test_adding_by_slug_puts_it_in_the_shoppers_cart(self):
        _product('rose-toner', '5.00')
        add_to_cart_tool.invoke({'slug': 'rose-toner', 'quantity': 1}, context=self.context)
        result = add_to_cart_tool.invoke(
            {'slug': 'rose-toner', 'quantity': 2}, context=self.context
        )
        self.assertEqual(result.output['item']['quantity'], 3)
        summary = get_cart_summary_tool.invoke({}, context=self.context)
        self.assertEqual(summary.output['item_count'], 3)

    def test_the_cart_rules_apply(self):
        _product('unpriced-oil', '0')
        with self.assertRaises(ToolError):
            add_to_cart_tool.invoke({'slug': 'unpriced-oil'}, context=self.context)
