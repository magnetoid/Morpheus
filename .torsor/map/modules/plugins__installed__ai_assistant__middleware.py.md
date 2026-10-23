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

# plugins/installed/ai_assistant/middleware.py

Symbols in `plugins/installed/ai_assistant/middleware.py`.

- L17 `AIContext` (class) — Enriched context attached to every request for AI personalisation.
- L28 `is_agent(self)` (method)
- L32 `is_personalized(self)` (method)
- L36 `AIContextMiddleware` (class) — Attach AIContext to request.ai_context for all views and resolvers.
- L39 `__init__(self, get_response)` (method)
- L42 `__call__(self, request)` (method)
- L46 `_resolve_agent_token(self, request)` (method)
- L55 `_attach_agent(self, ctx: AIContext, agent_token: str)` (method)
- L78 `_build_context(self, request)` (method)
