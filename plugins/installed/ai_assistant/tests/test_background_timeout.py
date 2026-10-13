"""A model call made in the background gets a background time limit.

The provider client gives every call 20 seconds, because the dashboard's Generate
buttons wait inside a request and gunicorn kills a worker after 60. The morning
Pulse rewrite runs in Celery, where no request is waiting, and on Irving
(Grok, a reasoning model) it timed out every day at 06:00 (2026-10-09 to 10-12):
the cards kept their rule-written copy and the error log gained one error a day.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from plugins.installed.ai_assistant.services.config import ProviderConfig
from plugins.installed.ai_assistant.services.llm import (
    _REASONING_RETRY_TIMEOUT_SECS,
    OpenAIGateway,
)


def _response(content, finish_reason='stop', reasoning_tokens=0):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
        ],
        usage=SimpleNamespace(
            prompt_tokens=1,
            completion_tokens=reasoning_tokens or 1,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
        ),
    )


def _gateway():
    with patch('core.agents.llm._openai_client', return_value=MagicMock()):
        return OpenAIGateway(
            ProviderConfig(
                provider='grok', api_key='k', base_url='', model='grok-4', embedding_model=''
            )
        )


@patch('plugins.installed.ai_assistant.services.llm.LLMGateway._log', MagicMock())
class BackgroundTimeoutTests(TestCase):
    def test_a_caller_can_give_the_call_a_longer_limit(self):
        gateway = _gateway()
        create = gateway.client.chat.completions.create
        create.side_effect = [_response('ok')]
        gateway.complete('x', timeout=90)
        self.assertEqual(create.call_args.kwargs['timeout'], 90)

    def test_the_reasoning_retry_keeps_the_longer_limit(self):
        gateway = _gateway()
        create = gateway.client.chat.completions.create
        create.side_effect = [_response('', 'length', reasoning_tokens=400), _response('ok')]
        gateway.complete('x', timeout=90)
        self.assertEqual(create.call_args_list[1].kwargs['timeout'], 90)
        self.assertGreater(90, _REASONING_RETRY_TIMEOUT_SECS)

    def test_call_llm_passes_the_limit_to_the_provider(self):
        from plugins.installed.admin_dashboard.views_split._shared import call_llm

        gateway = MagicMock()
        gateway.complete.return_value = 'text'
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            call_llm('x', timeout=90)
        self.assertEqual(gateway.complete.call_args.kwargs['timeout'], 90)

    def test_the_daily_task_asks_for_a_background_limit(self):
        from plugins.installed.ai_assistant import tasks

        with patch(
            'plugins.installed.ai_assistant.services.pulse.generate_pulse_insights', return_value=[]
        ) as gen:
            tasks.pulse_daily_refresh()
        self.assertGreaterEqual(gen.call_args.kwargs['timeout'], 60)

    def test_the_rewrite_passes_the_limit_on(self):
        from plugins.installed.ai_assistant.services import pulse

        with patch(
            'plugins.installed.admin_dashboard.views_split._shared.call_llm', return_value=('', 'x')
        ) as call:
            pulse._humanize_signal({'title': 'Low stock', 'body': 'Restock 3 items'}, timeout=90)
        self.assertEqual(call.call_args.kwargs['timeout'], 90)

    def test_a_refresh_inside_a_request_keeps_the_default(self):
        from plugins.installed.ai_assistant.services import pulse

        with patch(
            'plugins.installed.admin_dashboard.views_split._shared.call_llm', return_value=('', 'x')
        ) as call:
            pulse._humanize_signal({'title': 'Low stock', 'body': 'Restock 3 items'})
        self.assertIsNone(call.call_args.kwargs['timeout'])
