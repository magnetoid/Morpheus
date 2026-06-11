"""Wishlist tests."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents import agent_registry
from plugins.installed.catalog.models import Product
from plugins.installed.wishlist.services import (
    add_item,
    get_or_create_wishlist,
    make_shareable,
    remove_item,
)

User = get_user_model()


class WishlistServiceTests(TestCase):
    def test_get_or_create_for_customer(self):
        u = User.objects.create_user(username='x', email='x@example.com', password='x')
        wl = get_or_create_wishlist(customer=u)
        wl2 = get_or_create_wishlist(customer=u)
        self.assertEqual(wl.id, wl2.id)

    def test_add_and_remove_item(self):
        u = User.objects.create_user(username='y', email='y@example.com', password='x')
        wl = get_or_create_wishlist(customer=u)
        p = Product.objects.create(
            name='B',
            slug='b',
            sku='B1',
            price=Money(Decimal('10'), 'USD'),
            status='active',
        )
        add_item(wishlist=wl, product=p)
        self.assertEqual(wl.item_count, 1)
        # idempotent
        add_item(wishlist=wl, product=p)
        self.assertEqual(wl.item_count, 1)
        deleted = remove_item(wishlist=wl, product=p)
        self.assertEqual(deleted, 1)

    def test_make_shareable_generates_token(self):
        u = User.objects.create_user(username='z', email='z@example.com', password='x')
        wl = get_or_create_wishlist(customer=u)
        token = make_shareable(wl)
        wl.refresh_from_db()
        self.assertTrue(wl.is_public)
        self.assertEqual(wl.share_token, token)

    def test_agent_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('wishlist.add', names)
        self.assertIn('wishlist.summary', names)
