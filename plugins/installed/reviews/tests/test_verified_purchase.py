"""A review is published at once only from someone who bought the product.

Approved reviews feed the product's `aggregateRating` in structured data, a
public claim (CLAUDE.md). Any signed-in account's review was approved on submit,
and signing up does not verify an email, so anyone could rate anything; nothing
ever set `is_verified_purchase` either (found 2026-10-12). Now a buyer's review
is approved and marked verified; anyone else's waits for the merchant.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Review
from plugins.installed.orders.models import Order, OrderItem


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def paid_order_for(user, product):
    order = Order.objects.create(
        email=user.email, customer=user, subtotal=_usd(10), total=_usd(10), payment_status='paid'
    )
    OrderItem.objects.create(
        order=order, product=product, product_name=product.name, sku=product.sku,
        quantity=1, unit_price=_usd(10), total_price=_usd(10),
    )  # fmt: skip
    return order


class VerifiedPurchaseReviewTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Reviewed Lamp', slug='reviewed-lamp', sku='RL-1', status='active', price=_usd(10)
        )
        self.user = get_user_model().objects.create_user(
            username='buyer@example.com', email='buyer@example.com', password='pw-12345!'
        )
        self.client.force_login(self.user)
        self.url = f'/reviews/add/{self.product.id}/'

    def _review(self):
        return Review.objects.get(product=self.product, customer=self.user)

    def test_a_buyers_review_is_published_and_marked_verified(self):
        paid_order_for(self.user, self.product)
        self.client.post(self.url, {'rating': '5', 'body': 'Bright and steady.'})
        self.assertTrue(self._review().is_approved)
        self.assertTrue(self._review().is_verified_purchase)

    def test_anyone_elses_review_waits_for_the_merchant(self):
        self.client.post(self.url, {'rating': '1', 'body': 'Never bought it.'})
        self.assertFalse(self._review().is_approved)
        self.assertFalse(self._review().is_verified_purchase)

    def test_an_unpaid_order_is_not_a_purchase(self):
        order = paid_order_for(self.user, self.product)
        Order.objects.filter(pk=order.pk).update(payment_status='unpaid')
        self.client.post(self.url, {'rating': '5', 'body': 'Ordered, never paid.'})
        self.assertFalse(self._review().is_approved)
