"""What belongs in the sitemap.

A sitemap is a request: "please crawl these". Listing a URL that is then told
`noindex` spends crawl budget to reach a page Google must discard, and shows up
in Search Console as "Discovered — currently not indexed", which reads like a
fault. The merchant's own per-page choice overrides both ways.

`SeoMeta.sitemap_include` shipped in v0.47.0 with no reader at all — a control
that looked like a control and did nothing. This is the guard for its behaviour.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.models import SeoMeta
from plugins.installed.seo.services import iter_sitemap_entries


def _seo(obj, **fields):
    return SeoMeta.objects.update_or_create(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=str(obj.pk),
        defaults=fields,
    )[0]


class SitemapPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.listed = Product.objects.create(
            name='Listed',
            slug='listed-probe',
            sku='SM-1',
            status='active',
            price=Money(Decimal('5.00'), 'USD'),
        )
        cls.hidden = Product.objects.create(
            name='Hidden',
            slug='hidden-probe',
            sku='SM-2',
            status='active',
            price=Money(Decimal('5.00'), 'USD'),
        )

    def _locs(self) -> set[str]:
        return {e['loc'] for e in iter_sitemap_entries()}

    def test_an_active_product_is_listed(self):
        self.assertTrue(any('listed-probe' in loc for loc in self._locs()))

    def test_a_noindex_page_is_not_asked_to_be_crawled(self):
        """Asking Google to crawl a page we then tell it to drop is pure waste."""
        _seo(self.hidden, robots='noindex, follow')
        locs = self._locs()
        self.assertFalse(any('hidden-probe' in loc for loc in locs))
        self.assertTrue(any('listed-probe' in loc for loc in locs))

    def test_the_merchant_can_keep_a_page_out(self):
        _seo(self.hidden, sitemap_include=False)
        self.assertFalse(any('hidden-probe' in loc for loc in self._locs()))

    def test_the_merchant_can_override_the_noindex_exclusion(self):
        """An explicit choice beats the platform's inference, both ways."""
        _seo(self.hidden, robots='noindex, follow', sitemap_include=True)
        self.assertTrue(any('hidden-probe' in loc for loc in self._locs()))

    def test_the_default_is_untouched(self):
        """A row that exists for other reasons must not change listing."""
        _seo(self.hidden, title='Just a title')
        self.assertTrue(any('hidden-probe' in loc for loc in self._locs()))
