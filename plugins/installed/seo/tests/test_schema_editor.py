"""Visual schema editor — registry → JSON-LD, per-object editor, emission."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.models import SeoMeta
from plugins.installed.seo.schema_types import build_block, build_blocks


def _product(slug='ed-book', sku='ED-1'):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )


class RegistryTests(TestCase):
    def test_faq_block_shape(self):
        block = build_block('FAQPage', {'items': [{'question': 'Q1?', 'answer': 'A1.'}]})
        self.assertEqual(block['@type'], 'FAQPage')
        self.assertEqual(block['mainEntity'][0]['@type'], 'Question')
        self.assertEqual(block['mainEntity'][0]['acceptedAnswer']['text'], 'A1.')

    def test_book_block_shape(self):
        block = build_block(
            'Book',
            {
                'name': 'Utopia',
                'author': 'Thomas More',
                'isbn': '9780140449105',
                'book_format': 'Paperback',
                'in_language': 'en',
                'same_as': 'https://en.wikipedia.org/wiki/Utopia_(book)',
            },
        )
        self.assertEqual(block['@type'], 'Book')
        self.assertEqual(block['author'], {'@type': 'Person', 'name': 'Thomas More'})
        self.assertEqual(block['isbn'], '9780140449105')
        self.assertEqual(block['bookFormat'], 'https://schema.org/Paperback')
        self.assertEqual(block['inLanguage'], 'en')
        self.assertEqual(block['sameAs'], 'https://en.wikipedia.org/wiki/Utopia_(book)')

    def test_article_block_enriched(self):
        block = build_block(
            'Article',
            {'headline': 'Hi', 'publisher': 'Dot Books', 'date_modified': '2026-06-20'},
        )
        self.assertEqual(block['publisher'], {'@type': 'Organization', 'name': 'Dot Books'})
        self.assertEqual(block['dateModified'], '2026-06-20')

    def test_howto_duration_iso8601(self):
        block = build_block(
            'HowTo', {'name': 'X', 'total_time_min': '90', 'steps': [{'text': 'go'}]}
        )
        self.assertEqual(block['totalTime'], 'PT1H30M')

    def test_empty_and_unknown_dropped(self):
        self.assertIsNone(build_block('FAQPage', {'items': []}))
        self.assertIsNone(build_block('NopeType', {'x': 1}))
        # build_blocks skips the bad ones, keeps the good.
        out = build_blocks(
            [
                {'type': 'FAQPage', 'data': {'items': [{'question': 'q', 'answer': 'a'}]}},
                {'type': 'FAQPage', 'data': {'items': []}},
                {'type': 'Nope', 'data': {}},
            ]
        )
        self.assertEqual(len(out), 1)


class EmissionTests(TestCase):
    def test_schema_blocks_emit_as_script_tags(self):
        from plugins.installed.seo.services import resolve_meta

        product = _product()
        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(product.id),
            defaults={
                'schema_blocks': [
                    {
                        'type': 'FAQPage',
                        'data': {'items': [{'question': 'Hard?', 'answer': 'Yes.'}]},
                    },
                    {'type': 'Event', 'data': {'name': 'Launch', 'start_date': '2026-07-01T18:00'}},
                ]
            },
        )
        html = resolve_meta(obj=product).to_html()
        # The two schema-editor blocks. seo_meta no longer auto-emits a Product
        # (the PDP owns that via seo_product_jsonld), so there's no third script.
        self.assertEqual(html.count('<script type="application/ld+json">'), 2)
        self.assertIn('FAQPage', html)
        self.assertIn('"Launch"', html)

    def test_no_blocks_no_extra_scripts(self):
        from plugins.installed.seo.services import resolve_meta

        product = _product('no-schema', 'NS-1')
        html = resolve_meta(obj=product).to_html()
        # No editor blocks and no auto Product → seo_meta emits no JSON-LD here.
        self.assertEqual(html.count('<script type="application/ld+json">'), 0)


class EditorViewTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='sd', email='sd@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        self.product = _product()

    def _url(self):
        return reverse(
            'seo_dashboard:schema_editor', args=['catalog', 'product', str(self.product.id)]
        )

    def test_get_renders_editor(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="add-type"')  # the type picker
        self.assertContains(r, 'schema-types-data')  # registry embedded for the JS

    def test_post_saves_blocks(self):
        import json

        payload = json.dumps(
            [{'type': 'FAQPage', 'data': {'items': [{'question': 'Q?', 'answer': 'A.'}]}}]
        )
        r = self.client.post(self._url(), {'blocks_json': payload})
        self.assertEqual(r.status_code, 302)
        meta = SeoMeta.objects.get(object_id=str(self.product.id))
        self.assertEqual(len(meta.schema_blocks), 1)
        self.assertEqual(meta.schema_blocks[0]['type'], 'FAQPage')

    def test_post_drops_empty_blocks(self):
        import json

        payload = json.dumps([{'type': 'FAQPage', 'data': {'items': []}}])
        self.client.post(self._url(), {'blocks_json': payload})
        meta = SeoMeta.objects.filter(object_id=str(self.product.id)).first()
        # Empty block produced no JSON-LD → not stored.
        self.assertTrue(meta is None or meta.schema_blocks == [])

    def test_index_lists_objects_with_schema(self):
        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(self.product.id),
            defaults={'schema_blocks': [{'type': 'Event', 'data': {'name': 'X'}}]},
        )
        r = self.client.get(reverse('seo_dashboard:schema_index'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Event')
