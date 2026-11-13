"""The travel themes' images and maps (v0.159.1, release 5 of the SEO and analytics audit).

Montenegro and Croatia printed every listing photo as a raw ``<img src>`` at full
size, and loaded Leaflet's stylesheet and script from unpkg on every detail page
whether or not anyone scrolled to the map. Listing photos now go through seo's
responsive tag (sized variants, width and height, lazy below the fold), and a map
draws only once it nears the screen. The templates load ``booking_tags``, so this
lives with the app that ships it.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template import engines
from django.test import SimpleTestCase

THEMES = Path(__file__).resolve().parents[4] / 'themes' / 'library'


class TravelThemeTemplateTests(SimpleTestCase):
    TRAVEL = ('montenegro', 'croatia')
    PAGES = (
        'storefront/home.html',
        'booking_marketplace/_experience_card.html',
        'booking_marketplace/_leaflet_map.html',
        'booking_marketplace/detail.html',
        'booking_marketplace/events/detail.html',
        'booking_marketplace/events/index.html',
        'booking_marketplace/places/detail.html',
        'booking_marketplace/places/index.html',
        'booking_marketplace/stays/_hotel_card.html',
        'booking_marketplace/stays/detail.html',
    )

    def test_every_changed_template_compiles(self):
        django = engines['django']
        for theme in self.TRAVEL:
            for page in self.PAGES:
                path = THEMES / theme / 'templates' / page
                django.from_string(path.read_text())  # raises on a syntax error

    def test_listing_images_go_through_the_responsive_tag(self):
        raw = re.compile(r'<img[^>]+src="\{\{\s*[\w.]+\.url\s*\}\}"')
        for theme in self.TRAVEL:
            for page in self.PAGES:
                text = (THEMES / theme / 'templates' / page).read_text()
                self.assertIsNone(raw.search(text), f'{theme}/{page}')

    def test_maps_load_leaflet_only_on_demand(self):
        for theme in self.TRAVEL:
            for page in self.PAGES:
                text = (THEMES / theme / 'templates' / page).read_text()
                if page.endswith('_leaflet_map.html'):
                    self.assertIn('IntersectionObserver', text)
                    self.assertIn('nonce="{{ csp_nonce }}"', text)
                    continue
                self.assertNotIn('unpkg.com/leaflet', text, f'{theme}/{page}')
            for page, map_id in (
                ('booking_marketplace/detail.html', 'exp-map'),
                ('booking_marketplace/places/detail.html', 'place-map'),
                ('booking_marketplace/stays/detail.html', 'stay-map'),
            ):
                text = (THEMES / theme / 'templates' / page).read_text()
                self.assertIn(f'id="{map_id}"', text)
                self.assertIn(f'_leaflet_map.html" with map_id="{map_id}"', text)

    def test_the_map_partial_renders_its_map(self):
        text = (
            THEMES / 'montenegro' / 'templates' / 'booking_marketplace' / '_leaflet_map.html'
        ).read_text()
        html = (
            engines['django']
            .from_string(text)
            .render({'map_id': 'exp-map', 'zoom': 13, 'csp_nonce': 'n0nce'})
        )
        self.assertIn("getElementById('exp-map')", html)
        self.assertIn('setView(p,13)', html)
        self.assertIn('<script nonce="n0nce">', html)
