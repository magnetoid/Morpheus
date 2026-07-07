"""New recommendation strategies — trending / new_arrivals / best_sellers /
on_sale / similar_price (the 'more strategies' options)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.analytics.models import AnalyticsEvent
from plugins.installed.catalog.models import Product
from plugins.installed.dynamics.models import DynamicBlock
from plugins.installed.dynamics.services import recommend
from plugins.installed.orders.models import Order, OrderItem

Customer = get_user_model()


def _product(slug, *, price='10.00', compare_at=None):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal(price), 'USD'),
        status='active',
    )
    if compare_at is not None:
        p.compare_at_price = Money(Decimal(compare_at), 'USD')
        p.save(update_fields=['compare_at_price'])
    return p


def _paid(customer, product):
    o = Order.objects.create(
        customer=customer,
        email='b@x.io',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )
    Order.objects.filter(pk=o.pk).update(status='confirmed')
    OrderItem.objects.create(
        order=o,
        product=product,
        product_name=product.name,
        sku=product.sku,
        quantity=1,
        unit_price=product.price,
        total_price=product.price,
    )


def _rec(strategy, **kw):
    block = DynamicBlock.objects.create(
        name='B', slot='home_below_grid', strategy=strategy, limit=8
    )
    return recommend(block, request=RequestFactory().get('/'), **kw)


class NewStrategyTests(TestCase):
    def test_new_arrivals_newest_first(self):
        a, b = _product('a'), _product('b')
        Product.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=2))
        Product.objects.filter(pk=b.pk).update(created_at=timezone.now())
        ids = [p.id for p in _rec('new_arrivals')]
        self.assertEqual(ids[0], b.id)

    def test_on_sale_only_discounted(self):
        sale = _product('sale', price='8.00', compare_at='12.00')
        full = _product('full', price='10.00')
        ids = [p.id for p in _rec('on_sale')]
        self.assertIn(sale.id, ids)
        self.assertNotIn(full.id, ids)

    def test_best_sellers_by_units(self):
        hot, cold = _product('hot'), _product('cold')
        u = Customer.objects.create_user(username='u', email='u@x.io', password='pw')
        _paid(u, hot)
        _paid(u, hot)
        _paid(u, cold)
        ids = [p.id for p in _rec('best_sellers')]
        self.assertEqual(ids[0], hot.id)

    def test_trending_by_recent_views(self):
        hot = _product('hot')
        _product('cold')
        for _ in range(3):
            AnalyticsEvent.objects.create(
                name='product.viewed', kind='product_view', product_slug='hot'
            )
        AnalyticsEvent.objects.create(
            name='product.viewed', kind='product_view', product_slug='cold'
        )
        ids = [p.id for p in _rec('trending')]
        self.assertEqual(ids[0], hot.id)

    def test_similar_price_band(self):
        anchor = _product('anchor', price='20.00')
        near = _product('near', price='22.00')  # within ±30%
        far = _product('far', price='90.00')  # outside the band
        ids = [p.id for p in _rec('similar_price', context_product=anchor)]
        self.assertIn(near.id, ids)
        self.assertNotIn(far.id, ids)
        self.assertNotIn(anchor.id, ids)  # excludes the anchor itself
