"""The apps' direct model callers stop when AI is switched off, without a 500."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents import guardrails
from core.agents.llm import LLMProvider, LLMResponse
from plugins.installed.catalog.models import Product


class _Probe(LLMProvider):
    name = 'probe'
    model = 'gpt-4o'

    def __init__(self):
        self.calls = 0

    def respond(self, **_kw):
        self.calls += 1
        return LLMResponse(text='[]', model='gpt-4o')


class AppCallersPausedTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)
        self.probe = _Probe()
        patcher = patch('core.agents.llm.get_llm_provider', return_value=self.probe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_description_fill_says_ai_is_paused(self):
        staff = get_user_model().objects.create_user(
            username='fill', email='f@x.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        p = Product.objects.create(name='Fill', slug='fill-paused', sku='FP', price=Money(1, 'USD'))
        resp = self.client.post(f'/dashboard/products/{p.pk}/content-fill/')
        self.assertEqual(resp.json(), {'ok': False, 'error': guardrails.PAUSED_MESSAGE})
        self.assertEqual(self.probe.calls, 0)

    def test_the_morning_briefing_reports_the_refusal(self):
        from plugins.installed.morpheus_brain.services import generate_briefing

        out = generate_briefing()
        self.assertIn('paused', out.get('error', ''))
        self.assertEqual(self.probe.calls, 0)

    def test_autopilot_keeps_its_templates(self):
        from plugins.installed.dynamics.autopilot import _enrich_with_llm

        drafts = [{'title': 'Keep me', 'rationale': 'because'}]
        _enrich_with_llm(drafts)
        self.assertEqual(drafts[0]['title'], 'Keep me')
        self.assertEqual(self.probe.calls, 0)

    def test_the_draft_tool_returns_an_error_to_the_agent(self):
        from core.agents.tools import ToolError
        from plugins.installed.agent_core.tools import content

        Product.objects.create(name='Draft', slug='draft-paused', sku='DP', price=Money(1, 'USD'))
        with (
            patch.object(content, 'get_llm_provider', return_value=self.probe),
            self.assertRaises(ToolError) as cm,
        ):
            content.draft_product_description_tool.invoke({'slug': 'draft-paused'})
        self.assertIn('paused', str(cm.exception))
