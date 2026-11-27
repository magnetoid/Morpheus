"""A provider's key never reaches an error message.

Gemini took its key in the URL (`?key=`), `requests` quotes the URL in every
HTTPError, and the runtime passed an unrecognised error through as
"AI provider error: …", so the key landed in `AgentRun.error`, API answers and
the agent's own context.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

# Built from two parts: written whole, a secret scanner reports it as a live key.
FAKE_KEY = 'AIza' + 'FAKE-test-key-0123456789abcdefghijk'


class GeminiKeyHeaderTests(SimpleTestCase):
    def test_the_key_goes_in_a_header_never_the_url(self):
        from core.agents.llm import GeminiProvider, LLMMessage
        from core.agents.provider_registry import ProviderConfig

        cfg = ProviderConfig(
            provider='gemini', api_key=FAKE_KEY, base_url='', model='', embedding_model=''
        )
        with patch('core.agents.provider_registry.get_provider_config', return_value=cfg):
            provider = GeminiProvider()
        reply = MagicMock()
        reply.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        with patch('requests.post', return_value=reply) as post:
            provider.respond(messages=[LLMMessage(role='user', content=uuid.uuid4().hex)])
        url = post.call_args.args[0]
        self.assertNotIn(FAKE_KEY, url)
        self.assertNotIn('key=', url)
        self.assertEqual(post.call_args.kwargs['headers'], {'x-goog-api-key': FAKE_KEY})


class HumaniseProviderErrorTests(SimpleTestCase):
    def _humanise(self, text):
        from core.agents.runtime import _humanise_provider_error

        return _humanise_provider_error(RuntimeError(text))

    def test_a_key_in_the_query_string_is_removed(self):
        for name in ('key', 'api_key', 'token'):
            out = self._humanise(
                f'400 Client Error: Bad Request for url: '
                f'https://example.test/v1/models/m:generateContent?{name}=s3cr3tvalue123&alt=json'
            )
            self.assertNotIn('s3cr3tvalue123', out, name)
            self.assertIn('example.test', out)

    def test_anything_shaped_like_a_provider_key_is_removed(self):
        for key in (FAKE_KEY, 'sk-ant-FAKE0123456789abcdefghij', 'xai-FAKE0123456789abcdefghij'):
            out = self._humanise(f'upstream said: bad credentials {key} (code 7)')
            self.assertNotIn(key, out)
            self.assertIn('bad credentials', out)

    def test_a_plain_error_is_unchanged(self):
        self.assertEqual(
            self._humanise('the model returned malformed JSON'),
            'AI provider error: the model returned malformed JSON',
        )
