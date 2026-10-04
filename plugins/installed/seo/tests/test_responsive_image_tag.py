"""The responsive-image tag emits only URLs that resolve.

It used to add ``data-src-rel="products/x.jpg"`` — a bare storage path nothing
in the tree read. Crawlers resolved it against the page URL and logged roughly
13,000 404s a month on one store (``/products/<slug>/products/webp/<img>``).
"""

from __future__ import annotations

import re

from django.template import Context, Template
from django.test import SimpleTestCase


def render(src: str) -> str:
    return Template('{% load seo %}{% seo_responsive_image src alt="Cover" %}').render(
        Context({'src': src})
    )


class ResponsiveImageTagTests(SimpleTestCase):
    def test_every_emitted_path_is_absolute(self):
        html = render('/media/products/webp/cover.webp')
        self.assertIn('src="/img/webp/1200/products/webp/cover.webp"', html)
        self.assertIn('/img/avif/400/products/webp/cover.webp 400w', html)
        # No attribute value may start with a bare storage path.
        self.assertNotIn('data-src-rel', html)
        self.assertEqual(re.findall(r'="products/', html), [])
