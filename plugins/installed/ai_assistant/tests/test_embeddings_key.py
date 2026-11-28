"""The store's OpenAI key is used for embeddings only when the merchant says so.

Core's embeddings (Linda's shop memory, the knowledge base) ask
``EMBEDDINGS_API_KEY``; this app answers with the key saved under Settings → AI
while ``embeddings_use_store_key`` is on. Off, the default, nothing changes for
a store: the switch starts paid requests.
"""

from __future__ import annotations

from django.test import TestCase

from core.embeddings import _api_key
from plugins.registry import app_registry
from plugins.testing import set_app_settings


class StoreKeyForEmbeddingsTests(TestCase):
    def test_off_the_stores_key_is_not_used(self):
        set_app_settings(self, 'ai_assistant', openai_api_key='sk-' + 'store')
        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY=''):
            self.assertEqual(_api_key(), '')

    def test_on_the_stores_key_is_used(self):
        set_app_settings(
            self, 'ai_assistant', openai_api_key='sk-' + 'store', embeddings_use_store_key=True
        )
        with self.settings(AI_PROVIDER='deepseek', OPENAI_API_KEY=''):
            self.assertEqual(_api_key(), 'sk-store')

    def test_on_without_a_saved_key_the_environments_stays(self):
        set_app_settings(self, 'ai_assistant', openai_api_key='', embeddings_use_store_key=True)
        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            self.assertEqual(_api_key(), 'sk-env')

    def test_an_agent_cannot_switch_it_on(self):
        from plugins import config_schema

        key = 'embeddings_use_store_key'
        prop = app_registry.get('ai_assistant').get_config_schema()['properties'][key]
        self.assertFalse(config_schema.agent_writable(key, prop))
