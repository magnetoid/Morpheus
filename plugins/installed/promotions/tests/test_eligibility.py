"""Who a promotion applies to.

Until v0.150.0 a ``customer_groups`` rule iterated a related manager, which
raised; the cart step swallowed the error and skipped EVERY promotion for a
signed-in shopper. ``first_order`` read an ``order_count`` no customer has, so
it never excluded anyone, and ``category_slugs`` was documented but not read.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase

from plugins.installed.orders.services import OrderService

from ._fixtures import (
    ADDRESS,
    applied_names,
    breakdown,
    cart,
    category,
    customer,
    product,
    promotion,
)


class CustomerGroupTests(TestCase):
    def setUp(self):
        self.book = product('book', 50)
        promotion(
            'Members',
            {'kind': 'percent_off', 'value': 10},
            {'customer_groups': ['vip']},
        )
        promotion('Everyone', {'kind': 'fixed_off', 'value': 1})

    def test_a_member_of_the_group_gets_it(self):
        shopper = customer()
        shopper.groups.add(Group.objects.create(name='vip'))
        result = breakdown(cart((self.book, 50, 1), customer=shopper))
        self.assertEqual(applied_names(result), ['Members', 'Everyone'])
        self.assertEqual(result['discount'].amount, Decimal('6.00'))

    def test_a_signed_in_shopper_outside_the_group_still_gets_the_others(self):
        result = breakdown(cart((self.book, 50, 1), customer=customer()))
        self.assertEqual(applied_names(result), ['Everyone'])

    def test_a_guest_is_in_no_group(self):
        self.assertEqual(applied_names(breakdown(cart((self.book, 50, 1)))), ['Everyone'])


class FirstOrderTests(TestCase):
    def setUp(self):
        self.book = product('book', 50)
        promotion('Welcome', {'kind': 'percent_off', 'value': 10}, {'first_order': True})

    def test_a_customer_who_never_ordered_gets_it(self):
        self.assertEqual(
            applied_names(breakdown(cart((self.book, 50, 1), customer=customer()))), ['Welcome']
        )

    def test_a_customer_with_an_order_does_not(self):
        shopper = customer()
        OrderService.create_from_cart(
            cart((self.book, 50, 1), customer=shopper), shopper.email, ADDRESS, ADDRESS
        )
        self.assertEqual(applied_names(breakdown(cart((self.book, 50, 1), customer=shopper))), [])

    def test_a_cancelled_order_does_not_count(self):
        shopper = customer()
        order = OrderService.create_from_cart(
            cart((self.book, 50, 1), customer=shopper), shopper.email, ADDRESS, ADDRESS
        )
        type(order).objects.filter(pk=order.pk).update(status='cancelled')
        self.assertEqual(
            applied_names(breakdown(cart((self.book, 50, 1), customer=shopper))), ['Welcome']
        )

    def test_a_guest_never_matches(self):
        self.assertEqual(applied_names(breakdown(cart((self.book, 50, 1)))), [])


class CategoryTests(TestCase):
    def setUp(self):
        self.fiction = category('fiction')
        self.crime = category('crime', parent=self.fiction)
        self.novel = product('novel', 20, category=self.crime)
        self.mug = product('mug', 20)
        promotion(
            'Fiction week', {'kind': 'percent_off', 'value': 10}, {'category_slugs': ['fiction']}
        )

    def test_a_product_in_a_subcategory_counts(self):
        self.assertEqual(applied_names(breakdown(cart((self.novel, 20, 1)))), ['Fiction week'])

    def test_a_cross_listed_product_counts(self):
        self.mug.additional_categories.add(self.crime)
        self.assertEqual(applied_names(breakdown(cart((self.mug, 20, 1)))), ['Fiction week'])

    def test_a_cart_outside_the_category_does_not(self):
        self.assertEqual(applied_names(breakdown(cart((self.mug, 20, 1)))), [])


class BrokenRuleTests(TestCase):
    def test_a_rule_that_fails_skips_only_its_own_promotion(self):
        book = product('book', 50)
        promotion(
            'Broken', {'kind': 'percent_off', 'value': 10}, {'min_subtotal': 'lots'}, priority=1
        )
        promotion('Fine', {'kind': 'fixed_off', 'value': 2}, priority=2)
        with patch('plugins.installed.promotions.services.logger'):
            result = breakdown(cart((book, 50, 1)))
        self.assertEqual(applied_names(result), ['Fine'])
        self.assertEqual(result['discount'].amount, Decimal('2.00'))
