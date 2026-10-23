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

# plugins/installed/ai_assistant/models.py

Symbols in `plugins/installed/ai_assistant/models.py`.

- L9 `AgentIntent` (class) — Lifecycle record for a single agent action against the platform.
- L122 `__str__(self)` (method)
- L126 `AgentIntentEvent` (class) — Immutable audit log of every state transition on an AgentIntent.
- L158 `AgentRegistration` (class)
- L193 `save(self, *args, **kwargs)` (method)
- L200 `remaining_budget(self)` (method) — Decimal remaining budget, or None when no cap is configured.
- L206 `can_afford(self, amount)` (method) — Return True iff the configured budget can absorb `amount`.
- L215 `AIInteraction` (class)
- L258 `MerchantInsight` (class)
- L294 `ProductEmbedding` (class) — Vector embedding for a product's description + key attributes.
- L320 `KnowledgeChunk` (class) — A chunk of unstructured knowledge for Linda's RAG index.
- L347 `__str__(self)` (method)
- L351 `DynamicPriceRule` (class)
