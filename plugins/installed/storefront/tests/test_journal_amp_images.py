"""A journal post's images on its AMP page are valid `amp-img` elements.

The converter prefixed width="800" height="600" onto every <img>, so an image with
its own size carried both twice, and it kept `loading`, which amp-img does not
take: 9 of Montenegro's 24 AMP posts failed validation, reported in Search
Console as "attribute repeated" and "disallowed attribute" (2026-10-13).
"""

from __future__ import annotations

import re

from django.test import SimpleTestCase

from plugins.installed.storefront.views.content import _amp_images


class AmpImageTests(SimpleTestCase):
    def test_an_image_keeps_its_own_size_once_and_drops_loading(self):
        html = _amp_images(
            '<p>Bay</p><img src="/media/kotor.jpg" alt="Kotor &amp; bay" width="1400" '
            'height="788" loading="eager" decoding="async">'
        )
        tag = re.search(r'<amp-img[^>]*>', html).group(0)
        self.assertEqual(tag.count('width='), 1)
        self.assertEqual(tag.count('height='), 1)
        self.assertIn('width="1400"', tag)
        self.assertIn('height="788"', tag)
        self.assertNotIn('loading', tag)
        self.assertNotIn('decoding', tag)
        self.assertIn('alt="Kotor &amp; bay"', tag)
        self.assertIn('</amp-img>', html)
        self.assertNotIn('<img', html)

    def test_an_image_without_a_size_gets_a_responsive_default(self):
        html = _amp_images("<img src='/media/a.jpg' alt='a'/>")
        self.assertIn('width="800"', html)
        self.assertIn('height="600"', html)
        self.assertIn('layout="responsive"', html)

    def test_an_image_without_a_source_is_dropped(self):
        self.assertEqual(_amp_images('<p>x</p><img alt="none">'), '<p>x</p>')
