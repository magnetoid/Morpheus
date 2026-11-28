"""Which shown text began as an AI draft (EU AI Act Art. 50, v0.177.0).

A reviewed translation keeps `is_machine_translated` while its text is the AI's,
and an instance shown in that translation remembers which of its fields those are,
so the page can mark them. A store agent writing a translation always marks it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from core.agents.registry import agent_registry
from core.i18n import services as i18n
from core.i18n.models import Translation

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


def _product(**extra):
    from plugins.installed.catalog.models import Product

    fields = {
        'name': 'Sea Kayak',
        'slug': 'sea-kayak',
        'sku': 'SK-1',
        'status': 'active',
        'price': Money(Decimal('9.00'), 'EUR'),
        'description': '<p>A calm paddle.</p>',
        **extra,
    }
    return Product.objects.create(**fields)


def _call(tool_name: str, args: dict, *, agent=None, context=None):
    return agent_registry.get_tool(tool_name).invoke(args, agent=agent, context=context or {})


@override_settings(**BILINGUAL)
class ShownAiTranslationTests(TestCase):
    def test_an_ai_translation_a_person_approved_is_remembered(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak', machine_translated=True)
        i18n.set_translation(
            product, 'description', 'sr', '<p>Mirno veslanje.</p>', machine_translated=True
        )
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(product.name, 'Morski kajak')
        self.assertEqual(i18n.ai_translated(product), ['name', 'description'])

    def test_a_persons_translation_is_not_marked(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno veslanje.</p>')
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(product.name, 'Morski kajak')
        self.assertEqual(i18n.ai_translated(product), [])

    def test_only_the_ai_fields_are_named(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak')
        i18n.set_translation(
            product, 'description', 'sr', '<p>Mirno veslanje.</p>', machine_translated=True
        )
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(i18n.ai_translated(product), ['description'])

    def test_an_object_not_shown_in_translation_names_nothing(self):
        product = _product()
        # Partial: the page shows the English text, so nothing is the AI's.
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak', machine_translated=True)
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(i18n.ai_translated(product), [])
        # A draft is never shown.
        i18n.set_translation(
            product, 'description', 'sr', '<p>Mirno.</p>', machine_translated=True, reviewed=False
        )
        i18n.overlay_translation(product, 'sr')
        self.assertEqual(i18n.ai_translated(product), [])

    def test_a_save_forgets_the_marks(self):
        product = _product()
        i18n.set_translation(product, 'name', 'sr', 'Morski kajak', machine_translated=True)
        i18n.set_translation(product, 'description', 'sr', '<p>Mirno.</p>', machine_translated=True)
        i18n.overlay_translation(product, 'sr')
        product.save()
        self.assertEqual(product.name, 'Sea Kayak')
        self.assertEqual(i18n.ai_translated(product), [])

    def test_anything_else_names_nothing(self):
        self.assertEqual(i18n.ai_translated(None), [])
        self.assertEqual(i18n.ai_translated({'name': 'x'}), [])
        self.assertEqual(i18n.ai_translated(_product()), [])


@override_settings(**BILINGUAL)
class AgentWrittenTranslationTests(TestCase):
    def _row(self, product, field='name'):
        return Translation.objects.get(object_id=str(product.pk), field=field, language_code='sr')

    def test_linda_writing_a_translation_marks_it(self):
        product = _product()
        _call(
            'i18n.set_translation',
            {
                'content_type': 'catalog.product',
                'object_id': str(product.pk),
                'field': 'name',
                'language_code': 'sr',
                'value': 'Morski kajak',
                'machine_translated': False,
            },
            context={'source': 'linda'},
        )
        row = self._row(product)
        self.assertTrue(row.reviewed)
        self.assertTrue(row.is_machine_translated)

    def test_an_api_token_writing_a_translation_says_what_it_says(self):
        product = _product()
        args = {
            'content_type': 'catalog.product',
            'object_id': str(product.pk),
            'field': 'name',
            'language_code': 'sr',
            'value': 'Morski kajak',
        }
        _call('i18n.set_translation', args)
        self.assertFalse(self._row(product).is_machine_translated)
        _call('i18n.set_translation', {**args, 'machine_translated': True})
        self.assertTrue(self._row(product).is_machine_translated)

    def test_a_worker_translating_a_product_marks_it(self):
        product = _product()
        _call(
            'i18n.translate_product',
            {'slug': product.slug, 'language_code': 'sr', 'name': 'Morski kajak'},
            agent=object(),
        )
        self.assertTrue(self._row(product).is_machine_translated)

    def test_a_token_translating_a_product_marks_nothing(self):
        product = _product()
        _call(
            'i18n.translate_product',
            {'slug': product.slug, 'language_code': 'sr', 'name': 'Morski kajak'},
        )
        self.assertFalse(self._row(product).is_machine_translated)


@override_settings(**BILINGUAL)
class TranslationNobodySeesTests(TestCase):
    """A translation its page would never show is refused (v0.200.0)."""

    def test_translating_a_product_into_a_language_the_store_lacks_is_refused(self):
        from core.agents.tools import ToolError
        from core.i18n.models import Translation

        product = _product()
        for language in ('en', 'de'):
            with self.subTest(language=language), self.assertRaises(ToolError):
                _call(
                    'i18n.translate_product',
                    {'slug': product.slug, 'language_code': language, 'name': 'Seekajak'},
                )
        self.assertFalse(Translation.objects.exists())

    def test_an_object_its_owner_leaves_out_takes_no_translation(self):
        from unittest import mock

        from core.i18n import services

        product = _product()
        spec = dict(services.spec_for(product))
        self.assertEqual(services.translation_problem(product, 'name', 'sr'), '')
        spec['applies'] = lambda obj: False
        with mock.patch.object(services, 'spec_for', return_value=spec):
            self.assertIn('never be shown', services.translation_problem(product, 'name', 'sr'))
