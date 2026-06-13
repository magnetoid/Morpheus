"""Packy provider wired via the Anthropic-compatible Messages API."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from plugins.installed.ai_assistant.services.config import ProviderConfig


class PackyAnthropicTests(TestCase):
    @patch('anthropic.Anthropic')
    def test_packy_uses_anthropic_with_stripped_base_url(self, mock_anthropic):
        from plugins.installed.ai_assistant.services.llm import AnthropicGateway, PackyGateway

        cfg = ProviderConfig(
            provider='packy',
            api_key='k',
            base_url='https://www.packyapi.com/v1',
            model='claude-3-5-sonnet-20241022',
            embedding_model='',
        )
        g = PackyGateway(cfg)
        self.assertIsInstance(g, AnthropicGateway)  # Anthropic path, not OpenAI
        _, kwargs = mock_anthropic.call_args
        self.assertEqual(kwargs.get('api_key'), 'k')
        self.assertEqual(kwargs.get('base_url'), 'https://www.packyapi.com')  # /v1 stripped
        self.assertEqual(g.model, 'claude-3-5-sonnet-20241022')

    @patch('anthropic.Anthropic')
    def test_anthropic_default_omits_base_url(self, mock_anthropic):
        from plugins.installed.ai_assistant.services.llm import AnthropicGateway

        cfg = ProviderConfig(
            provider='anthropic',
            api_key='k',
            base_url='https://api.anthropic.com/v1',
            model='',
            embedding_model='',
        )
        AnthropicGateway(cfg)
        _, kwargs = mock_anthropic.call_args
        self.assertNotIn('base_url', kwargs)  # the public default is never passed
