---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/assistant/knowledge.py

Symbols in `core/assistant/knowledge.py`.

- L26 `register_retriever(fn: Retriever)` (function) — Install the knowledge retriever. Called once from ai_assistant.ready().
- L31 `retrieve(query: str, k: int=4)` (function) — Return up to ``k`` knowledge chunks relevant to ``query``.
