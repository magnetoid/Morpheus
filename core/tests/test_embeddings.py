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
