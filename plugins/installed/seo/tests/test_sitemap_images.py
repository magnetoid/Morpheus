"""The image sitemap lists every page's pictures, never a file someone paid for (v0.163.0).

It listed shoppable products only, so a travel store (experiences, hotels and
places are contributed through `SITEMAP_URLS`) and every journal post had no
image in it. An entry may now carry `images`; each leaves as at most six
absolute public addresses
(https://developers.google.com/search/docs/crawling-indexing/sitemaps/image-sitemaps).
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.test import TestCase

from core.hooks import MorpheusEvents, hook_registry


def _contribute(entries):
    def handler(value, **_):
        return [*(value or []), *entries]

    hook_registry.register(MorpheusEvents.SITEMAP_URLS, handler, priority=99)
    return handler


class ImageSitemapTests(TestCase):
    def _xml(self):
        from plugins.installed.seo.services.sitemaps import render_image_sitemap_xml

        return render_image_sitemap_xml()

    def _with(self, entries):
        handler = _contribute(entries)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.SITEMAP_URLS, handler)

    def test_a_contributed_page_lists_its_pictures(self):
        self._with(
            [
                {
                    'loc': 'https://shop.test/bookings/rafting/',
                    'images': ['/media/listings/raft.jpg', 'https://cdn.test/raft-2.jpg'],
                }
            ]
        )
        xml = self._xml()
        self.assertIn('<loc>https://shop.test/bookings/rafting/</loc>', xml)
        self.assertRegex(xml, r'<image:loc>https?://[^<]+/media/listings/raft\.jpg</image:loc>')
        self.assertIn('<image:loc>https://cdn.test/raft-2.jpg</image:loc>', xml)

    def test_a_sold_file_is_never_listed(self):
        self._with(
            [
                {
                    'loc': 'https://shop.test/products/ebook/',
                    'images': ['/media/digital/book.pdf', 'https://shop.test/media/digital/c.jpg'],
                },
                {'loc': 'https://shop.test/odd/', 'images': ['javascript:alert(1)', 'data:x']},
            ]
        )
        xml = self._xml()
        self.assertNotIn('digital/', xml)
        self.assertNotIn('/products/ebook/', xml)
        self.assertNotIn('/odd/', xml)

    def test_at_most_six_and_no_repeats(self):
        self._with(
            [
                {
                    'loc': 'https://shop.test/stays/hotel/',
                    'images': [f'/media/p/{n}.jpg' for n in (1, 1, 2, 3, 4, 5, 6, 7)],
                }
            ]
        )
        block = self._xml().split('/stays/hotel/</loc>', 1)[1].split('</url>', 1)[0]
        self.assertEqual(block.count('<image:loc>'), 6)
        self.assertEqual(block.count('/media/p/1.jpg'), 1)
        self.assertNotIn('/media/p/7.jpg', block)

    def test_a_cms_page_lists_its_cover_and_body_pictures(self):
        from plugins.installed.cms.models import Page

        Page.objects.create(
            slug='water-first',
            title='Water first',
            state='published',
            body='<p>Text</p><img src="/media/journal/a.jpg"> ![b](/media/journal/b.jpg)',
            metadata={'category': 'journal', 'cover': '/media/journal/cover.jpg'},
        )
        xml = self._xml()
        block = xml.split('water-first/</loc>', 1)[1].split('</url>', 1)[0]
        order = [block.index(f'/media/journal/{n}.jpg') for n in ('cover', 'a', 'b')]
        self.assertEqual(order, sorted(order))

    def test_entries_without_pictures_are_not_listed(self):
        self._with([{'loc': 'https://shop.test/about-us/'}])
        self.assertNotIn('/about-us/', self._xml())

    def test_the_url_sitemap_still_renders_the_entry(self):
        from plugins.installed.seo.services.sitemaps import render_sitemap_xml

        self._with([{'loc': 'https://shop.test/bookings/rafting/', 'images': ['/media/r.jpg']}])
        xml = render_sitemap_xml()
        self.assertIn('https://shop.test/bookings/rafting/', xml)
        self.assertNotIn('<image:', xml)
