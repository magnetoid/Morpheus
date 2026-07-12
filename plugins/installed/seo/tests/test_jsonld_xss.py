"""Stored-XSS regression tests for the JSON-LD serializer.

``_jsonld_dump`` embeds its output raw inside ``<script type="application/ld+json">``
via ``mark_safe``. ``json.dumps`` escapes quotes/backslashes but NOT ``</script>``,
so a product name/description containing a closing tag would break out of the
script element and inject arbitrary JS on every storefront viewer of that page.
The dumper must escape ``< > &`` (and the U+2028/U+2029 line separators) the same
way Django's ``json_script`` does.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.models import SiteSeoSettings
from plugins.installed.seo.services import product_jsonld
from plugins.installed.seo.services._helpers import _jsonld_dump


class JsonLdEscapeTests(TestCase):
    def test_script_breakout_is_neutralised(self):
        out = _jsonld_dump({'name': 'Evil </script><script>alert(1)</script>'})
        self.assertNotIn('</script>', out)
        self.assertNotIn('<script>', out)
        self.assertIn('\\u003C', out)

    def test_ampersand_and_angle_brackets_escaped(self):
        out = _jsonld_dump({'x': '<b> & </b>'})
        for raw in ('<', '>', '&'):
            self.assertNotIn(raw, out)

    def test_line_separators_escaped(self):
        out = _jsonld_dump({'x': 'a' + chr(0x2028) + 'b' + chr(0x2029) + 'c'})
        self.assertNotIn(chr(0x2028), out)
        self.assertNotIn(chr(0x2029), out)

    def test_product_name_with_breakout_is_safe_end_to_end(self):
        SiteSeoSettings.objects.create(organization_name='shop')
        p = Product.objects.create(
            name='Book </script><script>alert(1)</script>',
            slug='book-x',
            sku='BX1',
            price=Money(10, 'USD'),
            status='active',
        )
        rendered = _jsonld_dump(product_jsonld(p))
        self.assertNotIn('</script>', rendered)


class ProductSanitizeOnSaveTests(TestCase):
    def test_description_script_stripped_on_save(self):
        p = Product.objects.create(
            name='Clean',
            slug='clean',
            sku='C1',
            price=Money(10, 'USD'),
            status='active',
            description='<p>ok</p><script>alert(1)</script>',
            short_description='<img src=x onerror=alert(1)>hi',
        )
        p.refresh_from_db()
        self.assertNotIn('<script>', p.description)
        self.assertIn('<p>ok</p>', p.description)
        self.assertNotIn('onerror', p.short_description)
