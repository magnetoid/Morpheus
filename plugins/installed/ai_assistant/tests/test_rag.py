"""Tests for Linda's RAG knowledge base (ai_assistant.services.rag) and the
core retriever seam (core.assistant.knowledge)."""

from __future__ import annotations

from django.test import TestCase

from core.assistant import knowledge
from plugins.installed.ai_assistant.models import KnowledgeChunk
from plugins.installed.ai_assistant.services import rag


class ChunkMarkdownTests(TestCase):
    def test_splits_on_headings(self):
        md = 'intro line\n## First\nbody one\n### Second\nbody two'
        parts = rag._chunk_markdown(md)
        headings = [h for h, _ in parts]
        self.assertIn('First', headings)
        self.assertIn('Second', headings)
        # Pre-heading content is preserved under an empty heading.
        self.assertTrue(any(h == '' and 'intro line' in b for h, b in parts))

    def test_caps_oversized_section(self):
        big = '## Big\n' + ('x' * (rag._MAX_CHUNK_CHARS + 500))
        parts = [b for h, b in rag._chunk_markdown(big) if h == 'Big']
        self.assertGreaterEqual(len(parts), 2)
        self.assertTrue(all(len(b) <= rag._MAX_CHUNK_CHARS for b in parts))


class IngestRetrieveTests(TestCase):
    def test_ingest_is_idempotent_on_unchanged_text(self):
        items = [
            {'source': 's', 'ref': 'a', 'title': 'A', 'text': 'the alpha document'},
        ]
        self.assertEqual(rag.ingest(items), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)
        # Same text → no rewrite (hash matches).
        self.assertEqual(rag.ingest(items), 0)
        # Changed text → rewrite.
        items[0]['text'] = 'the alpha document, revised'
        self.assertEqual(rag.ingest(items), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)

    def test_retrieve_returns_dicts_and_tolerates_empty_index(self):
        self.assertEqual(rag.retrieve('anything', k=3), [])
        rag.ingest([{'source': 's', 'ref': 'r', 'title': 'T', 'text': 'plugin storefront block'}])
        res = rag.retrieve('plugin storefront block', k=3)
        # With the deterministic hash-embedding fallback an exact-text query is
        # its own nearest neighbour, so the row surfaces.
        self.assertTrue(all({'source', 'ref', 'title', 'text'} <= set(r) for r in res))

    def test_rebuild_indexes_platform_docs_and_prunes(self):
        total = rag.rebuild()
        self.assertGreater(total, 0)
        self.assertTrue(KnowledgeChunk.objects.filter(source='platform_docs').exists())
        # A stray row from another source is pruned on rebuild.
        KnowledgeChunk.objects.create(source='stale', ref='x', text='gone', vector=[0.0])
        rag.rebuild()
        self.assertFalse(KnowledgeChunk.objects.filter(source='stale').exists())


class CoreSeamTests(TestCase):
    def test_plugin_registered_retriever_into_core_seam(self):
        # ai_assistant.ready() wires rag.retrieve into the core seam.
        rag.ingest([{'source': 's', 'ref': 'r', 'title': 'T', 'text': 'seam wired text'}])
        res = knowledge.retrieve('seam wired text', k=2)
        self.assertTrue(all({'source', 'ref', 'title', 'text'} <= set(r) for r in res))

    def test_blank_query_is_noop(self):
        self.assertEqual(knowledge.retrieve('', k=3), [])
        self.assertEqual(knowledge.retrieve('   ', k=3), [])


class KnowledgeBeatTests(TestCase):
    """The RAG index refreshes nightly — before this beat existed it froze at
    the last manual rebuild, so post-deploy catalog changes were invisible."""

    def test_nightly_rebuild_task_and_beat_registered(self):
        from django.conf import settings as dj_settings

        from plugins.installed.ai_assistant.tasks import rebuild_knowledge

        self.assertEqual(rebuild_knowledge.name, 'ai_assistant.rebuild_knowledge')
        self.assertIn('ai_assistant:rebuild_knowledge', dj_settings.CELERY_BEAT_SCHEDULE)
        entry = dj_settings.CELERY_BEAT_SCHEDULE['ai_assistant:rebuild_knowledge']
        self.assertEqual(entry['task'], 'ai_assistant.rebuild_knowledge')
