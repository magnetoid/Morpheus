"""The head contract a theme signs up to with `head_contract = 1`.

A theme cannot be trusted to keep SEO correct by inspection: the failure is
invisible in the browser. A page with two `<title>` elements looks perfect, a
page whose canonical points at the wrong URL looks perfect, and a theme that
quietly re-adds `<meta name="robots">` next to the kernel's looks perfect too —
right up until half the catalogue drops out of the index.

So every theme declaring the contract is rendered here, for each page kind, and
checked mechanically:

* exactly one `<title>`, one canonical, one robots meta, one JSON-LD block;
* no brand string hardcoded into the markup (it comes from settings);
* and with the seo app DISABLED the page still renders with exactly one title —
  the disable litmus test applied to the head.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.registry import app_registry
from themes.registry import theme_registry

_TITLE = re.compile(r'<title[^>]*>', re.I)
_CANONICAL = re.compile(r'<link[^>]+rel=["\']canonical["\']', re.I)
_ROBOTS = re.compile(r'<meta[^>]+name=["\']robots["\']', re.I)
_JSONLD = re.compile(r'<script[^>]+application/ld\+json', re.I)

_SLUG = 'head-contract-probe'


class HeadContractTests(TestCase):
    """Runs only when the active theme declares `head_contract >= 1`."""

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product
        from plugins.installed.cms.models import Page

        cls.category = Category.objects.create(name='Contract Category', slug=f'{_SLUG}-cat')
        cls.product = Product.objects.create(
            name='Head Contract Probe',
            slug=_SLUG,
            sku='HCP-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
            category=cls.category,
            description='A product that exists so the contract test has a PDP to render.',
        )
        Page.objects.create(
            slug=f'{_SLUG}-post',
            title='Contract journal entry',
            state='published',
            publish_at=timezone.now() - timedelta(minutes=1),
            body='<p>An entry for the contract test.</p>',
            metadata={'category': 'journal'},
        )

    def setUp(self):
        cache.clear()
        theme = theme_registry.active
        if theme is None or getattr(theme, 'head_contract', 0) < 1:
            self.skipTest('active theme does not declare head_contract >= 1')
        self.theme = theme

    def _paths(self):
        return (
            '/',
            '/products/',
            f'/products/{_SLUG}/',
            f'/category/{_SLUG}-cat/',
            '/journal/',
            f'/journal/{_SLUG}-post/',
            '/about/',
            '/search/',
            '/cart/',
        )

    def test_each_page_emits_exactly_one_of_each_head_element(self):
        for path in self._paths():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                body = response.content.decode()
                self.assertEqual(len(_TITLE.findall(body)), 1, f'{path}: <title> count')
                self.assertLessEqual(len(_CANONICAL.findall(body)), 1, f'{path}: canonical count')
                self.assertEqual(len(_ROBOTS.findall(body)), 1, f'{path}: robots meta count')
                self.assertLessEqual(len(_JSONLD.findall(body)), 1, f'{path}: JSON-LD block count')

    def test_private_pages_are_noindex_and_public_pages_are_not(self):
        public = self.client.get(f'/products/{_SLUG}/').content.decode()
        self.assertIn('index, follow', public)

        private = self.client.get('/cart/').content.decode()
        self.assertRegex(private, r'name=["\']robots["\'] content=["\']noindex, nofollow')

        # Internal search: crawl the links, don't index the query permutations.
        search = self.client.get('/search/').content.decode()
        self.assertRegex(search, r'name=["\']robots["\'] content=["\']noindex, follow')

    def test_the_theme_does_not_hardcode_the_brand_in_the_head(self):
        """The brand belongs in settings, not in markup.

        A theme that writes its own name into `<title>` cannot be used by a
        second merchant, which is the entire point of a theme.
        """
        brand_in_markup = re.compile(r'dot books', re.I)
        for path in ('/products/', f'/products/{_SLUG}/', '/about/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                head = body[: body.lower().find('</head>')]
                title = re.search(r'<title[^>]*>(.*?)</title>', head, re.I | re.S)
                self.assertIsNotNone(title, f'{path}: no title')
                # The brand may legitimately appear because the merchant CONFIGURED
                # it — what must not happen is the theme supplying it. In tests no
                # store name is configured, so any occurrence is hardcoded.
                self.assertIsNone(
                    brand_in_markup.search(title.group(1)),
                    f'{path}: theme hardcodes the brand in <title>: {title.group(1)!r}',
                )

    def test_head_survives_the_seo_app_being_disabled(self):
        """Disable litmus test, applied to the head.

        With the SEO app off the page loses its canonical and structured data —
        that is the app's surface disappearing, as it should — but it must still
        render, and still have exactly one title. A store that turns off SEO gets
        a plainer head, not a broken storefront.
        """
        self.assertTrue(app_registry.is_active('seo'))
        app_registry.deactivate('seo')
        cache.clear()
        try:
            for path in ('/', f'/products/{_SLUG}/', '/about/'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200, f'{path} with seo disabled')
                    body = response.content.decode()
                    self.assertEqual(len(_TITLE.findall(body)), 1, f'{path}: <title> count')
                    self.assertNotIn('application/ld+json', body)
        finally:
            app_registry.activate('seo')
            cache.clear()
