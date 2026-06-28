"""Semantic recall for Linda's memory — embeddings rank, keyword still works."""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.assistant.models import LindaMemory
from core.assistant.tools.memory import memory_recall_tool, memory_remember_tool


def _ship_concept_embed(text: str):
    """Map any 'where do my orders ship from' phrasing to one vector and
    everything else to an orthogonal one — so synonyms collide without sharing
    a substring. Deterministic, no provider needed."""
    t = (text or '').lower()
    hit = any(w in t for w in ('warehouse', 'berlin', 'ship', 'orders', 'where', 'fulfil'))
    return [1.0, 0.0] if hit else [0.0, 1.0]


class MemoryEmbeddingWriteTests(TestCase):
    def test_remember_writes_an_embedding(self):
        memory_remember_tool.handler(key='postmark', value='prefers Postmark for email')
        row = LindaMemory.objects.get(key='postmark')
        self.assertTrue(row.embedding)  # non-empty vector (hash fallback in tests)

    def test_keyword_recall_still_works(self):
        memory_remember_tool.handler(key='bf', value='runs Black Friday in mid-November')
        out = memory_recall_tool.handler(query='black friday').output
        self.assertEqual(out['count'], 1)
        self.assertEqual(out['memories'][0]['key'], 'bf')

    def test_no_query_returns_recent(self):
        memory_remember_tool.handler(key='a', value='alpha')
        memory_remember_tool.handler(key='b', value='beta')
        out = memory_recall_tool.handler().output
        self.assertEqual(out['count'], 2)


class MemorySemanticRecallTests(TestCase):
    @patch('core.embeddings.embed', side_effect=_ship_concept_embed)
    def test_semantic_match_without_substring(self, _mock):
        # Stored fact shares NO words with the query, but is the same concept.
        memory_remember_tool.handler(key='fulfilment', value='our warehouse is in Berlin')
        memory_remember_tool.handler(key='returns', value='30 day return window')

        out = memory_recall_tool.handler(query='where do my parcels leave from').output
        keys = {m['key'] for m in out['memories']}
        self.assertIn('fulfilment', keys)  # recalled by meaning
        self.assertNotIn('returns', keys)  # unrelated concept excluded by the floor


class BackfillCommandTests(TestCase):
    def test_backfill_embeds_missing_rows(self):
        # Row created directly (no tool) → no embedding.
        LindaMemory.objects.create(scope='merchant', key='x', value='hello world')
        self.assertEqual(LindaMemory.objects.get(key='x').embedding, [])
        call_command('backfill_memory_embeddings')
        self.assertTrue(LindaMemory.objects.get(key='x').embedding)
