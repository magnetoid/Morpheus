---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/ai_assistant/middleware.py

Symbols in `plugins/installed/ai_assistant/middleware.py`.

- L19 `AIContext` (class) — Enriched context attached to every request for AI personalisation.
- L31 `is_agent(self)` (method)
- L35 `is_personalized(self)` (method)
- L38 `get_memory_context_string(self)` (method) — Format memories as an LLM-readable string.
- L49 `AIContextMiddleware` (class) — Attach AIContext to request.ai_context for all views and resolvers.
- L52 `__init__(self, get_response)` (method)
- L55 `__call__(self, request)` (method)
- L59 `_resolve_agent_token(self, request)` (method)
- L68 `_attach_agent(self, ctx: AIContext, agent_token: str)` (method)
- L90 `_attach_customer_memories(self, ctx: AIContext, user)` (method)
- L101 `_build_context(self, request)` (method)
