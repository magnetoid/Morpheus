"""RAG service — Linda's unstructured-knowledge retrieval.

Owns the ``KnowledgeChunk`` index: ingestion (chunk → embed → upsert) and
retrieval (embed query → cosine → top-k). ``retrieve`` is registered into the
core seam (``core.assistant.knowledge``) by the plugin's ``ready()``, so core
never imports this module directly.

JSON-vector + Python cosine, matching ``ProductEmbedding`` — fine at the
hundreds-of-chunks scale of the platform docs. pgvector is Phase 2
(docs/plans/rag-knowledge-base.md).
"""

from __future__ import annotations

import hashlib
import re

from core.embeddings import cosine_similarity, embed

# Platform docs worth indexing so Linda can answer "how does X work / what
# changed" from real sources. Relative to the repo's docs/ directory.
_PLATFORM_DOCS = [
    'ARCHITECTURE.md',
    'PLUGIN_DEVELOPMENT.md',
    'RELEASE_NOTES.md',
    'MORPHEUS_API.md',
    'QUICK_START.md',
]

_MAX_CHUNK_CHARS = 1500


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _chunk_markdown(md: str) -> list[tuple[str, str]]:
    """Split a markdown doc into ``(heading, body)`` chunks on ``##``/``###``
    headings, capping each chunk length. Content before the first heading is
    kept under an empty heading."""
    parts: list[tuple[str, str]] = []
    heading = ''
    buf: list[str] = []

    def flush() -> None:
        body = '\n'.join(buf).strip()
        if not body:
            return
        # Hard-cap oversized sections so a single chunk stays embeddable.
        for i in range(0, len(body), _MAX_CHUNK_CHARS):
            parts.append((heading, body[i : i + _MAX_CHUNK_CHARS]))

    for line in md.splitlines():
        if re.match(r'^#{2,3}\s', line):
            flush()
            heading = line.lstrip('#').strip()
            buf = []
        else:
            buf.append(line)
    flush()
    return parts


def _platform_doc_items() -> list[dict]:
    """Read the curated platform docs and yield chunk dicts."""
    from pathlib import Path

    from django.conf import settings

    docs_dir = Path(settings.BASE_DIR) / 'docs'
    items: list[dict] = []
    for name in _PLATFORM_DOCS:
        path = docs_dir / name
        try:
            md = path.read_text(encoding='utf-8')
        except OSError:
            continue
        for idx, (heading, body) in enumerate(_chunk_markdown(md)):
            items.append(
                {
                    'source': 'platform_docs',
                    'ref': f'{name}#{idx}',
                    'title': f'{name} — {heading}' if heading else name,
                    'text': body,
                }
            )
    return items


def _contributed_items() -> list[dict]:
    """Documents contributed by other plugins via the KNOWLEDGE_SOURCES filter.

    Each subscriber appends ``{source, ref, title, text}`` dicts. Inactive
    plugins are skipped by the bus, so a disabled contributor's slice vanishes.
    """
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        raw = hook_registry.filter(MorpheusEvents.KNOWLEDGE_SOURCES, value=[])
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for it in raw or []:
        if not isinstance(it, dict):
            continue
        text = (it.get('text') or '').strip()
        ref = (it.get('ref') or '').strip()
        if text and ref:
            out.append(
                {
                    'source': (it.get('source') or 'plugin').strip()[:64],
                    'ref': ref[:200],
                    'title': (it.get('title') or '').strip()[:300],
                    'text': text,
                }
            )
    return out


def ingest(items: list[dict]) -> int:
    """Upsert chunk dicts into the index, embedding only changed text.

    Returns the number of rows written (created or updated)."""
    from plugins.installed.ai_assistant.models import KnowledgeChunk

    written = 0
    for it in items:
        source = it['source']
        ref = it['ref']
        text = it['text']
        h = _hash(text)
        existing = KnowledgeChunk.objects.filter(source=source, ref=ref).first()
        if existing is not None and existing.source_text_hash == h:
            continue  # unchanged — skip the embed call
        vector = embed(text)
        KnowledgeChunk.objects.update_or_create(
            source=source,
            ref=ref,
            defaults={
                'title': it.get('title', ''),
                'text': text,
                'vector': vector,
                'dim': len(vector),
                'source_text_hash': h,
            },
        )
        written += 1
    return written


def rebuild() -> int:
    """(Re)build the whole index from platform docs + plugin contributions.

    Prunes rows whose ``(source, ref)`` no longer appears. Returns the total
    chunk count after the rebuild."""
    from plugins.installed.ai_assistant.models import KnowledgeChunk

    items = _platform_doc_items() + _contributed_items()
    ingest(items)
    keep = {(it['source'], it['ref']) for it in items}
    # Prune stale rows (deleted headings / removed sources).
    for row in KnowledgeChunk.objects.all().only('id', 'source', 'ref'):
        if (row.source, row.ref) not in keep:
            row.delete()
    return KnowledgeChunk.objects.count()


def retrieve(query: str, k: int = 4) -> list[dict]:
    """Embed ``query`` and return the top-``k`` chunks by cosine similarity.

    Signature matches ``core.assistant.knowledge.Retriever``. A small floor
    keeps near-irrelevant chunks out of the prompt."""
    from plugins.installed.ai_assistant.models import KnowledgeChunk

    qv = embed(query)
    if not qv:
        return []
    scored: list[tuple[float, KnowledgeChunk]] = []
    for row in KnowledgeChunk.objects.all().iterator(chunk_size=500):
        if not row.vector:
            continue
        scored.append((cosine_similarity(qv, row.vector), row))
    scored.sort(key=lambda t: t[0], reverse=True)
    out: list[dict] = []
    for score, row in scored[: max(1, k)]:
        if score < 0.15:  # relevance floor
            continue
        out.append({'source': row.source, 'ref': row.ref, 'title': row.title, 'text': row.text})
    return out
