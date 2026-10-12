"""An empty rail renders nothing.

The cart and checkout printed "Trending with shoppers like you" and "Looks like
you" headings with nothing under them on every store, and the product page two
empty customer-photo sections (ugc_reviews), because the blocks wrapped only
their lists in a loop (found live, 2026-10-12).
"""

from __future__ import annotations

from django.template.loader import render_to_string
from django.test import SimpleTestCase

BLOCKS = (
    ('rails/blocks/looks_like_you.html', 'looks_like_you_products'),
    ('rails/blocks/trending_with_you.html', 'trending_products'),
    ('rails/blocks/recently_viewed.html', 'recently_viewed'),
    ('ugc_reviews/blocks/ugc_gallery.html', 'approved_ugc_media'),
    ('ugc_reviews/blocks/ugc_highlights.html', 'ugc_highlights'),
)


class EmptyRailTests(SimpleTestCase):
    def test_an_empty_block_renders_nothing(self):
        for template, key in BLOCKS:
            with self.subTest(template=template):
                self.assertEqual(render_to_string(template, {key: []}).strip(), '')

    def test_a_filled_block_still_renders(self):
        html = render_to_string(
            'ugc_reviews/blocks/ugc_highlights.html',
            {'ugc_highlights': [{'body': 'Works in a blackout.', 'author': 'Ana'}]},
        )
        self.assertIn('Works in a blackout.', html)
