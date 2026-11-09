"""With AI switched off, no narration service is called."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.agents.guardrails import PAUSED_MESSAGE, AIPaused
from plugins.installed.audiobooks.narrators import ElevenLabsNarrator, QwenNarrator


class TtsPausedTests(TestCase):
    def test_no_request_while_paused(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)
        narrators = (
            ElevenLabsNarrator(api_key='k', voice='v', model='m'),
            QwenNarrator(api_key='k', base_url='', voice='Jennifer', model='qwen3-tts-flash'),
        )
        for narrator in narrators:
            with patch('requests.post') as post, self.assertRaises(AIPaused) as cm:
                narrator.narrate('hello')
            post.assert_not_called()
            self.assertEqual(str(cm.exception), PAUSED_MESSAGE)
