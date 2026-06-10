"""morph_seed_demo command tests — idempotent, fixture-driven."""

from __future__ import annotations

from unittest import skipIf, skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from plugins.installed.catalog.models import Category, Collection, Product, Vendor
from plugins.installed.orders.models import Order

# Cascade-delete on Vendor over UUID PKs hits a known SQLite/django-taggit
# OverflowError. The wipe path is only exercised on Postgres in production.
_IS_SQLITE = connection.vendor == 'sqlite'
_DEMO_INSTALLED = apps.is_installed('plugins.installed.demo_data')


@skipUnless(_DEMO_INSTALLED, 'demo_data is opt-in (not in MORPHEUS_DEFAULT_PLUGINS)')
class SeedDemoTests(TestCase):
    def test_seed_creates_categories_and_books(self):
        call_command('morph_seed_demo')
        self.assertGreaterEqual(Category.objects.count(), 6)
        self.assertGreaterEqual(Product.objects.filter(status='active').count(), 25)
        self.assertGreaterEqual(Vendor.objects.count(), 3)
        self.assertGreaterEqual(Collection.objects.count(), 3)

    def test_seed_is_idempotent(self):
        call_command('morph_seed_demo')
        first_books = Product.objects.count()
        first_categories = Category.objects.count()
        call_command('morph_seed_demo')
        self.assertEqual(Product.objects.count(), first_books)
        self.assertEqual(Category.objects.count(), first_categories)

    def test_seed_creates_at_least_one_paid_order(self):
        call_command('morph_seed_demo')
        self.assertGreaterEqual(
            Order.objects.filter(payment_status='paid').count(),
            1,
        )

    def test_demo_customer_exists_after_seed(self):
        call_command('morph_seed_demo')
        User = get_user_model()
        self.assertTrue(User.objects.filter(email='reader.one@example.com').exists())

    @skipIf(_IS_SQLITE, 'cascade delete + UUID PKs overflow SQLite — postgres-only path')
    def test_fresh_resets_then_reseeds(self):
        call_command('morph_seed_demo')
        # Prove seeding ran
        self.assertGreater(Product.objects.count(), 0)
        # --fresh should not crash; ends with the same final count
        call_command('morph_seed_demo', '--fresh')
        self.assertGreaterEqual(Product.objects.count(), 25)
