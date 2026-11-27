"""The Gemini gateway and the settings probe send the key in a header, never the URL
(an HTTPError quotes the URL, and the error text is stored and shown)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

# Built from two parts: written whole, a secret scanner reports it as a live key.
FAKE_KEY = 'AIza' + 'FAKE-test-key-0123456789abcdefghijk'


class GeminiKeyHeaderTests(TestCase):
    def _gateway(self):
        from plugins.installed.ai_assistant.services.llm import GeminiGateway

        return GeminiGateway(SimpleNamespace(api_key=FAKE_KEY, base_url='', model=''))

    def _assert_header_only(self, post):
        url = post.call_args.args[0]
        self.assertNotIn(FAKE_KEY, url)
        self.assertNotIn('key=', url)
        self.assertEqual(post.call_args.kwargs['headers'], {'x-goog-api-key': FAKE_KEY})

    def test_complete(self):
        reply = MagicMock()
        reply.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        with patch(
            'plugins.installed.ai_assistant.services.llm.requests.post', return_value=reply
        ) as post:
            self._gateway().complete('hello')
        self._assert_header_only(post)

    def test_embed(self):
        reply = MagicMock()
        reply.json.return_value = {'embedding': {'values': [0.1]}}
        with patch(
            'plugins.installed.ai_assistant.services.llm.requests.post', return_value=reply
        ) as post:
            self._gateway().embed('hello')
        self._assert_header_only(post)

    def test_probe(self):
        from plugins.installed.ai_assistant.services import probe as probes

        with patch.object(probes, '_http_get', return_value={'models': []}) as get:
            probes.probe_gemini(api_key=FAKE_KEY)
        url = get.call_args.args[0]
        self.assertNotIn(FAKE_KEY, url)
        self.assertNotIn('key=', url)
        self.assertEqual(get.call_args.kwargs['headers'], {'x-goog-api-key': FAKE_KEY})
