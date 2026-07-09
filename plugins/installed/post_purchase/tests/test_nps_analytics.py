"""NPS analytics — aggregation math + dashboard page + permission boundaries."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.post_purchase.analytics import nps_by_product, nps_summary
from plugins.installed.post_purchase.models import NPSResponse

User = get_user_model()


def _order():
    return Order.objects.create(
        email='n@x.io',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )


def _resp(score):
    return NPSResponse.objects.create(order=_order(), score=score)


class NPSSummaryTests(TestCase):
    def test_nps_math(self):
        for _ in range(6):
            _resp(10)  # promoters (9-10)
        for _ in range(2):
            _resp(8)  # passives (7-8)
        for _ in range(2):
            _resp(3)  # detractors (0-6)
        s = nps_summary(days=90)
        self.assertEqual(s['responses'], 10)
        self.assertEqual(s['promoters'], 6)
        self.assertEqual(s['passives'], 2)
        self.assertEqual(s['detractors'], 2)
        self.assertEqual(s['nps'], 40)  # (6 − 2) / 10 × 100

    def test_empty_db(self):
        s = nps_summary()
        self.assertIsNone(s['nps'])
        self.assertEqual(s['responses'], 0)
        self.assertIsNone(s['response_rate'])

    def test_per_product_splits_multi_item_order(self):
        p1 = Product.objects.create(
            name='Book A', slug='book-a', sku='A', price=Money(Decimal('20'), 'USD')
        )
        p2 = Product.objects.create(
            name='Book B', slug='book-b', sku='B', price=Money(Decimal('20'), 'USD')
        )
        order = _order()
        for p in (p1, p2):
            OrderItem.objects.create(
                order=order,
                product=p,
                product_name=p.name,
                sku=p.sku,
                quantity=1,
                unit_price=p.price,
                total_price=p.price,
            )
        NPSResponse.objects.create(order=order, score=10)  # promoter → both products inherit it
        rows = {r['product']: r for r in nps_by_product(days=90)}
        self.assertEqual(rows['Book A']['nps'], 100)
        self.assertEqual(rows['Book B']['nps'], 100)
        self.assertEqual(rows['Book A']['n'], 1)


class NPSPageTests(TestCase):
    URL = '/dashboard/apps/post_purchase/nps/'

    def test_anon_blocked(self):
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_non_staff_blocked(self):
        u = User.objects.create_user(username='cust', email='c@x.io', password='pw')
        self.client.force_login(u)
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_staff_ok(self):
        staff = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Net Promoter')
