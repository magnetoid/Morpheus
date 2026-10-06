"""The PDP hero must have its box before its markup is laid out.

The slider template emitted its ``<style>`` AFTER the markup. On a fast
connection the parser swallows both in one go and nothing is visible; on a
slow one the chunk boundary falls between them, the hero is laid out as an
empty 0 px div, and when the stylesheet arrives the box grows to its 2:3
aspect ratio — a layout shift of 0.42 on the live product page (Lighthouse's
"bad" threshold is 0.25), measured by the post-deploy lighthouse workflow.
The rules that size the hero have to precede the elements they size.

The thumbnail strip also loaded the raw ``/media/`` original of every image
(a 1.7 MB PNG for a 56 px thumbnail); it goes through the responsive proxy
like the slides do.
"""

from __future__ import annotations

import pathlib

from django.conf import settings
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
