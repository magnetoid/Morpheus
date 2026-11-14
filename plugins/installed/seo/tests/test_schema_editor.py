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
from plugins.installed.seo.schema_types import build_block, build_blocks, refusal


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

    def test_recipe_duration_iso8601(self):
        block = build_block(
            'Recipe', {'name': 'X', 'prep_time_min': '90', 'steps': [{'text': 'go'}]}
        )
        self.assertEqual(block['prepTime'], 'PT1H30M')

    def test_a_type_the_store_writes_is_refused(self):
        # A second Product or Event node contradicts the one its app builds.
        for custom in ('Product', 'Organization', 'Event', 'BreadcrumbList', 'Hotel'):
            data = {'custom_type': custom, 'props': [{'property': 'name', 'value': 'X'}]}
            self.assertIsNone(build_block('Custom', data), custom)
            self.assertTrue(refusal({'type': 'Custom', 'data': data}), custom)

    def test_retired_types_build_nothing(self):
        for kind in ('HowTo', 'Book', 'Event', 'Article'):
            self.assertIsNone(build_block(kind, {'name': 'X', 'headline': 'X'}), kind)
        self.assertEqual(refusal({'type': 'HowTo', 'data': {}}), 'No longer used by Google.')

    def test_a_custom_row_cannot_set_the_graph_keys(self):
        block = build_block(
            'Custom',
            {
                'custom_type': 'Dataset',
                'props': [
                    {'property': '@id', 'value': 'https://elsewhere.test/#x'},
                    {'property': 'name', 'value': 'Stock list'},
                ],
            },
        )
        self.assertEqual(block['@type'], 'Dataset')
        self.assertNotIn('@id', block)

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


def _graph(response) -> list[dict]:
    import json
    import re

    head = response.content.decode().split('</head>', 1)[0]
    nodes: list[dict] = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S):
        nodes.extend(json.loads(block).get('@graph', []))
    return nodes


class GraphTests(TestCase):
    """The blocks reach the object's page, in its graph (v0.163.0).

    Before, only the legacy `{% seo_meta %}` tag rendered them, and under the head
    contract every theme's `{% storefront_head %}` silences that tag: a saved FAQ
    appeared on no page.
    """

    def _blocks(self, product, blocks):
        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(product.id),
            defaults={'schema_blocks': blocks},
        )

    def test_a_block_is_in_the_page_graph(self):
        product = _product()
        self._blocks(
            product,
            [{'type': 'FAQPage', 'data': {'items': [{'question': 'Hard?', 'answer': 'Yes.'}]}}],
        )
        nodes = _graph(self.client.get(f'/products/{product.slug}/'))
        faq = [n for n in nodes if n.get('@type') == 'FAQPage']
        self.assertEqual(len(faq), 1)
        self.assertEqual(faq[0]['mainEntity'][0]['name'], 'Hard?')
        self.assertTrue(faq[0]['@id'].endswith(f'/products/{product.slug}/#schema-1'))
        self.assertNotIn('@context', faq[0])

    def test_retired_and_owned_blocks_render_nowhere(self):
        product = _product()
        self._blocks(
            product,
            [
                {'type': 'HowTo', 'data': {'name': 'X', 'steps': [{'text': 'go'}]}},
                {'type': 'Event', 'data': {'name': 'Launch', 'start_date': '2026-07-01T18:00'}},
                {
                    'type': 'Custom',
                    'data': {
                        'custom_type': 'Product',
                        'props': [{'property': 'name', 'value': 'Second product'}],
                    },
                },
            ],
        )
        nodes = _graph(self.client.get(f'/products/{product.slug}/'))
        types = [n.get('@type') for n in nodes]
        self.assertNotIn('HowTo', types)
        self.assertNotIn('Event', types)
        self.assertEqual(types.count('Product'), 1)
        self.assertNotIn('Second product', str(nodes))

    def test_a_type_already_in_the_graph_is_not_added_twice(self):
        from plugins.installed.seo.schema.graph import _add_editor_blocks

        product = _product()
        self._blocks(
            product,
            [{'type': 'FAQPage', 'data': {'items': [{'question': 'Q?', 'answer': 'A.'}]}}],
        )
        graph = {'@graph': [{'@type': 'FAQPage', 'mainEntity': []}]}
        page = type('Page', (), {'obj': product})()
        _add_editor_blocks(graph, page, 'https://shop.test/p/')
        self.assertEqual([n['@type'] for n in graph['@graph']], ['FAQPage'])

    def test_no_blocks_no_extra_nodes(self):
        product = _product('no-schema', 'NS-1')
        nodes = _graph(self.client.get(f'/products/{product.slug}/'))
        self.assertFalse([n for n in nodes if '#schema-' in str(n.get('@id', ''))])


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

    def test_a_retired_block_is_listed_with_a_delete_button(self):
        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(self.product.id),
            defaults={
                'schema_blocks': [
                    {'type': 'HowTo', 'data': {'name': 'X', 'steps': [{'text': 'go'}]}},
                    {'type': 'FAQPage', 'data': {'items': [{'question': 'Q?', 'answer': 'A.'}]}},
                ]
            },
        )
        r = self.client.get(self._url())
        self.assertContains(r, 'No longer used by Google.')
        self.assertContains(r, 'name="action" value="delete_retired"')
        # The editor's form gets only the block it can edit.
        self.assertEqual([b['type'] for b in r.context['existing_blocks']], ['FAQPage'])

        # Saving the form keeps the retired block; the button deletes it.
        import json

        faq = [{'type': 'FAQPage', 'data': {'items': [{'question': 'Q?', 'answer': 'B.'}]}}]
        self.client.post(self._url(), {'blocks_json': json.dumps(faq)})
        meta = SeoMeta.objects.get(object_id=str(self.product.id))
        self.assertEqual([b['type'] for b in meta.schema_blocks], ['FAQPage', 'HowTo'])
        self.client.post(self._url(), {'action': 'delete_retired', 'index': '1'})
        meta.refresh_from_db()
        self.assertEqual([b['type'] for b in meta.schema_blocks], ['FAQPage'])

    def test_a_block_of_an_owned_type_is_refused_at_save(self):
        import json

        payload = json.dumps(
            [
                {
                    'type': 'Custom',
                    'data': {
                        'custom_type': 'Organization',
                        'props': [{'property': 'name', 'value': 'Other'}],
                    },
                }
            ]
        )
        r = self.client.post(self._url(), {'blocks_json': payload}, follow=True)
        self.assertContains(r, 'A block was not saved.')
        meta = SeoMeta.objects.filter(object_id=str(self.product.id)).first()
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


class AgentToolTests(TestCase):
    """Linda reaches the editor through seo.schema_blocks / set / delete."""

    def setUp(self):
        self.product = _product('tool-book', 'TB-1')

    def test_tools_are_gated(self):
        from plugins.installed.seo.agent_tools import (
            delete_schema_block_tool,
            schema_blocks_tool,
            set_schema_block_tool,
        )

        self.assertFalse(schema_blocks_tool.requires_approval)
        self.assertEqual(schema_blocks_tool.scopes, ['seo.read'])
        for tool in (set_schema_block_tool, delete_schema_block_tool):
            self.assertTrue(tool.requires_approval, tool.name)
            self.assertEqual(tool.scopes, ['seo.write'])

    def test_set_read_and_delete_a_block(self):
        from plugins.installed.seo.agent_tools import (
            delete_schema_block_tool,
            schema_blocks_tool,
            set_schema_block_tool,
        )

        target = {'model': 'catalog.product', 'object_id': 'tool-book'}
        faq = {'items': [{'question': 'Signed?', 'answer': 'Yes.'}]}
        set_schema_block_tool.invoke({**target, 'type': 'FAQPage', 'data': faq})
        out = schema_blocks_tool.invoke(target).output
        self.assertEqual([(b['type'], b['shows']) for b in out['blocks']], [('FAQPage', True)])
        self.assertIn('Recipe', [t['type'] for t in out['types']])
        listed = schema_blocks_tool.invoke({}).output['objects']
        self.assertEqual(listed[0]['object_id'], str(self.product.id))

        delete_schema_block_tool.invoke({**target, 'index': 0})
        meta = SeoMeta.objects.get(object_id=str(self.product.id))
        self.assertEqual(meta.schema_blocks, [])

    def test_an_owned_or_retired_type_is_refused(self):
        from morpheus.core import ToolError
        from plugins.installed.seo.agent_tools import set_schema_block_tool

        target = {'model': 'catalog.product', 'object_id': str(self.product.id)}
        product_block = {'custom_type': 'Product', 'props': [{'property': 'name', 'value': 'X'}]}
        with self.assertRaises(ToolError):
            set_schema_block_tool.invoke({**target, 'type': 'Custom', 'data': product_block})
        with self.assertRaises(ToolError):
            set_schema_block_tool.invoke({**target, 'type': 'HowTo', 'data': {'name': 'X'}})
        # (Creating a product mints its SeoMeta row; the blocks stay empty.)
        meta = SeoMeta.objects.filter(object_id=str(self.product.id)).first()
        self.assertTrue(meta is None or meta.schema_blocks == [])
