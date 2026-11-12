"""AI drafts: the guarded provider, nothing written on a refusal, reviewed text kept."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.agents.llm import LLMResponse, MockLLMProvider
from core.i18n.models import Translation
from core.i18n.services import set_translation, spec_by_key
from plugins.installed.localization import drafting

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


def _product():
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name='Harbour Map',
        slug='harbour-map',
        sku='HM-1',
        price=Money(Decimal('9.00'), 'EUR'),
        status='active',
        description='<p>Every quay, drawn.</p>',
    )


def _set(**kw):
    from plugins.registry import app_registry

    plugin = app_registry.get('agent_core')
    for key, value in kw.items():
        plugin.set_config(key, value)


@override_settings(**BILINGUAL)
class DraftingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.product = _product()
        self.spec = spec_by_key('catalog.product')
        self.addCleanup(_set, agents_paused=False)

    def test_one_call_json_in_and_out_sanitised(self):
        provider = MockLLMProvider(
            [
                LLMResponse(
                    text='Here: '
                    + json.dumps({'name': 'Mapa', 'description': '<p>Gat</p><script>x</script>'})
                )
            ]
        )
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            result = drafting.run_drafts('catalog.product', 'sr', [str(self.product.pk)])
        self.assertEqual(result['drafted'], 1)
        self.assertEqual(len(provider.calls), 1)
        sent = provider.calls[0]['messages']
        self.assertIn('Latin script', sent[0].content)
        self.assertIn('HTML', sent[0].content)
        self.assertEqual(
            json.loads(sent[1].content),
            {'name': 'Harbour Map', 'description': '<p>Every quay, drawn.</p>'},
        )
        description = Translation.objects.get(field='description')
        self.assertNotIn('<script', description.value)
        self.assertFalse(description.reviewed)
        self.assertTrue(description.is_machine_translated)
        self.assertEqual(drafting.last_run('catalog.product', 'sr')['state'], 'done')

    def test_switched_off_ai_writes_nothing_and_says_why(self):
        _set(agents_paused=True)
        provider = MockLLMProvider([LLMResponse(text=json.dumps({'name': 'Mapa'}))])
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            result = drafting.run_drafts('catalog.product', 'sr', [str(self.product.pk)])
        self.assertEqual(result['drafted'], 0)
        self.assertEqual(provider.calls, [])
        self.assertFalse(Translation.objects.exists())
        status = drafting.last_run('catalog.product', 'sr')
        self.assertEqual(status['state'], 'stopped')
        self.assertTrue(status['message'])

    def test_a_provider_error_writes_nothing(self):
        class Broken(MockLLMProvider):
            def respond(self, **kwargs):
                raise RuntimeError('boom')

        with patch('core.agents.llm.get_llm_provider', return_value=Broken()):
            drafting.run_drafts('catalog.product', 'sr', [str(self.product.pk)])
        self.assertFalse(Translation.objects.exists())
        self.assertIn('did not answer', drafting.last_run('catalog.product', 'sr')['message'])

    def test_a_draft_never_replaces_a_reviewed_translation(self):
        set_translation(self.product, 'name', 'sr', 'Lučka mapa')
        provider = MockLLMProvider(
            [LLMResponse(text=json.dumps({'name': 'Drugo', 'description': '<p>Gat.</p>'}))]
        )
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            drafting.run_drafts('catalog.product', 'sr', [str(self.product.pk)])
        # Only the field with no reviewed text was sent, and the reviewed one stands.
        self.assertEqual(
            json.loads(provider.calls[0]['messages'][1].content),
            {'description': '<p>Every quay, drawn.</p>'},
        )
        name = Translation.objects.get(field='name')
        self.assertEqual(name.value, 'Lučka mapa')
        self.assertTrue(name.reviewed)

    def test_the_task_is_registered_under_its_name(self):
        from morph.celery import app
        from plugins.installed.localization import tasks  # noqa: F401

        self.assertIn('localization.draft_translations', app.tasks)
