"""Tests for the AEO/GEO features: answer-readiness scorer, the AI-answer
TL;DR in JSON-LD, Article citation/E-E-A-T fields, and the 2026 crawler set.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield
from plugins.installed.seo.services import score_aeo
from plugins.installed.seo.services.crawler_files import AI_CRAWLERS, render_robots_txt
from plugins.installed.seo.services.jsonld import article_jsonld, product_jsonld


def _make_product(**kwargs) -> Product:
    defaults = {
        'name': 'Atomic Habits',
        'slug': 'atomic-habits',
        'status': 'active',
        'price': Money(Decimal('18.00'), 'USD'),
    }
    defaults.update(kwargs)
    # SKU is unique; derive it from the slug so callers only vary slug.
    defaults.setdefault('sku', f'SKU-{defaults["slug"]}')
    return Product.objects.create(**defaults)


class ScoreAeoTests(TestCase):
    def test_thin_product_scores_low(self):
        p = _make_product(slug='thin', description='')
        result = score_aeo(p)
        self.assertLess(result['score'], 50)
        # The TL;DR signal must be present and failing.
        codes = {s['code']: s['ok'] for s in result['signals']}
        self.assertIn('tldr_answer', codes)
        self.assertFalse(codes['tldr_answer'])
        self.assertTrue(result['suggestions'])

    def test_explicit_ai_answer_metafield_satisfies_tldr_signal(self):
        p = _make_product(slug='answered')
        Metafield.objects.set(
            p,
            namespace='seo',
            key='ai_answer',
            value='A practical guide to building good habits in small steps.',
        )
        result = score_aeo(p)
        codes = {s['code']: s['ok'] for s in result['signals']}
        self.assertTrue(codes['tldr_answer'])

    def test_rich_product_scores_higher_than_thin(self):
        thin = _make_product(slug='thin-2', description='Short.')
        rich = _make_product(
            slug='rich',
            short_description='A clear, practical framework for habit change.',
            description=(
                '<h2>What it is</h2><p>' + ('word ' * 150) + '</p>'
                '<h2>The details</h2><p>320 pages, published 2018, '
                'covering 4 laws across 20 chapters.</p>'
            ),
        )
        Metafield.objects.set(
            rich,
            namespace='seo',
            key='ai_answer',
            value='Atomic Habits explains how tiny 1% changes compound into results.',
        )
        Metafield.objects.set(rich, namespace='book', key='author', value='James Clear')
        Metafield.objects.set(
            rich,
            namespace='seo',
            key='same_as',
            value='https://en.wikipedia.org/wiki/Atomic_Habits',
        )
        self.assertGreater(score_aeo(rich)['score'], score_aeo(thin)['score'])

    def test_score_shape_is_stable(self):
        p = _make_product(slug='shape')
        result = score_aeo(p)
        self.assertEqual(set(result), {'score', 'signals', 'suggestions'})
        self.assertTrue(0 <= result['score'] <= 100)
        for sig in result['signals']:
            self.assertEqual(set(sig), {'code', 'label', 'ok', 'weight', 'detail'})


class ProductJsonLdAnswerTests(TestCase):
    def test_disambiguating_description_emitted_from_metafield(self):
        p = _make_product(slug='dd')
        Metafield.objects.set(
            p,
            namespace='seo',
            key='ai_answer',
            value='The quotable one-line answer AI engines can lift.',
        )
        out = product_jsonld(p)
        self.assertEqual(
            out['disambiguatingDescription'],
            'The quotable one-line answer AI engines can lift.',
        )

    def test_no_disambiguating_description_when_unset(self):
        p = _make_product(slug='no-dd')
        out = product_jsonld(p)
        self.assertNotIn('disambiguatingDescription', out)


class ArticleJsonLdTrustTests(TestCase):
    def test_citations_emit_citation_and_isbasedon(self):
        out = article_jsonld(
            headline='Why small habits win',
            body='Body text.',
            url='https://example.com/journal/habits/',
            citations=['https://source.example/study', 'https://source.example/book'],
        )
        self.assertIn('citation', out)
        self.assertEqual(out['citation'][0]['@type'], 'CreativeWork')
        self.assertEqual(
            out['isBasedOn'],
            ['https://source.example/study', 'https://source.example/book'],
        )

    def test_author_same_as_attached_to_author_node(self):
        out = article_jsonld(
            headline='H',
            body='B',
            url='https://example.com/journal/h/',
            author='James Clear',
            author_same_as=['https://twitter.com/jamesclear'],
        )
        self.assertEqual(out['author']['name'], 'James Clear')
        self.assertEqual(out['author']['sameAs'], ['https://twitter.com/jamesclear'])

    def test_no_trust_fields_when_omitted(self):
        out = article_jsonld(headline='H', body='B', url='https://example.com/j/')
        self.assertNotIn('citation', out)
        self.assertNotIn('isBasedOn', out)


class CrawlerMatrixTests(TestCase):
    def test_cohere_ai_in_catalogue(self):
        uas = {ua.lower() for ua, _label, _kind in AI_CRAWLERS}
        self.assertIn('cohere-ai', uas)

    def test_2026_generative_crawler_set_present(self):
        uas = {ua.lower() for ua, _label, _kind in AI_CRAWLERS}
        for required in (
            'gptbot',
            'oai-searchbot',
            'chatgpt-user',
            'claudebot',
            'claude-searchbot',
            'perplexitybot',
            'perplexity-user',
            'google-extended',
            'applebot-extended',
            'bytespider',
            'meta-externalagent',
            'amazonbot',
            'cohere-ai',
        ):
            self.assertIn(required, uas)

    def test_cohere_ai_emitted_in_robots_txt(self):
        self.assertIn('cohere-ai', render_robots_txt())
