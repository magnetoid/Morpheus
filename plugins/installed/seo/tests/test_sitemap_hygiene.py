"""What the sitemap lists is what the store wants indexed, in the plain protocol.

* Every product entry carried `<xhtml:link rel="alternate" type="text/markdown">`.
  A sitemap's `xhtml:link` is Google's hreflang extension and nothing else: an
  alternate without `hreflang` is a malformed hreflang entry to a validator. The
  Markdown mirror is announced in the product page's own `<head>`.
* 1,186 of the 1,526 topic pages dotbooks listed held one book: the product page
  again with chrome around it. A topic is indexed and listed from as many books as
  it takes to be a filter (`TOPIC_MIN_BOOKS`), and a thinner one says
  `noindex, follow` so its links still count.
* Every lastmod carried microseconds, and no taxonomy page had a lastmod at all.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.listing_facets import TOPIC_MIN_BOOKS
from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Product
from plugins.installed.seo.services.sitemaps import render_sitemap_xml

_ROBOTS = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)


def _book(slug):
    product = Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper()[:30],
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=product)


def _robots(response) -> str:
    match = _ROBOTS.search(response.content.decode().split('</head>', 1)[0])
    return match.group(1) if match else ''


class SitemapProtocolTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_no_entry_carries_a_markdown_alternate(self):
        _book('mirror-probe')
        xml = render_sitemap_xml()
        self.assertIn('/products/mirror-probe/', xml)
        self.assertNotIn('text/markdown', xml)
        self.assertNotIn('<xhtml:link', xml)

    def test_the_product_page_still_announces_its_markdown_mirror(self):
        _book('mirror-head')
        head = self.client.get('/products/mirror-head/').content.decode().split('</head>', 1)[0]
        self.assertIn('type="text/markdown"', head)

    def test_lastmod_is_to_the_second(self):
        _book('lastmod-probe')
        lastmods = re.findall(r'<lastmod>([^<]+)</lastmod>', render_sitemap_xml())
        self.assertTrue(lastmods)
        for value in lastmods:
            self.assertRegex(value, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$')


class ThinTopicTests(TestCase):
    def setUp(self):
        cache.clear()
        self.assertEqual(TOPIC_MIN_BOOKS, 2, 'the fixtures below assume a floor of two')
        self.lonely = Topic.objects.create(name='Lonely Topic', slug='lonely-topic')
        self.lonely.books.add(_book('only-book'))
        self.shelf = Topic.objects.create(name='Shelf Topic', slug='shelf-topic')
        self.shelf.books.add(_book('shelf-one'), _book('shelf-two'))
        self.genre = Genre.objects.create(name='Small Genre', slug='small-genre')
        self.genre.books.add(_book('genre-one'))

    def test_a_one_book_topic_is_followed_but_not_indexed(self):
        response = self.client.get('/topic/lonely-topic/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_robots(response).replace(' ', '').split(',')[:2], ['noindex', 'follow'])

    def test_a_topic_with_enough_books_is_indexed(self):
        robots = _robots(self.client.get('/topic/shelf-topic/'))
        self.assertTrue(robots.startswith('index'), robots)

    def test_a_one_book_genre_is_still_indexed(self):
        robots = _robots(self.client.get('/genre/small-genre/'))
        self.assertTrue(robots.startswith('index'), robots)

    def test_the_sitemap_lists_what_the_pages_index_with_a_lastmod(self):
        xml = render_sitemap_xml()
        self.assertNotIn('/topic/lonely-topic/', xml)
        self.assertIn('/genre/small-genre/', xml)
        entry = re.search(r'<url><loc>[^<]*/topic/shelf-topic/</loc>(.*?)</url>', xml)
        self.assertIsNotNone(entry, 'the stocked topic is not listed')
        self.assertIn('<lastmod>', entry.group(1))


class CmsPagePingTests(TestCase):
    """Every published CMS page was pinged to IndexNow as `/journal/<slug>/`,
    a 404 for anything but a journal post. The ping names the url the sitemap
    lists."""

    def _pinged(self, **page):
        from unittest import mock

        from plugins.installed.cms.models import Page
        from plugins.installed.seo.services import indexnow

        with mock.patch.object(indexnow, 'ping_in_background') as ping:
            Page.objects.create(state='published', **page)
        return [url for call in ping.call_args_list for url in call.args[0]]

    def test_a_standalone_page_is_pinged_at_its_own_path(self):
        urls = self._pinged(slug='opening-hours', title='Opening hours')
        self.assertTrue(urls, 'no ping was sent')
        self.assertTrue(all(u.endswith('/p/opening-hours/') for u in urls), urls)

    def test_a_journal_post_is_pinged_under_the_journal(self):
        urls = self._pinged(slug='a-post', title='A post', metadata={'category': 'journal'})
        self.assertTrue(urls, 'no ping was sent')
        self.assertTrue(all(u.endswith('/journal/a-post/') for u in urls), urls)
