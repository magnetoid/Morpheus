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


class ProductFormDualWriteTests(TestCase):
    """Phase 3: the admin product form's multi-select Collections picker
    writes the new `categories` M2M AND keeps the legacy `category` FK
    pointed at the first selection (primary), so the public storefront
    keeps working during the read-cutover window."""

    def setUp(self):
        self.fiction = Category.objects.create(name='Fiction', slug='fiction')
        self.classics = Category.objects.create(name='Classics', slug='classics')

    def _post(self, category_ids):
        # Mirror request.POST — a QueryDict, which is what ProductForm
        # always receives in production (its save() reads
        # self.data.getlist('categories')).
        from django.http import QueryDict
        q = QueryDict('', mutable=True)
        q.update({
            'name': 'Crime and Punishment',
            'slug': 'crime-and-punishment',
            'sku': 'CP-1',
            'status': 'active',
            'product_type': 'simple',
            'price': '12.00',
        })
        q.setlist('categories', [str(c) for c in category_ids])
        return q

    def test_multi_select_sets_m2m_and_primary_fk(self):
        from plugins.installed.admin_dashboard.forms import ProductForm
        form = ProductForm(self._post([self.fiction.id, self.classics.id]))
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        # M2M holds both selected collections.
        self.assertEqual(
            set(product.categories.values_list('slug', flat=True)),
            {'fiction', 'classics'},
        )
        # Legacy FK = first selection (primary) for storefront back-compat.
        self.assertEqual(product.category_id, self.fiction.id)

    def test_no_selection_clears_both(self):
        from plugins.installed.admin_dashboard.forms import ProductForm
        form = ProductForm(self._post([]))
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.categories.count(), 0)
        self.assertIsNone(product.category_id)


class ProductCollectionsGraphQLTests(TestCase):
    """Phase 3b (additive): ProductType.collections returns the M2M
    memberships, falling back to the primary category when empty.

    Calls the resolver directly with a Product instance — the full
    `product(slug:)` query can't execute under the SQLite test DB
    (a pre-existing 'int too large for SQLite' limitation in that
    resolver; prod runs Postgres), so we test the field in isolation
    the same way test_variant_fallback does.
    """

    def setUp(self):
        self.fiction = Category.objects.create(name='Fiction', slug='fiction')
        self.classics = Category.objects.create(name='Classics', slug='classics')

    def _resolve(self, product):
        from plugins.installed.catalog.graphql.types import ProductType
        attr = ProductType.__dict__['collections']
        fn = getattr(attr, 'base_resolver', None) or attr
        fn = getattr(fn, 'wrapped_func', fn)  # unwrap strawberry's StrawberryResolver
        return [c.slug for c in fn(product)]

    def test_returns_m2m_memberships(self):
        p = _product('dune', category=self.fiction)
        p.categories.set([self.fiction, self.classics])
        self.assertEqual(set(self._resolve(p)), {'fiction', 'classics'})

    def test_falls_back_to_primary_when_m2m_empty(self):
        # A product the backfill hasn't touched (no M2M) still surfaces
        # its primary category, so the storefront never sees it uncollected.
        p = _product('emma', category=self.fiction)
        self.assertEqual(set(self._resolve(p)), {'fiction'})
