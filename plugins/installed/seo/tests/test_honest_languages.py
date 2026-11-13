"""A page names only the languages its content is in (v0.160.0).

Montenegro and Croatia served every product, experience, place and hotel under
`/sr/` or `/hr/` in English while the head claimed both languages: hreflang en + sr,
a self-canonical on `/sr/x/` and `inLanguage: sr`. A page about one object exists in
a language only once the object has a reviewed translation there of every field it
fills (core.i18n); until then `/sr/x/` names `/x/` as its canonical and `/x/` names
no alternates. Pages with no object keep every language.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.i18n.services import set_translation

_TWO_LANGUAGES = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}

_TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
_ROBOTS = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
_CANONICAL = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', re.I)
_ALTERNATE = re.compile(r'<link[^>]+rel="alternate"[^>]+href="([^"]*)"[^>]+hreflang="([^"]+)"')
_OG_LOCALE = re.compile(r'<meta[^>]+property="og:locale"[^>]+content="([^"]*)"', re.I)


def _head(response) -> str:
    return response.content.decode().split('</head>', 1)[0]


def _alternates(head: str) -> dict[str, str]:
    return {code: href.replace('&amp;', '&') for href, code in _ALTERNATE.findall(head)}


def _webpage(head: str) -> dict:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    for block in blocks:
        for node in json.loads(block).get('@graph', []):
            if node.get('@id', '').endswith('#webpage'):
                return node
    return {}


@override_settings(**_TWO_LANGUAGES)
class HonestLanguagesTests(TestCase):
    def setUp(self):
        cache.clear()
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Lighthouse Walk',
            slug='lighthouse-walk',
            sku='LW-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            description='<p>A walk to the old lighthouse.</p>',
        )

    def _translate(self, *, reviewed=True, fields=('name', 'description')):
        values = {'name': 'Šetnja do svetionika', 'description': '<p>Do starog svetionika.</p>'}
        for field in fields:
            set_translation(self.product, field, 'sr', values[field], reviewed=reviewed)

    def _get(self, path):
        cache.clear()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return _head(response)

    def test_an_untranslated_object_claims_one_language(self):
        english = self._get('/products/lighthouse-walk/')
        self.assertEqual(_alternates(english), {})
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(
            _CANONICAL.findall(serbian), ['http://testserver/products/lighthouse-walk/']
        )
        self.assertEqual(_alternates(serbian), {})
        self.assertNotIn('noindex', _ROBOTS.search(serbian).group(1))

    def test_the_untranslated_copy_names_the_language_it_is_in(self):
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(_OG_LOCALE.search(serbian).group(1), 'en')
        self.assertEqual(_webpage(serbian).get('inLanguage'), 'en')

    def test_a_reviewed_translation_makes_both_pages(self):
        self._translate()
        english = self._get('/products/lighthouse-walk/')
        self.assertEqual(
            _alternates(english),
            {
                'en': 'http://testserver/products/lighthouse-walk/',
                'sr': 'http://testserver/sr/products/lighthouse-walk/',
                'x-default': 'http://testserver/products/lighthouse-walk/',
            },
        )
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(
            _CANONICAL.findall(serbian), ['http://testserver/sr/products/lighthouse-walk/']
        )
        self.assertIn('Šetnja do svetionika', _TITLE.search(serbian).group(1))
        self.assertEqual(_OG_LOCALE.search(serbian).group(1), 'sr')
        self.assertEqual(_webpage(serbian).get('inLanguage'), 'sr')

    def test_a_draft_counts_for_nothing(self):
        self._translate(reviewed=False)
        self.assertEqual(_alternates(self._get('/products/lighthouse-walk/')), {})
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(
            _CANONICAL.findall(serbian), ['http://testserver/products/lighthouse-walk/']
        )
        self.assertNotIn('Šetnja', serbian)

    def test_a_partial_translation_counts_for_nothing(self):
        self._translate(fields=('name',))
        self.assertEqual(_alternates(self._get('/products/lighthouse-walk/')), {})
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(
            _CANONICAL.findall(serbian), ['http://testserver/products/lighthouse-walk/']
        )

    def test_a_page_with_no_object_keeps_every_language(self):
        self.assertEqual(set(_alternates(self._get('/'))), {'en', 'sr', 'x-default'})
        self.assertEqual(_CANONICAL.findall(self._get('/sr/')), ['http://testserver/sr/'])

    def test_the_merchants_canonical_still_wins(self):
        self.product.canonical_url = 'https://example.com/the-walk/'
        self.product.save()
        serbian = self._get('/sr/products/lighthouse-walk/')
        self.assertEqual(_CANONICAL.findall(serbian), ['https://example.com/the-walk/'])

    def test_the_seo_row_does_not_name_a_translated_page(self):
        from plugins.installed.seo.models import SeoMeta

        self._translate()
        from django.contrib.contenttypes.models import ContentType

        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(type(self.product)),
            object_id=str(self.product.pk),
            defaults={'title': 'English SEO Title', 'auto_filled': False},
        )
        self.assertIn(
            'English SEO Title', _TITLE.search(self._get('/products/lighthouse-walk/')).group(1)
        )
        serbian = _TITLE.search(self._get('/sr/products/lighthouse-walk/')).group(1)
        self.assertNotIn('English SEO Title', serbian)
        self.assertIn('Šetnja do svetionika', serbian)
