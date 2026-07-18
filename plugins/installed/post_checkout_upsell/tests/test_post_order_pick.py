"""The post-order upsell pick — config-first, newest-active fallback,
never a title the customer just bought, and the receipt block renders it.
"""

from __future__ import annotations

from decimal import Decimal

from django.template.loader import get_template
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.post_checkout_upsell.templatetags.post_checkout_upsell import (
    post_order_upsell_pick,
)


def _product(slug, status='active'):
    return Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper(),
        status=status,
        price=Money(Decimal('15'), 'USD'),
    )


def _order_of(*products):
    order = Order.objects.create(
        email='b@example.com',
        subtotal=Money(Decimal('15'), 'USD'),
        total=Money(Decimal('15'), 'USD'),
    )
    for p in products:
        OrderItem.objects.create(
            order=order,
            product=p,
            product_name=p.name,
            sku=p.sku,
            quantity=1,
            unit_price=p.price,
            total_price=p.price,
        )
    return order


class PostOrderUpsellPickTests(TestCase):
    def test_no_products_returns_none(self):
        order = _order_of()
        self.assertIsNone(post_order_upsell_pick(order))

    def test_fallback_picks_newest_active_not_in_order(self):
        bought = _product('bought-book')
        _product('draft-book', status='draft')  # never offered
        newest = _product('newest-book')
        order = _order_of(bought)
        pick = post_order_upsell_pick(order)
        self.assertIsNotNone(pick)
        self.assertEqual(pick['slug'], newest.slug)

    def test_never_offers_a_title_just_bought(self):
        only = _product('only-book')
        order = _order_of(only)
        self.assertIsNone(post_order_upsell_pick(order))

    def test_receipt_block_renders_the_pick(self):
        _product('bought-2')
        upsell = _product('upsell-2')
        order = _order_of(Product.objects.get(slug='bought-2'))
        html = get_template('post_checkout_upsell/blocks/post_order.html').render({'order': order})
        self.assertIn(upsell.name, html)
        self.assertIn(f'/products/{upsell.slug}/', html)
