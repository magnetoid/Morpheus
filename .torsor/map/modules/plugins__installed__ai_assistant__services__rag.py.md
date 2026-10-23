---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/ai_assistant/services/rag.py

Symbols in `plugins/installed/ai_assistant/services/rag.py`.

- L33 `_hash(text: str)` (function)
- L37 `_chunk_markdown(md: str)` (function) — Split a markdown doc into ``(heading, body)`` chunks on ``##``/``###``
- L64 `_platform_doc_items()` (function) — Read the curated platform docs and yield chunk dicts.
- L90 `_contributed_items()` (function) — Documents contributed by other plugins via the KNOWLEDGE_SOURCES filter.
- L120 `ingest(items: list[dict])` (function) — Upsert chunk dicts into the index, embedding only changed text.
- L151 `rebuild()` (function) — (Re)build the whole index from platform docs + plugin contributions.
- L168 `retrieve(query: str, k: int=4)` (function) — Embed ``query`` and return the top-``k`` chunks by cosine similarity.
