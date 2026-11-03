"""Text an AI wrote is marked, and only that text (EU AI Act Art. 50, v0.133.0).

Two directions, like every public claim in the store's markup: text a store agent
wrote carries the mark on the product page and in its structured data; text
nothing says an AI wrote (a person, an API token) carries none.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import QueryDict
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from core.agents.registry import agent_registry
from core.hooks import MorpheusEvents, hook_registry
from core.seo_page import KIND_PRODUCT, SeoPage
from plugins.installed.admin_dashboard.tests.test_product_form_roundtrip import (
    _AJAX,
    browser_form_data,
)
from plugins.installed.ai_content.marks import NAMESPACE, marks_for
from plugins.installed.ai_content.seo_graph import GENERATED
from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield
from plugins.installed.seo.schema import build_graph
from plugins.registry import app_registry

LABEL = "This product's description was written with the help of AI."


def _product(**extra) -> Product:
    fields = {
        'name': 'Lantern',
        'slug': 'lantern',
        'sku': 'LAN-1',
        'status': 'active',
        'price': Money(Decimal('20'), 'USD'),
    }
    fields.update(extra)
    return Product.objects.create(**fields)


def _call(tool_name: str, args: dict, *, agent=None, context=None):
    return agent_registry.get_tool(tool_name).invoke(args, agent=agent, context=context or {})


def _mark(product, field, source='linda'):
    Metafield.objects.set(product, namespace=NAMESPACE, key=field, value=source)


def _graph(product) -> dict:
    return build_graph(
        SeoPage(
            kind=KIND_PRODUCT,
            obj=product,
            rendered={
                'slug': product.slug,
                'name': product.name,
                'description': product.description,
                'short_description': product.short_description,
                'price': {'amount': '20.00', 'currency': 'USD'},
            },
            path=f'/products/{product.slug}/',
            title=product.name,
        )
    )


def _nodes(graph, type_name):
    return [n for n in graph['@graph'] if type_name in str(n.get('@type', ''))]


class WhoWroteItTests(TestCase):
    """The tools mark what a store agent wrote, and nothing a token wrote."""

    def test_linda_writing_a_description_marks_it(self):
        p = _product()
        _call(
            'catalog.update_product',
            {'slug': p.slug, 'description': '<p>A brass lantern.</p>'},
            context={'source': 'linda', 'user': None},
        )
        self.assertEqual(marks_for(p), {'description': 'linda'})

    def test_a_worker_writing_text_marks_it(self):
        p = _product()
        _call(
            'catalog.update_product',
            {'slug': p.slug, 'meta_description': 'Brass lantern, 20 cm.'},
            agent=object(),
        )
        self.assertEqual(marks_for(p), {'meta_description': 'worker'})

    def test_an_api_token_writing_text_marks_nothing(self):
        # A token call may be a product-information system copying a person's text.
        p = _product()
        _call(
            'catalog.update_product',
            {'slug': p.slug, 'description': '<p>Written by the buyer.</p>'},
            context={'source': 'mcp'},
        )
        self.assertEqual(marks_for(p), {})

    def test_only_the_text_fields_written_are_marked(self):
        _call(
            'catalog.create_product',
            {
                'name': 'Compass',
                'price_amount': '15.00',
                'short_description': 'Points north.',
                'description': '',
                'status': 'draft',
            },
            context={'source': 'linda'},
        )
        p = Product.objects.get(name='Compass')
        self.assertEqual(marks_for(p), {'short_description': 'linda'})

    def test_changing_a_status_marks_nothing(self):
        p = _product()
        _call('catalog.update_product', {'slug': p.slug, 'status': 'draft'}, agent=object())
        self.assertEqual(marks_for(p), {})

    def test_a_bulk_rewrite_marks_what_it_applied(self):
        from plugins.installed.ai_content import services_bulk_catalog as bulk

        p = _product(description='<p>Old.</p>')
        with mock.patch.object(bulk, '_call_llm', return_value=('<p>New.</p>', 0)):
            bulk.rewrite(target='description', tone='concise', product_ids=[p.pk], dry_run=False)
        self.assertEqual(marks_for(p), {'description': 'bulk'})

    def test_a_bulk_dry_run_marks_nothing(self):
        from plugins.installed.ai_content import services_bulk_catalog as bulk

        p = _product(description='<p>Old.</p>')
        with mock.patch.object(bulk, '_call_llm', return_value=('<p>New.</p>', 0)):
            bulk.rewrite(target='description', tone='concise', product_ids=[p.pk], dry_run=True)
        self.assertEqual(marks_for(p), {})

    def test_linda_reads_the_marks(self):
        p = _product()
        _mark(p, 'description', 'editor')
        out = _call('products.ai_written', {'slug': p.slug}).output
        self.assertEqual(out['ai_written'], {'description': "The product editor's AI writer"})


class EditorCardTests(TestCase):
    """The merchant sees each mark in the product editor and clears it there."""

    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='ai-marks', email='ai-marks@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.product = _product(description='<p>A brass lantern.</p>')
        self.url = reverse('admin_dashboard:product_edit', kwargs={'product_id': self.product.id})

    def _form(self) -> dict:
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return browser_form_data(resp.content.decode(), 'product-form')

    def _save(self, data):
        resp = self.client.post(self.url, data, headers=_AJAX)
        self.assertEqual(resp.status_code, 200, resp.content[:500])

    def test_the_card_lists_every_field_with_its_mark(self):
        _mark(self.product, 'description')
        data = self._form()
        self.assertEqual(data.get('ai_text_submitted'), ['1'])
        self.assertEqual(data.get('ai_written_description'), ['1'])
        self.assertNotIn('ai_written_short_description', data)
        body = self.client.get(self.url).content.decode()
        for field in ('description', 'short_description', 'meta_title', 'meta_description'):
            self.assertIn(f'name="ai_written_{field}"', body)

    def test_an_unchanged_save_keeps_the_marks(self):
        _mark(self.product, 'description')
        self._save(self._form())
        self.assertEqual(marks_for(self.product), {'description': 'linda'})

    def test_unticking_a_box_clears_its_mark(self):
        _mark(self.product, 'description')
        data = self._form()
        data.pop('ai_written_description')
        self._save(data)
        self.assertEqual(marks_for(self.product), {})

    def test_ticking_a_box_marks_the_field_as_the_editors(self):
        data = self._form()
        data['ai_written_short_description'] = ['1']
        self._save(data)
        self.assertEqual(marks_for(self.product), {'short_description': 'editor'})

    def test_the_editor_announces_ai_text_and_the_card_ticks_its_own_box(self):
        # The product editor belongs to admin_dashboard: it says an AI wrote the
        # description and names nothing of this app's; the card does the ticking.
        from pathlib import Path

        import plugins.installed.admin_dashboard as dashboard

        editor = (
            Path(dashboard.__file__).parent / 'templates/admin_dashboard/product_form.html'
        ).read_text()
        self.assertNotIn('ai_written_', editor)
        self.assertEqual(editor.count("'morph:ai-text-written'"), 2)  # Draft and Rewrite
        body = self.client.get(self.url).content.decode()
        self.assertIn("document.addEventListener('morph:ai-text-written'", body)

    def test_a_save_without_the_card_changes_no_mark(self):
        # Every unticked box is absent from a POST, so without the card's marker a
        # save from anywhere else would read as "untick everything".
        _mark(self.product, 'description')
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=QueryDict(''), files=None
        )
        self.assertEqual(marks_for(self.product), {'description': 'linda'})


class ProductPageTests(TestCase):
    def setUp(self):
        cache.clear()

    def _block(self, product) -> str:
        return render_to_string(
            'ai_content/blocks/ai_text_mark.html', {'product': {'id': str(product.pk)}}
        )

    def test_a_marked_description_is_marked_on_the_page(self):
        p = _product(description='<p>A brass lantern.</p>')
        _mark(p, 'description')
        out = self._block(p)
        self.assertIn('data-ai-generated="description"', out)
        self.assertNotIn(LABEL, out)  # the sentence is the merchant's choice

    def test_the_merchant_can_say_it_in_words(self):
        p = _product(description='<p>A brass lantern.</p>')
        _mark(p, 'description')
        plugin = app_registry.get('ai_content')
        plugin.set_config('label_ai_text', True)
        self.addCleanup(plugin.set_config, 'label_ai_text', False)
        self.assertIn(LABEL, self._block(p))

    def test_unmarked_text_is_not_marked(self):
        p = _product(description='<p>A brass lantern.</p>')
        _mark(p, 'meta_description')  # not text the page shows
        self.assertEqual(self._block(p).strip(), '')

    def test_a_mark_on_emptied_text_says_nothing(self):
        # The merchant cleared the description and kept the box: no text, no claim.
        for empty in ('', '<p></p>', '<p> &nbsp; </p>'):
            with self.subTest(text=empty):
                Product.objects.filter(slug='lantern').delete()
                p = _product(description=empty)
                _mark(p, 'description')
                self.assertEqual(self._block(p).strip(), '')

    def test_a_booking_page_with_empty_product_text_says_nothing(self):
        # A booking page passes the model and shows the host's own text when the
        # product has none; the mark must not land on that text.
        p = _product(description='', short_description='<p>A night walk.</p>')
        _mark(p, 'description')
        out = render_to_string('ai_content/blocks/ai_text_mark.html', {'product': p})
        self.assertEqual(out.strip(), '')
        _mark(p, 'short_description')
        out = render_to_string('ai_content/blocks/ai_text_mark.html', {'product': p})
        self.assertIn('data-ai-generated="short_description"', out)

    def test_the_product_page_carries_both_marks(self):
        p = _product(description='<p>A brass lantern.</p>')
        _mark(p, 'description')
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertIn('data-ai-generated="description"', body)
        self.assertIn(GENERATED, body)

    def test_an_unmarked_product_page_carries_neither(self):
        p = _product(description='<p>A brass lantern.</p>')
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)


class StructuredDataTests(TestCase):
    def test_a_marked_description_is_a_generated_creative_work_about_the_product(self):
        p = _product(description='<p>A <b>brass</b> lantern.</p>')
        _mark(p, 'description')
        graph = _graph(p)
        product = _nodes(graph, 'Product')[0]
        works = _nodes(graph, 'CreativeWork')
        self.assertEqual(len(works), 1)
        work = works[0]
        self.assertEqual(work['digitalSourceType'], GENERATED)
        self.assertEqual(work['text'], 'A brass lantern.')
        self.assertEqual(work['about'], {'@id': product['@id']})
        self.assertEqual(product['subjectOf'], {'@id': work['@id']})
        # digitalSourceType is a CreativeWork property: the Product never carries it.
        self.assertNotIn('digitalSourceType', product)
        self.assertNotIn('creditText', product)

    def test_unmarked_text_adds_nothing_to_the_graph(self):
        p = _product(description='<p>A brass lantern.</p>')
        graph = _graph(p)
        self.assertEqual(_nodes(graph, 'CreativeWork'), [])
        self.assertNotIn('subjectOf', _nodes(graph, 'Product')[0])

    def test_a_mark_on_empty_text_claims_nothing(self):
        p = _product(description='')
        _mark(p, 'description')
        self.assertEqual(_nodes(_graph(p), 'CreativeWork'), [])


class DisabledTests(TestCase):
    """With the app off nothing is recorded and nothing is published."""

    def setUp(self):
        cache.clear()
        app_registry.deactivate('ai_content')
        self.addCleanup(cache.clear)
        self.addCleanup(app_registry.activate, 'ai_content')

    def test_nothing_is_recorded(self):
        p = _product()
        _call(
            'catalog.update_product',
            {'slug': p.slug, 'description': '<p>A brass lantern.</p>'},
            context={'source': 'linda'},
        )
        self.assertFalse(Metafield.objects.filter(namespace=NAMESPACE).exists())

    def test_nothing_is_published(self):
        p = _product(description='<p>A brass lantern.</p>')
        _mark(p, 'description')
        body = self.client.get(f'/products/{p.slug}/').content.decode()
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)


class ReportTests(TestCase):
    def test_the_ai_act_report_lists_the_marks_in_its_window(self):
        from plugins.installed.agent_core.compliance import build_ai_act_report

        p = _product()
        _mark(p, 'description', 'linda')
        _mark(p, 'meta_description', 'bulk')
        Metafield.objects.filter(key='meta_description').update(
            updated_at=timezone.now() - timedelta(days=40)
        )
        report = build_ai_act_report(since=timezone.now() - timedelta(days=30))
        self.assertEqual([r['field'] for r in report['ai_text']], ['description'])
        self.assertEqual(report['summary']['total_ai_text'], 1)
        self.assertEqual(report['summary']['ai_text_by_source'], {'linda': 1})

    def test_the_csv_export_carries_the_marks(self):
        from io import StringIO

        from django.core.management import call_command

        p = _product()
        _mark(p, 'description', 'worker')
        out = StringIO()
        call_command('export_ai_act_report', '--days', '7', stdout=out, stderr=StringIO())
        self.assertIn(f'catalog.product:{p.pk}.description', out.getvalue())
