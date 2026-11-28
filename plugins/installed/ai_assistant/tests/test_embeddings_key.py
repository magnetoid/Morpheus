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

    def test_a_switch_turned_off_in_another_process_stops_this_one(self):
        # Each web and Celery worker keeps its own copy of the settings. The
        # dashboard's worker saved "off"; this one must not go on making paid
        # requests with the key it read earlier.
        from plugins.models import PluginConfig

        set_app_settings(
            self, 'ai_assistant', openai_api_key='sk-' + 'store', embeddings_use_store_key=True
        )
        plugin = app_registry.get('ai_assistant')
        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY=''):
            self.assertEqual(_api_key(), 'sk-store')

            row = PluginConfig.objects.get(plugin_name='ai_assistant')
            row.config = {**row.config, 'embeddings_use_store_key': False}
            row.save(update_fields=['config'])  # the other process's save
            self.assertTrue(plugin.get_config_value('embeddings_use_store_key'))  # stale copy

            plugin._config_read_at -= 60  # the copy is now older than the window
            self.assertEqual(_api_key(), '')
