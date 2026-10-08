"""The sitemap lists pages that have something on them (v0.80.0).

The travel store's sitemap carried 520 URLs and 181 of them were empty pages
answering 200 + `index, follow`: 171 host pages reading "0 listings", seven
categories reading "Nothing here yet", the catalogue and the category index.
Google files those as soft 404s, and every one of them was an invitation the
sitemap made. The rule: a listing URL enters the sitemap only when its owner
says it has items — and an app whose items are not catalog Products (the
host's experiences and stays) tells the catalog through `VENDOR_LISTING_COUNTS`.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from core.utils.site import site_base_url


def _paths() -> set[str]:
    from plugins.installed.seo.services.sitemaps import _merged_sitemap_entries

    base = site_base_url().rstrip('/')
    return {(e.get('loc') or '').replace(base, '') or '/' for e in _merged_sitemap_entries()}


def _product(slug: str, *, status: str = 'active', **extra):
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper()[:30],
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status=status,
        **extra,
    )


class ListingEntriesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_an_empty_category_is_left_out_and_a_stocked_one_is_listed(self):
        from plugins.installed.catalog.models import Category

        Category.objects.create(name='Empty shelf', slug='empty-shelf')
        stocked = Category.objects.create(name='Stocked shelf', slug='stocked-shelf')
        also = Category.objects.create(name='Cross listed', slug='cross-listed')
        product = _product('shelf-item', category=stocked)
        product.additional_categories.add(also)
        _product(
            'archived-item', status='archived', category=Category.objects.get(slug='empty-shelf')
        )

        paths = _paths()
        self.assertNotIn('/category/empty-shelf/', paths)
        self.assertIn('/category/stocked-shelf/', paths)
        self.assertIn('/category/cross-listed/', paths)

    def test_an_empty_collection_is_left_out(self):
        from plugins.installed.catalog.models import Collection

        Collection.objects.create(name='Nothing yet', slug='nothing-yet', is_active=True)
        full = Collection.objects.create(name='Picks', slug='picks', is_active=True)
        full.products.add(_product('picked-item'))

        paths = _paths()
        self.assertNotIn('/collection/nothing-yet/', paths)
        self.assertIn('/collection/picks/', paths)

    def test_a_vendor_with_nothing_to_show_is_left_out(self):
        from plugins.installed.catalog.models import Vendor

        Vendor.objects.create(name='Quiet host', slug='quiet-host')
        busy = Vendor.objects.create(name='Busy press', slug='busy-press')
        _product('busy-title', vendor=busy)

        paths = _paths()
        self.assertNotIn('/vendor/quiet-host/', paths)
        self.assertIn('/vendor/busy-press/', paths)

    def test_listings_another_app_contributes_put_a_vendor_in(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.catalog.models import Vendor

        host = Vendor.objects.create(name='Boat host', slug='boat-host')

        def _counts(value, **kwargs):
            value[str(host.pk)] = value.get(str(host.pk), 0) + 3
            return value

        hook_registry.register(MorpheusEvents.VENDOR_LISTING_COUNTS, _counts, priority=50)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.VENDOR_LISTING_COUNTS, _counts)
        self.assertIn('/vendor/boat-host/', _paths())


class StorefrontEntriesTests(TestCase):
    """The storefront's own index pages enter the sitemap only with content."""

    def setUp(self):
        cache.clear()

    def test_an_empty_store_lists_no_empty_index_page(self):
        paths = _paths()
        for path in ('/products/', '/staff-picks/', '/vendors/', '/journal/', '/categories/'):
            with self.subTest(path=path):
                self.assertNotIn(path, paths)
        # Pages that are content in their own right stay.
        self.assertIn('/about/', paths)
        self.assertIn('/contact/', paths)

    def test_a_stocked_store_lists_its_catalogue_and_vendors(self):
        from plugins.installed.catalog.models import Collection, Vendor

        vendor = Vendor.objects.create(name='A press', slug='a-press')
        product = _product('stocked-title', vendor=vendor)
        picks = Collection.objects.create(name='Staff picks', slug='staff-picks', is_active=True)
        picks.products.add(product)

        paths = _paths()
        self.assertIn('/products/', paths)
        self.assertIn('/vendors/', paths)
        self.assertIn('/staff-picks/', paths)

    def test_the_journal_index_needs_a_live_post(self):
        from datetime import timedelta

        from django.utils import timezone

        from plugins.installed.cms.models import Page

        Page.objects.create(
            slug='first-post',
            title='First post',
            state='published',
            publish_at=timezone.now() - timedelta(days=1),
            body='<p>Hello.</p>',
            metadata={'category': 'journal'},
        )
        paths = _paths()
        self.assertIn('/journal/', paths)
        self.assertIn('/journal/first-post/', paths)


class AuthorEntriesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_an_author_whose_books_are_all_withdrawn_is_left_out(self):
        from plugins.installed.book_product.models import BookProduct

        BookProduct.objects.create(product=_product('in-print'), author='Ada Inprint')
        BookProduct.objects.create(
            product=_product('out-of-print', status='archived'), author='Otto Outofprint'
        )
        paths = _paths()
        self.assertIn('/author/ada-inprint/', paths)
        self.assertNotIn('/author/otto-outofprint/', paths)


class ClaimedCmsPageTests(TestCase):
    """A CMS page rendered at another route has ONE url, and that is the sitemap's."""

    def setUp(self):
        cache.clear()

    def test_the_shipping_policy_page_is_listed_once_at_its_route(self):
        from plugins.installed.cms.models import Page

        # update_or_create: the legal-pages seed may already have written either.
        for slug in ('shipping', 'our-story'):
            Page.objects.update_or_create(
                slug=slug,
                defaults={'title': slug.title(), 'state': 'published', 'body': '<p>x</p>'},
            )
        paths = _paths()
        self.assertIn('/shipping/', paths)
        self.assertNotIn('/p/shipping/', paths)
        self.assertIn('/p/our-story/', paths)


class DisabledAppEntriesTests(TestCase):
    """A route the app no longer serves must leave the sitemap with it."""

    def setUp(self):
        cache.clear()

    def test_a_disabled_book_vertical_takes_its_urls_along(self):
        from plugins.installed.book_product.models import BookProduct
        from plugins.registry import app_registry

        BookProduct.objects.create(
            product=_product('vertical-book'), author='Vera Vertical', publisher='Vertical Press'
        )
        self.assertIn('/author/vera-vertical/', _paths())

        app_registry.deactivate('book_product')
        self.addCleanup(app_registry.activate, 'book_product')
        cache.clear()
        paths = _paths()
        self.assertNotIn('/author/vera-vertical/', paths)
        self.assertNotIn('/publisher/vertical-press/', paths)
