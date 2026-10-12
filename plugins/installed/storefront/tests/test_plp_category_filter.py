"""The shop's category filter lists only categories the merchant has switched on.

Irving Survival switched two old categories off after a catalogue rework
(2026-10-12), and the "Category" dropdown on /products/ still offered both:
picking one showed an empty shop. The category pages themselves already 404 an
inactive category; the filter now agrees with them.
"""

from __future__ import annotations

import re

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.catalog.models import Category

_OPTION = re.compile(r'<option value="([^"]+)"')


class PlpCategoryFilterTests(TestCase):
    def setUp(self):
        cache.clear()
        Category.objects.create(name='Water', slug='water-on')
        Category.objects.create(name='Food', slug='food-on')
        Category.objects.create(name='Old shelf', slug='old-shelf-off', is_active=False)

    def test_an_inactive_category_is_not_offered(self):
        body = self.client.get('/products/').content.decode()
        offered = set(_OPTION.findall(body))
        self.assertNotIn('old-shelf-off', offered)
        self.assertIn('water-on', body)
