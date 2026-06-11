"""Wishlist smoke test — add, list, remove."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money


class WishlistSmoke(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.user = get_user_model().objects.create_user(
            username='reader@example.com',
            email='reader@example.com',
            password='hunter2',
        )
        self.product = Product.objects.create(
            name='Test',
            slug='wl-test',
            sku='WL-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )

    def test_add_then_remove(self):
        from plugins.installed.wishlist.services import (
            add_item,
            get_or_create_wishlist,
            remove_item,
        )

        wl = get_or_create_wishlist(customer=self.user)
        add_item(wishlist=wl, product=self.product)
        self.assertEqual(wl.items.count(), 1)
        deleted = remove_item(wishlist=wl, product=self.product)
        self.assertEqual(deleted, 1)
        self.assertEqual(wl.items.count(), 0)
