"""(Re)build Linda's RAG knowledge index.

Chunks the curated platform docs plus any plugin-contributed sources
(KNOWLEDGE_SOURCES filter), embeds each chunk, and upserts KnowledgeChunk rows.
Idempotent: unchanged chunks (matching source_text_hash) skip the embed call;
rows whose (source, ref) no longer appears are pruned.

Usage:
    python manage.py rebuild_knowledge
    python manage.py rebuild_knowledge --all    # embed every chunk again
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild Linda's RAG knowledge index from docs + plugin sources."

    def add_arguments(self, parser) -> None:
        parser.add_argument('--all', action='store_true', help='Embed every chunk again.')

    def handle(self, *args, **options):
        from plugins.installed.ai_assistant.services import rag

        total = rag.rebuild(force=bool(options.get('all')))
        self.stdout.write(self.style.SUCCESS(f'Knowledge index rebuilt: {total} chunks.'))
