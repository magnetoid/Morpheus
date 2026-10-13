"""Every completion through the app's provider gateway obeys the agent guardrails.

The kill switch and the daily spend cap stopped the Worker and Linda but not the
gateway the dashboard's AI buttons, the Pulse rewrite, classification and store
bootstrap use: switching AI off left them all running, and their tokens were
invisible to the cap. Each gateway's ``complete`` now checks both first, and the
app reports its usage to the cap (core's ``AI_USAGE_TODAY`` filter).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.agents import guardrails
from plugins.installed.ai_assistant.models import AIInteraction
from plugins.installed.ai_assistant.services.config import ProviderConfig
from plugins.installed.ai_assistant.services.llm import AIPaused, OpenAIGateway


def _set(**kw):
    from plugins.registry import app_registry

    plugin = app_registry.get('agent_core')
    for k, v in kw.items():
        plugin.set_config(k, v)


def _gateway():
    with patch('core.agents.llm._openai_client', return_value=MagicMock()):
        gw = OpenAIGateway(
            ProviderConfig(
                provider='openai', api_key='k', base_url='', model='gpt-4o', embedding_model=''
            )
        )
    gw.client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='copy'), finish_reason='stop')],
        usage=SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, completion_tokens_details=None
        ),
    )
    return gw


class GuardedGatewayTests(TestCase):
    def setUp(self):
        self.addCleanup(_set, agents_paused=False, spend_cap_daily=0)

    def test_switched_off_ai_makes_no_call(self):
        _set(agents_paused=True)
        gw = _gateway()
        with self.assertRaises(AIPaused):
            gw.complete('write copy')
        gw.client.chat.completions.create.assert_not_called()

    def test_a_reached_spend_cap_makes_no_call(self):
        _set(spend_cap_daily=0.01)
        AIInteraction.objects.create(
            interaction_type='completion',
            model_used='gpt-4o',
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        gw = _gateway()
        with self.assertRaises(AIPaused):
            gw.complete('write copy')
        gw.client.chat.completions.create.assert_not_called()

    def test_within_the_limits_the_call_goes_through(self):
        self.assertEqual(_gateway().complete('write copy'), 'copy')

    def test_the_apps_calls_count_toward_the_cap(self):
        before = guardrails.daily_spend_usd()
        AIInteraction.objects.create(
            interaction_type='completion',
            model_used='gpt-4o',
            prompt_tokens=1_000_000,
            completion_tokens=0,
        )
        self.assertGreater(guardrails.daily_spend_usd(), before)

    def test_the_dashboard_buttons_say_ai_is_paused(self):
        from plugins.installed.admin_dashboard.views_split._shared import call_llm

        _set(agents_paused=True)
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=_gateway()):
            text, error = call_llm('write copy')
        self.assertEqual(text, '')
        self.assertIn('paused', error.lower())
