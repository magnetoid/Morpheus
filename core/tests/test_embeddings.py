"""Embedding service contract — fixed dimension in, safe similarity out.

The module promises a fixed-dimension vector regardless of backend. These
guard the two places that promise used to leak: an OpenAI vector of the wrong
size, and `cosine_similarity` silently comparing mismatched-length vectors.
"""

from __future__ import annotations

from django.test import TestCase

from core.embeddings import EMBEDDING_DIM, cosine_similarity, embed


class EmbedFallbackTests(TestCase):
    def test_hash_fallback_is_fixed_dimension(self):
        # No provider configured in tests → deterministic hash embedding.
        vec = embed('hello world')
        self.assertEqual(len(vec), EMBEDDING_DIM)

    def test_empty_text_is_zero_vector_of_fixed_dimension(self):
        vec = embed('')
        self.assertEqual(len(vec), EMBEDDING_DIM)
        self.assertEqual(set(vec), {0.0})

    def test_hash_embedding_is_deterministic(self):
        self.assertEqual(embed('same text'), embed('same text'))


class CosineSimilarityTests(TestCase):
    def test_identical_vectors_score_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=6)

    def test_mismatched_length_vectors_score_zero(self):
        # Regression: a 384-dim stored vector vs a 1536-dim query vector must
        # not produce a silently garbage score — different lengths → 0.0.
        self.assertEqual(cosine_similarity([1.0] * 384, [1.0] * 1536), 0.0)

    def test_zero_vector_scores_zero(self):
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)


class _FakeOpenAI:
    """Stands in for the SDK client: answers with one vector, or raises."""

    vector: list[float] | None = None
    keys: list[str] = []

    def __init__(self, api_key='', **_kw):
        type(self).keys.append(api_key)
        self.embeddings = self

    def create(self, **_kw):
        from types import SimpleNamespace

        if type(self).vector is None:
            raise RuntimeError('provider is down')
        return SimpleNamespace(data=[SimpleNamespace(embedding=type(self).vector)])


class ComparableVectorTests(TestCase):
    """A store with an embeddings provider keeps only the provider's vectors
    (v0.200.0). When the provider could not answer, the hash vector was stored
    in its place, and that row then matched nothing by meaning, for good."""

    def setUp(self):
        from unittest import mock

        _FakeOpenAI.vector = None
        _FakeOpenAI.keys = []
        patcher = mock.patch('openai.OpenAI', _FakeOpenAI)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_with_no_provider_the_hash_vector_is_kept(self):
        from core.embeddings import _hash_embedding, embed_comparable

        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY=''):
            self.assertEqual(embed_comparable('kayak'), _hash_embedding('kayak'))
        self.assertEqual(_FakeOpenAI.keys, [])

    def test_a_provider_that_is_down_gives_no_vector_to_keep(self):
        from core.embeddings import _hash_embedding, embed_comparable

        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            self.assertIsNone(embed_comparable('kayak'))
            # `embed` still answers with something, for callers that only compare.
            self.assertEqual(embed('kayak'), _hash_embedding('kayak'))

    def test_a_provider_that_answers_gives_its_vector(self):
        from core.embeddings import embed_comparable

        _FakeOpenAI.vector = [0.5] * EMBEDDING_DIM
        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            self.assertEqual(embed_comparable('kayak'), [0.5] * EMBEDDING_DIM)

    def test_a_note_saved_while_the_provider_is_down_keeps_no_vector(self):
        from core.assistant.models import LindaMemory
        from core.assistant.tools.memory import memory_recall_tool, memory_remember_tool

        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            memory_remember_tool.handler(key='ships', value='we ship from Berlin')
            self.assertEqual(LindaMemory.objects.get(key='ships').embedding, [])
            # Recall still finds it by its words.
            found = memory_recall_tool.handler(query='berlin').output
        self.assertEqual([m['key'] for m in found['memories']], ['ships'])


class EmbeddingsKeyTests(TestCase):
    """Which key embeddings are made with. The store's own key was looked up
    through a registry method that does not exist, so it was never used."""

    def setUp(self):
        from core.hooks import MorpheusEvents, hook_registry

        self.event = MorpheusEvents.EMBEDDINGS_API_KEY
        before = list(hook_registry._handlers.get(self.event, []))
        self.addCleanup(hook_registry._handlers.__setitem__, self.event, before)
        # Only this test's subscribers answer.
        hook_registry._handlers[self.event] = []

    def test_the_environments_key_while_the_environment_names_openai(self):
        from core.embeddings import _api_key

        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            self.assertEqual(_api_key(), 'sk-env')
        with self.settings(AI_PROVIDER='deepseek', OPENAI_API_KEY='sk-' + 'env'):
            self.assertEqual(_api_key(), '')

    def test_an_app_can_answer_with_the_stores_key(self):
        from core.embeddings import _api_key
        from core.hooks import hook_registry

        hook_registry.register(self.event, lambda value, **_: 'sk-' + 'store')
        with self.settings(AI_PROVIDER='deepseek', OPENAI_API_KEY=''):
            self.assertEqual(_api_key(), 'sk-store')

    def test_an_answer_that_is_no_text_is_ignored(self):
        from core.embeddings import _api_key
        from core.hooks import hook_registry

        hook_registry.register(self.event, lambda value, **_: None)
        with self.settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-' + 'env'):
            self.assertEqual(_api_key(), 'sk-env')
