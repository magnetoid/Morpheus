"""Product pictures take the shape chosen in Settings, on every theme.

Settings → Products → "Image shape" (`catalog.image_aspect_ratio`) reaches a
page as `--img-ratio` (`{% image_frame_style %}`). The gallery's frames were
hard-coded `2 / 3` — a book cover — so on Irving, set to square, a product with
no photo still showed a tall portrait box (the theme had re-squared the slides
and thumbnails but not the placeholder). Every frame now reads the setting and
keeps 2 / 3 only as the fallback for a store that never chose a shape; and a
product with no photo shows the store's own placeholder image when one is set
(Settings → General → Default images).
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

_TEMPLATES = Path(__file__).resolve().parents[1] / 'templates' / 'product_gallery'


class ImageFrameTests(SimpleTestCase):
    def test_no_frame_ignores_the_shape_setting(self):
        for path in sorted(_TEMPLATES.glob('*.html')):
            # Prose in comments may name the old ratio; only declarations count.
            src = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8'), flags=re.S)
            for ratio in re.findall(r'aspect-ratio:\s*([^;"]+)', src):
                with self.subTest(template=path.name, ratio=ratio):
                    if re.match(r'\s*2\s*/\s*3', ratio):
                        self.fail(
                            f'{path.name}: aspect-ratio {ratio} — use var(--img-ratio, 2 / 3)'
                        )

    def test_a_product_without_photos_shows_the_store_placeholder(self):
        html = render_to_string(
            'product_gallery/_pdp_hero_slider.html',
            {
                'images': [],
                'product': {'name': 'Signal whistle'},
                'alt': 'Signal whistle',
                'PRODUCT_PLACEHOLDER_IMAGE': '/media/store/irving-placeholder.png',
            },
        )
        self.assertIn('class="pdp-hero__placeholder"', html)
        self.assertIn('src="/media/store/irving-placeholder.png"', html)

    def test_without_a_placeholder_image_it_says_so(self):
        html = render_to_string(
            'product_gallery/_pdp_hero_slider.html',
            {'images': [], 'product': {'name': 'Signal whistle'}, 'alt': 'Signal whistle'},
        )
        self.assertIn('No image yet', html)
