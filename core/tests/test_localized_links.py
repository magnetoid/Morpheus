"""A page in a prefixed language links to pages in that language (v0.80.1).

The storefront is language-routed (`i18n_patterns`, the default language
unprefixed). `{% url %}` adds the prefix, but themes, apps and the merchant's
own CMS copy write plain paths — and on montenegro-experience.me 106 of the 108
internal links on `/sr/` pointed into the English tree. A Serbian visitor left
Serbian on the first click, and the Serbian pages linked only to English ones.
"""

from __future__ import annotations

import re

from django.test import TestCase, override_settings

from core.i18n_links import localize_links

_LANGUAGES = [('en', 'English'), ('sr', 'Srpski')]


@override_settings(LANGUAGES=_LANGUAGES, LANGUAGE_CODE='en')
class LocalizeLinksTests(TestCase):
    def test_a_link_to_a_language_routed_page_gets_the_prefix(self):
        html = '<a class="x" href="/products/?page=2">Shop</a><form action="/search/">'
        self.assertEqual(
            localize_links(html, 'sr'),
            '<a class="x" href="/sr/products/?page=2">Shop</a><form action="/sr/search/">',
        )

    def test_the_home_link_gets_the_prefix(self):
        self.assertEqual(localize_links('<a href="/">Home</a>', 'sr'), '<a href="/sr/">Home</a>')

    def test_routes_outside_the_language_tree_are_left_alone(self):
        for href in (
            '/auth/login/',
            '/dashboard/',
            '/static/app.css',
            '/media/x.jpg',
            '/sitemap.xml',
        ):
            with self.subTest(href=href):
                html = f'<a href="{href}">x</a>'
                self.assertEqual(localize_links(html, 'sr'), html)

    def test_already_prefixed_external_and_fragment_links_are_left_alone(self):
        for href in ('/sr/products/', 'https://example.com/', '//cdn.example.com/a.js', '#top'):
            with self.subTest(href=href):
                html = f'<a href="{href}">x</a>'
                self.assertEqual(localize_links(html, 'sr'), html)

    def test_an_absolute_link_to_this_store_gets_the_prefix(self):
        # Breadcrumbs are built with request.build_absolute_uri('/').
        html = '<a href="https://shop.example/vendors/">Hosts</a><a href="https://other.example/x/">x</a>'
        self.assertEqual(
            localize_links(html, 'sr', host='shop.example'),
            '<a href="https://shop.example/sr/vendors/">Hosts</a><a href="https://other.example/x/">x</a>',
        )

    def test_an_absolute_link_needs_the_host_to_be_known(self):
        html = '<a href="https://shop.example/vendors/">Hosts</a>'
        self.assertEqual(localize_links(html, 'sr'), html)

    def test_a_link_into_another_language_is_left_alone(self):
        # A language switcher built from anchors names the other tree on purpose.
        for html in (
            '<a href="/" hreflang="en">English</a>',
            '<a lang="en" class="x" href="/products/">English</a>',
        ):
            with self.subTest(html=html):
                self.assertEqual(localize_links(html, 'sr'), html)

    def test_only_links_and_forms_are_rewritten(self):
        # A <link> names a document for machines (manifest, feeds, alternates);
        # the hreflang alternates must keep pointing at the other language.
        html = '<link rel="manifest" href="/manifest.webmanifest"><link rel="alternate" hreflang="en" href="/">'
        self.assertEqual(localize_links(html, 'sr'), html)


@override_settings(LANGUAGES=_LANGUAGES, LANGUAGE_CODE='en')
class LocalizedPageTests(TestCase):
    _HREF = re.compile(r'<a\b[^>]*?\shref="(/[^"]*)"')

    def test_a_serbian_page_links_into_the_serbian_tree(self):
        body = self.client.get('/sr/').content.decode()
        hrefs = self._HREF.findall(body)
        self.assertTrue(hrefs)
        self.assertIn('/sr/', hrefs)
        self.assertNotIn('/products/', hrefs)
        self.assertNotIn('/', hrefs)

    def test_the_breadcrumb_trail_names_the_serbian_pages(self):
        # Views build the trail with build_absolute_uri('/'); the structured
        # data on a /sr/ page must not send its breadcrumbs to the English tree.
        import json
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.catalog.models import Product, Vendor

        vendor = Vendor.objects.create(name='Kotor Boats', slug='kotor-boats')
        Product.objects.create(
            name='Bay Map',
            slug='bay-map',
            sku='MAP-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
            vendor=vendor,
        )
        body = self.client.get('/sr/vendors/').content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        self.assertEqual(len(blocks), 1)
        crumbs = next(
            n for n in json.loads(blocks[0])['@graph'] if n.get('@type') == 'BreadcrumbList'
        )
        urls = [
            i['item'] if isinstance(i['item'], str) else i['item']['@id']
            for i in crumbs['itemListElement']
        ]
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith('http://testserver/sr/'), url)

    def test_the_default_language_is_untouched(self):
        body = self.client.get('/').content.decode()
        self.assertFalse(any(h.startswith('/sr/') for h in self._HREF.findall(body)))
