"""apikey.fun provider — registered, OpenAI-compatible, correct base URL."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from plugins.installed.ai_assistant.services.config import ProviderConfig


class ApikeyFunProviderTests(TestCase):
    def test_registered_and_openai_compatible(self):
        from plugins.installed.ai_assistant.services.llm import (
            _GATEWAYS,
            ApikeyFunGateway,
            OpenAIGateway,
        )

        self.assertIs(_GATEWAYS['apikey'], ApikeyFunGateway)
        self.assertTrue(issubclass(ApikeyFunGateway, OpenAIGateway))

    @patch('plugins.installed.ai_assistant.services.llm._openai_client')
    def test_defaults_to_apikey_base_url(self, mock_client):
        from plugins.installed.ai_assistant.services.llm import ApikeyFunGateway

        ApikeyFunGateway(
            ProviderConfig(provider='apikey', api_key='k', base_url='', model='', embedding_model='')
        )
        _, kwargs = mock_client.call_args
        self.assertEqual(kwargs.get('base_url'), 'https://api.apikey.fun/v1')
        self.assertEqual(kwargs.get('api_key'), 'k')
