"""Renaming a page must not lose it.

Changing a slug changes the URL, and every inbound link, every ranking and
every bookmark pointing at the old one breaks at once — with nothing in the
dashboard to say so. These tests cover the automatic 301 that prevents it, and
the cases where it must NOT act.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.catalog.models import Product
from plugins.installed.seo.models import Redirect, SiteSeoSettings, SlugHistory
from plugins.installed.seo.services.redirects import resolve_redirect


def _product(slug: str) -> Product:
    return Product.objects.create(
        name='Slug History Probe',
        slug=slug,
        sku=f'SKU-{slug}',
        price=Decimal('10.00'),
        status='active',
    )


class SlugHistoryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_renaming_a_product_mints_a_301_from_the_old_url(self):
        product = _product('old-name')
        product.slug = 'new-name'
        product.save()

        self.assertEqual(resolve_redirect('/products/old-name/'), ('/products/new-name/', 301))
        self.assertTrue(SlugHistory.objects.filter(old_path='/products/old-name/').exists())

    def test_the_history_row_is_kept_even_when_auto_redirects_are_off(self):
        """One row is cheap, and it is what later lets the 404 suggester answer
        "this URL used to be that product" with certainty instead of a guess."""
        SiteSeoSettings.objects.create(auto_redirect_on_slug_change=False)
        product = _product('old-name')
        product.slug = 'new-name'
        product.save()

        self.assertTrue(SlugHistory.objects.filter(old_path='/products/old-name/').exists())
        self.assertIsNone(resolve_redirect('/products/old-name/'))

    def test_a_hand_written_rule_is_never_overwritten(self):
        """A merchant may have deliberately sent the old URL somewhere other
        than the renamed page."""
        product = _product('old-name')
        Redirect.objects.create(
            from_path='/products/old-name/', to_path='/collection/classics/', source='manual'
        )
        product.slug = 'new-name'
        product.save()

        self.assertEqual(resolve_redirect('/products/old-name/'), ('/collection/classics/', 301))

    def test_renaming_twice_does_not_leave_a_chain(self):
        product = _product('one')
        product.slug = 'two'
        product.save()
        product.slug = 'three'
        product.save()

        self.assertEqual(resolve_redirect('/products/one/'), ('/products/three/', 301))
        self.assertEqual(resolve_redirect('/products/two/'), ('/products/three/', 301))

    def test_saving_without_changing_the_slug_creates_nothing(self):
        product = _product('stable')
        product.name = 'A new display name'
        product.save()

        self.assertFalse(SlugHistory.objects.exists())
        self.assertFalse(Redirect.objects.exists())

    def test_the_404_suggester_prefers_a_known_former_url(self):
        from plugins.installed.seo.services.redirects import suggest_redirect

        product = _product('the-great-gatsby')
        product.slug = 'great-gatsby'
        product.save()

        self.assertEqual(suggest_redirect('/products/the-great-gatsby/'), '/products/great-gatsby/')
