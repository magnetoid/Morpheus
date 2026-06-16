---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/middleware.py

Symbols in `plugins/installed/ai_assistant/middleware.py`.

- L20 `AIContext` (class) — Enriched context attached to every request for AI personalisation.
- L33 `is_agent(self)` (method)
- L37 `is_personalized(self)` (method)
- L40 `get_memory_context_string(self)` (method) — Format memories as an LLM-readable string.
- L49 `AIContextMiddleware` (class) — Attach AIContext to request.ai_context for all views and resolvers.
- L52 `__init__(self, get_response)` (method)
- L55 `__call__(self, request)` (method)
- L59 `_resolve_agent_token(self, request)` (method)
- L68 `_attach_agent(self, ctx: AIContext, agent_token: str)` (method)
- L91 `_attach_customer_memories(self, ctx: AIContext, user)` (method)
- L103 `_build_context(self, request)` (method)
