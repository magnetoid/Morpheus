"""Markup the live axe audit flagged on the dot_books storefront.

`.github/workflows/accessibility.yml` runs axe-core against the live store
after every deploy. Two of its findings were structural, so they are guarded
here, before a deploy, by rendering the real pages:

* ``image-redundant-alt`` — a product card's cover sat inside the same link as
  the title with ``alt`` equal to that title, so a screen reader announced every
  book twice ("Peter Pan, Peter Pan"). Inside the card link the cover is
  decorative (``alt=""``); the link's accessible name is the title.
* ``aria-allowed-role`` — the home hero's panels were
  ``<article role="tabpanel">``, and ``article`` does not permit that role.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from themes.registry import theme_registry

_IMG = re.compile(r'<img\b[^>]*>', re.I)
_ALT = re.compile(r'\balt="([^"]*)"', re.I)
_TABPANEL_ARTICLE = re.compile(r'<article\b[^>]*role="tabpanel"', re.I)


class DotBooksA11yMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product, ProductImage

        category = Category.objects.create(name='A11y Category', slug='a11y-cat')
        for i in (1, 2):
            product = Product.objects.create(
                name=f'A11y Probe {i}',
                slug=f'a11y-probe-{i}',
                sku=f'A11Y-{i}',
                price=Money(Decimal('9.00'), 'USD'),
                product_type='simple',
                status='active',
                is_featured=True,
                category=category,
            )
            # A stored path is enough: the card renders the URL, never the bytes.
            ProductImage.objects.create(
                product=product, image=f'products/a11y-probe-{i}.jpg', is_primary=True
            )

    def setUp(self):
        cache.clear()
        override = override_settings(MORPHEUS_ACTIVE_THEME='dot_books')
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active('dot_books')
        self.addCleanup(setattr, theme_registry, '_active_name', previous)

    @staticmethod
    def _card_links(body: str) -> list[str]:
        """The hit link of every product card — cover and title share one <a>."""
        return [chunk.split('</a>', 1)[0] for chunk in body.split('data-product-card')[1:]]

    def test_card_cover_is_decorative_inside_the_title_link(self):
        for path in ('/', '/products/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                links = self._card_links(body)
                self.assertTrue(links, f'{path}: no product card rendered — fixture drift')
                covers = [img for link in links for img in _IMG.findall(link)]
                self.assertTrue(covers, f'{path}: no cover rendered in a card — fixture drift')
                for img in covers:
                    alt = _ALT.search(img)
                    self.assertIsNotNone(alt, f'{path}: cover has no alt attribute: {img}')
                    self.assertEqual(
                        alt.group(1), '', f'{path}: cover alt repeats the title: {img}'
                    )

    def test_hero_panels_use_an_element_that_permits_tabpanel(self):
        body = self.client.get('/').content.decode()
        self.assertIn('role="tabpanel"', body, 'hero did not render as tabs — fixture drift')
        self.assertIsNone(_TABPANEL_ARTICLE.search(body), '<article> does not permit role=tabpanel')
