# RAG / Knowledge Base for Linda

Give Linda retrieval over **unstructured** knowledge (platform docs, ADRs,
release notes, product long-descriptions, plugin-contributed sources) to
complement her existing structured tool-calling. Structured data (orders,
inventory, products) stays on live tool-calls — exact and fresh; RAG only adds
what she currently can't see.

## Architecture (per ADR 0017 — powerful via modularity)

- **Core owns the *mechanism*, not the content.** A retriever *seam* in
  `core/assistant/knowledge.py` — a plugin registers the actual retriever in its
  `ready()` (mirrors `provider_config_registry.register` for LLM config). Core
  never imports the plugin; the plugin pushes its retriever in. Disable-safe:
  the retriever just returns `[]`, and Linda's prompt loses the knowledge block.
- **The knowledge store + ingestion live in the `ai_assistant` plugin** —
  where `ProductEmbedding`, semantic search, and the old `rag.py` stub already
  are. One concept, one owner.
- **Sources are plugin-contributed** via the `KNOWLEDGE_SOURCES` filter
  (`hook_registry.filter`), same pattern as `BRAIN_SIGNALS` — each plugin yields
  its own documents; ai_assistant ingests them. No cross-plugin model imports.

## Phase 1 (this slice) — JSON embeddings, no native deps, additive migration

1. `core/hooks.py` — add `KNOWLEDGE_SOURCES = 'knowledge.sources'` (filter).
2. `core/assistant/knowledge.py` (new) — `register_retriever(fn)` + `retrieve(query, k)`
   seam; fail-soft (`[]` on no retriever / any error).
3. `core/assistant/runtime.py` — `_format_knowledge(query)` mirroring
   `_format_recent_memories`; inject as a system message in `_to_llm_messages`.
4. `ai_assistant/models.py` — `KnowledgeChunk(source, ref, title, text, vector JSON,
   dim, source_text_hash, updated_at)` + additive migration. (JSON vector, same as
   `ProductEmbedding` — pgvector swap is Phase 2.)
5. `ai_assistant/services/rag.py` — fill stub: `retrieve()` (embed query → cosine over
   chunks → top-k), `ingest(source, items)` (chunk + embed + hash-guarded upsert),
   `rebuild()` (platform docs/*.md by heading + `KNOWLEDGE_SOURCES` contributions).
6. `ai_assistant/management/commands/rebuild_knowledge.py` — CLI to (re)build.
7. `ai_assistant/plugin.py:ready()` — `register_retriever(retrieve)`; contribute its
   own docs source via `KNOWLEDGE_SOURCES`.
8. Optional Linda tool `knowledge.search` so she can query explicitly.

Verify: `DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.ai_assistant`;
`rebuild_knowledge` populates chunks; disable ai_assistant → retriever returns `[]`.

## Phase 2 (later, deploy-critical — separate PR) — pgvector

Swap `postgres:16-alpine` → `pgvector/pgvector:pg16`, add `pgvector` dep, migrate
`ProductEmbedding` + `LindaMemory.embedding` + `KnowledgeChunk.vector` to
`VectorField` + HNSW. **Native-dep + cross-type migration = the combo that 503'd
prod (PR #62/#64) — ship alone, apply on real Postgres in CI first.**
