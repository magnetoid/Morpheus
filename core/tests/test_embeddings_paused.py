"""With AI switched off, embeddings use the hash fallback instead of OpenAI."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from core import embeddings


class EmbeddingsPausedTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        p = app_registry.get('agent_core')
        p.set_config('agents_paused', True)
        self.addCleanup(p.set_config, 'agents_paused', False)

    @override_settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-test')
    def test_no_openai_call_and_the_hash_vector_comes_back(self):
        with patch('openai.OpenAI') as client:
            vec = embeddings.embed('kayak kotor')
        client.assert_not_called()
        self.assertEqual(vec, embeddings._hash_embedding('kayak kotor'))
