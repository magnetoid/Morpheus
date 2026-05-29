"""Collections-merge backfill command (phase 2) tests.

Verifies the legacy single `category` FK + the `collections` M2M both
land in the new `categories` M2M, that collections get mirrored as
top-level categories, and that the command is idempotent.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Collection, Product


def _product(slug, **kw):
    defaults = dict(
        name=slug.replace('-', ' ').title(), slug=slug, sku=slug.upper(),
        status='active', price=Money(Decimal('10.00'), 'USD'), product_type='simple',
    )
    defaults.update(kw)
    return Product.objects.create(**defaults)


class BackfillTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='Fiction', slug='fiction')
        self.col_a = Collection.objects.create(name='Staff Picks', slug='staff-picks')
        self.col_b = Collection.objects.create(name='Summer', slug='summer-reads')

    def test_category_fk_and_collections_both_land_in_categories(self):
        p = _product('dune', category=self.cat)
        p.collections.add(self.col_a, self.col_b)

        call_command('merge_collections_into_categories')

        names = set(p.categories.values_list('name', flat=True))
        # The single category + both collections (mirrored as categories).
        self.assertIn('Fiction', names)
        self.assertIn('Staff Picks', names)
        self.assertIn('Summer', names)
        self.assertEqual(p.categories.count(), 3)

    def test_collection_mirrored_as_top_level_category(self):
        call_command('merge_collections_into_categories')
        mirrored = Category.objects.filter(slug='staff-picks').first()
        self.assertIsNotNone(mirrored)
        self.assertEqual(mirrored.name, 'Staff Picks')
        self.assertIsNone(mirrored.parent)  # top-level

    def test_idempotent(self):
        p = _product('idem', category=self.cat)
        p.collections.add(self.col_a)
        call_command('merge_collections_into_categories')
        first = p.categories.count()
        # Re-run — must not duplicate links or mirror categories twice.
        call_command('merge_collections_into_categories')
        self.assertEqual(p.categories.count(), first)
        self.assertEqual(Category.objects.filter(slug='staff-picks').count(), 1)

    def test_slug_clash_reuses_existing_category(self):
        # A Category already owns the slug a Collection would mirror to —
        # reuse it, don't duplicate.
        Category.objects.create(name='Summer (taxonomy)', slug='summer-reads')
        p = _product('beach', )
        p.collections.add(self.col_b)
        call_command('merge_collections_into_categories')
        self.assertEqual(Category.objects.filter(slug='summer-reads').count(), 1)
        names = set(p.categories.values_list('slug', flat=True))
        self.assertIn('summer-reads', names)

    def test_dry_run_writes_nothing(self):
        p = _product('dry', category=self.cat)
        p.collections.add(self.col_a)
        call_command('merge_collections_into_categories', '--dry-run')
        self.assertEqual(p.categories.count(), 0)
        self.assertFalse(Category.objects.filter(slug='staff-picks').exists())
