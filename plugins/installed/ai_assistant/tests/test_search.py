"""Tests for the embedding-aware semantic search service."""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.ai_assistant.models import ProductEmbedding
from plugins.installed.ai_assistant.services.embeddings import (
    EMBEDDING_DIM,
    cosine_similarity,
    embed,
)
from plugins.installed.ai_assistant.services.search import (
    hybrid_search,
    semantic_search,
    upsert_product_embedding,
)
from plugins.installed.catalog.models import Product


class EmbeddingTests(TestCase):
    def test_embed_returns_fixed_dim_floats(self):
        v = embed('hello world')
        self.assertEqual(len(v), EMBEDDING_DIM)
        self.assertTrue(all(isinstance(x, float) for x in v))

    def test_embed_is_deterministic(self):
        self.assertEqual(embed('blender'), embed('blender'))

    def test_cosine_self_similarity_is_one(self):
        v = embed('cup')
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=4)


class SemanticSearchTests(TestCase):
    def setUp(self) -> None:
        self.p1 = Product.objects.create(
            name='Pro Blender',
            slug='pro-blender',
            sku='B1',
            short_description='powerful kitchen blender',
            description='professional grade blender for smoothies',
            price=Money(75, 'USD'),
            status='active',
        )
        self.p2 = Product.objects.create(
            name='Toaster',
            slug='toaster',
            sku='T1',
            short_description='2-slice toaster',
            description='wide slot toaster',
            price=Money(25, 'USD'),
            status='active',
        )

    def test_keyword_fallback_when_no_embeddings(self):
        # Products auto-embed via the product.created hook, so clear embeddings
        # to exercise the genuine no-embeddings keyword-fallback path.
        ProductEmbedding.objects.all().delete()
        results, used = semantic_search('blender', limit=5)
        self.assertFalse(used)
        self.assertIn(self.p1, results)
        self.assertNotIn(self.p2, results)

    def test_used_embedding_when_embeddings_present(self):
        upsert_product_embedding(self.p1)
        upsert_product_embedding(self.p2)
        self.assertTrue(ProductEmbedding.objects.exists())
        results, used = semantic_search('smoothie', limit=2)
        self.assertTrue(used)
        # Result list must be non-empty and ranked
        self.assertGreaterEqual(len(results), 1)

    def test_upsert_is_idempotent_on_unchanged_text(self):
        upsert_product_embedding(self.p1)
        first = ProductEmbedding.objects.get(product=self.p1)
        upsert_product_embedding(self.p1)
        second = ProductEmbedding.objects.get(product=self.p1)
        self.assertEqual(first.updated_at, second.updated_at)


class HybridSearchTests(TestCase):
    """Golden queries for BM25 + dense + RRF fusion."""

    def setUp(self) -> None:
        self.blender = Product.objects.create(
            name='Pro Blender',
            slug='pro-blender',
            sku='B1',
            short_description='powerful kitchen blender',
            description='professional grade blender for smoothies',
            price=Money(75, 'USD'),
            status='active',
        )
        self.toaster = Product.objects.create(
            name='Toaster',
            slug='toaster',
            sku='T1',
            short_description='2-slice toaster',
            description='wide slot toaster for bread',
            price=Money(25, 'USD'),
            status='active',
        )
        self.kettle = Product.objects.create(
            name='Kettle',
            slug='kettle',
            sku='K1',
            short_description='1.7L electric kettle',
            description='fast-boil cordless kettle',
            price=Money(40, 'USD'),
            status='active',
        )

    def test_hybrid_falls_back_when_query_empty(self):
        results = hybrid_search('', top_k=5)
        # Empty query → keyword fallback returns a list (may include featured).
        self.assertIsInstance(results, list)

    def test_hybrid_keyword_match_without_embeddings(self):
        # No ProductEmbedding rows → dense pass returns []; BM25 alone (or
        # keyword fallback on sqlite) must still surface the blender.
        results = hybrid_search('blender', top_k=5)
        self.assertIn(self.blender, results)
        self.assertNotIn(self.toaster, results)

    def test_hybrid_dense_pass_surfaces_semantic_match(self):
        upsert_product_embedding(self.blender)
        upsert_product_embedding(self.toaster)
        upsert_product_embedding(self.kettle)
        # "smoothie" appears in the blender's description; the dense pass
        # should put it at rank 1 of the fused result.
        results = hybrid_search('smoothie', top_k=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0], self.blender)
