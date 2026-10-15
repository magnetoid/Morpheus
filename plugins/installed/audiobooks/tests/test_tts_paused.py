"""With AI switched off, no ElevenLabs call is made."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.agents.guardrails import PAUSED_MESSAGE, AIPaused
from plugins.installed.audiobooks.services import _tts


class TtsPausedTests(TestCase):
    def test_no_request_while_paused(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)
        with patch('requests.post') as post, self.assertRaises(AIPaused) as cm:
            _tts('hello', api_key='k', voice_id='v', model='m')
        post.assert_not_called()
        self.assertEqual(str(cm.exception), PAUSED_MESSAGE)
