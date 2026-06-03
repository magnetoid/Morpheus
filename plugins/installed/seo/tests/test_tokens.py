"""SEO title/description metafield-token expansion."""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield
from plugins.installed.seo.models import SeoMeta
from plugins.installed.seo.services.meta import resolve_meta
from plugins.installed.seo.services.tokens import available_tokens, expand_tokens


class SeoTokenTests(TestCase):
    def setUp(self):
        self.p = Product.objects.create(
            name='Persuasion', slug='persuasion', sku='PER', price=Money(9, 'USD'), status='active'
        )
        Metafield.objects.set(self.p, namespace='book', key='author', value='Jane Austen')

    def test_expand_field_and_metafield_tokens(self):
        self.assertEqual(expand_tokens('{name} by {author}', self.p), 'Persuasion by Jane Austen')

    def test_unknown_token_left_literal(self):
        self.assertEqual(expand_tokens('{name} {nope}', self.p), 'Persuasion {nope}')

    def test_noop_without_braces_or_obj(self):
        self.assertEqual(expand_tokens('plain title', self.p), 'plain title')
        self.assertEqual(expand_tokens('{name}', None), '{name}')

    def test_available_tokens_includes_fields_and_metafields(self):
        toks = {t['token'] for t in available_tokens(self.p)}
        self.assertIn('{name}', toks)
        self.assertIn('{author}', toks)

    def test_resolve_meta_expands_tokens(self):
        # The winning title source (here the SeoMeta override) carries tokens;
        # resolve_meta must expand them. (A site suffix may be appended.)
        sm = SeoMeta.for_obj(self.p)
        self.assertIsNotNone(sm)  # autofilled on product create
        sm.title = '{name} by {author}'
        sm.save()
        meta = resolve_meta(obj=self.p)
        self.assertIn('Persuasion by Jane Austen', meta.title)
