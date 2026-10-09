"""Open Graph image dimensions are claimed only when known, never invented.

Both head renderers declared every og:image 1200×630 — a product photo, a
square default social image, a CMS cover alike. Social platforms lay a share
card out from those numbers before they fetch the file, so a wrong ratio is a
wrong card. The size is not known where the URL is resolved, so it is omitted.
"""

from __future__ import annotations

import re

from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.seo.services import resolve_meta


class OgImageDimensionTests(TestCase):
    def test_the_head_claims_no_size_for_the_default_social_image(self):
        StoreSettings.objects.create(default_social_image='store/square-social.png')
        html = self.client.get('/').content.decode()
        self.assertRegex(html, r'<meta property="og:image" content="[^"]*square-social\.png"')
        self.assertIsNone(re.search(r'og:image:(width|height)', html))

    def test_the_legacy_meta_block_claims_no_size(self):
        html = resolve_meta(
            obj=None,
            fallback_title='t',
            fallback_description='d',
            fallback_image='https://example.com/square.png',
        ).to_html()
        self.assertIn('og:image', html)
        self.assertNotIn('og:image:width', html)
        self.assertNotIn('og:image:height', html)
