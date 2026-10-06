"""The PDP hero: sized before it is laid out, and its first slide is the LCP.

The slider template emitted its ``<style>`` AFTER the markup, so on a slow
connection the hero could be laid out before the rules that give its slides a
2:3 box arrive. (v0.77.0 blamed this for the live product page's 0.42 layout
shift; it was not the cause — that was the theme's two-column rule arriving
after the grid, see ``themes/test_pdp_images.py`` — but the rules that size an
element still belong ahead of it.)

The first slide is the page's largest contentful paint, and it rendered with
``loading="lazy"`` and no fetch priority — Lighthouse's "LCP image was lazily
loaded" penalty on every product page. It is the one image that must be eager.

The thumbnail strip also loaded the raw ``/media/`` original of every image
(a 1.7 MB PNG for a 56 px thumbnail); it goes through the responsive proxy
like the slides do.
"""

from __future__ import annotations

import pathlib
import re

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

_TEMPLATE = (
    pathlib.Path(settings.BASE_DIR)
    / 'plugins'
    / 'installed'
    / 'product_gallery'
    / 'templates'
    / 'product_gallery'
    / '_pdp_hero_slider.html'
)


class HeroLayoutTests(SimpleTestCase):
    def test_hero_stylesheet_precedes_the_hero_markup(self):
        src = _TEMPLATE.read_text()
        style_at = src.index('<style>')
        markup_at = src.index('<div class="pdp-hero"')
        self.assertLess(style_at, markup_at, 'the hero is laid out before its sizing rules arrive')

    def test_thumbnails_do_not_load_the_raw_original(self):
        src = _TEMPLATE.read_text()
        thumbs = src[src.index('pdp-hero__thumbs') :]
        self.assertNotIn('<img src="{{ img.url }}"', thumbs)

    def test_first_slide_is_eager_and_high_priority_the_rest_lazy(self):
        html = render_to_string(
            'product_gallery/_pdp_hero_slider.html',
            {
                'product': {'name': 'Probe', 'slug': 'probe'},
                'images': [
                    {'url': '/media/products/probe-1.png', 'altText': '', 'sortOrder': 0},
                    {'url': '/media/products/probe-2.png', 'altText': '', 'sortOrder': 1},
                ],
                'videos': [],
                'alt': 'Probe',
            },
        )
        # Markup-only anchors: the class names also occur in the stylesheet above it.
        track = html[html.index('data-slider-track') : html.index('role="tablist"')]
        slides = re.findall(r'<img\b[^>]*>', track)
        self.assertEqual(len(slides), 2, slides)
        self.assertIn('fetchpriority="high"', slides[0])
        self.assertIn('loading="eager"', slides[0])
        self.assertIn('loading="lazy"', slides[1])
        self.assertNotIn('fetchpriority', slides[1])
