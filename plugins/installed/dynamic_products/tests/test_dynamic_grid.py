"""Real propensity scorecard (arch/automation Phase 1).

`calculate_grid_probabilities()` used to be a mock (constant ~0.4 for every
product). It now scores active products from ACTUAL sales + product-view signals,
runs on a nightly Celery beat, and refreshes (throttled) after each order. These
tests seed real orders/analytics events and assert the ranking + the automation
wiring — replacing the old mock-attribute tests.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.analytics.models import AnalyticsEvent
from plugins.installed.catalog.models import Product
from plugins.installed.dynamic_products.models import DynamicBlock, DynamicGridItem
from plugins.installed.dynamic_products.services import calculate_grid_probabilities, recommend
from plugins.installed.orders.models import Order, OrderItem

Customer = get_user_model()


def _product(slug, *, featured=False):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('10.00'), 'USD'),
        status='active',
        is_featured=featured,
    )


def _paid_order(customer, product, *, status='confirmed'):
    order = Order.objects.create(
        customer=customer,
        email='b@x.io',
        subtotal=Money(Decimal('10.00'), 'USD'),
        total=Money(Decimal('10.00'), 'USD'),
    )
    # status is a protected FSMField — set the paid state via update().
    Order.objects.filter(pk=order.pk).update(status=status)
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        sku=product.sku,
        quantity=1,
        unit_price=product.price,
        total_price=product.price,
    )
    return order


def _views(product, n=1):
    for _ in range(n):
        AnalyticsEvent.objects.create(
            name='product.viewed', kind='product_view', product_slug=product.slug
        )


class PropensityScorecardTests(TestCase):
    def setUp(self):
        self.user = Customer.objects.create_user(username='u', email='u@x.io', password='pw')
        self.hot = _product('hot')
        self.cold = _product('cold')

    def test_scorecard_ranks_hot_above_cold(self):
        _paid_order(self.user, self.hot)  # real sale
        _views(self.hot, n=5)  # real demand
        result = calculate_grid_probabilities()
        self.assertEqual(result['updated'], 2)
        hot = DynamicGridItem.objects.get(product=self.hot)
        cold = DynamicGridItem.objects.get(product=self.cold)
        self.assertGreater(hot.purchase_probability, cold.purchase_probability)
        self.assertGreater(hot.purchase_probability, 0.0)

    def test_recompute_updates_not_duplicates(self):
        _views(self.hot, n=3)
        calculate_grid_probabilities()
        first = DynamicGridItem.objects.get(product=self.hot).purchase_probability
        calculate_grid_probabilities()  # no new signals → same score, no new rows
        self.assertEqual(DynamicGridItem.objects.count(), 2)
        self.assertAlmostEqual(
            DynamicGridItem.objects.get(product=self.hot).purchase_probability, first, places=5
        )

    def test_empty_catalog_is_safe(self):
        Product.objects.all().update(status='draft')
        self.assertEqual(calculate_grid_probabilities()['updated'], 0)


class ProbabilityGridStrategyTests(TestCase):
    def test_orders_by_score_high_first(self):
        hi, lo = _product('hi'), _product('lo')
        DynamicGridItem.objects.create(product=hi, title='Hi', purchase_probability=0.9)
        DynamicGridItem.objects.create(product=lo, title='Lo', purchase_probability=0.2)
        block = DynamicBlock.objects.create(
            name='G', slot='home_below_grid', strategy='probability_grid', limit=4
        )
        products = recommend(block, request=RequestFactory().get('/'))
        self.assertEqual([p.id for p in products], [hi.id, lo.id])


class PaidOrderHelperTests(TestCase):
    def test_canonical_paid_statuses(self):
        from plugins.installed.orders.services import PAID_STATUSES, paid_order_items_qs

        u = Customer.objects.create_user(username='p', email='p@x.io', password='pw')
        book = _product('bk')
        for st in ('confirmed', 'delivered', 'cancelled', 'refunded', 'pending'):
            _paid_order(u, book, status=st)
        # Only the two genuinely-paid statuses count.
        self.assertEqual(paid_order_items_qs().count(), 2)
        for dead in ('cancelled', 'refunded', 'pending', 'paid', 'completed'):
            self.assertNotIn(dead, PAID_STATUSES)


class AutomationWiringTests(TestCase):
    def test_task_and_nightly_beat_registered(self):
        from django.conf import settings

        from plugins.installed.dynamic_products.tasks import recompute_probabilities

        self.assertEqual(recompute_probabilities.name, 'dynamic_products.recompute_probabilities')
        self.assertIn('dynamic_products:recompute_probabilities', settings.CELERY_BEAT_SCHEDULE)

    def test_throttled_refresh_recomputes_then_debounces(self):
        from django.core.cache import cache

        from plugins.installed.dynamic_products.tasks import (
            _REFRESH_LOCK_KEY,
            refresh_probabilities_throttled,
        )

        cache.delete(_REFRESH_LOCK_KEY)  # ensure the window is open
        _product('rf')
        self.assertEqual(refresh_probabilities_throttled().get('updated'), 1)
        # A second call inside the window is debounced, not a second recompute.
        self.assertEqual(refresh_probabilities_throttled().get('skipped'), 'throttled')
