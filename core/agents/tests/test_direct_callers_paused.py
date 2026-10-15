"""Core's direct model callers stop when AI is switched off, without a 500.

Each used to reach the provider with the switch off. They now meet the
provider guard (test_provider_guard) and each turns the refusal into its own
quiet failure; page help shows the merchant the reason.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import LLMProvider, LLMResponse


class _Probe(LLMProvider):
    name = 'probe'
    model = 'gpt-4o'

    def __init__(self):
        self.calls = 0

    def respond(self, **_kw):
        self.calls += 1
        return LLMResponse(text='{}', model='gpt-4o')


def _pause():
    from plugins.registry import app_registry

    p = app_registry.get('agent_core')
    p.set_config('agents_paused', True)
    return p


class CoreCallersPausedTests(TestCase):
    def setUp(self):
        p = _pause()
        self.addCleanup(p.set_config, 'agents_paused', False)
        self.probe = _Probe()
        patcher = patch('core.agents.llm.get_llm_provider', return_value=self.probe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_page_help_names_the_reason(self):
        from core.assistant.page_help import build_page_help

        out = build_page_help({'page_text': 'x' * 400}, provider=self.probe)
        self.assertFalse(out['ok'])
        self.assertEqual(out['message'], guardrails.PAUSED_MESSAGE)
        self.assertEqual(self.probe.calls, 0)

    def test_the_brain_analyst_reports_the_refusal(self):
        from core.brain.analyst import analyze

        out = analyze(signals={})
        self.assertIn('paused', out.get('error', ''))
        self.assertEqual(self.probe.calls, 0)

    def test_self_improvement_falls_back_without_calling(self):
        from core.self_improvement.verify import verify_recommendation

        result = verify_recommendation({'title': 't'})
        self.assertIsNotNone(result)
        self.assertEqual(self.probe.calls, 0)
