"""A missing file is not a missing page (v0.80.0).

Every 404 rendered the full storefront theme — 53 KB on montenegro, 120 KB on
dotbooks — including for `/static/x.css`, `/media/x.jpg` and the steady stream
of `wp-login.php`-style probes. A browser asking for a stylesheet cannot use a
themed page, and a crawler asking for an image learns nothing from one; each was
a full render with every context processor for nobody. Pages still get the
theme's 404; files get a plain-text one.
"""

from __future__ import annotations

from django.test import TestCase


class NotFoundHandlerTests(TestCase):
    def test_a_missing_file_gets_a_small_plain_text_404(self):
        for path in (
            '/static/no-such-sheet.css',
            '/media/products/no-such-image.jpg',
            '/no-such-script.js',
            '/wp-login.php',
            '/sitemap-nothing.xml',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertTrue(
                    response['Content-Type'].startswith('text/plain'), response['Content-Type']
                )
                self.assertLess(len(response.content), 200)

    def test_a_missing_page_still_gets_the_themes_404(self):
        response = self.client.get('/no-such-page-here/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertIn('<main', response.content.decode())


class NotFoundLogTests(TestCase):
    """The 404 log skips only a page number past the end of a REAL listing."""

    def _logged(self, path) -> bool:
        from plugins.installed.seo.models import NotFoundLog

        self.client.get(path)
        return NotFoundLog.objects.filter(path=path.split('?', 1)[0]).exists()

    def test_a_broken_address_carrying_a_page_parameter_is_still_logged(self):
        # Before: any 404 with `?page=` in the query was skipped, so a dead
        # address linked as `/old-listing/?page=2` never reached the log.
        self.assertTrue(self._logged('/an-old-listing-that-moved/?page=2'))

    def test_a_page_past_the_end_of_a_live_listing_is_not_logged(self):
        self.assertFalse(self._logged('/products/?page=999'))
