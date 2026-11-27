"""The content audit's fill never saves an outage or setup message as product copy.

The breaker, the fallback router and the unconfigured provider answer with text,
not an exception, so "Fill all" during an outage, or on a store with no AI key,
saved "[Upstream AI provider is degraded — circuit open. …]" or "No AI provider
selected…" as the short description and the description of every product.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents.llm import (
    DEGRADED_SENTINEL_ALL,
    DEGRADED_SENTINEL_CIRCUIT,
    LLMProvider,
    LLMResponse,
    _make_unconfigured_mock,
)
from plugins.installed.catalog.models import Product


class _Replies(LLMProvider):
    name = 'replies'
    model = 'gpt-4o'

    def __init__(self, *texts):
        self.texts = list(texts)

    def respond(self, **_kw):
        return LLMResponse(text=self.texts.pop(0), model='gpt-4o')


class ContentFillOutageTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='filler', email='filler@x.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.product = Product.objects.create(
            name='Outage', slug='outage-fill', sku='OF', price=Money(1, 'USD')
        )

    def _fill(self, provider):
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            return self.client.post(f'/dashboard/products/{self.product.pk}/content-fill/')

    def _assert_nothing_saved(self, resp):
        self.assertFalse(resp.json()['ok'])
        self.assertTrue(resp.json()['error'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.short_description, '')
        self.assertEqual(self.product.description, '')

    def test_an_open_circuit_saves_nothing(self):
        outage = f'{DEGRADED_SENTINEL_CIRCUIT} — circuit open. retry in 30s]'
        self._assert_nothing_saved(self._fill(_Replies(outage, outage, outage)))

    def test_every_provider_failing_saves_nothing(self):
        outage = f'{DEGRADED_SENTINEL_ALL}. Last error: openai: boom]'
        self._assert_nothing_saved(self._fill(_Replies(outage, outage, outage)))

    def test_no_ai_provider_saves_nothing(self):
        provider = _make_unconfigured_mock('No AI provider selected. Open Settings.')
        self._assert_nothing_saved(self._fill(provider))

    def test_a_real_answer_is_still_saved(self):
        resp = self._fill(_Replies('A short line.', 'A longer description.'))
        self.assertEqual(resp.json()['updated'], ['short_description', 'description'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.short_description, 'A short line.')
        self.assertEqual(self.product.description, 'A longer description.')

    def test_copy_the_model_wrote_is_marked(self):
        with patch('core.agents.provenance.mark_ai_written') as mark:
            self._fill(_Replies('A short line.', 'A longer description.'))
        mark.assert_called_once()
        product, fields, source = mark.call_args.args
        self.assertEqual(product.pk, self.product.pk)
        self.assertEqual(fields, ['short_description', 'description'])
        self.assertEqual(source, 'bulk')
